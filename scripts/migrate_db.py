#!/usr/bin/env python3
"""
migrate_db.py - Script สำหรับ migrate ฐานข้อมูล SQLite
รัน: python scripts/migrate_db.py

Script นี้จะตรวจสอบและเพิ่ม columns ที่ขาดหายไปในฐานข้อมูล
รองรับการรันซ้ำหลายครั้งได้อย่างปลอดภัย (idempotent)

Migrations ที่รองรับ:
- เพิ่ม impressions (Integer, nullable) ใน daily_metrics
- เพิ่ม impressions_ctr (Float, nullable) ใน daily_metrics
- เพิ่ม summary_th (Text, nullable) ใน research_items
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.utils.config import load_config
from src.utils.logger import setup_logger, print_banner, print_success, print_error, print_info, print_warning

console = Console()


def get_table_columns(cursor, table_name: str) -> list:
    """
    ดึงรายชื่อ columns ของตาราง
    
    Args:
        cursor: SQLite cursor
        table_name: ชื่อตาราง
        
    Returns:
        List ของชื่อ columns
    """
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return [col[1] for col in columns]


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    """
    ตรวจสอบว่า column มีอยู่ในตารางหรือไม่
    
    Args:
        cursor: SQLite cursor
        table_name: ชื่อตาราง
        column_name: ชื่อ column
        
    Returns:
        True ถ้า column มีอยู่
    """
    columns = get_table_columns(cursor, table_name)
    return column_name in columns


def add_column(cursor, table_name: str, column_name: str, column_type: str, default: str = None) -> bool:
    """
    เพิ่ม column ใหม่ในตาราง
    
    Args:
        cursor: SQLite cursor
        table_name: ชื่อตาราง
        column_name: ชื่อ column
        column_type: ชนิดข้อมูล (INTEGER, REAL, TEXT, etc.)
        default: ค่า default (optional)
        
    Returns:
        True ถ้าเพิ่มสำเร็จ หรือ column มีอยู่แล้ว
    """
    if column_exists(cursor, table_name, column_name):
        print_info(f"  ✓ Column '{column_name}' มีอยู่แล้วในตาราง '{table_name}'")
        return True
    
    try:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        if default is not None:
            sql += f" DEFAULT {default}"
        
        cursor.execute(sql)
        print_success(f"  ✓ เพิ่ม column '{column_name}' ในตาราง '{table_name}' สำเร็จ")
        return True
    except sqlite3.Error as e:
        print_error(f"  ✗ ไม่สามารถเพิ่ม column '{column_name}': {e}")
        return False


def migrate_daily_metrics(cursor) -> dict:
    """
    Migrate ตาราง daily_metrics
    
    เพิ่ม columns:
    - impressions (INTEGER, nullable)
    - impressions_ctr (REAL, nullable)
    
    Returns:
        Dictionary ของผลลัพธ์
    """
    console.print("\n[bold cyan]📊 กำลัง migrate ตาราง daily_metrics...[/bold cyan]")
    
    results = {
        "impressions": add_column(cursor, "daily_metrics", "impressions", "INTEGER"),
        "impressions_ctr": add_column(cursor, "daily_metrics", "impressions_ctr", "REAL"),
    }
    
    return results


def migrate_research_items(cursor) -> dict:
    """
    Migrate ตาราง research_items
    
    เพิ่ม columns:
    - summary_th (TEXT, nullable)
    
    Returns:
        Dictionary ของผลลัพธ์
    """
    console.print("\n[bold cyan]🔬 กำลัง migrate ตาราง research_items...[/bold cyan]")
    
    results = {
        "summary_th": add_column(cursor, "research_items", "summary_th", "TEXT"),
    }
    
    return results


def show_migration_summary(all_results: dict) -> None:
    """แสดงสรุปผลการ migrate"""
    table = Table(title="📋 สรุปผลการ Migration", show_header=True)
    table.add_column("ตาราง", style="cyan")
    table.add_column("Column", style="white")
    table.add_column("สถานะ", style="green")
    
    for table_name, columns in all_results.items():
        for column_name, success in columns.items():
            status = "✅ สำเร็จ" if success else "❌ ล้มเหลว"
            table.add_row(table_name, column_name, status)
    
    console.print()
    console.print(table)


def check_database_exists(db_path: str) -> bool:
    """ตรวจสอบว่าไฟล์ฐานข้อมูลมีอยู่หรือไม่"""
    return Path(db_path).exists()


def check_table_exists(cursor, table_name: str) -> bool:
    """ตรวจสอบว่าตารางมีอยู่หรือไม่"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


