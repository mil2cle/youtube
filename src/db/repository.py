"""
Repository Module - จัดการ CRUD operations สำหรับทุก models
ใช้ Repository Pattern เพื่อแยก business logic ออกจาก data access
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Type, TypeVar, Generic
from uuid import uuid4

from sqlalchemy import select, update, delete, func, and_, or_, desc
from sqlalchemy.orm import Session

from src.db.models import (
    Base,
    Video,
    DailyMetric,
    ResearchItem,
    ContentIdea,
    PlaybookRule,
    RunLog,
)

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base Repository สำหรับ CRUD operations ทั่วไป"""
    
    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model
    
    def get_by_id(self, id: int) -> Optional[T]:
        """ดึงข้อมูลด้วย ID"""
        return self.session.get(self.model, id)
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """ดึงข้อมูลทั้งหมด พร้อม pagination"""
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())
    
    def create(self, **kwargs) -> T:
        """สร้างข้อมูลใหม่"""
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.flush()
        return instance
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """อัพเดทข้อมูล"""
        instance = self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            self.session.flush()
        return instance
    
    def delete(self, id: int) -> bool:
        """ลบข้อมูล"""
        instance = self.get_by_id(id)
        if instance:
            self.session.delete(instance)
            self.session.flush()
            return True
        return False
    
    def count(self) -> int:
        """นับจำนวนข้อมูลทั้งหมด"""
        stmt = select(func.count()).select_from(self.model)
        return self.session.scalar(stmt) or 0


