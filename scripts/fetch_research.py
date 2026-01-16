#!/usr/bin/env python3
"""
Fetch Research Script - ดึงข้อมูล Anime Research จากแหล่งต่างๆ

รองรับแหล่งข้อมูล:
- AniList GraphQL API: trending, seasonal, top anime
- Anime News Network RSS: ข่าวสารอนิเมะ
- RSS feeds อื่นๆ ที่อยู่ใน whitelist

การใช้งาน:
    # ดึงทุกแหล่ง (7 วันล่าสุด)
    python scripts/fetch_research.py --all
    
    # ดึงเฉพาะ AniList
    python scripts/fetch_research.py --anilist
    
    # ดึงเฉพาะ RSS feeds
    python scripts/fetch_research.py --rss --days 14
    
    # ดึงแบบ incremental (ตั้งแต่วันที่ล่าสุดที่มีในฐานข้อมูล)
    python scripts/fetch_research.py --all --incremental
    
    # ระบุช่วงวันที่
    python scripts/fetch_research.py --all --start 2024-01-01 --end 2024-01-31
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, List

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.db.connection import init_db, session_scope
from src.db.repository import ResearchItemRepository, RunLogRepository
from src.anime.anilist import AniListClient
from src.anime.rss_parser import RSSFeedParser
from src.anime.entity_linker import EntityLinker
from src.utils.config import load_config
from src.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="ดึงข้อมูล Anime Research จากแหล่งต่างๆ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:
  %(prog)s --all                    ดึงทุกแหล่ง (7 วันล่าสุด)
  %(prog)s --anilist                ดึงเฉพาะ AniList
  %(prog)s --rss --days 14          ดึง RSS feeds 14 วันล่าสุด
  %(prog)s --all --incremental      ดึงแบบ incremental
  %(prog)s --all --start 2024-01-01 ระบุวันที่เริ่มต้น
        """
    )
    
    # Source selection
    source_group = parser.add_argument_group("แหล่งข้อมูล")
    source_group.add_argument(
        "--all",
        action="store_true",
        help="ดึงจากทุกแหล่ง"
    )
    source_group.add_argument(
        "--anilist",
        action="store_true",
        help="ดึงจาก AniList API (trending, seasonal, top)"
    )
    source_group.add_argument(
        "--rss",
        action="store_true",
        help="ดึงจาก RSS feeds (ANN, Crunchyroll, MAL)"
    )
    source_group.add_argument(
        "--rss-source",
        type=str,
        help="ดึงจาก RSS source เฉพาะ (เช่น ann, crunchyroll)"
    )
    
    # Date range
    date_group = parser.add_argument_group("ช่วงเวลา")
    date_group.add_argument(
        "--days",
        type=int,
        default=7,
        help="จำนวนวันย้อนหลัง (default: 7)"
    )
    date_group.add_argument(
        "--start",
        type=str,
        help="วันที่เริ่มต้น (YYYY-MM-DD)"
    )
    date_group.add_argument(
        "--end",
        type=str,
        help="วันที่สิ้นสุด (YYYY-MM-DD)"
    )
    date_group.add_argument(
        "--incremental",
        action="store_true",
        default=True,
        help="ดึงแบบ incremental จากวันที่ล่าสุดในฐานข้อมูล (default: true)"
    )
    date_group.add_argument(
        "--no-incremental",
        action="store_true",
        help="ไม่ใช้ incremental mode"
    )
    
    # Options
    options_group = parser.add_argument_group("ตัวเลือก")
    options_group.add_argument(
        "--limit",
        type=int,
        default=50,
        help="จำนวนรายการสูงสุดต่อแหล่ง (default: 50)"
    )
    options_group.add_argument(
        "--link-entities",
        action="store_true",
        help="ทำ entity linking สำหรับข่าว RSS"
    )
    options_group.add_argument(
        "--dry-run",
        action="store_true",
        help="แสดงผลลัพธ์โดยไม่บันทึกลงฐานข้อมูล"
    )
    options_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="แสดงรายละเอียดเพิ่มเติม"
    )
    
    return parser.parse_args()


def get_last_research_date(session, source: str) -> Optional[date]:
    """ดึงวันที่ล่าสุดที่มีข้อมูลในฐานข้อมูล"""
    from sqlalchemy import select, func
    from src.db.models import ResearchItem
    
    stmt = (
        select(func.max(ResearchItem.published_at))
        .where(ResearchItem.source == source)
    )
    result = session.execute(stmt).scalar()
    
    if result:
        return result.date() if isinstance(result, datetime) else result
    
    return None