@click.command()
@click.option("--config", default="configs/default.yaml", help="path ไปยังไฟล์ config")
@click.option("--dry-run", is_flag=True, help="แสดงสิ่งที่จะทำโดยไม่ทำจริง")
@click.option("--verbose", "-v", is_flag=True, help="แสดงรายละเอียดเพิ่มเติม")
def main(config: str, dry_run: bool, verbose: bool):
    """
    Migrate ฐานข้อมูล SQLite สำหรับ YouTube Content Assistant
    
    Script นี้จะตรวจสอบและเพิ่ม columns ที่ขาดหายไป
    สามารถรันซ้ำได้อย่างปลอดภัย (idempotent)
    
    ตัวอย่าง:
        python scripts/migrate_db.py
        python scripts/migrate_db.py --dry-run
        python scripts/migrate_db.py --verbose
    """
    print_banner(
        "YouTube Content Assistant",
        "Database Migration Script"
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
    
    # ตรวจสอบว่าฐานข้อมูลมีอยู่หรือไม่
    if not check_database_exists(db_path):
        print_error(f"ไม่พบไฟล์ฐานข้อมูล: {db_path}")
        print_info("กรุณารัน 'python scripts/init_db.py' ก่อนเพื่อสร้างฐานข้อมูล")
        sys.exit(1)
    
    if dry_run:
        console.print(Panel(
            "[yellow]🔍 โหมด Dry Run - จะแสดงสิ่งที่จะทำโดยไม่ทำจริง[/yellow]",
            border_style="yellow"
        ))
    
    console.print()
    
    # เชื่อมต่อฐานข้อมูล
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ตรวจสอบตารางที่ต้อง migrate
        tables_to_migrate = []
        
        if check_table_exists(cursor, "daily_metrics"):
            tables_to_migrate.append("daily_metrics")
        else:
            print_warning("ไม่พบตาราง 'daily_metrics' - ข้ามการ migrate")
        
        if check_table_exists(cursor, "research_items"):
            tables_to_migrate.append("research_items")
        else:
            print_warning("ไม่พบตาราง 'research_items' - ข้ามการ migrate")
        
        if not tables_to_migrate:
            print_error("ไม่พบตารางที่ต้อง migrate")
            sys.exit(1)
        
        # แสดง columns ปัจจุบัน (ถ้า verbose)
        if verbose:
            console.print("\n[bold]📋 Columns ปัจจุบัน:[/bold]")
            for table_name in tables_to_migrate:
                columns = get_table_columns(cursor, table_name)
                console.print(f"  {table_name}: {', '.join(columns)}")
        
        # ทำ migration
        all_results = {}
        
        if not dry_run:
            if "daily_metrics" in tables_to_migrate:
                all_results["daily_metrics"] = migrate_daily_metrics(cursor)
            
            if "research_items" in tables_to_migrate:
                all_results["research_items"] = migrate_research_items(cursor)
            
            # Commit changes
            conn.commit()
            
            # แสดงสรุป
            show_migration_summary(all_results)
            
            # ตรวจสอบผลลัพธ์
            all_success = all(
                all(columns.values())
                for columns in all_results.values()
            )
            
            console.print()
            if all_success:
                console.print(Panel(
                    "[green]✓ Migration เสร็จสมบูรณ์![/green]\n\n"
                    "ขั้นตอนถัดไป:\n"
                    "  • รัน fetch_youtube.py เพื่อดึงข้อมูลใหม่\n"
                    "  • รัน dashboard เพื่อดูผลลัพธ์",
                    title="✅ สำเร็จ",
                    border_style="green"
                ))
            else:
                console.print(Panel(
                    "[yellow]⚠️ Migration เสร็จสิ้นแต่มีบางส่วนล้มเหลว[/yellow]",
                    title="⚠️ คำเตือน",
                    border_style="yellow"
                ))
        else:
            # Dry run - แสดงสิ่งที่จะทำ
            console.print("\n[bold]📝 สิ่งที่จะทำ (Dry Run):[/bold]")
            
            if "daily_metrics" in tables_to_migrate:
                columns = get_table_columns(cursor, "daily_metrics")
                console.print("\n  [cyan]daily_metrics:[/cyan]")
                if "impressions" not in columns:
                    console.print("    • จะเพิ่ม column 'impressions' (INTEGER)")
                else:
                    console.print("    • 'impressions' มีอยู่แล้ว - ข้าม")
                if "impressions_ctr" not in columns:
                    console.print("    • จะเพิ่ม column 'impressions_ctr' (REAL)")
                else:
                    console.print("    • 'impressions_ctr' มีอยู่แล้ว - ข้าม")
            
            if "research_items" in tables_to_migrate:
                columns = get_table_columns(cursor, "research_items")
                console.print("\n  [cyan]research_items:[/cyan]")
                if "summary_th" not in columns:
                    console.print("    • จะเพิ่ม column 'summary_th' (TEXT)")
                else:
                    console.print("    • 'summary_th' มีอยู่แล้ว - ข้าม")
            
            console.print("\n[yellow]รัน command โดยไม่มี --dry-run เพื่อทำจริง[/yellow]")
        
        conn.close()
        
    except sqlite3.Error as e:
        print_error(f"เกิดข้อผิดพลาดกับฐานข้อมูล: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาด: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
