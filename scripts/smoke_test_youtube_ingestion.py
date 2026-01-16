#!/usr/bin/env python3
"""
smoke_test_youtube_ingestion.py - Script ทดสอบการทำงานของระบบ YouTube Ingestion
รัน: python scripts/smoke_test_youtube_ingestion.py

ทดสอบ:
1. ตรวจสอบ schema ฐานข้อมูล (columns ที่จำเป็น)
2. ตรวจสอบ mapping logic ระหว่าง API response และ model
3. ทดสอบการสร้าง DailyMetric object
"""

import sys
from pathlib import Path
from datetime import datetime, date, timedelta

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.utils.config import load_config
from src.utils.logger import print_banner, print_success, print_error, print_info, print_warning

console = Console()


def check_database_schema(db_path: str) -> dict:
    """
    ตรวจสอบ schema ของฐานข้อมูล
    
    Args:
        db_path: path ไปยังไฟล์ฐานข้อมูล
        
    Returns:
        Dictionary ของผลการตรวจสอบ
    """
    import sqlite3
    
    results = {
        "database_exists": False,
        "daily_metrics_table_exists": False,
        "impressions_column_exists": False,
        "impressions_ctr_column_exists": False,
        "all_required_columns": False,
    }
    
    # ตรวจสอบว่าไฟล์มีอยู่หรือไม่
    if not Path(db_path).exists():
        return results
    
    results["database_exists"] = True
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ตรวจสอบว่าตาราง daily_metrics มีอยู่หรือไม่
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_metrics'"
        )
        if cursor.fetchone():
            results["daily_metrics_table_exists"] = True
            
            # ดึงรายชื่อ columns
            cursor.execute("PRAGMA table_info(daily_metrics)")
            columns = [col[1] for col in cursor.fetchall()]
            
            results["impressions_column_exists"] = "impressions" in columns
            results["impressions_ctr_column_exists"] = "impressions_ctr" in columns
            
            # ตรวจสอบ columns ที่จำเป็นทั้งหมด
            required_columns = [
                "id", "video_id", "date", "views", "likes", "comments",
                "watch_time_minutes", "average_view_duration", "average_view_percentage",
                "subscribers_gained", "impressions", "impressions_ctr"
            ]
            results["all_required_columns"] = all(col in columns for col in required_columns)
        
        conn.close()
        
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาดในการตรวจสอบฐานข้อมูล: {e}")
    
    return results


def test_metric_data_mapping() -> dict:
    """
    ทดสอบ mapping logic ระหว่าง MetricData และ DailyMetric
    
    Returns:
        Dictionary ของผลการทดสอบ
    """
    from src.youtube.client import MetricData
    from src.db.models import DailyMetric
    
    results = {
        "metric_data_has_impressions": False,
        "metric_data_has_impressions_ctr": False,
        "daily_metric_accepts_impressions": False,
        "daily_metric_accepts_impressions_ctr": False,
        "null_safe_handling": False,
    }
    
    try:
        # ทดสอบ MetricData
        metric_data = MetricData(
            video_id="test123",
            date=date.today(),
            views=1000,
            impressions=5000,
            impressions_ctr=5.5,
        )
        
        results["metric_data_has_impressions"] = hasattr(metric_data, "impressions")
        results["metric_data_has_impressions_ctr"] = hasattr(metric_data, "impressions_ctr")
        
        # ทดสอบ DailyMetric model
        # ตรวจสอบว่า model รับ impressions และ impressions_ctr ได้
        try:
            daily_metric = DailyMetric(
                video_id=1,
                date=date.today(),
                views=1000,
                impressions=5000,
                impressions_ctr=5.5,
            )
            results["daily_metric_accepts_impressions"] = True
            results["daily_metric_accepts_impressions_ctr"] = True
        except TypeError as e:
            if "impressions" in str(e):
                results["daily_metric_accepts_impressions"] = False
            if "impressions_ctr" in str(e):
                results["daily_metric_accepts_impressions_ctr"] = False
        
        # ทดสอบ null-safe handling
        try:
            metric_data_null = MetricData(
                video_id="test456",
                date=date.today(),
                views=500,
                impressions=None,
                impressions_ctr=None,
            )
            
            daily_metric_null = DailyMetric(
                video_id=2,
                date=date.today(),
                views=500,
                impressions=metric_data_null.impressions,
                impressions_ctr=metric_data_null.impressions_ctr,
            )
            results["null_safe_handling"] = True
        except Exception:
            results["null_safe_handling"] = False
        
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาดในการทดสอบ mapping: {e}")
    
    return results


def test_youtube_client_import() -> dict:
    """
    ทดสอบการ import YouTubeClient
    
    Returns:
        Dictionary ของผลการทดสอบ
    """
    results = {
        "youtube_client_importable": False,
        "metric_data_importable": False,
        "fetch_video_analytics_exists": False,
    }
    
    try:
        from src.youtube.client import YouTubeClient, MetricData
        results["youtube_client_importable"] = True
        results["metric_data_importable"] = True
        
        # ตรวจสอบว่า method fetch_video_analytics มีอยู่
        results["fetch_video_analytics_exists"] = hasattr(YouTubeClient, "fetch_video_analytics")
        
    except ImportError as e:
        print_error(f"ไม่สามารถ import module: {e}")
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาด: {e}")
    
    return results


