#!/usr/bin/env python3
"""
Entity Linker Script - Normalize ชื่ออนิเมะและ map กับ series

ใช้สำหรับ:
- Link ชื่ออนิเมะกับ AniList ID
- อัพเดท research_items ที่ยังไม่ได้ link
- ค้นหาและ verify ชื่ออนิเมะ

การใช้งาน:
    # Link ชื่อเดียว
    python scripts/entity_linker.py --link "Attack on Titan"
    
    # Link หลายชื่อ
    python scripts/entity_linker.py --link "AOT" "Demon Slayer" "One Piece"
    
    # อัพเดท research_items ที่ยังไม่ได้ link
    python scripts/entity_linker.py --update-db
    
    # ค้นหาอนิเมะ
    python scripts/entity_linker.py --search "Frieren"
    
    # ดู aliases ที่รองรับ
    python scripts/entity_linker.py --list-aliases
    
    # เพิ่ม alias ใหม่
    python scripts/entity_linker.py --add-alias "bnha" "Boku no Hero Academia"
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.db.connection import init_db, session_scope
from src.db.repository import ResearchItemRepository
from src.anime.anilist import AniListClient
from src.anime.entity_linker import EntityLinker, LinkedEntity
from src.utils.config import load_config
from src.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Normalize ชื่ออนิเมะและ map กับ series",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:
  %(prog)s --link "Attack on Titan"       Link ชื่อเดียว
  %(prog)s --link "AOT" "JJK"             Link หลายชื่อ
  %(prog)s --update-db                    อัพเดท research_items
  %(prog)s --search "Frieren"             ค้นหาอนิเมะ
  %(prog)s --list-aliases                 ดู aliases ทั้งหมด
        """
    )
    
    # Actions
    action_group = parser.add_argument_group("การทำงาน")
    action_group.add_argument(
        "--link",
        nargs="+",
        metavar="TITLE",
        help="Link ชื่ออนิเมะกับ AniList"
    )
    action_group.add_argument(
        "--search",
        type=str,
        metavar="QUERY",
        help="ค้นหาอนิเมะใน AniList"
    )
    action_group.add_argument(
        "--update-db",
        action="store_true",
        help="อัพเดท research_items ที่ยังไม่ได้ link"
    )
    action_group.add_argument(
        "--extract",
        type=str,
        metavar="TEXT",
        help="ดึงชื่ออนิเมะจากข้อความ"
    )
    
    # Alias management
    alias_group = parser.add_argument_group("จัดการ Aliases")
    alias_group.add_argument(
        "--list-aliases",
        action="store_true",
        help="แสดงรายการ aliases ทั้งหมด"
    )
    alias_group.add_argument(
        "--add-alias",
        nargs=2,
        metavar=("ALIAS", "FULL_NAME"),
        help="เพิ่ม alias ใหม่"
    )
    
    # Cache management
    cache_group = parser.add_argument_group("จัดการ Cache")
    cache_group.add_argument(
        "--clear-cache",
        action="store_true",
        help="ล้าง entity cache"
    )
    cache_group.add_argument(
        "--cache-stats",
        action="store_true",
        help="แสดงสถิติ cache"
    )
    
    # Options
    options_group = parser.add_argument_group("ตัวเลือก")
    options_group.add_argument(
        "--no-cache",
        action="store_true",
        help="ไม่ใช้ cache"
    )
    options_group.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="ค่า confidence ขั้นต่ำ (default: 0.6)"
    )
    options_group.add_argument(
        "--limit",
        type=int,
        default=100,
        help="จำนวนรายการสูงสุดสำหรับ --update-db (default: 100)"
    )
    options_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="แสดงรายละเอียดเพิ่มเติม"
    )
    
    return parser.parse_args()


def display_linked_entity(entity: LinkedEntity, verbose: bool = False):
    """แสดงผลลัพธ์ LinkedEntity"""
    # Color based on confidence
    if entity.confidence >= 0.9:
        color = "green"
    elif entity.confidence >= 0.7:
        color = "yellow"
    else:
        color = "red"
    
    console.print(f"\n[bold]{entity.original_text}[/bold]")
    console.print(f"  ├─ Normalized: [{color}]{entity.normalized_title}[/{color}]")
    console.print(f"  ├─ Confidence: [{color}]{entity.confidence:.2%}[/{color}] ({entity.match_type})")
    
    if entity.anilist_id:
        console.print(f"  ├─ AniList ID: {entity.anilist_id}")
        console.print(f"  └─ URL: https://anilist.co/anime/{entity.anilist_id}")
    else:
        console.print(f"  └─ [dim]ไม่พบใน AniList[/dim]")
    
    if verbose and entity.anime_data:
        data = entity.anime_data
        console.print(f"\n  [dim]รายละเอียด:[/dim]")
        if data.get("genres"):
            console.print(f"    Genres: {', '.join(data['genres'])}")
        if data.get("average_score"):
            console.print(f"    Score: {data['average_score']}/100")
        if data.get("popularity"):
            console.print(f"    Popularity: {data['popularity']:,}")
        if data.get("status"):
            console.print(f"    Status: {data['status']}")


def link_titles(titles: List[str], linker: EntityLinker, verbose: bool = False):
    """Link รายการชื่ออนิเมะ"""
    console.print(f"\n[bold cyan]🔗 กำลัง link {len(titles)} ชื่อ...[/bold cyan]")
    
    results = linker.link_entities(titles)
    
    for entity in results:
        display_linked_entity(entity, verbose)
    
    # Summary
    linked = sum(1 for e in results if e.anilist_id)
    console.print(f"\n[bold]สรุป: Link สำเร็จ {linked}/{len(results)} รายการ[/bold]")


