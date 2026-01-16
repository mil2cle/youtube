#!/usr/bin/env python3
"""
run_all.py - Script สำหรับรันทุก modules
รัน: python scripts/run_all.py [OPTIONS]

รัน tasks ต่างๆ ของระบบ YouTube Content Assistant
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
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.db.connection import init_db, session_scope
from src.db.repository import (
    VideoRepository,
    DailyMetricRepository,
    ResearchItemRepository,
    ContentIdeaRepository,
    PlaybookRuleRepository,
    RunLogRepository,
)
from src.modules.analytics import AnalyticsModule
from src.modules.content import ContentModule
from src.modules.research import ResearchModule
from src.modules.playbook import PlaybookModule
from src.modules.scheduler import SchedulerModule, get_scheduler
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


def run_analytics_task(session) -> dict:
    """รัน Analytics task"""
    task_logger = TaskLogger("Analytics")
    task_logger.start("เริ่มวิเคราะห์ข้อมูล")
    
    analytics = AnalyticsModule(session)
    results = {}
    
    try:
        task_logger.step("กำลังสรุปข้อมูล channel")
        summary = analytics.get_channel_summary()
        results["channel_summary"] = summary
        
        task_logger.step("กำลังวิเคราะห์เวลาโพสต์ที่ดีที่สุด")
        posting_times = analytics.get_best_posting_times()
        results["best_posting_times"] = posting_times
        
        task_logger.step("กำลังสร้าง insights")
        insights = analytics.generate_insights()
        results["insights"] = insights
        
        task_logger.complete("วิเคราะห์ข้อมูลเสร็จสิ้น")
        results["status"] = "success"
        
    except Exception as e:
        task_logger.fail(str(e))
        results["status"] = "failed"
        results["error"] = str(e)
    
    return results


def run_content_task(session) -> dict:
    """รัน Content task"""
    task_logger = TaskLogger("Content")
    task_logger.start("เริ่มจัดการ content")
    
    content = ContentModule(session)
    results = {}
    
    try:
        task_logger.step("กำลังดึงสถิติไอเดีย")
        stats = content.get_idea_stats()
        results["idea_stats"] = stats
        
        task_logger.step("กำลังสร้างคำแนะนำไอเดีย")
        suggestions = content.generate_suggestions(count=5)
        results["suggestions"] = [
            {
                "title": s.title,
                "category": s.category,
                "potential_score": s.potential_score,
            }
            for s in suggestions
        ]
        
        task_logger.step("กำลัง archive ไอเดียเก่า")
        archived = content.archive_old_ideas(days=90)
        results["archived_count"] = archived
        
        task_logger.complete("จัดการ content เสร็จสิ้น")
        results["status"] = "success"
        
    except Exception as e:
        task_logger.fail(str(e))
        results["status"] = "failed"
        results["error"] = str(e)
    
    return results


def run_research_task(session) -> dict:
    """รัน Research task"""
    task_logger = TaskLogger("Research")
    task_logger.start("เริ่มอัพเดท research")
    
    research = ResearchModule(session)
    results = {}
    
    try:
        task_logger.step("กำลังดึง trending topics")
        trending = research.get_trending_topics(min_score=0.5, limit=10)
        results["trending_topics"] = [
            {
                "title": t.title,
                "source": t.source,
                "trend_score": t.trend_score,
            }
            for t in trending
        ]
        
        task_logger.step("กำลังวิเคราะห์การแข่งขัน")
        competition = research.analyze_competition()
        results["competition_analysis"] = competition
        
        task_logger.step("กำลังสร้างรายงาน")
        report = research.generate_research_report()
        results["report_summary"] = report["summary"]
        
        task_logger.step("กำลังทำความสะอาดข้อมูลเก่า")
        cleaned = research.cleanup_old_items(days=90)
        results["cleaned_count"] = cleaned
        
        task_logger.complete("อัพเดท research เสร็จสิ้น")
        results["status"] = "success"
        
    except Exception as e:
        task_logger.fail(str(e))
        results["status"] = "failed"
        results["error"] = str(e)
    
    return results


def run_playbook_task(session) -> dict:
    """รัน Playbook task"""
    task_logger = TaskLogger("Playbook")
    task_logger.start("เริ่มอัพเดท playbook")
    
    playbook = PlaybookModule(session)
    results = {}
    
    try:
        task_logger.step("กำลังดึงสถิติกฎ")
        stats = playbook.get_rule_stats()
        results["rule_stats"] = stats
        
        task_logger.step("กำลังเรียนรู้กฎใหม่")
        new_rules = playbook.learn_from_performance(min_videos=3)
        results["new_rules_count"] = len(new_rules)
        results["new_rules"] = [
            {
                "name": r.name,
                "category": r.category,
                "confidence": r.confidence_score,
            }
            for r in new_rules
        ]
        
        task_logger.step("กำลังดึงคำแนะนำ")
        recommendations = playbook.get_recommendations()
        results["recommendations"] = recommendations[:5]
        
        task_logger.complete("อัพเดท playbook เสร็จสิ้น")
        results["status"] = "success"
        
    except Exception as e:
        task_logger.fail(str(e))
        results["status"] = "failed"
        results["error"] = str(e)
    
    return results


def display_results(all_results: dict) -> None:
    """แสดงผลลัพธ์ทั้งหมด"""
    console.print()
    console.print(Panel("📊 สรุปผลการทำงาน", style="bold blue"))
    console.print()
    
    # Analytics Results
    if "analytics" in all_results:
        analytics = all_results["analytics"]
        if analytics.get("status") == "success":
            table = Table(title="🔍 Analytics", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            summary = analytics.get("channel_summary", {})
            table.add_row("Total Videos", str(summary.get("total_videos", 0)))
            table.add_row("Total Views", f"{summary.get('total_views', 0):,}")
            table.add_row("Engagement Rate", f"{summary.get('engagement_rate', 0):.2f}%")
            
            insights = analytics.get("insights", [])
            table.add_row("Insights Generated", str(len(insights)))
            
            console.print(table)
            
            if insights:
                console.print("\n[bold]💡 Insights:[/bold]")
                for insight in insights[:3]:
                    console.print(f"  • {insight}")
        else:
            print_error(f"Analytics failed: {analytics.get('error', 'Unknown error')}")
    
    console.print()
    
    # Content Results
    if "content" in all_results:
        content = all_results["content"]
        if content.get("status") == "success":
            table = Table(title="📝 Content", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            stats = content.get("idea_stats", {})
            table.add_row("Total Ideas", str(stats.get("total_ideas", 0)))
            table.add_row("Suggestions Generated", str(len(content.get("suggestions", []))))
            table.add_row("Ideas Archived", str(content.get("archived_count", 0)))
            
            console.print(table)
            
            suggestions = content.get("suggestions", [])
            if suggestions:
                console.print("\n[bold]💡 Content Suggestions:[/bold]")
                for s in suggestions[:3]:
                    console.print(f"  • {s['title']} (Score: {s['potential_score']:.0f})")
        else:
            print_error(f"Content failed: {content.get('error', 'Unknown error')}")
    
    console.print()
    
    # Research Results
    if "research" in all_results:
        research = all_results["research"]
        if research.get("status") == "success":
            table = Table(title="🔬 Research", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            summary = research.get("report_summary", {})
            table.add_row("Total Items", str(summary.get("total_items", 0)))
            table.add_row("Trending Topics", str(len(research.get("trending_topics", []))))
            table.add_row("Items Cleaned", str(research.get("cleaned_count", 0)))
            
            console.print(table)
            
            trending = research.get("trending_topics", [])
            if trending:
                console.print("\n[bold]🔥 Trending Topics:[/bold]")
                for t in trending[:3]:
                    console.print(f"  • {t['title']} (Score: {t['trend_score']:.2f})")
        else:
            print_error(f"Research failed: {research.get('error', 'Unknown error')}")
    
    console.print()
    
    # Playbook Results
    if "playbook" in all_results:
        playbook = all_results["playbook"]
        if playbook.get("status") == "success":
            table = Table(title="📖 Playbook", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            stats = playbook.get("rule_stats", {})
            table.add_row("Total Rules", str(stats.get("total_rules", 0)))
            table.add_row("Active Rules", str(stats.get("active_rules", 0)))
            table.add_row("New Rules Learned", str(playbook.get("new_rules_count", 0)))
            table.add_row("Avg Confidence", f"{stats.get('avg_confidence', 0):.2%}")
            
            console.print(table)
            
            recommendations = playbook.get("recommendations", [])
            if recommendations:
                console.print("\n[bold]📌 Recommendations:[/bold]")
                for r in recommendations[:3]:
                    console.print(f"  • {r}")
        else:
            print_error(f"Playbook failed: {playbook.get('error', 'Unknown error')}")


def log_run(session, run_type: str, results: dict) -> None:
    """บันทึก run log"""
    repo = RunLogRepository(session)
    
    run = repo.create_run(
        run_type=run_type,
        triggered_by="cli",
        parameters={"script": "run_all.py"},
    )
    
    status = "completed" if results.get("status") == "success" else "failed"
    
    if status == "completed":
        repo.complete_run(
            run.id,
            status=status,
            result=results,
        )
    else:
        repo.fail_run(
            run.id,
            error_message=results.get("error", "Unknown error"),
        )


@click.command()
@click.option("--analytics", is_flag=True, help="รัน Analytics module")
@click.option("--content", is_flag=True, help="รัน Content module")
@click.option("--research", is_flag=True, help="รัน Research module")
@click.option("--playbook", is_flag=True, help="รัน Playbook module")
@click.option("--all", "run_all", is_flag=True, help="รันทุก modules")
@click.option("--scheduler", is_flag=True, help="เริ่ม scheduler")
@click.option("--export", type=click.Path(), help="Export ผลลัพธ์เป็น JSON")
@click.option("--config", default="configs/default.yaml", help="path ไปยังไฟล์ config")
def main(
    analytics: bool,
    content: bool,
    research: bool,
    playbook: bool,
    run_all: bool,
    scheduler: bool,
    export: str,
    config: str,
):
    """
    รัน modules ต่างๆ ของ YouTube Content Assistant
    
    ตัวอย่าง:
        python scripts/run_all.py --all
        python scripts/run_all.py --analytics --content
        python scripts/run_all.py --scheduler
    """
    print_banner(
        "YouTube Content Assistant",
        "Module Runner Script"
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
    except Exception as e:
        print_error(f"ไม่สามารถเชื่อมต่อฐานข้อมูล: {e}")
        sys.exit(1)
    
    # ถ้าไม่ได้เลือก module ใดเลย ให้รันทั้งหมด
    if not any([analytics, content, research, playbook, run_all, scheduler]):
        run_all = True
    
    # Scheduler mode
    if scheduler:
        console.print(Panel(
            "🕐 กำลังเริ่ม Scheduler...\n"
            "กด Ctrl+C เพื่อหยุด",
            title="Scheduler Mode",
            border_style="blue"
        ))
        
        sched = get_scheduler()
        sched.setup_default_jobs()
        sched.start()
        
        try:
            # แสดง jobs ที่กำลังรัน
            jobs = sched.get_jobs()
            if jobs:
                table = Table(title="📅 Scheduled Jobs", show_header=True)
                table.add_column("Job ID", style="cyan")
                table.add_column("Next Run", style="green")
                table.add_column("Type", style="yellow")
                
                for job in jobs:
                    next_run = job.next_run.strftime("%Y-%m-%d %H:%M:%S") if job.next_run else "N/A"
                    table.add_row(job.job_id, next_run, job.trigger_type)
                
                console.print(table)
            
            # รอจนกว่าจะกด Ctrl+C
            import time
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            sched.stop()
            print_info("Scheduler หยุดทำงาน")
        
        return
    
    # รัน modules
    all_results = {}
    
    with session_scope() as session:
        if run_all or analytics:
            console.print()
            console.print(Panel("🔍 กำลังรัน Analytics...", border_style="blue"))
            all_results["analytics"] = run_analytics_task(session)
            log_run(session, "analytics", all_results["analytics"])
        
        if run_all or content:
            console.print()
            console.print(Panel("📝 กำลังรัน Content...", border_style="blue"))
            all_results["content"] = run_content_task(session)
            log_run(session, "content", all_results["content"])
        
        if run_all or research:
            console.print()
            console.print(Panel("🔬 กำลังรัน Research...", border_style="blue"))
            all_results["research"] = run_research_task(session)
            log_run(session, "research", all_results["research"])
        
        if run_all or playbook:
            console.print()
            console.print(Panel("📖 กำลังรัน Playbook...", border_style="blue"))
            all_results["playbook"] = run_playbook_task(session)
            log_run(session, "playbook", all_results["playbook"])
    
    # แสดงผลลัพธ์
    display_results(all_results)
    
    # Export ถ้าต้องการ
    if export:
        try:
            export_path = Path(export)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
            
            print_success(f"Export ผลลัพธ์ไปยัง: {export}")
        except Exception as e:
            print_error(f"ไม่สามารถ export: {e}")
    
    # Summary
    console.print()
    success_count = sum(1 for r in all_results.values() if r.get("status") == "success")
    total_count = len(all_results)
    
    if success_count == total_count:
        console.print(Panel(
            f"[green]✓ ทำงานสำเร็จทั้งหมด {success_count}/{total_count} modules[/green]",
            title="✅ เสร็จสมบูรณ์",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[yellow]⚠ สำเร็จ {success_count}/{total_count} modules[/yellow]",
            title="⚠️ มีบางส่วนล้มเหลว",
            border_style="yellow"
        ))


if __name__ == "__main__":
    main()
