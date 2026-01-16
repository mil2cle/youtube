#!/usr/bin/env python3
"""
Smoke Test Research Script - ทดสอบความทนทานของ Research Module

ทดสอบว่า:
1. RSS parser สามารถดึงข้อมูลได้อย่างน้อย 1 แหล่ง แม้บางแหล่งจะล้มเหลว
2. ระบบ fail-open ทำงานถูกต้อง (ข้ามแหล่งที่ล้มเหลวและดำเนินการต่อ)
3. แหล่งที่ถูก disable จะถูกข้ามอย่างถูกต้อง

การใช้งาน:
    python scripts/smoke_test_research.py
    python scripts/smoke_test_research.py --verbose
    python scripts/smoke_test_research.py --simulate-failure
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table

console = Console()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="ทดสอบความทนทานของ Research Module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="แสดงรายละเอียดเพิ่มเติม"
    )
    parser.add_argument(
        "--simulate-failure",
        action="store_true",
        help="จำลองการล้มเหลวของ RSS feed เพื่อทดสอบ fail-open"
    )
    
    return parser.parse_args()


def test_rss_parser_import() -> Dict[str, Any]:
    """ทดสอบการ import RSS parser"""
    result = {
        "name": "RSS Parser Import",
        "passed": False,
        "message": "",
    }
    
    try:
        from src.anime.rss_parser import RSSFeedParser, RSS_SOURCES, RSSItem
        result["passed"] = True
        result["message"] = "นำเข้า RSSFeedParser สำเร็จ"
    except ImportError as e:
        result["message"] = f"ไม่สามารถนำเข้า RSSFeedParser: {e}"
    
    return result


def test_rss_sources_config() -> Dict[str, Any]:
    """ทดสอบการตั้งค่า RSS sources"""
    result = {
        "name": "RSS Sources Configuration",
        "passed": False,
        "message": "",
        "details": {},
    }
    
    try:
        from src.anime.rss_parser import RSS_SOURCES
        
        enabled_count = 0
        disabled_count = 0
        
        for key, source in RSS_SOURCES.items():
            is_enabled = source.get("enabled", True)
            if is_enabled:
                enabled_count += 1
            else:
                disabled_count += 1
            result["details"][key] = {
                "name": source.get("name", key),
                "enabled": is_enabled,
            }
        
        if enabled_count > 0:
            result["passed"] = True
            result["message"] = f"มี {enabled_count} แหล่งที่เปิดใช้งาน, {disabled_count} แหล่งที่ปิดใช้งาน"
        else:
            result["message"] = "ไม่มีแหล่ง RSS ที่เปิดใช้งาน"
    
    except Exception as e:
        result["message"] = f"เกิดข้อผิดพลาด: {e}"
    
    return result


def test_crunchyroll_disabled() -> Dict[str, Any]:
    """ทดสอบว่า Crunchyroll RSS ถูก disable"""
    result = {
        "name": "Crunchyroll RSS Disabled",
        "passed": False,
        "message": "",
    }
    
    try:
        from src.anime.rss_parser import RSS_SOURCES
        
        crunchyroll = RSS_SOURCES.get("crunchyroll", {})
        is_enabled = crunchyroll.get("enabled", True)
        
        if not is_enabled:
            result["passed"] = True
            result["message"] = "Crunchyroll RSS ถูกปิดการใช้งานอย่างถูกต้อง"
        else:
            result["message"] = "Crunchyroll RSS ยังเปิดใช้งานอยู่ (ควรปิด)"
    
    except Exception as e:
        result["message"] = f"เกิดข้อผิดพลาด: {e}"
    
    return result


def test_fetch_at_least_one_source() -> Dict[str, Any]:
    """ทดสอบว่าสามารถดึงข้อมูลได้อย่างน้อย 1 แหล่ง"""
    result = {
        "name": "Fetch At Least One Source",
        "passed": False,
        "message": "",
        "stats": {},
    }
    
    try:
        from src.anime.rss_parser import RSSFeedParser
        
        parser = RSSFeedParser(timeout=15)
        items, stats = parser.fetch_all_sources(days=7)
        
        result["stats"] = stats
        
        if stats["successful_sources"] > 0:
            result["passed"] = True
            result["message"] = f"ดึงข้อมูลสำเร็จจาก {stats['successful_sources']} แหล่ง ({len(items)} รายการ)"
        else:
            result["message"] = "ไม่สามารถดึงข้อมูลจากแหล่งใดได้เลย"
    
    except Exception as e:
        result["message"] = f"เกิดข้อผิดพลาด: {type(e).__name__}: {e}"
    
    return result


def test_fail_open_behavior(simulate_failure: bool = False) -> Dict[str, Any]:
    """ทดสอบพฤติกรรม fail-open"""
    result = {
        "name": "Fail-Open Behavior",
        "passed": False,
        "message": "",
    }
    
    try:
        from src.anime.rss_parser import RSSFeedParser, RSS_SOURCES
        
        parser = RSSFeedParser(timeout=15)
        
        if simulate_failure:
            # เพิ่มแหล่งที่จะล้มเหลวแน่นอน
            parser.add_source(
                key="fake_broken_feed",
                name="Fake Broken Feed (ทดสอบ)",
                url="https://this-url-does-not-exist-12345.com/rss.xml",
                reliability_score=0.5,
                category="test",
            )
            # อัพเดท enabled flag
            parser.sources["fake_broken_feed"]["enabled"] = True
        
        # ดึงข้อมูลจากทุกแหล่ง
        items, stats = parser.fetch_all_sources(days=7)
        
        # ถ้ามีแหล่งที่ล้มเหลว แต่ยังดึงข้อมูลจากแหล่งอื่นได้ = fail-open ทำงาน
        if stats["failed_sources"] > 0 and stats["successful_sources"] > 0:
            result["passed"] = True
            result["message"] = f"Fail-open ทำงานถูกต้อง: {stats['failed_sources']} แหล่งล้มเหลว แต่ดึงจาก {stats['successful_sources']} แหล่งสำเร็จ"
        elif stats["failed_sources"] == 0 and stats["successful_sources"] > 0:
            result["passed"] = True
            result["message"] = f"ทุกแหล่งทำงานปกติ ({stats['successful_sources']} แหล่ง) - ไม่มีการล้มเหลวให้ทดสอบ"
        else:
            result["message"] = f"ไม่สามารถยืนยัน fail-open: successful={stats['successful_sources']}, failed={stats['failed_sources']}"
    
    except Exception as e:
        result["message"] = f"เกิดข้อผิดพลาด: {type(e).__name__}: {e}"
    
    return result


def test_disabled_source_skipped() -> Dict[str, Any]:
    """ทดสอบว่าแหล่งที่ disabled จะถูกข้าม"""
    result = {
        "name": "Disabled Source Skipped",
        "passed": False,
        "message": "",
    }
    
    try:
        from src.anime.rss_parser import RSSFeedParser
        
        parser = RSSFeedParser(timeout=15)
        
        # ลองดึงจาก crunchyroll โดยตรง (ควรถูกข้าม)
        items = parser.fetch_source("crunchyroll", days=7)
        
        if len(items) == 0:
            result["passed"] = True
            result["message"] = "แหล่งที่ disabled ถูกข้ามอย่างถูกต้อง (ไม่มีข้อมูลถูกดึง)"
        else:
            result["message"] = f"แหล่งที่ disabled ไม่ถูกข้าม (ดึงได้ {len(items)} รายการ)"
    
    except Exception as e:
        result["message"] = f"เกิดข้อผิดพลาด: {type(e).__name__}: {e}"
    
    return result


def run_all_tests(verbose: bool = False, simulate_failure: bool = False) -> List[Dict[str, Any]]:
    """รันการทดสอบทั้งหมด"""
    tests = [
        test_rss_parser_import,
        test_rss_sources_config,
        test_crunchyroll_disabled,
        test_disabled_source_skipped,
        lambda: test_fail_open_behavior(simulate_failure),
        test_fetch_at_least_one_source,
    ]
    
    results = []
    
    for test_func in tests:
        if verbose:
            console.print(f"\n[cyan]🔍 กำลังทดสอบ: {test_func.__name__ if hasattr(test_func, '__name__') else 'anonymous'}...[/cyan]")
        
        result = test_func()
        results.append(result)
        
        if verbose:
            status = "[green]✅ ผ่าน[/green]" if result["passed"] else "[red]❌ ไม่ผ่าน[/red]"
            console.print(f"   {status}: {result['message']}")
    
    return results


def main():
    """Main function"""
    args = parse_args()
    
    console.print("=" * 60)
    console.print("[bold]  YouTube Content Assistant[/bold]")
    console.print("[bold]  Smoke Test Research Script[/bold]")
    console.print("=" * 60)
    
    if args.simulate_failure:
        console.print("[yellow]⚠️ โหมดจำลองการล้มเหลว: เพิ่มแหล่ง RSS ที่จะล้มเหลวเพื่อทดสอบ fail-open[/yellow]")
    
    console.print("\n[cyan]🔍 กำลังทดสอบระบบ...[/cyan]")
    
    results = run_all_tests(
        verbose=args.verbose,
        simulate_failure=args.simulate_failure,
    )
    
    # แสดงผลลัพธ์ในตาราง
    console.print("\n")
    table = Table(title="📋 ผลการทดสอบ Smoke Test Research")
    table.add_column("หมวด", style="cyan")
    table.add_column("รายการทดสอบ", style="white")
    table.add_column("ผลลัพธ์", style="white")
    
    passed_count = 0
    failed_count = 0
    
    for result in results:
        status = "✅ ผ่าน" if result["passed"] else "❌ ไม่ผ่าน"
        table.add_row(
            "Research Module",
            result["name"],
            status,
        )
        
        if result["passed"]:
            passed_count += 1
        else:
            failed_count += 1
    
    console.print(table)
    
    # สรุปผล
    console.print("")
    if failed_count == 0:
        console.print("[green]╭" + "─" * 58 + "╮[/green]")
        console.print("[green]│[/green] [bold green]✅ Smoke Test ผ่านทั้งหมด![/bold green]" + " " * 32 + "[green]│[/green]")
        console.print("[green]│[/green]" + " " * 58 + "[green]│[/green]")
        console.print(f"[green]│[/green]  ผ่าน: {passed_count} รายการ" + " " * (47 - len(str(passed_count))) + "[green]│[/green]")
        console.print("[green]│[/green]  ระบบ Research Module พร้อมใช้งาน" + " " * 21 + "[green]│[/green]")
        console.print("[green]╰" + "─" * 58 + "╯[/green]")
        return 0
    else:
        console.print("[red]╭" + "─" * 58 + "╮[/red]")
        console.print("[red]│[/red] [bold red]❌ Smoke Test ไม่ผ่านบางรายการ[/bold red]" + " " * 24 + "[red]│[/red]")
        console.print("[red]│[/red]" + " " * 58 + "[red]│[/red]")
        console.print(f"[red]│[/red]  ผ่าน: {passed_count}, ไม่ผ่าน: {failed_count}" + " " * (40 - len(str(passed_count)) - len(str(failed_count))) + "[red]│[/red]")
        console.print("[red]│[/red]  กรุณาตรวจสอบรายการที่ไม่ผ่าน" + " " * 25 + "[red]│[/red]")
        console.print("[red]╰" + "─" * 58 + "╯[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