def fetch_anilist_data(
    session,
    limit: int = 50,
    dry_run: bool = False,
    verbose: bool = False
) -> int:
    """ดึงข้อมูลจาก AniList API"""
    console.print("\n[bold cyan]📊 กำลังดึงข้อมูลจาก AniList API...[/bold cyan]")
    
    client = AniListClient()
    repo = ResearchItemRepository(session)
    items_saved = 0
    
    # Get current season
    year, season = client.get_current_season()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # 1. Trending Anime
        task = progress.add_task("ดึง Trending Anime...", total=None)
        trending = client.get_trending_anime(limit=min(limit, 20))
        progress.update(task, completed=True)
        
        for anime in trending:
            if not dry_run:
                # Check if already exists
                existing = repo.get_by_source_url(f"https://anilist.co/anime/{anime.anilist_id}")
                if existing:
                    continue
                
                repo.create(
                    title=anime.get_best_title(),
                    source="anilist_trending",
                    source_url=anime.site_url,
                    summary=anime.description[:500] if anime.description else None,
                    content=anime.description,
                    keywords={"genres": anime.genres, "tags": [t["name"] for t in anime.tags]},
                    entities={"anime_titles": [anime.title_romaji, anime.title_english, anime.title_native]},
                    linked_series=anime.to_dict(),
                    category="anime",
                    item_type="trending",
                    trend_score=anime.trending / 1000 if anime.trending else 0.5,
                    reliability_score=1.0,
                    anilist_id=anime.anilist_id,
                    mal_id=anime.mal_id,
                    is_actionable=True,
                    is_linked=True,
                    published_at=datetime.now(),
                )
                items_saved += 1
        
        console.print(f"  [green]✅ Trending: {len(trending)} รายการ[/green]")
        
        # 2. Seasonal Anime
        task = progress.add_task(f"ดึง Seasonal Anime ({season} {year})...", total=None)
        seasonal = client.get_seasonal_anime(year, season, limit=min(limit, 30))
        progress.update(task, completed=True)
        
        for anime in seasonal:
            if not dry_run:
                existing = repo.get_by_source_url(f"https://anilist.co/anime/{anime.anilist_id}")
                if existing:
                    continue
                
                repo.create(
                    title=anime.get_best_title(),
                    source="anilist_seasonal",
                    source_url=anime.site_url,
                    summary=anime.description[:500] if anime.description else None,
                    content=anime.description,
                    keywords={"genres": anime.genres, "season": season, "year": year},
                    entities={"anime_titles": [anime.title_romaji, anime.title_english, anime.title_native]},
                    linked_series=anime.to_dict(),
                    category="anime",
                    item_type="seasonal",
                    trend_score=anime.popularity / 100000 if anime.popularity else 0.3,
                    reliability_score=1.0,
                    anilist_id=anime.anilist_id,
                    mal_id=anime.mal_id,
                    is_actionable=True,
                    is_linked=True,
                    published_at=datetime.now(),
                )
                items_saved += 1
        
        console.print(f"  [green]✅ Seasonal ({season} {year}): {len(seasonal)} รายการ[/green]")
        
        # 3. Top Anime by Score
        task = progress.add_task("ดึง Top Anime...", total=None)
        top_anime = client.get_top_anime(sort_by="SCORE_DESC", limit=min(limit, 20))
        progress.update(task, completed=True)
        
        for anime in top_anime:
            if not dry_run:
                existing = repo.get_by_source_url(f"https://anilist.co/anime/{anime.anilist_id}")
                if existing:
                    continue
                
                repo.create(
                    title=anime.get_best_title(),
                    source="anilist_top",
                    source_url=anime.site_url,
                    summary=anime.description[:500] if anime.description else None,
                    content=anime.description,
                    keywords={"genres": anime.genres, "score": anime.average_score},
                    entities={"anime_titles": [anime.title_romaji, anime.title_english, anime.title_native]},
                    linked_series=anime.to_dict(),
                    category="anime",
                    item_type="top_rated",
                    trend_score=anime.average_score / 100 if anime.average_score else 0.5,
                    reliability_score=1.0,
                    anilist_id=anime.anilist_id,
                    mal_id=anime.mal_id,
                    is_actionable=True,
                    is_linked=True,
                    published_at=datetime.now(),
                )
                items_saved += 1
        
        console.print(f"  [green]✅ Top Anime: {len(top_anime)} รายการ[/green]")
    
    if not dry_run:
        session.commit()
    
    return items_saved


