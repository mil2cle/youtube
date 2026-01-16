#!/usr/bin/env python3
"""
fetch_youtube.py - Script สำหรับดึงข้อมูลจาก YouTube API
รัน: python scripts/fetch_youtube.py [OPTIONS]

ใช้สำหรับ:
- ดึงรายการวิดีโอทั้งหมดจาก channel
- ดึง daily metrics สำหรับแต่ละวิดีโอ
- รองรับ incremental fetch
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta
import json

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.db.connection import init_db, session_scope
from src.db.repository import VideoRepository, DailyMetricRepository, RunLogRepository
from src.youtube.oauth import YouTubeAuth, get_youtube_auth
from src.youtube.client import YouTubeClient, FetchResult
from src.utils.config import load_config
from src.utils.logger import (
    setup_logger,
    get_logger,
    print_banner,
    print_success,
    print_error,
    print_info,
    print_warning,
    TaskLogger,
)

console = Console()
logger = get_logger()


def parse_date(date_str: str) -> date:
    """แปลง string เป็น date"""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def display_fetch_result(result: FetchResult, title: str) -> None:
    """แสดงผลลัพธ์การดึงข้อมูล"""
    table = Table(title=title, show_header=True)
    table.add_column("รายการ", style="cyan")
    table.add_column("ค่า", style="green")
    
    if hasattr(result, "videos_fetched"):
        table.add_row("วิดีโอที่ดึง", str(result.videos_fetched))
        table.add_row("สร้างใหม่", str(result.videos_created))
        table.add_row("อัพเดท", str(result.videos_updated))
    
    if hasattr(result, "metrics_fetched"):
        table.add_row("Metrics ที่ดึง", str(result.metrics_fetched))
        table.add_row("Metrics สร้างใหม่", str(result.metrics_created))
    
    table.add_row("ระยะเวลา", f"{result.duration_seconds:.2f} วินาที")
    table.add_row("สถานะ", "✅ สำเร็จ" if result.success else "❌ ล้มเหลว")
    
    console.print(table)
    
    if result.errors:
        console.print()
        print_warning("Errors:")
        for error in result.errors:
            console.print(f"  • {error}")


def log_run(session, run_type: str, result: FetchResult) -> None:
    """บันทึก run log"""
    repo = RunLogRepository(session)
    
    run = repo.create_run(
        run_type=run_type,
        triggered_by="cli",
        parameters={"script": "fetch_youtube.py"},
    )
    
    items_processed = result.videos_fetched + result.metrics_fetched
    items_succeeded = result.videos_created + result.videos_updated + result.metrics_created
    items_failed = len(result.errors)
    
    if result.success:
        repo.complete_run(
            run.id,
            status="completed",
            items_processed=items_processed,
            items_succeeded=items_succeeded,
            items_failed=items_failed,
            result={
                "videos_fetched": result.videos_fetched,
                "videos_created": result.videos_created,
                "videos_updated": result.videos_updated,
                "metrics_fetched": result.metrics_fetched,
                "metrics_created": result.metrics_created,
            },
        )
    else:
        repo.fail_run(
            run.id,
            error_message="; ".join(result.errors) if result.errors else "Unknown error",
        )


@click.command()
@click.option("--videos", is_flag=True, help="ดึงรายการวิดีโอ")
@click.option("--metrics", is_flag=True, help="ดึง daily metrics")
@click.option("--all", "fetch_all", is_flag=True, help="ดึงทั้งวิดีโอและ metrics")
@click.option("--days", default=30, help="จำนวนวันที่จะดึง metrics (default: 30)")
@click.option("--start", "start_date", help="วันที่เริ่มต้น (YYYY-MM-DD)")
@click.option("--end", "end_date", help="วันที่สิ้นสุด (YYYY-MM-DD)")
@click.option("--incremental/--no-incremental", default=True, help="ดึงเฉพาะข้อมูลใหม่ (default: true)")
@click.option("--max-videos", default=None, type=int, help="จำนวนวิดีโอสูงสุดที่จะดึง")
@click.option("--export", type=click.Path(), help="Export ผลลัพธ์เป็น JSON")
@click.option("--config", default="configs/default.yaml", help="path ไปยังไฟล์ config")
def main(
    videos: bool,
    metrics: bool,
    fetch_all: bool,
    days: int,
    start_date: str,
    end_date: str,
    incremental: bool,
    max_videos: int,
    export: str,
    config: str,
):
    """
    ดึงข้อมูลจาก YouTube API และบันทึกลงฐานข้อมูล
    
    ตัวอย่าง:
        python scripts/fetch_youtube.py --all
        python scripts/fetch_youtube.py --videos
        python scripts/fetch_youtube.py --metrics --days 7
        python scripts/fetch_youtube.py --metrics --start 2024-01-01 --end 2024-01-31
    """
    print_banner(
        "YouTube Content Assistant",
        "YouTube Data Fetcher"
    )
    
    # โหลด config
    try:
        cfg = load_config(config)
        print_info(f"ใช้ config: {config}")
    except Exception as e:
        print_error(f"ไม่สามารถโหลด config: {e}")
        sys.exit(1)
    
    # Setup logger
    setup_logger(log_file=cfg.logging.file, level=cfg.app.log_level)
    
    # Initialize database
    try:
        init_db(cfg.database.path)
        print_info(f"เชื่อมต่อฐานข้อมูล: {cfg.database.path}")
    except Exception as e:
        print_error(f"ไม่สามารถเชื่อมต่อฐานข้อมูล: {e}")
        sys.exit(1)
    
    # ถ้าไม่ได้เลือก option ใดเลย ให้ดึงทั้งหมด
    if not any([videos, metrics, fetch_all]):
        fetch_all = True
    
    # ตรวจสอบ authentication
    console.print()
    print_info("กำลังตรวจสอบ authentication...")
    
    try:
        auth = get_youtube_auth()
        credentials = auth.get_credentials()
        
        if not credentials:
            print_error("ไม่พบ credentials - กรุณารัน validate_youtube_auth.py --authenticate ก่อน")
            sys.exit(1)
        
        status = auth.get_auth_status()
        if status.channel_title:
            print_success(f"Authenticated: {status.channel_title}")
        else:
            print_success("Authenticated")
            
    except Exception as e:
        print_error(f"Authentication error: {e}")
        sys.exit(1)
    
    # สร้าง client
    client = YouTubeClient(auth=auth)
    
    # Parse dates
    parsed_start_date = None
    parsed_end_date = None
    
    if start_date:
        try:
            parsed_start_date = parse_date(start_date)
        except ValueError:
            print_error(f"รูปแบบวันที่ไม่ถูกต้อง: {start_date} (ต้องเป็น YYYY-MM-DD)")
            sys.exit(1)
    
    if end_date:
        try:
            parsed_end_date = parse_date(end_date)
        except ValueError:
            print_error(f"รูปแบบวันที่ไม่ถูกต้อง: {end_date} (ต้องเป็น YYYY-MM-DD)")
            sys.exit(1)
    
    # Results
    all_results = {}
    
    with session_scope() as session:
        # ดึงวิดีโอ
        if fetch_all or videos:
            console.print()
            console.print(Panel(
                f"กำลังดึงรายการวิดีโอจาก YouTube...\n"
                f"Max videos: {max_videos or 'ทั้งหมด'}",
                title="📹 Fetch Videos",
                border_style="blue"
            ))
            
            try:
                result = client.sync_videos_to_db(
                    session=session,
                    max_results=max_videos,
                )
                all_results["videos"] = result
                
                console.print()
                display_fetch_result(result, "📹 ผลลัพธ์การดึงวิดีโอ")
                log_run(session, "fetch_videos", result)
                
            except Exception as e:
                print_error(f"Error fetching videos: {e}")
                all_results["videos"] = FetchResult(success=False, errors=[str(e)])
        
        # ดึง metrics
        if fetch_all or metrics:
            console.print()
            
            # แสดงช่วงวันที่
            if parsed_start_date and parsed_end_date:
                date_range = f"{parsed_start_date} - {parsed_end_date}"
            else:
                date_range = f"{days} วันล่าสุด"
            
            console.print(Panel(
                f"กำลังดึง daily metrics...\n"
                f"ช่วงวันที่: {date_range}\n"
                f"Incremental: {'ใช่' if incremental else 'ไม่'}",
                title="📊 Fetch Metrics",
                border_style="blue"
            ))
            
            try:
                result = client.sync_daily_metrics_to_db(
                    session=session,
                    days=days,
                    start_date=parsed_start_date,
                    end_date=parsed_end_date,
                    incremental=incremental,
                )
                all_results["metrics"] = result
                
                console.print()
                display_fetch_result(result, "📊 ผลลัพธ์การดึง Metrics")
                log_run(session, "fetch_metrics", result)
                
            except Exception as e:
                print_error(f"Error fetching metrics: {e}")
                all_results["metrics"] = FetchResult(success=False, errors=[str(e)])
    
    # Export ถ้าต้องการ
    if export:
        try:
            export_path = Path(export)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            export_data = {}
            for key, result in all_results.items():
                export_data[key] = {
                    "success": result.success,
                    "videos_fetched": getattr(result, "videos_fetched", 0),
                    "videos_created": getattr(result, "videos_created", 0),
                    "videos_updated": getattr(result, "videos_updated", 0),
                    "metrics_fetched": getattr(result, "metrics_fetched", 0),
                    "metrics_created": getattr(result, "metrics_created", 0),
                    "duration_seconds": result.duration_seconds,
                    "errors": result.errors,
                }
            
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print_success(f"Export ผลลัพธ์ไปยัง: {export}")
        except Exception as e:
            print_error(f"ไม่สามารถ export: {e}")
    
    # Summary
    console.print()
    
    total_success = all(r.success for r in all_results.values())
    
    if total_success:
        # สรุปจำนวนข้อมูลในฐานข้อมูล
        with session_scope() as session:
            video_repo = VideoRepository(session)
            metric_repo = DailyMetricRepository(session)
            
            total_videos = video_repo.count()
            total_metrics = metric_repo.count()
        
        console.print(Panel(
            f"[green]✓ ดึงข้อมูลสำเร็จ![/green]\n\n"
            f"ข้อมูลในฐานข้อมูล:\n"
            f"  • วิดีโอ: {total_videos:,} รายการ\n"
            f"  • Daily Metrics: {total_metrics:,} รายการ\n\n"
            f"ขั้นตอนถัดไป:\n"
            f"  • รัน dashboard: streamlit run dashboard/app.py\n"
            f"  • รัน analysis: python scripts/run_all.py --analytics",
            title="✅ สำเร็จ",
            border_style="green"
        ))
    else:
        failed_tasks = [k for k, v in all_results.items() if not v.success]
        console.print(Panel(
            f"[yellow]⚠ บาง task ล้มเหลว: {', '.join(failed_tasks)}[/yellow]\n\n"
            f"ตรวจสอบ:\n"
            f"  • Log file: {cfg.logging.file}\n"
            f"  • Authentication: python scripts/validate_youtube_auth.py --test",
            title="⚠️ คำเตือน",
            border_style="yellow"
        ))


if __name__ == "__main__":
    main()
