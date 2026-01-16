"""
Service Layer - จัดการ tasks ทั้งหมดสำหรับ Dashboard
รองรับการเรียกใช้จาก GUI โดยไม่ต้องใช้ command line
"""

import time
import traceback
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from threading import Lock

from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import text

from src.db.connection import session_scope, get_engine
from src.db.models import Video, DailyMetric, ResearchItem, PlaybookRule, RunLog
from src.db.repository import (
    VideoRepository,
    DailyMetricRepository,
    ResearchItemRepository,
    PlaybookRuleRepository,
    RunLogRepository,
)
from src.utils.logger import get_logger

logger = get_logger()

# Lock เพื่อป้องกันการรัน task ซ้ำซ้อน
_task_locks: Dict[str, Lock] = {
    "sync_videos": Lock(),
    "sync_metrics": Lock(),
    "fetch_research": Lock(),
    "train_playbook": Lock(),
}


@dataclass
class TaskResult:
    """ผลลัพธ์การรัน task"""
    success: bool = False
    task_name: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # สถิติ
    fetched_total: int = 0
    unique_after_dedupe: int = 0
    inserted_new: int = 0
    updated_existing: int = 0
    duplicates_removed: int = 0
    skipped_bad_records: int = 0
    
    # ข้อมูลเพิ่มเติม
    message: str = ""
    error_message: str = ""
    error_traceback: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Log ID สำหรับอ้างอิง
    run_log_id: Optional[int] = None


def is_task_running(task_name: str) -> bool:
    """ตรวจสอบว่า task กำลังทำงานอยู่หรือไม่"""
    lock = _task_locks.get(task_name)
    if lock:
        return lock.locked()
    return False


