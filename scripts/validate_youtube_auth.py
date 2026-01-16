#!/usr/bin/env python3
"""
validate_youtube_auth.py - Script สำหรับตรวจสอบและตั้งค่า YouTube API authentication
รัน: python scripts/validate_youtube_auth.py [OPTIONS]

ใช้สำหรับ:
- ตรวจสอบสถานะ authentication
- ทำ OAuth flow ครั้งแรก
- ตรวจสอบ scopes
- ทดสอบ API calls
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

from src.youtube.oauth import YouTubeAuth, get_youtube_auth
from src.utils.config import load_config
from src.utils.logger import (
    setup_logger,
    print_banner,
    print_success,
    print_error,
    print_info,
    print_warning,
)

console = Console()


def check_client_secrets(config) -> bool:
    """ตรวจสอบว่ามีไฟล์ client_secrets.json หรือไม่"""
    secrets_path = Path(config.youtube.oauth.client_secrets_file)
    
    if not secrets_path.exists():
        print_error(f"ไม่พบไฟล์ client_secrets.json: {secrets_path}")
        console.print()
        console.print(Panel(
            "[yellow]วิธีสร้างไฟล์ client_secrets.json:[/yellow]\n\n"
            "1. ไปที่ [link=https://console.cloud.google.com/]Google Cloud Console[/link]\n"
            "2. สร้างหรือเลือก Project\n"
            "3. เปิดใช้งาน YouTube Data API v3 และ YouTube Analytics API\n"
            "4. ไปที่ 'APIs & Services' > 'Credentials'\n"
            "5. สร้าง 'OAuth 2.0 Client ID' (ประเภท Desktop app)\n"
            "6. ดาวน์โหลดไฟล์ JSON และบันทึกเป็น:\n"
            f"   [cyan]{secrets_path}[/cyan]\n\n"
            "[dim]หมายเหตุ: ต้องตั้งค่า OAuth consent screen ก่อน[/dim]",
            title="📋 คำแนะนำ",
            border_style="yellow"
        ))
        return False
    
    print_success(f"พบไฟล์ client_secrets.json: {secrets_path}")
    return True


def check_token(config) -> bool:
    """ตรวจสอบว่ามี token หรือไม่"""
    token_path = Path(config.youtube.oauth.token_file)
    
    if not token_path.exists():
        print_warning(f"ไม่พบไฟล์ token: {token_path}")
        print_info("ต้องทำ OAuth flow เพื่อสร้าง token")
        return False
    
    print_success(f"พบไฟล์ token: {token_path}")
    return True


def display_auth_status(auth: YouTubeAuth) -> None:
    """แสดงสถานะ authentication"""
    status = auth.get_auth_status()
    
    table = Table(title="🔐 สถานะ Authentication", show_header=True)
    table.add_column("รายการ", style="cyan")
    table.add_column("ค่า", style="green")
    
    table.add_row("Authenticated", "✅ ใช่" if status.is_authenticated else "❌ ไม่")
    table.add_row("Token Valid", "✅ ใช่" if status.has_valid_token else "❌ ไม่")
    table.add_row("Token Expiry", status.token_expiry or "-")
    table.add_row("Channel ID", status.channel_id or "-")
    table.add_row("Channel Name", status.channel_title or "-")
    
    console.print(table)
    
    if status.scopes:
        console.print()
        console.print("[bold]📜 Scopes ที่ได้รับ:[/bold]")
        for scope in status.scopes:
            console.print(f"  • {scope}")
    
    if status.error:
        console.print()
        print_error(status.error)


def test_youtube_api(auth: YouTubeAuth) -> bool:
    """ทดสอบ YouTube Data API"""
    console.print()
    console.print("[bold]🧪 ทดสอบ YouTube Data API...[/bold]")
    
    try:
        youtube = auth.get_youtube_service()
        if not youtube:
            print_error("ไม่สามารถสร้าง YouTube service")
            return False
        
        # ทดสอบดึงข้อมูล channel
        response = youtube.channels().list(
            part="snippet,statistics",
            mine=True,
        ).execute()
        
        if response.get("items"):
            channel = response["items"][0]
            snippet = channel["snippet"]
            stats = channel["statistics"]
            
            table = Table(title="📺 ข้อมูล Channel", show_header=True)
            table.add_column("รายการ", style="cyan")
            table.add_column("ค่า", style="green")
            
            table.add_row("ชื่อ Channel", snippet.get("title", "-"))
            table.add_row("คำอธิบาย", snippet.get("description", "-")[:50] + "...")
            table.add_row("จำนวน Subscribers", f"{int(stats.get('subscriberCount', 0)):,}")
            table.add_row("จำนวนวิดีโอ", f"{int(stats.get('videoCount', 0)):,}")
            table.add_row("จำนวน Views ทั้งหมด", f"{int(stats.get('viewCount', 0)):,}")
            
            console.print(table)
            print_success("YouTube Data API ทำงานปกติ")
            return True
        else:
            print_error("ไม่พบข้อมูล channel")
            return False
            
    except Exception as e:
        print_error(f"YouTube Data API error: {e}")
        return False


def test_analytics_api(auth: YouTubeAuth) -> bool:
    """ทดสอบ YouTube Analytics API"""
    console.print()
    console.print("[bold]🧪 ทดสอบ YouTube Analytics API...[/bold]")
    
    try:
        analytics = auth.get_analytics_service()
        if not analytics:
            print_error("ไม่สามารถสร้าง Analytics service")
            return False
        
        # ดึง channel ID
        youtube = auth.get_youtube_service()
        channel_response = youtube.channels().list(
            part="id",
            mine=True,
        ).execute()
        
        if not channel_response.get("items"):
            print_error("ไม่พบ channel")
            return False
        
        channel_id = channel_response["items"][0]["id"]
        
        # ทดสอบดึง analytics
        from datetime import date, timedelta
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=7)
        
        response = analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date.strftime("%Y-%m-%d"),
            endDate=end_date.strftime("%Y-%m-%d"),
            metrics="views,estimatedMinutesWatched,subscribersGained",
        ).execute()
        
        if "rows" in response:
            row = response["rows"][0] if response["rows"] else [0, 0, 0]
            
            table = Table(title=f"📊 Analytics (7 วันล่าสุด)", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("ค่า", style="green")
            
            table.add_row("Views", f"{int(row[0]):,}")
            table.add_row("Watch Time (นาที)", f"{float(row[1]):,.1f}")
            table.add_row("Subscribers Gained", f"{int(row[2]):,}")
            
            console.print(table)
        
        print_success("YouTube Analytics API ทำงานปกติ")
        return True
        
    except Exception as e:
        print_error(f"YouTube Analytics API error: {e}")
        print_info("หมายเหตุ: Analytics API อาจต้องใช้เวลาสักครู่หลังจากเปิดใช้งาน")
        return False


@click.command()
@click.option("--authenticate", is_flag=True, help="ทำ OAuth flow เพื่อ authenticate")
@click.option("--headless", is_flag=True, help="ใช้ console-based OAuth flow")
@click.option("--revoke", is_flag=True, help="ยกเลิก token ที่มีอยู่")
@click.option("--test", is_flag=True, help="ทดสอบ API calls")
@click.option("--config", default="configs/default.yaml", help="path ไปยังไฟล์ config")
def main(
    authenticate: bool,
    headless: bool,
    revoke: bool,
    test: bool,
    config: str,
):
    """
    ตรวจสอบและจัดการ YouTube API authentication
    
    ตัวอย่าง:
        python scripts/validate_youtube_auth.py
        python scripts/validate_youtube_auth.py --authenticate
        python scripts/validate_youtube_auth.py --test
    """
    print_banner(
        "YouTube Content Assistant",
        "YouTube API Authentication Validator"
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
    
    console.print()
    
    # ตรวจสอบ client secrets
    if not check_client_secrets(cfg):
        sys.exit(1)
    
    # สร้าง auth instance
    auth = YouTubeAuth(
        client_secrets_file=cfg.youtube.oauth.client_secrets_file,
        token_file=cfg.youtube.oauth.token_file,
        scopes=cfg.youtube.oauth.scopes,
    )
    
    # Revoke token
    if revoke:
        console.print()
        if Confirm.ask("ยืนยันการยกเลิก token?"):
            if auth.revoke_token():
                print_success("ยกเลิก token สำเร็จ")
            else:
                print_error("ไม่สามารถยกเลิก token")
        return
    
    # ตรวจสอบ token
    console.print()
    has_token = check_token(cfg)
    
    # Authenticate
    if authenticate or not has_token:
        console.print()
        
        if has_token:
            if not Confirm.ask("มี token อยู่แล้ว ต้องการ authenticate ใหม่?"):
                pass
            else:
                authenticate = True
        
        if authenticate or not has_token:
            console.print(Panel(
                "กำลังเริ่ม OAuth flow...\n\n"
                "เบราว์เซอร์จะเปิดขึ้นเพื่อให้คุณ login และอนุญาตสิทธิ์\n"
                "หลังจากอนุญาตแล้ว ให้กลับมาที่ terminal นี้",
                title="🔐 OAuth Authentication",
                border_style="blue"
            ))
            
            if auth.authenticate(headless=headless):
                print_success("Authentication สำเร็จ!")
            else:
                print_error("Authentication ล้มเหลว")
                sys.exit(1)
    
    # แสดงสถานะ
    console.print()
    display_auth_status(auth)
    
    # ทดสอบ API
    if test or authenticate:
        youtube_ok = test_youtube_api(auth)
        analytics_ok = test_analytics_api(auth)
        
        console.print()
        if youtube_ok and analytics_ok:
            console.print(Panel(
                "[green]✓ ระบบพร้อมใช้งาน![/green]\n\n"
                "ขั้นตอนถัดไป:\n"
                "  • ดึงข้อมูลวิดีโอ: python scripts/fetch_youtube.py\n"
                "  • รัน dashboard: streamlit run dashboard/app.py",
                title="✅ สำเร็จ",
                border_style="green"
            ))
        else:
            console.print(Panel(
                "[yellow]⚠ บาง API อาจยังไม่พร้อมใช้งาน[/yellow]\n\n"
                "ตรวจสอบ:\n"
                "  • เปิดใช้งาน API ใน Google Cloud Console แล้วหรือยัง\n"
                "  • OAuth consent screen ตั้งค่าถูกต้องหรือไม่\n"
                "  • Scopes ที่ขอครบถ้วนหรือไม่",
                title="⚠️ คำเตือน",
                border_style="yellow"
            ))


if __name__ == "__main__":
    main()
