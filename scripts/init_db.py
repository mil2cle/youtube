#!/usr/bin/env python3
"""
init_db.py - Script สำหรับ initialize ฐานข้อมูล
รัน: python scripts/init_db.py [--reset] [--seed]

สร้างตารางทั้งหมดและเพิ่มข้อมูลตัวอย่าง (ถ้าต้องการ)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import random

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.db.connection import init_db, reset_db, session_scope, get_engine
from src.db.models import (
    Base,
    Video,
    DailyMetric,
    ResearchItem,
    ContentIdea,
    PlaybookRule,
    RunLog,
    get_all_models,
)
from src.utils.config import load_config
from src.utils.logger import setup_logger, print_banner, print_success, print_error, print_info

console = Console()


def seed_sample_data(session) -> dict:
    """
    เพิ่มข้อมูลตัวอย่างลงฐานข้อมูล
    
    Returns:
        Dictionary ของจำนวนข้อมูลที่เพิ่ม
    """
    counts = {
        "videos": 0,
        "daily_metrics": 0,
        "research_items": 0,
        "content_ideas": 0,
        "playbook_rules": 0,
        "runs_log": 0,
    }
    
    # Sample Videos
    sample_videos = [
        {
            "youtube_id": "abc123xyz",
            "title": "วิธีเริ่มต้นทำ YouTube Channel ในปี 2024",
            "description": "คู่มือฉบับสมบูรณ์สำหรับผู้เริ่มต้น",
            "channel_id": "UC_sample_channel",
            "channel_name": "Sample Channel",
            "category": "tutorial",
            "tags": {"tags": ["youtube", "beginner", "tutorial"]},
            "duration_seconds": 900,
            "view_count": 15000,
            "like_count": 800,
            "comment_count": 120,
            "published_at": datetime.now() - timedelta(days=30),
        },
        {
            "youtube_id": "def456uvw",
            "title": "รีวิว iPhone 15 Pro Max หลังใช้งาน 3 เดือน",
            "description": "รีวิวจากประสบการณ์จริง",
            "channel_id": "UC_sample_channel",
            "channel_name": "Sample Channel",
            "category": "review",
            "tags": {"tags": ["iphone", "review", "apple"]},
            "duration_seconds": 1200,
            "view_count": 25000,
            "like_count": 1200,
            "comment_count": 200,
            "published_at": datetime.now() - timedelta(days=15),
        },
        {
            "youtube_id": "ghi789rst",
            "title": "Vlog: หนึ่งวันในชีวิต YouTuber",
            "description": "ตามติดชีวิตประจำวัน",
            "channel_id": "UC_sample_channel",
            "channel_name": "Sample Channel",
            "category": "vlog",
            "tags": {"tags": ["vlog", "lifestyle", "youtuber"]},
            "duration_seconds": 600,
            "view_count": 8000,
            "like_count": 500,
            "comment_count": 80,
            "published_at": datetime.now() - timedelta(days=7),
        },
    ]
    
    for video_data in sample_videos:
        video = Video(**video_data)
        session.add(video)
        counts["videos"] += 1
    
    session.flush()
    
    # Sample Daily Metrics
    videos = session.query(Video).all()
    for video in videos:
        for days_ago in range(30):
            metric = DailyMetric(
                video_id=video.id,
                date=datetime.now().date() - timedelta(days=days_ago),
                views=random.randint(100, 1000),
                likes=random.randint(10, 100),
                comments=random.randint(1, 20),
                watch_time_minutes=random.uniform(100, 500),
                average_view_duration=random.uniform(120, 300),
                average_view_percentage=random.uniform(30, 70),
                subscribers_gained=random.randint(0, 10),
                impressions=random.randint(500, 5000),
                impressions_ctr=random.uniform(2.0, 10.0),  # CTR เป็นเปอร์เซ็นต์
            )
            session.add(metric)
            counts["daily_metrics"] += 1
    
    # Sample Research Items
    sample_research = [
        {
            "title": "Trend: AI และ Machine Learning กำลังมาแรง",
            "source": "youtube_trending",
            "summary": "วิดีโอเกี่ยวกับ AI มียอดวิวเพิ่มขึ้น 200% ในเดือนที่ผ่านมา",
            "keywords": {"keywords": ["AI", "machine learning", "technology"]},
            "category": "technology",
            "relevance_score": 0.85,
            "trend_score": 0.9,
            "is_actionable": True,
        },
        {
            "title": "คู่แข่ง: Channel XYZ ทำวิดีโอ Shorts ได้ดี",
            "source": "competitor",
            "summary": "ใช้ format 60 วินาที พร้อม hook ที่แรง",
            "keywords": {"keywords": ["shorts", "competitor", "strategy"]},
            "category": "strategy",
            "relevance_score": 0.75,
            "trend_score": 0.6,
            "is_actionable": True,
        },
        {
            "title": "Google Trends: คำค้นหา 'วิธีทำ' เพิ่มขึ้น",
            "source": "google_trends",
            "summary": "How-to content ยังคงได้รับความนิยม",
            "keywords": {"keywords": ["how-to", "tutorial", "guide"]},
            "category": "content",
            "relevance_score": 0.7,
            "trend_score": 0.75,
            "is_actionable": False,
        },
    ]
    
    for research_data in sample_research:
        research = ResearchItem(**research_data)
        session.add(research)
        counts["research_items"] += 1
    
    # Sample Content Ideas
    sample_ideas = [
        {
            "title": "สอนใช้ ChatGPT สำหรับ YouTuber",
            "description": "วิธีใช้ AI ช่วยเขียน script และวางแผน content",
            "category": "tutorial",
            "priority": "high",
            "status": "draft",
            "target_audience": "YouTuber มือใหม่",
            "estimated_duration_minutes": 15,
            "potential_score": 85.0,
        },
        {
            "title": "เปรียบเทียบ Camera สำหรับ Vlog ราคาไม่เกิน 20,000",
            "description": "รีวิวและเปรียบเทียบกล้อง 5 รุ่น",
            "category": "review",
            "priority": "medium",
            "status": "in_progress",
            "target_audience": "Vlogger",
            "estimated_duration_minutes": 20,
            "potential_score": 72.0,
        },
        {
            "title": "Behind the Scenes: ทำวิดีโอ 1 ชิ้นใช้เวลาเท่าไหร่",
            "description": "เปิดเบื้องหลังการทำงาน",
            "category": "vlog",
            "priority": "low",
            "status": "scheduled",
            "scheduled_date": datetime.now().date() + timedelta(days=7),
            "target_audience": "ผู้สนใจทำ YouTube",
            "estimated_duration_minutes": 10,
            "potential_score": 65.0,
        },
    ]
    
    for idea_data in sample_ideas:
        idea = ContentIdea(**idea_data)
        session.add(idea)
        counts["content_ideas"] += 1
    
    # Sample Playbook Rules
    sample_rules = [
        {
            "name": "Title Length Optimization",
            "description": "ใช้ title ความยาว 50-70 ตัวอักษรเพื่อ CTR ที่ดีที่สุด",
            "category": "title_optimization",
            "condition": {"field": "title_length", "operator": "gte", "value": 50},
            "action": {
                "action_type": "suggest",
                "target": "title",
                "recommendation": "ปรับ title ให้มีความยาว 50-70 ตัวอักษร",
            },
            "confidence_score": 0.8,
            "success_rate": 0.75,
            "times_applied": 15,
            "times_successful": 11,
            "is_active": True,
            "is_auto_generated": False,
        },
        {
            "name": "Best Posting Time",
            "description": "โพสต์เวลา 18:00-20:00 ได้ engagement ดีที่สุด",
            "category": "posting_time",
            "condition": {"field": "publish_hour", "operator": "gte", "value": 18},
            "action": {
                "action_type": "suggest",
                "target": "schedule",
                "recommendation": "กำหนดเวลาโพสต์ระหว่าง 18:00-20:00",
            },
            "confidence_score": 0.7,
            "success_rate": 0.68,
            "times_applied": 20,
            "times_successful": 14,
            "is_active": True,
            "is_auto_generated": True,
        },
        {
            "name": "Optimal Video Length",
            "description": "วิดีโอ 8-12 นาทีมี retention ดีที่สุด",
            "category": "content_length",
            "condition": {"field": "duration_minutes", "operator": "gte", "value": 8},
            "action": {
                "action_type": "suggest",
                "target": "content",
                "recommendation": "ทำวิดีโอความยาว 8-12 นาที",
            },
            "confidence_score": 0.65,
            "success_rate": 0.6,
            "times_applied": 10,
            "times_successful": 6,
            "is_active": True,
            "is_auto_generated": True,
        },
    ]
    
    for rule_data in sample_rules:
        rule = PlaybookRule(**rule_data)
        session.add(rule)
        counts["playbook_rules"] += 1
    
    # Sample Run Logs
    sample_runs = [
        {
            "run_id": "daily_metrics_20240101_120000_abc123",
            "run_type": "daily_metrics_collection",
            "status": "completed",
            "started_at": datetime.now() - timedelta(hours=6),
            "completed_at": datetime.now() - timedelta(hours=6) + timedelta(minutes=5),
            "duration_seconds": 300,
            "items_processed": 50,
            "items_succeeded": 50,
            "items_failed": 0,
            "triggered_by": "scheduler",
        },
        {
            "run_id": "weekly_analysis_20240101_090000_def456",
            "run_type": "weekly_analysis",
            "status": "completed",
            "started_at": datetime.now() - timedelta(days=1),
            "completed_at": datetime.now() - timedelta(days=1) + timedelta(minutes=10),
            "duration_seconds": 600,
            "items_processed": 100,
            "items_succeeded": 98,
            "items_failed": 2,
            "triggered_by": "scheduler",
        },
    ]
    
    for run_data in sample_runs:
        run = RunLog(**run_data)
        session.add(run)
        counts["runs_log"] += 1
    
    session.commit()
    return counts


def show_table_info(engine) -> None:
    """แสดงข้อมูล tables ที่สร้าง"""
    table = Table(title="📊 ตารางในฐานข้อมูล", show_header=True, header_style="bold cyan")
    table.add_column("ชื่อตาราง", style="green")
    table.add_column("คำอธิบาย", style="white")
    table.add_column("Columns", justify="right", style="yellow")
    
    table_info = [
        ("videos", "เก็บข้อมูลวิดีโอ YouTube", 18),
        ("daily_metrics", "เก็บ metrics รายวันของแต่ละวิดีโอ", 16),
        ("research_items", "เก็บข้อมูลการวิจัยและ trends", 15),
        ("content_ideas", "เก็บไอเดียเนื้อหา", 17),
        ("playbook_rules", "เก็บกฎการปรับปรุงตัวเอง", 16),
        ("runs_log", "เก็บ log การทำงานของระบบ", 15),
    ]
    
    for name, desc, cols in table_info:
        table.add_row(name, desc, str(cols))
    
    console.print(table)


@click.command()
@click.option("--reset", is_flag=True, help="รีเซ็ตฝานข้อมูล (ลบข้อมูลเดิมทั้งหมด)")
@click.option("--seed", is_flag=True, help="เพิ่มข้อมูลตัวอย่าง")
@click.option("--yes", "-y", is_flag=True, help="ข้ามการยืนยัน (สำหรับใช้กับ --reset)")
@click.option("--config", default="configs/default.yaml", help="path ไปยังไฟล์ config")
def main(reset: bool, seed: bool, yes: bool, config: str):
    """
    Initialize ฐานข้อมูลสำหรับ YouTube Content Assistant
    
    สร้างตารางทั้งหมดและเพิ่มข้อมูลตัวอย่าง (ถ้าต้องการ)
    """
    print_banner(
        "YouTube Content Assistant",
        "Database Initialization Script"
    )
    
    # โหลด config
    try:
        cfg = load_config(config)
        db_path = cfg.database.path
        print_info(f"ใช้ config: {config}")
        print_info(f"Database path: {db_path}")
    except Exception as e:
        print_error(f"ไม่สามารถโหลด config: {e}")
        sys.exit(1)
    
    # Setup logger
    setup_logger(log_file=cfg.logging.file, level=cfg.app.log_level)
    
    # สร้าง directories
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg.logging.file).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg.export.output_dir).mkdir(parents=True, exist_ok=True)
    
    console.print()
    
    # Reset database ถ้าต้องการ
    if reset:
        console.print(Panel(
            "[yellow]⚠️ คำเตือน: การรีเซ็ตจะลบข้อมูลทั้งหมด![/yellow]",
            title="Reset Database",
            border_style="yellow"
        ))
        
        # ถ้าใช้ --yes จะข้ามการยืนยัน
        if yes or click.confirm("ยืนยันการรีเซ็ตฝานข้อมูล?"):
            if yes:
                print_info("ข้ามการยืนยัน (ใช้ --yes flag)")
            reset_db(db_path)
            console.print()
        else:
            print_info("ยกเลิกการรีเซ็ต")
            return
    
    # Initialize database
    try:
        engine = init_db(db_path, echo=cfg.database.echo)
        console.print()
        show_table_info(engine)
        console.print()
    except Exception as e:
        print_error(f"ไม่สามารถ initialize database: {e}")
        sys.exit(1)
    
    # Seed data ถ้าต้องการ
    if seed:
        console.print(Panel(
            "กำลังเพิ่มข้อมูลตัวอย่าง...",
            title="Seed Data",
            border_style="blue"
        ))
        
        try:
            with session_scope() as session:
                counts = seed_sample_data(session)
            
            seed_table = Table(title="📦 ข้อมูลตัวอย่างที่เพิ่ม", show_header=True)
            seed_table.add_column("ตาราง", style="green")
            seed_table.add_column("จำนวน", justify="right", style="cyan")
            
            for table_name, count in counts.items():
                seed_table.add_row(table_name, str(count))
            
            console.print(seed_table)
            console.print()
            print_success("เพิ่มข้อมูลตัวอย่างสำเร็จ!")
            
        except Exception as e:
            print_error(f"ไม่สามารถเพิ่มข้อมูลตัวอย่าง: {e}")
            sys.exit(1)
    
    # Summary
    console.print()
    console.print(Panel(
        "[green]✓ Database initialization เสร็จสมบูรณ์![/green]\n\n"
        f"Database: {db_path}\n"
        f"Tables: {len(get_all_models())}\n\n"
        "ขั้นตอนถัดไป:\n"
        "  • รัน dashboard: streamlit run dashboard/app.py\n"
        "  • รัน all modules: python scripts/run_all.py",
        title="✅ สำเร็จ",
        border_style="green"
    ))


if __name__ == "__main__":
    main()