class VideoRepository(BaseRepository[Video]):
    """Repository สำหรับจัดการ Videos"""
    
    def __init__(self, session: Session):
        super().__init__(session, Video)
    
    def get_by_youtube_id(self, youtube_id: str) -> Optional[Video]:
        """ดึงวิดีโอด้วย YouTube ID"""
        stmt = select(Video).where(Video.youtube_id == youtube_id)
        return self.session.scalar(stmt)
    
    def get_by_channel(self, channel_id: str, limit: int = 50) -> List[Video]:
        """ดึงวิดีโอทั้งหมดของ channel"""
        stmt = (
            select(Video)
            .where(Video.channel_id == channel_id)
            .order_by(desc(Video.published_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_recent(self, days: int = 30, limit: int = 50) -> List[Video]:
        """ดึงวิดีโอล่าสุด"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(Video)
            .where(Video.published_at >= cutoff_date)
            .order_by(desc(Video.published_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_top_performing(self, metric: str = "view_count", limit: int = 10) -> List[Video]:
        """ดึงวิดีโอที่มี performance ดีที่สุด"""
        order_column = getattr(Video, metric, Video.view_count)
        stmt = (
            select(Video)
            .where(Video.status == "active")
            .order_by(desc(order_column))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def search(self, query: str, limit: int = 20) -> List[Video]:
        """ค้นหาวิดีโอด้วย title หรือ description"""
        search_pattern = f"%{query}%"
        stmt = (
            select(Video)
            .where(
                or_(
                    Video.title.ilike(search_pattern),
                    Video.description.ilike(search_pattern),
                )
            )
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())


class DailyMetricRepository(BaseRepository[DailyMetric]):
    """Repository สำหรับจัดการ Daily Metrics"""
    
    def __init__(self, session: Session):
        super().__init__(session, DailyMetric)
    
    def get_by_video_and_date(self, video_id: int, metric_date: date) -> Optional[DailyMetric]:
        """ดึง metric ของวิดีโอในวันที่กำหนด"""
        stmt = select(DailyMetric).where(
            and_(
                DailyMetric.video_id == video_id,
                DailyMetric.date == metric_date,
            )
        )
        return self.session.scalar(stmt)
    
    def get_video_metrics(
        self, video_id: int, start_date: date, end_date: date
    ) -> List[DailyMetric]:
        """ดึง metrics ของวิดีโอในช่วงเวลา"""
        stmt = (
            select(DailyMetric)
            .where(
                and_(
                    DailyMetric.video_id == video_id,
                    DailyMetric.date >= start_date,
                    DailyMetric.date <= end_date,
                )
            )
            .order_by(DailyMetric.date)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_aggregate_stats(self, video_id: int) -> dict:
        """คำนวณ aggregate stats ของวิดีโอ"""
        stmt = select(
            func.sum(DailyMetric.views).label("total_views"),
            func.sum(DailyMetric.likes).label("total_likes"),
            func.sum(DailyMetric.comments).label("total_comments"),
            func.avg(DailyMetric.average_view_percentage).label("avg_view_percentage"),
            func.sum(DailyMetric.watch_time_minutes).label("total_watch_time"),
        ).where(DailyMetric.video_id == video_id)
        
        result = self.session.execute(stmt).first()
        return {
            "total_views": result.total_views or 0,
            "total_likes": result.total_likes or 0,
            "total_comments": result.total_comments or 0,
            "avg_view_percentage": result.avg_view_percentage or 0.0,
            "total_watch_time": result.total_watch_time or 0.0,
        }
    
    def get_latest_for_video(self, video_id: int) -> Optional[DailyMetric]:
        """ดึง metric ล่าสุดของวิดีโอ"""
        stmt = (
            select(DailyMetric)
            .where(DailyMetric.video_id == video_id)
            .order_by(desc(DailyMetric.date))
            .limit(1)
        )
        return self.session.scalar(stmt)
    
    def get_all_for_video(self, video_id: int, limit: int = 365) -> List[DailyMetric]:
        """ดึง metrics ทั้งหมดของวิดีโอ"""
        stmt = (
            select(DailyMetric)
            .where(DailyMetric.video_id == video_id)
            .order_by(desc(DailyMetric.date))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_metrics_in_range(self, start_date: date, end_date: date) -> List[DailyMetric]:
        """ดึง metrics ทั้งหมดในช่วงวันที่"""
        stmt = (
            select(DailyMetric)
            .where(
                and_(
                    DailyMetric.date >= start_date,
                    DailyMetric.date <= end_date,
                )
            )
            .order_by(DailyMetric.date)
        )
        return list(self.session.scalars(stmt).all())
    
    def upsert(self, video_id: int, metric_date: date, **kwargs) -> DailyMetric:
        """สร้างหรืออัพเดท metric"""
        existing = self.get_by_video_and_date(video_id, metric_date)
        if existing:
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            self.session.flush()
            return existing
        else:
            return self.create(video_id=video_id, date=metric_date, **kwargs)


class ResearchItemRepository(BaseRepository[ResearchItem]):
    """Repository สำหรับจัดการ Research Items"""
    
    def __init__(self, session: Session):
        super().__init__(session, ResearchItem)
    
    def get_by_source(self, source: str, limit: int = 50) -> List[ResearchItem]:
        """ดึง research items ตาม source"""
        stmt = (
            select(ResearchItem)
            .where(ResearchItem.source == source)
            .order_by(desc(ResearchItem.researched_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_actionable(self, limit: int = 20) -> List[ResearchItem]:
        """ดึง research items ที่ actionable"""
        stmt = (
            select(ResearchItem)
            .where(
                and_(
                    ResearchItem.is_actionable == True,
                    ResearchItem.status != "archived",
                )
            )
            .order_by(desc(ResearchItem.relevance_score))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_trending(self, min_score: float = 0.5, limit: int = 20) -> List[ResearchItem]:
        """ดึง trending research items"""
        stmt = (
            select(ResearchItem)
            .where(ResearchItem.trend_score >= min_score)
            .order_by(desc(ResearchItem.trend_score))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def mark_as_reviewed(self, id: int) -> Optional[ResearchItem]:
        """เปลี่ยนสถานะเป็น reviewed"""
        return self.update(id, status="reviewed")
    
    def get_by_source_url(self, url: str) -> Optional[ResearchItem]:
        """ดึง research item ตาม source URL"""
        stmt = select(ResearchItem).where(ResearchItem.source_url == url)
        return self.session.scalar(stmt)
    
    def get_by_anilist_id(self, anilist_id: int) -> Optional[ResearchItem]:
        """ดึง research item ตาม AniList ID"""
        stmt = select(ResearchItem).where(ResearchItem.anilist_id == anilist_id)
        return self.session.scalar(stmt)
    
    def get_unlinked(self, limit: int = 100) -> List[ResearchItem]:
        """ดึง research items ที่ยังไม่ได้ link entities"""
        stmt = (
            select(ResearchItem)
            .where(ResearchItem.is_linked == False)
            .order_by(desc(ResearchItem.created_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_by_category(self, category: str, limit: int = 50) -> List[ResearchItem]:
        """ดึง research items ตาม category"""
        stmt = (
            select(ResearchItem)
            .where(ResearchItem.category == category)
            .order_by(desc(ResearchItem.created_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_recent_news(self, days: int = 7, limit: int = 50) -> List[ResearchItem]:
        """ดึงข่าวล่าสุด"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(ResearchItem)
            .where(
                and_(
                    ResearchItem.source.like("rss_%"),
                    ResearchItem.published_at >= cutoff_date,
                )
            )
            .order_by(desc(ResearchItem.published_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_anime_by_popularity(self, limit: int = 20) -> List[ResearchItem]:
        """ดึงอนิเมะตามความนิยม"""
        stmt = (
            select(ResearchItem)
            .where(
                and_(
                    ResearchItem.source.like("anilist_%"),
                    ResearchItem.anilist_id.isnot(None),
                )
            )
            .order_by(desc(ResearchItem.trend_score))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())


class ContentIdeaRepository(BaseRepository[ContentIdea]):
    """Repository สำหรับจัดการ Content Ideas"""
    
    def __init__(self, session: Session):
        super().__init__(session, ContentIdea)
    
    def get_by_status(self, status: str, limit: int = 50) -> List[ContentIdea]:
        """ดึง ideas ตาม status"""
        stmt = (
            select(ContentIdea)
            .where(ContentIdea.status == status)
            .order_by(desc(ContentIdea.created_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_by_priority(self, priority: str, limit: int = 50) -> List[ContentIdea]:
        """ดึง ideas ตาม priority"""
        stmt = (
            select(ContentIdea)
            .where(ContentIdea.priority == priority)
            .order_by(desc(ContentIdea.potential_score))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_scheduled(self, start_date: date, end_date: date) -> List[ContentIdea]:
        """ดึง ideas ที่ scheduled ในช่วงเวลา"""
        stmt = (
            select(ContentIdea)
            .where(
                and_(
                    ContentIdea.scheduled_date >= start_date,
                    ContentIdea.scheduled_date <= end_date,
                    ContentIdea.status == "scheduled",
                )
            )
            .order_by(ContentIdea.scheduled_date)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_top_ideas(self, limit: int = 10) -> List[ContentIdea]:
        """ดึง ideas ที่มี potential สูงสุด"""
        stmt = (
            select(ContentIdea)
            .where(ContentIdea.status.in_(["draft", "in_progress"]))
            .order_by(desc(ContentIdea.potential_score))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())


class PlaybookRuleRepository(BaseRepository[PlaybookRule]):
    """Repository สำหรับจัดการ Playbook Rules"""
    
    def __init__(self, session: Session):
        super().__init__(session, PlaybookRule)
    
    def get_active_rules(self, category: Optional[str] = None) -> List[PlaybookRule]:
        """ดึง rules ที่ active"""
        conditions = [PlaybookRule.is_active == True]
        if category:
            conditions.append(PlaybookRule.category == category)
        
        stmt = (
            select(PlaybookRule)
            .where(and_(*conditions))
            .order_by(desc(PlaybookRule.confidence_score))
        )
        return list(self.session.scalars(stmt).all())
    
    def get_high_confidence_rules(self, min_confidence: float = 0.7) -> List[PlaybookRule]:
        """ดึง rules ที่มี confidence สูง"""
        stmt = (
            select(PlaybookRule)
            .where(
                and_(
                    PlaybookRule.is_active == True,
                    PlaybookRule.confidence_score >= min_confidence,
                )
            )
            .order_by(desc(PlaybookRule.confidence_score))
        )
        return list(self.session.scalars(stmt).all())
    
    def record_application(self, id: int, success: bool) -> Optional[PlaybookRule]:
        """บันทึกการใช้งาน rule"""
        rule = self.get_by_id(id)
        if rule:
            rule.times_applied += 1
            if success:
                rule.times_successful += 1
            rule.success_rate = rule.times_successful / rule.times_applied
            rule.last_applied_at = datetime.utcnow()
            self.session.flush()
        return rule
    
    def get_auto_generated(self) -> List[PlaybookRule]:
        """ดึง rules ที่ถูกสร้างอัตโนมัติ"""
        stmt = (
            select(PlaybookRule)
            .where(PlaybookRule.is_auto_generated == True)
            .order_by(desc(PlaybookRule.created_at))
        )
        return list(self.session.scalars(stmt).all())


class RunLogRepository(BaseRepository[RunLog]):
    """Repository สำหรับจัดการ Run Logs"""
    
    def __init__(self, session: Session):
        super().__init__(session, RunLog)
    
    def create_run(self, run_type: str, triggered_by: str = "system", **kwargs) -> RunLog:
        """สร้าง run log ใหม่"""
        run_id = f"{run_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        return self.create(
            run_id=run_id,
            run_type=run_type,
            triggered_by=triggered_by,
            status="running",
            **kwargs,
        )
    
    def complete_run(
        self,
        id: int,
        status: str = "completed",
        result: Optional[dict] = None,
        items_processed: int = 0,
        items_succeeded: int = 0,
        items_failed: int = 0,
    ) -> Optional[RunLog]:
        """อัพเดท run log เมื่อเสร็จสิ้น"""
        run = self.get_by_id(id)
        if run:
            run.status = status
            run.completed_at = datetime.utcnow()
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
            run.result = result
            run.items_processed = items_processed
            run.items_succeeded = items_succeeded
            run.items_failed = items_failed
            self.session.flush()
        return run
    
    def fail_run(self, id: int, error_message: str, error_traceback: Optional[str] = None) -> Optional[RunLog]:
        """บันทึก error สำหรับ run ที่ล้มเหลว"""
        run = self.get_by_id(id)
        if run:
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
            run.error_message = error_message
            run.error_traceback = error_traceback
            self.session.flush()
        return run
    
    def get_recent_runs(self, run_type: Optional[str] = None, limit: int = 50) -> List[RunLog]:
        """ดึง runs ล่าสุด"""
        conditions = []
        if run_type:
            conditions.append(RunLog.run_type == run_type)
        
        stmt = select(RunLog)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(RunLog.started_at)).limit(limit)
        
        return list(self.session.scalars(stmt).all())
    
    def get_failed_runs(self, since: Optional[datetime] = None) -> List[RunLog]:
        """ดึง runs ที่ล้มเหลว"""
        conditions = [RunLog.status == "failed"]
        if since:
            conditions.append(RunLog.started_at >= since)
        
        stmt = (
            select(RunLog)
            .where(and_(*conditions))
            .order_by(desc(RunLog.started_at))
        )
        return list(self.session.scalars(stmt).all())
    
    def get_run_stats(self, run_type: Optional[str] = None, days: int = 30) -> dict:
        """คำนวณ statistics ของ runs"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        conditions = [RunLog.started_at >= cutoff_date]
        if run_type:
            conditions.append(RunLog.run_type == run_type)
        
        stmt = select(
            func.count(RunLog.id).label("total_runs"),
            func.sum(func.case((RunLog.status == "completed", 1), else_=0)).label("completed"),
            func.sum(func.case((RunLog.status == "failed", 1), else_=0)).label("failed"),
            func.avg(RunLog.duration_seconds).label("avg_duration"),
        ).where(and_(*conditions))
        
        result = self.session.execute(stmt).first()
        return {
            "total_runs": result.total_runs or 0,
            "completed": result.completed or 0,
            "failed": result.failed or 0,
            "avg_duration": result.avg_duration or 0.0,
            "success_rate": (result.completed / result.total_runs * 100) if result.total_runs else 0.0,
        }