def fetch_rss_data(
    session,
    days: int = 7,
    sources: Optional[List[str]] = None,
    limit: int = 50,
    link_entities: bool = False,
    dry_run: bool = False,
    verbose: bool = False
) -> int:
    """ดึงข้อมูลจาก RSS feeds"""
    console.print("\n[bold cyan]📰 กำลังดึงข้อมูลจาก RSS feeds...[/bold cyan]")
    
    parser = RSSFeedParser()
    repo = ResearchItemRepository(session)
    linker = EntityLinker() if link_entities else None
    items_saved = 0
    
    # Get available sources
    available_sources = parser.get_available_sources()
    
    if sources:
        # Filter to requested sources
        source_keys = [s for s in sources if s in available_sources]
    else:
        source_keys = list(available_sources.keys())
    
    if not source_keys:
        console.print("[yellow]⚠️ ไม่พบแหล่ง RSS ที่ระบุ[/yellow]")
        return 0
    
    # Fetch from each source
    for source_key in source_keys:
        source_info = available_sources[source_key]
        console.print(f"\n  [cyan]📡 {source_info['name']}...[/cyan]")
        
        items = parser.fetch_source(source_key, days=days, limit=limit)
        
        for item in items:
            if not dry_run:
                # Check if already exists by URL
                existing = repo.get_by_source_url(item.link)
                if existing:
                    continue
                
                # Extract entities if requested
                entities = None
                linked_series = None
                is_linked = False
                
                if linker and item.raw_text:
                    linked = linker.extract_and_link(item.title + " " + (item.raw_text or ""))
                    if linked:
                        entities = {"anime_titles": [e.original_text for e in linked]}
                        linked_series = [e.to_dict() for e in linked if e.anilist_id]
                        is_linked = bool(linked_series)
                
                repo.create(
                    title=item.title,
                    source=f"rss_{source_key}",
                    source_url=item.link,
                    summary=item.description,
                    content=item.raw_text,
                    keywords={"categories": item.categories},
                    entities=entities,
                    linked_series=linked_series,
                    category="news",
                    item_type="news",
                    trend_score=0.5,
                    reliability_score=item.reliability_score,
                    is_actionable=True,
                    is_linked=is_linked,
                    published_at=item.published_at,
                )
                items_saved += 1
        
        console.print(f"    [green]✅ {len(items)} รายการ[/green]")
    
    if not dry_run:
        session.commit()
    
    return items_saved


def main():
    """Main function"""
    args = parse_args()
    
    # Validate arguments
    if not any([args.all, args.anilist, args.rss, args.rss_source]):
        console.print("[yellow]⚠️ กรุณาระบุแหล่งข้อมูล (--all, --anilist, --rss, --rss-source)[/yellow]")
        return 1
    
    # Load config and init DB
    config = load_config()
    init_db(config.database.path)
    
    console.print("[bold]🔬 Anime Research Fetcher[/bold]")
    console.print(f"[dim]วันที่: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
    
    if args.dry_run:
        console.print("[yellow]⚠️ Dry-run mode: ไม่บันทึกลงฐานข้อมูล[/yellow]")
    
    total_items = 0
    
    with session_scope() as session:
        run_repo = RunLogRepository(session)
        
        # Create run log
        run_log = run_repo.create_run(
            run_type="fetch_research",
            triggered_by="cli",
        )
        
        try:
            # Determine date range
            days = args.days
            
            if args.start:
                start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
                if args.end:
                    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
                else:
                    end_date = date.today()
                days = (end_date - start_date).days
            
            # Fetch AniList data
            if args.all or args.anilist:
                anilist_items = fetch_anilist_data(
                    session,
                    limit=args.limit,
                    dry_run=args.dry_run,
                    verbose=args.verbose,
                )
                total_items += anilist_items
            
            # Fetch RSS data
            if args.all or args.rss or args.rss_source:
                sources = [args.rss_source] if args.rss_source else None
                rss_items = fetch_rss_data(
                    session,
                    days=days,
                    sources=sources,
                    limit=args.limit,
                    link_entities=args.link_entities,
                    dry_run=args.dry_run,
                    verbose=args.verbose,
                )
                total_items += rss_items
            
            # Update run log
            if not args.dry_run:
                run_repo.complete_run(
                    run_log.id,
                    status="completed",
                    items_processed=total_items,
                    items_succeeded=total_items,
                    items_failed=0,
                )
            
            console.print(f"\n[bold green]✅ ดึงข้อมูลสำเร็จ: {total_items} รายการ[/bold green]")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาด: {e}")
            console.print(f"[bold red]❌ เกิดข้อผิดพลาด: {e}[/bold red]")
            
            if not args.dry_run:
                run_repo.fail_run(run_log.id, str(e))
            
            return 1
    
    return 0


# Add helper method to repository
def _add_get_by_source_url_method():
    """เพิ่ม method get_by_source_url ให้ ResearchItemRepository"""
    from sqlalchemy import select
    from src.db.models import ResearchItem
    
    def get_by_source_url(self, url: str):
        stmt = select(ResearchItem).where(ResearchItem.source_url == url)
        return self.session.scalar(stmt)
    
    ResearchItemRepository.get_by_source_url = get_by_source_url


_add_get_by_source_url_method()


if __name__ == "__main__":
    sys.exit(main())
