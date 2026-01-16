#!/usr/bin/env python3
"""
Weekly Report - สร้างรายงานสรุปประจำสัปดาห์ภาษาไทย

การใช้งาน:
    # สร้างรายงานสัปดาห์ล่าสุด
    python scripts/report_weekly.py
    
    # ระบุช่วงวันที่
    python scripts/report_weekly.py --start 2024-01-01 --end 2024-01-07
    
    # Export เป็น CSV
    python scripts/report_weekly.py --csv
    
    # ใช้ข้อมูลตัวอย่าง
    python scripts/report_weekly.py --demo
"""

import sys
import os
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

import numpy as np
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import track

from src.utils.config import load_config
from src.utils.logger import setup_logger
from src.db.connection import DatabaseConnection
from src.db.models import Video, DailyMetric, PlaybookRule as PlaybookRuleModel, ResearchItem, RunLog
from src.db.repository import (
    VideoRepository, DailyMetricRepository, PlaybookRuleRepository,
    ResearchItemRepository, RunLogRepository
)
from src.playbook.feature_extractor import FeatureExtractor
from src.playbook.rule_generator import ThaiRuleGenerator

console = Console()
logger = setup_logger(__name__)


def generate_demo_report_data() -> dict:
    """สร้างข้อมูลตัวอย่างสำหรับ demo report"""
    np.random.seed(42)
    
    # Generate video performance data
    videos = []
    for i in range(20):
        videos.append({
            'title': f'วิดีโอตัวอย่าง {i+1}',
            'views': np.random.randint(1000, 50000),
            'likes': np.random.randint(50, 2000),
            'comments': np.random.randint(10, 500),
            'ctr': np.random.uniform(2, 12),
            'avg_view_duration': np.random.uniform(60, 600),
            'published_at': datetime.now() - timedelta(days=np.random.randint(1, 30)),
        })
    
    # Generate playbook rules
    rules = [
        {'name': 'rule_001', 'description': '✅ ใส่ตัวเลขใน title', 'confidence': 0.85, 'priority': 'high'},
        {'name': 'rule_002', 'description': '✅ เผยแพร่ช่วงเย็น (17:00-21:00)', 'confidence': 0.78, 'priority': 'high'},
        {'name': 'rule_003', 'description': '✅ ทำวิดีโอความยาว 8-15 นาที', 'confidence': 0.72, 'priority': 'medium'},
        {'name': 'rule_004', 'description': '✅ ใช้ keywords เชิงบวก', 'confidence': 0.68, 'priority': 'medium'},
        {'name': 'rule_005', 'description': '✅ ใส่ timestamps ใน description', 'confidence': 0.65, 'priority': 'low'},
    ]
    
    # Generate research items
    research = [
        {'title': 'Solo Leveling Season 2', 'source': 'anilist', 'trend_score': 95},
        {'title': 'Frieren: Beyond Journey\'s End', 'source': 'anilist', 'trend_score': 92},
        {'title': 'Oshi no Ko Season 2', 'source': 'ann_rss', 'trend_score': 88},
        {'title': 'Jujutsu Kaisen', 'source': 'anilist', 'trend_score': 85},
        {'title': 'Demon Slayer', 'source': 'anilist', 'trend_score': 82},
    ]
    
    return {
        'videos': videos,
        'rules': rules,
        'research': research,
        'period': {
            'start': datetime.now() - timedelta(days=7),
            'end': datetime.now(),
        },
        'summary': {
            'total_views': sum(v['views'] for v in videos),
            'total_likes': sum(v['likes'] for v in videos),
            'total_comments': sum(v['comments'] for v in videos),
            'avg_ctr': np.mean([v['ctr'] for v in videos]),
            'avg_view_duration': np.mean([v['avg_view_duration'] for v in videos]),
            'videos_published': len([v for v in videos if v['published_at'] > datetime.now() - timedelta(days=7)]),
        }
    }