def _deduplicate_videos(videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate videos by youtube_id (เก็บตัวล่าสุด)
    
    Args:
        videos: List ของ video dictionaries
        
    Returns:
        List ของ unique videos
    """
    seen = {}
    for video in videos:
        youtube_id = video.get("youtube_id")
        if youtube_id:
            seen[youtube_id] = video  # เก็บตัวล่าสุด
    return list(seen.values())


def _upsert_video(session: Session, video_data: Dict[str, Any]) -> str:
    """
    UPSERT video - insert หรือ update ถ้ามีอยู่แล้ว
    
    Args:
        session: SQLAlchemy session
        video_data: Dictionary ของข้อมูลวิดีโอ
        
    Returns:
        "inserted" หรือ "updated"
    """
    youtube_id = video_data.get("youtube_id")
    
    # ตรวจสอบว่ามีอยู่แล้วหรือไม่
    existing = session.query(Video).filter(Video.youtube_id == youtube_id).first()
    
    if existing:
        # Update existing
        existing.title = video_data.get("title", existing.title)
        existing.description = video_data.get("description", existing.description)
        existing.thumbnail_url = video_data.get("thumbnail_url", existing.thumbnail_url)
        existing.tags = video_data.get("tags", existing.tags)
        existing.duration_seconds = video_data.get("duration_seconds", existing.duration_seconds)
        existing.view_count = video_data.get("view_count", existing.view_count)
        existing.like_count = video_data.get("like_count", existing.like_count)
        existing.comment_count = video_data.get("comment_count", existing.comment_count)
        existing.published_at = video_data.get("published_at", existing.published_at)
        existing.updated_at = datetime.now()
        return "updated"
    else:
        # Insert new
        video = Video(
            youtube_id=youtube_id,
            title=video_data.get("title", ""),
            description=video_data.get("description", ""),
            channel_id=video_data.get("channel_id", ""),
            channel_name=video_data.get("channel_name", ""),
            published_at=video_data.get("published_at"),
            duration_seconds=video_data.get("duration_seconds", 0),
            tags=video_data.get("tags", {}),
            category=video_data.get("category"),
            thumbnail_url=video_data.get("thumbnail_url"),
            view_count=video_data.get("view_count", 0),
            like_count=video_data.get("like_count", 0),
            comment_count=video_data.get("comment_count", 0),
        )
        session.add(video)
        return "inserted"


def sync_youtube_videos(
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> TaskResult:
    """
    Sync วิดีโอจาก YouTube API ลงฐานข้อมูล
    
    Features:
    - Deduplicate in-memory ก่อนบันทึก
    - UPSERT (insert หรือ update)
    - Skip และ log records ที่ parse ไม่ได้
    
    Args:
        progress_callback: Callback function(message, progress_percent)
        
    Returns:
        TaskResult
    """
    task_name = "sync_videos"
    result = TaskResult(task_name=task_name, started_at=datetime.now())
    
    # ตรวจสอบว่ากำลังรันอยู่หรือไม่
    if not _task_locks[task_name].acquire(blocking=False):
        result.error_message = "งานนี้กำลังทำงานอยู่แล้ว กรุณารอสักครู่"
        return result
    
    try:
        if progress_callback:
            progress_callback("กำลังเริ่มต้น...", 0.0)
        
        with session_scope() as session:
            # บันทึก run log
            run_repo = RunLogRepository(session)
            run_log = run_repo.create_run("sync_youtube_videos", triggered_by="dashboard")
            result.run_log_id = run_log.id
            session.commit()
            
            try:
                # ตรวจสอบ YouTube OAuth
                from src.youtube.oauth import get_youtube_auth
                auth = get_youtube_auth()
                
                if not auth.is_authenticated():
                    result.error_message = "ยังไม่ได้เชื่อมต่อ YouTube OAuth กรุณาตั้งค่า credentials ก่อน"
                    run_repo.fail_run(run_log.id, result.error_message)
                    session.commit()
                    return result
                
                if progress_callback:
                    progress_callback("กำลังดึงข้อมูลจาก YouTube API...", 0.1)
                
                # ดึงวิดีโอจาก YouTube
                from src.youtube.client import YouTubeClient
                client = YouTubeClient(auth=auth)
                
                videos_raw = []
                skipped = []
                
                for video_data in client.fetch_all_videos():
                    result.fetched_total += 1
                    
                    try:
                        videos_raw.append({
                            "youtube_id": video_data.youtube_id,
                            "title": video_data.title,
                            "description": video_data.description,
                            "channel_id": video_data.channel_id,
                            "channel_name": video_data.channel_name,
                            "published_at": video_data.published_at,
                            "duration_seconds": video_data.duration_seconds,
                            "tags": {"tags": video_data.tags},
                            "category": video_data.category_id,
                            "thumbnail_url": video_data.thumbnail_url,
                            "view_count": video_data.view_count,
                            "like_count": video_data.like_count,
                            "comment_count": video_data.comment_count,
                        })
                    except Exception as e:
                        # Skip และ log record ที่ parse ไม่ได้
                        skipped.append({
                            "youtube_id": getattr(video_data, "youtube_id", "unknown"),
                            "reason": str(e),
                        })
                        result.skipped_bad_records += 1
                        logger.warning(f"ข้ามวิดีโอที่ parse ไม่ได้: {e}")
                
                if progress_callback:
                    progress_callback(f"ดึงข้อมูลแล้ว {result.fetched_total} รายการ กำลัง deduplicate...", 0.5)
                
                # Deduplicate in-memory
                videos_unique = _deduplicate_videos(videos_raw)
                result.unique_after_dedupe = len(videos_unique)
                result.duplicates_removed = result.fetched_total - result.unique_after_dedupe - result.skipped_bad_records
                
                if progress_callback:
                    progress_callback(f"กำลังบันทึก {result.unique_after_dedupe} รายการลงฐานข้อมูล...", 0.7)
                
                # UPSERT ทีละรายการ
                for i, video_data in enumerate(videos_unique):
                    try:
                        action = _upsert_video(session, video_data)
                        if action == "inserted":
                            result.inserted_new += 1
                        else:
                            result.updated_existing += 1
                    except Exception as e:
                        result.skipped_bad_records += 1
                        logger.warning(f"ไม่สามารถบันทึกวิดีโอ {video_data.get('youtube_id')}: {e}")
                    
                    if progress_callback and i % 10 == 0:
                        progress = 0.7 + (0.25 * i / len(videos_unique))
                        progress_callback(f"บันทึกแล้ว {i+1}/{len(videos_unique)} รายการ", progress)
                
                session.commit()
                
                # อัพเดท run log
                run_repo.complete_run(
                    run_log.id,
                    status="completed",
                    items_processed=result.fetched_total,
                    items_succeeded=result.inserted_new + result.updated_existing,
                    items_failed=result.skipped_bad_records,
                    result={
                        "fetched_total": result.fetched_total,
                        "unique_after_dedupe": result.unique_after_dedupe,
                        "inserted_new": result.inserted_new,
                        "updated_existing": result.updated_existing,
                        "duplicates_removed": result.duplicates_removed,
                        "skipped_bad_records": result.skipped_bad_records,
                    }
                )
                session.commit()
                
                result.success = True
                result.message = (
                    f"Sync สำเร็จ! ดึงมา {result.fetched_total} รายการ, "
                    f"ไม่ซ้ำ {result.unique_after_dedupe} รายการ, "
                    f"เพิ่มใหม่ {result.inserted_new}, อัพเดท {result.updated_existing}"
                )
                
                if progress_callback:
                    progress_callback(result.message, 1.0)
                
            except Exception as e:
                result.error_message = str(e)
                result.error_traceback = traceback.format_exc()
                run_repo.fail_run(run_log.id, result.error_message, result.error_traceback)
                session.commit()
                logger.error(f"Sync videos failed: {e}")
    
    finally:
        result.completed_at = datetime.now()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        _task_locks[task_name].release()
    
    return result


def sync_youtube_metrics(
    days: int = 30,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> TaskResult:
    """
    Sync metrics จาก YouTube Analytics API
    
    Args:
        days: จำนวนวันที่จะดึง (7, 30, 90, 180)
        progress_callback: Callback function(message, progress_percent)
        
    Returns:
        TaskResult
    """
    task_name = "sync_metrics"
    result = TaskResult(task_name=task_name, started_at=datetime.now())
    
    if not _task_locks[task_name].acquire(blocking=False):
        result.error_message = "งานนี้กำลังทำงานอยู่แล้ว กรุณารอสักครู่"
        return result
    
    try:
        if progress_callback:
            progress_callback("กำลังเริ่มต้น...", 0.0)
        
        with session_scope() as session:
            run_repo = RunLogRepository(session)
            run_log = run_repo.create_run("sync_youtube_metrics", triggered_by="dashboard")
            result.run_log_id = run_log.id
            session.commit()
            
            try:
                from src.youtube.oauth import get_youtube_auth
                auth = get_youtube_auth()
                
                if not auth.is_authenticated():
                    result.error_message = "ยังไม่ได้เชื่อมต่อ YouTube OAuth กรุณาตั้งค่า credentials ก่อน"
                    run_repo.fail_run(run_log.id, result.error_message)
                    session.commit()
                    return result
                
                from src.youtube.client import YouTubeClient
                client = YouTubeClient(auth=auth)
                
                if progress_callback:
                    progress_callback(f"กำลังดึง metrics {days} วันล่าสุด...", 0.1)
                
                fetch_result = client.sync_daily_metrics_to_db(session, days=days)
                
                result.fetched_total = fetch_result.metrics_fetched
                result.inserted_new = fetch_result.metrics_created
                
                run_repo.complete_run(
                    run_log.id,
                    status="completed" if fetch_result.success else "failed",
                    items_processed=fetch_result.metrics_fetched,
                    items_succeeded=fetch_result.metrics_created,
                    result={"days": days, "metrics_created": fetch_result.metrics_created}
                )
                session.commit()
                
                result.success = fetch_result.success
                result.message = f"Sync metrics สำเร็จ! สร้างใหม่ {fetch_result.metrics_created} รายการ"
                
                if progress_callback:
                    progress_callback(result.message, 1.0)
                
            except Exception as e:
                result.error_message = str(e)
                result.error_traceback = traceback.format_exc()
                run_repo.fail_run(run_log.id, result.error_message, result.error_traceback)
                session.commit()
    
    finally:
        result.completed_at = datetime.now()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        _task_locks[task_name].release()
    
    return result


def fetch_anime_research(
    fetch_all: bool = True,
    link_entities: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> TaskResult:
    """
    ดึงข้อมูล Anime Research จาก AniList และ RSS feeds
    
    Args:
        fetch_all: ดึงจากทุกแหล่ง (True) หรือเฉพาะ 7 วันล่าสุด (False)
        link_entities: เชื่อมโยง entities หรือไม่
        progress_callback: Callback function(message, progress_percent)
        
    Returns:
        TaskResult
    """
    task_name = "fetch_research"
    result = TaskResult(task_name=task_name, started_at=datetime.now())
    
    if not _task_locks[task_name].acquire(blocking=False):
        result.error_message = "งานนี้กำลังทำงานอยู่แล้ว กรุณารอสักครู่"
        return result
    
    try:
        if progress_callback:
            progress_callback("กำลังเริ่มต้น...", 0.0)
        
        with session_scope() as session:
            run_repo = RunLogRepository(session)
            run_log = run_repo.create_run("fetch_anime_research", triggered_by="dashboard")
            result.run_log_id = run_log.id
            session.commit()
            
            try:
                research_repo = ResearchItemRepository(session)
                total_items = 0
                
                # ดึงจาก AniList
                if progress_callback:
                    progress_callback("กำลังดึงข้อมูลจาก AniList...", 0.1)
                
                try:
                    from src.anime.anilist import AniListClient
                    anilist = AniListClient()
                    
                    # ดึง trending anime
                    trending = anilist.fetch_trending(limit=50)
                    for item in trending:
                        # ตรวจสอบว่ามีอยู่แล้วหรือไม่
                        existing = research_repo.get_by_anilist_id(item.get("anilist_id"))
                        if not existing:
                            research_repo.create(**item)
                            result.inserted_new += 1
                        else:
                            result.updated_existing += 1
                        total_items += 1
                    
                    # ดึง seasonal anime
                    seasonal = anilist.fetch_seasonal(limit=50)
                    for item in seasonal:
                        existing = research_repo.get_by_anilist_id(item.get("anilist_id"))
                        if not existing:
                            research_repo.create(**item)
                            result.inserted_new += 1
                        else:
                            result.updated_existing += 1
                        total_items += 1
                    
                except Exception as e:
                    logger.warning(f"ไม่สามารถดึงข้อมูลจาก AniList: {e}")
                    result.details["anilist_error"] = str(e)
                
                if progress_callback:
                    progress_callback("กำลังดึงข้อมูลจาก RSS feeds...", 0.5)
                
                # ดึงจาก RSS
                try:
                    from src.anime.rss_parser import fetch_all_sources
                    rss_items = fetch_all_sources()
                    
                    for item in rss_items:
                        # ตรวจสอบว่ามีอยู่แล้วหรือไม่ (ด้วย source_url)
                        existing = research_repo.get_by_source_url(item.get("source_url"))
                        if not existing:
                            research_repo.create(**item)
                            result.inserted_new += 1
                        else:
                            result.updated_existing += 1
                        total_items += 1
                    
                except Exception as e:
                    logger.warning(f"ไม่สามารถดึงข้อมูลจาก RSS: {e}")
                    result.details["rss_error"] = str(e)
                
                session.commit()
                
                # Link entities
                if link_entities:
                    if progress_callback:
                        progress_callback("กำลังเชื่อมโยง entities...", 0.8)
                    
                    try:
                        from src.anime.entity_linker import link_research_items
                        linked_count = link_research_items(session)
                        result.details["entities_linked"] = linked_count
                    except Exception as e:
                        logger.warning(f"ไม่สามารถเชื่อมโยง entities: {e}")
                
                result.fetched_total = total_items
                
                run_repo.complete_run(
                    run_log.id,
                    status="completed",
                    items_processed=total_items,
                    items_succeeded=result.inserted_new,
                    result={
                        "total_items": total_items,
                        "inserted_new": result.inserted_new,
                        "updated_existing": result.updated_existing,
                    }
                )
                session.commit()
                
                result.success = True
                result.message = (
                    f"ดึงข้อมูล Research สำเร็จ! รวม {total_items} รายการ, "
                    f"เพิ่มใหม่ {result.inserted_new}, อัพเดท {result.updated_existing}"
                )
                
                if progress_callback:
                    progress_callback(result.message, 1.0)
                
            except Exception as e:
                result.error_message = str(e)
                result.error_traceback = traceback.format_exc()
                run_repo.fail_run(run_log.id, result.error_message, result.error_traceback)
                session.commit()
    
    finally:
        result.completed_at = datetime.now()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        _task_locks[task_name].release()
    
    return result


def train_playbook(
    save_rules: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> TaskResult:
    """
    ฝึก Playbook Model และบันทึกกฎ
    
    Args:
        save_rules: บันทึกกฎลงฐานข้อมูลหรือไม่
        progress_callback: Callback function(message, progress_percent)
        
    Returns:
        TaskResult
    """
    task_name = "train_playbook"
    result = TaskResult(task_name=task_name, started_at=datetime.now())
    
    if not _task_locks[task_name].acquire(blocking=False):
        result.error_message = "งานนี้กำลังทำงานอยู่แล้ว กรุณารอสักครู่"
        return result
    
    try:
        if progress_callback:
            progress_callback("กำลังเริ่มต้น...", 0.0)
        
        with session_scope() as session:
            run_repo = RunLogRepository(session)
            run_log = run_repo.create_run("train_playbook", triggered_by="dashboard")
            result.run_log_id = run_log.id
            session.commit()
            
            try:
                if progress_callback:
                    progress_callback("กำลังเตรียมข้อมูลสำหรับ training...", 0.2)
                
                from src.playbook.model_trainer import PlaybookTrainer
                from src.db.repository import VideoRepository, DailyMetricRepository
                
                video_repo = VideoRepository(session)
                metric_repo = DailyMetricRepository(session)
                
                # ดึงข้อมูลวิดีโอและ metrics
                videos = video_repo.get_all(limit=10000)
                
                if len(videos) < 5:
                    result.error_message = "ข้อมูลวิดีโอไม่เพียงพอสำหรับ training (ต้องมีอย่างน้อย 5 วิดีโอ)"
                    run_repo.fail_run(run_log.id, result.error_message)
                    session.commit()
                    return result
                
                if progress_callback:
                    progress_callback(f"พบวิดีโอ {len(videos)} รายการ กำลัง training...", 0.4)
                
                # เตรียมข้อมูลสำหรับ training
                training_data = []
                for video in videos:
                    metrics = metric_repo.get_all_for_video(video.id, limit=30)
                    if metrics:
                        total_views = sum(m.views for m in metrics)
                        avg_retention = sum(m.average_view_percentage or 0 for m in metrics) / len(metrics)
                        
                        training_data.append({
                            "video_id": video.id,
                            "title": video.title,
                            "duration_seconds": video.duration_seconds,
                            "total_views": total_views,
                            "avg_retention": avg_retention,
                            "is_success": total_views > 1000,  # กำหนดเกณฑ์ความสำเร็จ
                        })
                
                if len(training_data) < 5:
                    result.error_message = "ข้อมูล metrics ไม่เพียงพอสำหรับ training"
                    run_repo.fail_run(run_log.id, result.error_message)
                    session.commit()
                    return result
                
                if progress_callback:
                    progress_callback("กำลัง training model...", 0.6)
                
                # Training
                trainer = PlaybookTrainer()
                train_result = trainer.fit_classification(
                    training_data,
                    target_column="is_success",
                    model_type="random_forest",
                )
                
                rules_created = 0
                
                if save_rules and train_result.get("rules"):
                    if progress_callback:
                        progress_callback("กำลังบันทึกกฎ...", 0.8)
                    
                    rule_repo = PlaybookRuleRepository(session)
                    
                    for rule in train_result.get("rules", []):
                        rule_repo.create(
                            rule_name=rule.get("name", "Auto-generated rule"),
                            category="auto",
                            condition_json=rule.get("condition", {}),
                            action_json=rule.get("action", {}),
                            confidence_score=rule.get("confidence", 0.5),
                            is_auto_generated=True,
                        )
                        rules_created += 1
                    
                    session.commit()
                
                result.inserted_new = rules_created
                result.details = {
                    "model_accuracy": train_result.get("accuracy", 0),
                    "rules_generated": len(train_result.get("rules", [])),
                    "rules_saved": rules_created,
                    "training_samples": len(training_data),
                }
                
                run_repo.complete_run(
                    run_log.id,
                    status="completed",
                    items_processed=len(training_data),
                    items_succeeded=rules_created,
                    result=result.details
                )
                session.commit()
                
                result.success = True
                result.message = (
                    f"Training สำเร็จ! ความแม่นยำ {train_result.get('accuracy', 0):.1%}, "
                    f"สร้างกฎ {rules_created} ข้อ"
                )
                
                if progress_callback:
                    progress_callback(result.message, 1.0)
                
            except Exception as e:
                result.error_message = str(e)
                result.error_traceback = traceback.format_exc()
                run_repo.fail_run(run_log.id, result.error_message, result.error_traceback)
                session.commit()
    
    finally:
        result.completed_at = datetime.now()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        _task_locks[task_name].release()
    
    return result


def check_youtube_oauth() -> Dict[str, Any]:
    """
    ตรวจสอบสถานะ YouTube OAuth
    
    Returns:
        Dictionary ของสถานะ
    """
    result = {
        "is_authenticated": False,
        "has_credentials_file": False,
        "has_token_file": False,
        "channel_id": None,
        "channel_name": None,
        "error": None,
        "instructions": None,
    }
    
    try:
        import os
        from pathlib import Path
        
        # ตรวจสอบไฟล์ credentials
        secrets_dir = Path(".secrets")
        credentials_file = secrets_dir / "client_secrets.json"
        token_file = secrets_dir / "youtube_token.json"
        
        result["has_credentials_file"] = credentials_file.exists()
        result["has_token_file"] = token_file.exists()
        
        if not result["has_credentials_file"]:
            result["instructions"] = (
                "ไม่พบไฟล์ client_secrets.json\n\n"
                "วิธีตั้งค่า:\n"
                "1. ไปที่ Google Cloud Console (https://console.cloud.google.com/)\n"
                "2. สร้าง Project ใหม่หรือเลือก Project ที่มีอยู่\n"
                "3. เปิดใช้งาน YouTube Data API v3 และ YouTube Analytics API\n"
                "4. สร้าง OAuth 2.0 Client ID (Desktop App)\n"
                "5. ดาวน์โหลดไฟล์ JSON และบันทึกเป็น .secrets/client_secrets.json"
            )
            return result
        
        from src.youtube.oauth import get_youtube_auth
        auth = get_youtube_auth()
        
        result["is_authenticated"] = auth.is_authenticated()
        
        if result["is_authenticated"]:
            # ลองดึงข้อมูล channel
            try:
                youtube = auth.get_youtube_service()
                response = youtube.channels().list(
                    part="snippet",
                    mine=True,
                ).execute()
                
                if response.get("items"):
                    channel = response["items"][0]
                    result["channel_id"] = channel["id"]
                    result["channel_name"] = channel["snippet"]["title"]
            except Exception as e:
                result["error"] = f"ไม่สามารถดึงข้อมูล channel: {e}"
        else:
            result["instructions"] = (
                "พบไฟล์ credentials แต่ยังไม่ได้ authenticate\n\n"
                "วิธี authenticate:\n"
                "1. รันคำสั่ง: python scripts/youtube_auth.py\n"
                "2. เปิด browser และ login ด้วย Google Account\n"
                "3. อนุญาตการเข้าถึง YouTube Data"
            )
    
    except Exception as e:
        result["error"] = str(e)
    
    return result


def get_recent_runs(limit: int = 20) -> List[Dict[str, Any]]:
    """
    ดึงประวัติการรัน task ล่าสุด
    
    Args:
        limit: จำนวนรายการที่จะดึง
        
    Returns:
        List ของ run logs
    """
    runs = []
    
    try:
        with session_scope() as session:
            run_repo = RunLogRepository(session)
            recent_runs = run_repo.get_recent_runs(limit=limit)
            
            for run in recent_runs:
                runs.append({
                    "id": run.id,
                    "run_id": run.run_id,
                    "run_type": run.run_type,
                    "status": run.status,
                    "triggered_by": run.triggered_by,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                    "duration_seconds": run.duration_seconds,
                    "items_processed": run.items_processed,
                    "items_succeeded": run.items_succeeded,
                    "items_failed": run.items_failed,
                    "error_message": run.error_message,
                })
    
    except Exception as e:
        logger.error(f"Error getting recent runs: {e}")
    
    return runs


def get_app_log(lines: int = 100) -> str:
    """
    อ่าน log file ล่าสุด
    
    Args:
        lines: จำนวนบรรทัดที่จะอ่าน
        
    Returns:
        เนื้อหา log
    """
    try:
        from pathlib import Path
        log_file = Path("logs/app.log")
        
        if not log_file.exists():
            return "ไม่พบไฟล์ log"
        
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    
    except Exception as e:
        return f"ไม่สามารถอ่านไฟล์ log: {e}"