def show_test_results(all_results: dict) -> bool:
    """
    แสดงผลการทดสอบทั้งหมด
    
    Returns:
        True ถ้าผ่านทุกการทดสอบ
    """
    table = Table(title="📋 ผลการทดสอบ Smoke Test", show_header=True)
    table.add_column("หมวด", style="cyan")
    table.add_column("รายการทดสอบ", style="white")
    table.add_column("ผลลัพธ์", style="green")
    
    all_passed = True
    
    for category, tests in all_results.items():
        for test_name, passed in tests.items():
            status = "✅ ผ่าน" if passed else "❌ ไม่ผ่าน"
            if not passed:
                all_passed = False
            
            # แปลงชื่อ test ให้อ่านง่าย
            readable_name = test_name.replace("_", " ").title()
            table.add_row(category, readable_name, status)
    
    console.print()
    console.print(table)
    
    return all_passed


@click.command()
@click.option("--config", default="configs/default.yaml", help="path ไปยังไฟล์ config")
@click.option("--verbose", "-v", is_flag=True, help="แสดงรายละเอียดเพิ่มเติม")
def main(config: str, verbose: bool):
    """
    Smoke Test สำหรับ YouTube Ingestion
    
    ตรวจสอบว่าระบบพร้อมใช้งานหรือไม่:
    - Schema ฐานข้อมูลถูกต้อง
    - Mapping logic ทำงานได้
    - Module imports ได้
    
    ตัวอย่าง:
        python scripts/smoke_test_youtube_ingestion.py
        python scripts/smoke_test_youtube_ingestion.py --verbose
    """
    print_banner(
        "YouTube Content Assistant",
        "Smoke Test Script"
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
    
    console.print()
    console.print("[bold]🔍 กำลังทดสอบระบบ...[/bold]")
    
    all_results = {}
    
    # 1. ตรวจสอบ Database Schema
    console.print("\n[cyan]1. ตรวจสอบ Database Schema...[/cyan]")
    schema_results = check_database_schema(db_path)
    all_results["Database Schema"] = schema_results
    
    if verbose:
        for test, passed in schema_results.items():
            status = "✓" if passed else "✗"
            console.print(f"   {status} {test}")
    
    # 2. ตรวจสอบ YouTube Client Import
    console.print("\n[cyan]2. ตรวจสอบ YouTube Client...[/cyan]")
    import_results = test_youtube_client_import()
    all_results["YouTube Client"] = import_results
    
    if verbose:
        for test, passed in import_results.items():
            status = "✓" if passed else "✗"
            console.print(f"   {status} {test}")
    
    # 3. ทดสอบ Mapping Logic
    console.print("\n[cyan]3. ทดสอบ Mapping Logic...[/cyan]")
    mapping_results = test_metric_data_mapping()
    all_results["Mapping Logic"] = mapping_results
    
    if verbose:
        for test, passed in mapping_results.items():
            status = "✓" if passed else "✗"
            console.print(f"   {status} {test}")
    
    # แสดงผลรวม
    all_passed = show_test_results(all_results)
    
    console.print()
    
    if all_passed:
        console.print(Panel(
            "[green]✓ Smoke Test ผ่านทั้งหมด![/green]\n\n"
            "ระบบพร้อมใช้งาน คุณสามารถ:\n"
            "  • รัน `python scripts/fetch_youtube.py --all` เพื่อดึงข้อมูล\n"
            "  • รัน `streamlit run dashboard/app.py` เพื่อดู Dashboard",
            title="✅ สำเร็จ",
            border_style="green"
        ))
        sys.exit(0)
    else:
        # แสดงคำแนะนำตามปัญหาที่พบ
        recommendations = []
        
        if not schema_results.get("database_exists"):
            recommendations.append("• รัน `python scripts/init_db.py` เพื่อสร้างฐานข้อมูล")
        elif not schema_results.get("impressions_column_exists") or not schema_results.get("impressions_ctr_column_exists"):
            recommendations.append("• รัน `python scripts/migrate_db.py` เพื่อเพิ่ม columns ที่ขาดหายไป")
        
        if not mapping_results.get("daily_metric_accepts_impressions"):
            recommendations.append("• ตรวจสอบว่า model DailyMetric มี columns impressions และ impressions_ctr")
        
        recommendation_text = "\n".join(recommendations) if recommendations else "ตรวจสอบ error messages ด้านบน"
        
        console.print(Panel(
            f"[yellow]⚠️ Smoke Test ไม่ผ่านบางรายการ[/yellow]\n\n"
            f"คำแนะนำ:\n{recommendation_text}",
            title="⚠️ ต้องแก้ไข",
            border_style="yellow"
        ))
        sys.exit(1)


if __name__ == "__main__":
    main()