def load_report_data(
    db: DatabaseConnection,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """โหลดข้อมูลจากฐานข้อมูลสำหรับรายงาน"""
    console.print("[cyan]📦 กำลังโหลดข้อมูลจากฐานข้อมูล...[/cyan]")
    
    with db.get_session() as session:
        video_repo = VideoRepository(session)
        metric_repo = DailyMetricRepository(session)
        rule_repo = PlaybookRuleRepository(session)
        research_repo = ResearchItemRepository(session)
        
        # Get videos
        videos = video_repo.get_all(limit=100)
        video_data = []
        
        for video in videos:
            # Get metrics for the period
            metrics = metric_repo.get_by_video_and_date_range(
                video.id, start_date, end_date
            )
            
            total_views = sum(m.views for m in metrics) if metrics else video.view_count or 0
            total_likes = sum(m.likes for m in metrics) if metrics else video.like_count or 0
            total_comments = sum(m.comments for m in metrics) if metrics else video.comment_count or 0
            
            video_data.append({
                'title': video.title,
                'views': total_views,
                'likes': total_likes,
                'comments': total_comments,
                'ctr': 0.0,  # Would need impressions data
                'avg_view_duration': metrics[-1].average_view_duration if metrics else 0,
                'published_at': video.published_at,
            })
        
        # Get active rules
        rules = rule_repo.get_active()
        rule_data = [
            {
                'name': r.name,
                'description': r.description,
                'confidence': r.confidence_score,
                'priority': r.priority,
            }
            for r in rules
        ]
        
        # Get recent research
        research = research_repo.get_recent(days=7, limit=10)
        research_data = [
            {
                'title': r.title,
                'source': r.source,
                'trend_score': r.trend_score,
            }
            for r in research
        ]
        
        # Calculate summary
        summary = {
            'total_views': sum(v['views'] for v in video_data),
            'total_likes': sum(v['likes'] for v in video_data),
            'total_comments': sum(v['comments'] for v in video_data),
            'avg_ctr': np.mean([v['ctr'] for v in video_data]) if video_data else 0,
            'avg_view_duration': np.mean([v['avg_view_duration'] for v in video_data]) if video_data else 0,
            'videos_published': len([v for v in video_data if v['published_at'] and v['published_at'] >= start_date]),
        }
        
        return {
            'videos': video_data,
            'rules': rule_data,
            'research': research_data,
            'period': {
                'start': start_date,
                'end': end_date,
            },
            'summary': summary,
        }


def generate_thai_report(data: dict) -> str:
    """สร้างรายงานภาษาไทย"""
    lines = []
    
    # Header
    lines.append("=" * 70)
    lines.append("📊 รายงานสรุปประจำสัปดาห์ - YouTube Content Assistant")
    lines.append("=" * 70)
    lines.append("")
    
    # Period
    period = data['period']
    lines.append(f"📅 ช่วงเวลา: {period['start'].strftime('%Y-%m-%d')} ถึง {period['end'].strftime('%Y-%m-%d')}")
    lines.append(f"📆 วันที่สร้างรายงาน: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Summary
    summary = data['summary']
    lines.append("-" * 70)
    lines.append("📈 สรุปภาพรวม")
    lines.append("-" * 70)
    lines.append(f"  • ยอดวิว รวม: {summary['total_views']:,}")
    lines.append(f"  • ยอดไลค์ รวม: {summary['total_likes']:,}")
    lines.append(f"  • ยอดคอมเมนต์ รวม: {summary['total_comments']:,}")
    lines.append(f"  • CTR เฉลี่ย: {summary['avg_ctr']:.2f}%")
    lines.append(f"  • ระยะเวลาดูเฉลี่ย: {summary['avg_view_duration']:.0f} วินาที")
    lines.append(f"  • วิดีโอที่เผยแพร่: {summary['videos_published']} วิดีโอ")
    lines.append("")
    
    # Top Videos
    videos = sorted(data['videos'], key=lambda x: x['views'], reverse=True)[:10]
    if videos:
        lines.append("-" * 70)
        lines.append("🏆 Top 10 วิดีโอยอดนิยม")
        lines.append("-" * 70)
        for i, video in enumerate(videos, 1):
            title = video['title'][:40] + "..." if len(video['title']) > 40 else video['title']
            lines.append(f"  {i:2d}. {title}")
            lines.append(f"      👁️ {video['views']:,} views | 👍 {video['likes']:,} likes | 💬 {video['comments']:,} comments")
        lines.append("")
    
    # Active Rules
    rules = data['rules']
    if rules:
        lines.append("-" * 70)
        lines.append("📋 กฎ Playbook ที่ใช้งาน")
        lines.append("-" * 70)
        
        # Group by priority
        high_rules = [r for r in rules if r['priority'] == 'high']
        medium_rules = [r for r in rules if r['priority'] == 'medium']
        low_rules = [r for r in rules if r['priority'] == 'low']
        
        if high_rules:
            lines.append("  🔴 กฎสำคัญ (High Priority):")
            for rule in high_rules:
                lines.append(f"     • {rule['description']} (ความมั่นใจ: {rule['confidence']:.0%})")
        
        if medium_rules:
            lines.append("  🟡 กฎทั่วไป (Medium Priority):")
            for rule in medium_rules:
                lines.append(f"     • {rule['description']} (ความมั่นใจ: {rule['confidence']:.0%})")
        
        if low_rules:
            lines.append("  🟢 กฎเสริม (Low Priority):")
            for rule in low_rules:
                lines.append(f"     • {rule['description']} (ความมั่นใจ: {rule['confidence']:.0%})")
        
        lines.append("")
    
    # Trending Research
    research = data['research']
    if research:
        lines.append("-" * 70)
        lines.append("🔥 Trending Topics")
        lines.append("-" * 70)
        for item in research[:5]:
            lines.append(f"  • {item['title']} (Score: {item['trend_score']}) [{item['source']}]")
        lines.append("")
    
    # Recommendations
    lines.append("-" * 70)
    lines.append("💡 คำแนะนำสำหรับสัปดาห์หน้า")
    lines.append("-" * 70)
    
    # Generate recommendations based on data
    recommendations = []
    
    if summary['avg_ctr'] < 5:
        recommendations.append("• พิจารณาปรับปรุง thumbnail และ title เพื่อเพิ่ม CTR")
    
    if summary['avg_view_duration'] < 180:
        recommendations.append("• พิจารณาปรับปรุงเนื้อหาช่วงต้นวิดีโอเพื่อดึงดูดผู้ชม")
    
    if summary['videos_published'] < 3:
        recommendations.append("• เพิ่มความถี่ในการเผยแพร่วิดีโอ (แนะนำ 3-5 วิดีโอ/สัปดาห์)")
    
    if research:
        top_trend = research[0]['title']
        recommendations.append(f"• พิจารณาทำเนื้อหาเกี่ยวกับ '{top_trend}' ที่กำลัง trending")
    
    if not recommendations:
        recommendations.append("• รักษามาตรฐานการทำงานที่ดีต่อไป!")
    
    for rec in recommendations:
        lines.append(f"  {rec}")
    
    lines.append("")
    lines.append("=" * 70)
    lines.append("สร้างโดย YouTube Content Assistant")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def generate_csv_report(data: dict, output_dir: Path) -> list:
    """สร้างรายงาน CSV"""
    files = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Videos CSV
    if data['videos']:
        videos_df = pd.DataFrame(data['videos'])
        videos_file = output_dir / f"report_videos_{timestamp}.csv"
        videos_df.to_csv(videos_file, index=False, encoding='utf-8-sig')
        files.append(str(videos_file))
    
    # Rules CSV
    if data['rules']:
        rules_df = pd.DataFrame(data['rules'])
        rules_file = output_dir / f"report_rules_{timestamp}.csv"
        rules_df.to_csv(rules_file, index=False, encoding='utf-8-sig')
        files.append(str(rules_file))
    
    # Research CSV
    if data['research']:
        research_df = pd.DataFrame(data['research'])
        research_file = output_dir / f"report_research_{timestamp}.csv"
        research_df.to_csv(research_file, index=False, encoding='utf-8-sig')
        files.append(str(research_file))
    
    # Summary CSV
    summary_df = pd.DataFrame([data['summary']])
    summary_file = output_dir / f"report_summary_{timestamp}.csv"
    summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
    files.append(str(summary_file))
    
    return files


def print_report_to_console(data: dict):
    """แสดงรายงานใน console"""
    period = data['period']
    summary = data['summary']
    
    # Header
    console.print(Panel.fit(
        f"[bold cyan]📊 รายงานสรุปประจำสัปดาห์[/bold cyan]\n"
        f"📅 {period['start'].strftime('%Y-%m-%d')} - {period['end'].strftime('%Y-%m-%d')}",
        border_style="cyan"
    ))
    
    # Summary table
    console.print("\n[bold]📈 สรุปภาพรวม[/bold]")
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", justify="right")
    
    summary_table.add_row("ยอดวิว รวม", f"{summary['total_views']:,}")
    summary_table.add_row("ยอดไลค์ รวม", f"{summary['total_likes']:,}")
    summary_table.add_row("ยอดคอมเมนต์ รวม", f"{summary['total_comments']:,}")
    summary_table.add_row("CTR เฉลี่ย", f"{summary['avg_ctr']:.2f}%")
    summary_table.add_row("ระยะเวลาดูเฉลี่ย", f"{summary['avg_view_duration']:.0f} วินาที")
    summary_table.add_row("วิดีโอที่เผยแพร่", f"{summary['videos_published']}")
    
    console.print(summary_table)
    
    # Top videos
    videos = sorted(data['videos'], key=lambda x: x['views'], reverse=True)[:5]
    if videos:
        console.print("\n[bold]🏆 Top 5 วิดีโอยอดนิยม[/bold]")
        video_table = Table()
        video_table.add_column("#", style="dim")
        video_table.add_column("Title")
        video_table.add_column("Views", justify="right")
        video_table.add_column("Likes", justify="right")
        
        for i, video in enumerate(videos, 1):
            title = video['title'][:35] + "..." if len(video['title']) > 35 else video['title']
            video_table.add_row(
                str(i),
                title,
                f"{video['views']:,}",
                f"{video['likes']:,}",
            )
        
        console.print(video_table)
    
    # Rules
    rules = data['rules']
    if rules:
        console.print("\n[bold]📋 กฎ Playbook ที่ใช้งาน[/bold]")
        for rule in rules[:5]:
            priority_icon = "🔴" if rule['priority'] == 'high' else "🟡" if rule['priority'] == 'medium' else "🟢"
            console.print(f"  {priority_icon} {rule['description']} ({rule['confidence']:.0%})")
    
    # Research
    research = data['research']
    if research:
        console.print("\n[bold]🔥 Trending Topics[/bold]")
        for item in research[:5]:
            console.print(f"  • {item['title']} (Score: {item['trend_score']})")


def main():
    parser = argparse.ArgumentParser(
        description='Weekly Report - สร้างรายงานสรุปประจำสัปดาห์ภาษาไทย',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:
  python scripts/report_weekly.py --demo
  python scripts/report_weekly.py --start 2024-01-01 --end 2024-01-07
  python scripts/report_weekly.py --csv --output-dir exports
        """
    )
    
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                        help='Path to config file')
    parser.add_argument('--demo', action='store_true',
                        help='ใช้ข้อมูลตัวอย่าง (demo mode)')
    parser.add_argument('--start', type=str,
                        help='วันที่เริ่มต้น (YYYY-MM-DD)')
    parser.add_argument('--end', type=str,
                        help='วันที่สิ้นสุด (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=7,
                        help='จำนวนวันย้อนหลัง (default: 7)')
    parser.add_argument('--csv', action='store_true',
                        help='Export เป็น CSV')
    parser.add_argument('--output-dir', type=str, default='exports',
                        help='โฟลเดอร์สำหรับ output')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='ไม่แสดงผลใน console')
    
    args = parser.parse_args()
    
    # Print header
    if not args.quiet:
        console.print(Panel.fit(
            "[bold cyan]📊 Weekly Report Generator[/bold cyan]\n"
            "สร้างรายงานสรุปประจำสัปดาห์ภาษาไทย",
            border_style="cyan"
        ))
    
    try:
        # Determine date range
        if args.start and args.end:
            start_date = datetime.strptime(args.start, '%Y-%m-%d')
            end_date = datetime.strptime(args.end, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days)
        
        # Load or generate data
        if args.demo:
            data = generate_demo_report_data()
            data['period'] = {'start': start_date, 'end': end_date}
        else:
            config = load_config(args.config)
            db = DatabaseConnection(config.database.url)
            db.create_tables()
            data = load_report_data(db, start_date, end_date)
        
        # Print to console
        if not args.quiet:
            print_report_to_console(data)
        
        # Generate outputs
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate Thai report
        report_text = generate_thai_report(data)
        report_file = output_dir / f"weekly_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        console.print(f"\n[green]✅ บันทึกรายงาน: {report_file}[/green]")
        
        # Generate CSV if requested
        if args.csv:
            csv_files = generate_csv_report(data, output_dir)
            for f in csv_files:
                console.print(f"[green]✅ บันทึก CSV: {f}[/green]")
        
        # Final summary
        console.print(Panel.fit(
            f"[bold green]✅ สร้างรายงานเสร็จสมบูรณ์![/bold green]\n\n"
            f"📅 ช่วงเวลา: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}\n"
            f"📁 Output: {output_dir}",
            border_style="green"
        ))
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาด: {e}")
        console.print(f"[red]❌ เกิดข้อผิดพลาด: {e}[/red]")
        raise


if __name__ == '__main__':
    main()