def search_anime(query: str, verbose: bool = False):
    """ค้นหาอนิเมะใน AniList"""
    console.print(f"\n[bold cyan]🔎 กำลังค้นหา: {query}[/bold cyan]")
    
    client = AniListClient()
    results = client.search_anime(query, limit=10)
    
    if not results:
        console.print("[yellow]ไม่พบผลลัพธ์[/yellow]")
        return
    
    table = Table(title="ผลการค้นหา")
    table.add_column("ID", style="cyan")
    table.add_column("Title (EN)", style="green")
    table.add_column("Title (JP)", style="dim")
    table.add_column("Format")
    table.add_column("Score")
    table.add_column("Status")
    
    for anime in results:
        table.add_row(
            str(anime.anilist_id),
            anime.title_english or "-",
            anime.title_romaji or "-",
            anime.format or "-",
            f"{anime.average_score}/100" if anime.average_score else "-",
            anime.status or "-",
        )
    
    console.print(table)


def extract_entities(text: str, linker: EntityLinker, verbose: bool = False):
    """ดึงชื่ออนิเมะจากข้อความ"""
    console.print(f"\n[bold cyan]📝 กำลังดึง entities จากข้อความ...[/bold cyan]")
    console.print(f"[dim]ข้อความ: {text[:200]}{'...' if len(text) > 200 else ''}[/dim]")
    
    # Extract without linking first
    entities = linker.extract_entities(text)
    
    if not entities:
        console.print("[yellow]ไม่พบชื่ออนิเมะในข้อความ[/yellow]")
        return
    
    console.print(f"\n[green]พบ {len(entities)} entities:[/green]")
    for entity in entities:
        console.print(f"  • {entity}")
    
    # Link entities
    console.print("\n[cyan]กำลัง link entities...[/cyan]")
    linked = linker.link_entities(entities)
    
    for entity in linked:
        display_linked_entity(entity, verbose)


def update_database(linker: EntityLinker, limit: int = 100, verbose: bool = False):
    """อัพเดท research_items ที่ยังไม่ได้ link"""
    console.print(f"\n[bold cyan]🔄 กำลังอัพเดท research_items...[/bold cyan]")
    
    config = load_config()
    init_db(config.database.path)
    
    with session_scope() as session:
        repo = ResearchItemRepository(session)
        
        # Get unlinked items
        from sqlalchemy import select
        from src.db.models import ResearchItem
        
        stmt = (
            select(ResearchItem)
            .where(ResearchItem.is_linked == False)
            .where(ResearchItem.source.like("rss_%"))
            .limit(limit)
        )
        
        items = session.scalars(stmt).all()
        
        if not items:
            console.print("[green]✅ ไม่มีรายการที่ต้องอัพเดท[/green]")
            return
        
        console.print(f"[dim]พบ {len(items)} รายการที่ยังไม่ได้ link[/dim]")
        
        updated = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("กำลังอัพเดท...", total=len(items))
            
            for item in items:
                # Extract and link entities from title and content
                text = f"{item.title} {item.content or ''}"
                linked = linker.extract_and_link(text)
                
                if linked:
                    # Update item
                    item.entities = {"anime_titles": [e.original_text for e in linked]}
                    item.linked_series = [e.to_dict() for e in linked if e.anilist_id]
                    item.is_linked = bool(item.linked_series)
                    
                    if item.is_linked:
                        updated += 1
                        if verbose:
                            console.print(f"  [green]✓[/green] {item.title[:50]}...")
                
                progress.advance(task)
        
        session.commit()
        console.print(f"\n[bold green]✅ อัพเดทสำเร็จ: {updated}/{len(items)} รายการ[/bold green]")


def list_aliases(linker: EntityLinker):
    """แสดงรายการ aliases ทั้งหมด"""
    aliases = linker.get_aliases()
    
    table = Table(title="Anime Aliases")
    table.add_column("Alias", style="cyan")
    table.add_column("Full Name", style="green")
    
    for alias, full_name in sorted(aliases.items()):
        table.add_row(alias, full_name)
    
    console.print(table)
    console.print(f"\n[dim]รวม {len(aliases)} aliases[/dim]")


def main():
    """Main function"""
    args = parse_args()
    
    # Create linker
    linker = EntityLinker(min_confidence=args.min_confidence)
    
    # Handle cache operations
    if args.clear_cache:
        linker.clear_cache()
        return 0
    
    if args.cache_stats:
        stats = linker.get_cache_stats()
        console.print("\n[bold]Cache Statistics[/bold]")
        for key, value in stats.items():
            console.print(f"  {key}: {value}")
        return 0
    
    # Handle alias operations
    if args.list_aliases:
        list_aliases(linker)
        return 0
    
    if args.add_alias:
        alias, full_name = args.add_alias
        linker.add_alias(alias, full_name)
        return 0
    
    # Handle main operations
    use_cache = not args.no_cache
    
    if args.link:
        link_titles(args.link, linker, args.verbose)
        return 0
    
    if args.search:
        search_anime(args.search, args.verbose)
        return 0
    
    if args.extract:
        extract_entities(args.extract, linker, args.verbose)
        return 0
    
    if args.update_db:
        update_database(linker, args.limit, args.verbose)
        return 0
    
    # No action specified
    console.print("[yellow]⚠️ กรุณาระบุการทำงาน (--link, --search, --update-db, --extract)[/yellow]")
    console.print("[dim]ใช้ --help เพื่อดูวิธีใช้งาน[/dim]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
