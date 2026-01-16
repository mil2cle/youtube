#!/usr/bin/env python3
"""
Train Playbook - ฝึก ML model จาก YouTube metrics และสร้างกฎภาษาไทย

การใช้งาน:
    # ฝึก classification model (default)
    python scripts/train_playbook.py
    
    # ฝึก regression model
    python scripts/train_playbook.py --task regression --target views
    
    # ใช้ Decision Tree
    python scripts/train_playbook.py --model tree --max-depth 5
    
    # บันทึกกฎลง database
    python scripts/train_playbook.py --save-rules
    
    # ใช้ข้อมูลตัวอย่าง (demo mode)
    python scripts/train_playbook.py --demo
"""

import sys
import os
import argparse
import json
from datetime import datetime, timedelta
import uuid
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

from src.utils.config import load_config
from src.utils.logger import setup_logger
from src.db.connection import DatabaseConnection
from src.db.models import Video, DailyMetric, PlaybookRule as PlaybookRuleModel, RunLog
from src.db.repository import VideoRepository, DailyMetricRepository, PlaybookRuleRepository, RunLogRepository
from src.playbook.feature_extractor import FeatureExtractor, VideoFeatures
from src.playbook.model_trainer import PlaybookModelTrainer
from src.playbook.rule_generator import ThaiRuleGenerator, PlaybookRule

console = Console()
logger = setup_logger(__name__)


def generate_demo_data(n_samples: int = 100) -> pd.DataFrame:
    """สร้างข้อมูลตัวอย่างสำหรับ demo"""
    console.print("[cyan]📦 กำลังสร้างข้อมูลตัวอย่าง...[/cyan]")
    
    np.random.seed(42)
    
    data = []
    for i in range(n_samples):
        # Generate features with some patterns
        title_length = np.random.randint(20, 100)
        has_number = np.random.random() > 0.5
        has_question = np.random.random() > 0.7
        has_emoji = np.random.random() > 0.6
        has_bracket = np.random.random() > 0.4
        positive_keywords = np.random.randint(0, 4)
        
        desc_length = np.random.randint(100, 2000)
        has_timestamps = np.random.random() > 0.5
        has_hashtags = np.random.random() > 0.6
        
        publish_hour = np.random.randint(0, 24)
        publish_day = np.random.randint(0, 7)
        is_weekend = publish_day >= 5
        is_evening = 17 <= publish_hour < 21
        
        duration = np.random.choice([30, 180, 480, 900, 1800, 3600], p=[0.2, 0.15, 0.25, 0.2, 0.15, 0.05])
        is_shorts = duration <= 60
        
        tags_count = np.random.randint(0, 20)
        
        # Generate views with patterns (features that help)
        base_views = 1000
        views = base_views
        
        # Positive factors
        if has_number:
            views *= np.random.uniform(1.2, 1.5)
        if has_question:
            views *= np.random.uniform(1.1, 1.3)
        if has_emoji:
            views *= np.random.uniform(1.05, 1.2)
        if positive_keywords > 0:
            views *= (1 + positive_keywords * 0.1)
        if has_timestamps and duration > 600:
            views *= np.random.uniform(1.1, 1.3)
        if is_evening:
            views *= np.random.uniform(1.2, 1.4)
        if 8 <= duration / 60 <= 15:  # 8-15 minutes sweet spot
            views *= np.random.uniform(1.3, 1.6)
        if tags_count >= 10:
            views *= np.random.uniform(1.1, 1.2)
        
        # Add noise
        views *= np.random.uniform(0.5, 2.0)
        views = int(views)
        
        # Calculate engagement
        likes = int(views * np.random.uniform(0.02, 0.08))
        comments = int(views * np.random.uniform(0.005, 0.02))
        
        data.append({
            'video_id': f'video_{i:04d}',
            'title_length_chars': title_length,
            'title_length_words': title_length // 5,
            'title_has_number': int(has_number),
            'title_has_year': int(np.random.random() > 0.7),
            'title_has_square_bracket': int(has_bracket),
            'title_has_round_bracket': int(np.random.random() > 0.5),
            'title_has_japanese_bracket': int(np.random.random() > 0.8),
            'title_has_emoji': int(has_emoji),
            'title_has_question': int(has_question),
            'title_has_exclamation': int(np.random.random() > 0.6),
            'title_has_colon': int(np.random.random() > 0.5),
            'title_has_pipe': int(np.random.random() > 0.7),
            'title_caps_ratio': np.random.uniform(0, 0.3),
            'title_positive_keywords_count': positive_keywords,
            'title_anime_keywords_count': np.random.randint(0, 3),
            
            'desc_length_chars': desc_length,
            'desc_length_words': desc_length // 5,
            'desc_has_links': int(np.random.random() > 0.3),
            'desc_link_count': np.random.randint(0, 5),
            'desc_has_timestamps': int(has_timestamps),
            'desc_timestamp_count': np.random.randint(0, 10) if has_timestamps else 0,
            'desc_has_hashtags': int(has_hashtags),
            'desc_hashtag_count': np.random.randint(0, 10) if has_hashtags else 0,
            
            'publish_hour': publish_hour,
            'publish_day_of_week': publish_day,
            'publish_is_weekend': int(is_weekend),
            'publish_is_morning': int(8 <= publish_hour < 12),
            'publish_is_afternoon': int(12 <= publish_hour < 17),
            'publish_is_evening': int(is_evening),
            'publish_is_night': int(21 <= publish_hour or publish_hour < 5),
            
            'duration_seconds': duration,
            'duration_minutes': duration / 60,
            'is_shorts': int(is_shorts),
            'is_very_short': int(60 < duration <= 180),
            'is_short': int(180 < duration <= 480),
            'is_medium': int(480 < duration <= 900),
            'is_long': int(900 < duration <= 1800),
            'is_very_long': int(duration > 1800),
            
            'tags_count': tags_count,
            'tags_avg_length': np.random.uniform(5, 20),
            
            'views': views,
            'likes': likes,
            'comments': comments,
            'ctr': np.random.uniform(2, 10),
            'avg_view_duration': duration * np.random.uniform(0.3, 0.7),
            'engagement_rate': (likes + comments) / views * 100 if views > 0 else 0,
        })
    
    df = pd.DataFrame(data)
    
    # Add performance labels
    p75 = df['views'].quantile(0.75)
    df['is_high_performer'] = df['views'] >= p75
    
    console.print(f"[green]✅ สร้างข้อมูลตัวอย่างสำเร็จ: {len(df)} รายการ[/green]")
    
    return df


def load_data_from_db(db: DatabaseConnection, min_videos: int = 20) -> pd.DataFrame:
    """โหลดข้อมูลจากฐานข้อมูล"""
    console.print("[cyan]📦 กำลังโหลดข้อมูลจากฐานข้อมูล...[/cyan]")
    
    with db.get_session() as session:
        video_repo = VideoRepository(session)
        metric_repo = DailyMetricRepository(session)
        
        # Get all videos
        videos = video_repo.get_all(limit=1000)
        
        if len(videos) < min_videos:
            console.print(f"[yellow]⚠️ มีวิดีโอในฐานข้อมูลน้อยเกินไป ({len(videos)} < {min_videos})[/yellow]")
            return pd.DataFrame()
        
        # Extract features
        extractor = FeatureExtractor()
        features_list = []
        
        for video in videos:
            video_dict = {
                'id': video.id,
                'youtube_video_id': video.youtube_video_id,
                'title': video.title,
                'description': video.description,
                'published_at': video.published_at,
                'duration_seconds': video.duration_seconds,
                'tags': video.tags,
                'view_count': video.view_count,
                'like_count': video.like_count,
                'comment_count': video.comment_count,
            }
            
            # Get latest metrics
            metrics = metric_repo.get_latest_for_video(video.id)
            metrics_dict = None
            if metrics:
                metrics_dict = {
                    'impressions': getattr(metrics, 'impressions', 0),
                    'average_view_duration': metrics.average_view_duration,
                }
            
            features = extractor.extract(video_dict, metrics_dict)
            features_list.append(features.to_dict())
        
        df = pd.DataFrame(features_list)
        
        # Add performance labels
        df = extractor.label_performance(df, metric='views')
        
        console.print(f"[green]✅ โหลดข้อมูลสำเร็จ: {len(df)} วิดีโอ[/green]")
        
        return df


def save_rules_to_db(
    db: DatabaseConnection,
    rules: list,
    model_type: str,
    target: str,
    model_metrics: dict,
):
    """บันทึกกฎลงฐานข้อมูล"""
    console.print("[cyan]💾 กำลังบันทึกกฎลงฐานข้อมูล...[/cyan]")
    
    generator = ThaiRuleGenerator()
    records = generator.to_database_format(rules, model_type, target, model_metrics)
    
    with db.get_session() as session:
        rule_repo = PlaybookRuleRepository(session)
        
        saved_count = 0
        for record in records:
            try:
                # Check if rule already exists
                existing = rule_repo.get_by_name(record['name'])
                if existing:
                    # Update existing rule
                    rule_repo.update(existing.id, **record)
                else:
                    # Create new rule
                    rule_repo.create(**record)
                saved_count += 1
            except Exception as e:
                logger.error(f"ไม่สามารถบันทึกกฎ {record['name']}: {e}")
        
        session.commit()
        console.print(f"[green]✅ บันทึกกฎสำเร็จ: {saved_count} กฎ[/green]")


def log_run(
    db: DatabaseConnection,
    status: str,
    message: str,
    metrics: dict = None,
    params: dict = None,
):
    """บันทึก log การรัน"""
    with db.get_session() as session:
        log_repo = RunLogRepository(session)
        run_log_data = {
            'run_id': f'train-playbook-{uuid.uuid4().hex[:8]}',
            'run_type': 'rule_learning',
            'status': status,
            'started_at': datetime.now(),
            'completed_at': datetime.now(),
            'parameters': params,
        }
        if status == 'success':
            run_log_data['result'] = {'message': message, 'metrics': metrics}
        else:
            run_log_data['error_message'] = message

        log_repo.create(**run_log_data)
        session.commit()


def main():
    parser = argparse.ArgumentParser(
        description='Train Playbook - ฝึก ML model และสร้างกฎภาษาไทย',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:
  python scripts/train_playbook.py --demo
  python scripts/train_playbook.py --task classification --model logistic
  python scripts/train_playbook.py --task regression --target views --model tree
  python scripts/train_playbook.py --save-rules --top-rules 15
        """
    )
    
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                        help='Path to config file')
    parser.add_argument('--demo', action='store_true',
                        help='ใช้ข้อมูลตัวอย่าง (demo mode)')
    parser.add_argument('--task', type=str, default='classification',
                        choices=['classification', 'regression'],
                        help='ประเภท task (default: classification)')
    parser.add_argument('--target', type=str, default='is_high_performer',
                        help='Target variable (default: is_high_performer)')
    parser.add_argument('--model', type=str, default='logistic',
                        choices=['logistic', 'linear', 'ridge', 'tree', 'forest'],
                        help='ประเภท model (default: logistic)')
    parser.add_argument('--max-depth', type=int, default=5,
                        help='Max depth สำหรับ tree models')
    parser.add_argument('--top-rules', type=int, default=10,
                        help='จำนวนกฎที่ต้องการสร้าง')
    parser.add_argument('--save-rules', action='store_true',
                        help='บันทึกกฎลงฐานข้อมูล')
    parser.add_argument('--save-model', action='store_true',
                        help='บันทึก model')
    parser.add_argument('--output-dir', type=str, default='exports',
                        help='โฟลเดอร์สำหรับ output')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='แสดงรายละเอียดเพิ่มเติม')
    
    args = parser.parse_args()
    
    # Print header
    console.print(Panel.fit(
        "[bold cyan]🎓 Playbook Training[/bold cyan]\n"
        "ฝึก ML model จาก YouTube metrics และสร้างกฎภาษาไทย",
        border_style="cyan"
    ))
    
    try:
        # Load config
        config = load_config(args.config)
        console.print(f"[green]✓[/green] โหลด config สำเร็จ: {args.config}")
        
        # Initialize database
        db_url = f"sqlite:///{config.database.path}"
        db = DatabaseConnection(db_url)
        db.create_tables()
        console.print(f"[green]✓[/green] เชื่อมต่อฐานข้อมูลสำเร็จ")
        
        # Load or generate data
        if args.demo:
            df = generate_demo_data(n_samples=200)
        else:
            df = load_data_from_db(db)
            if df.empty:
                console.print("[yellow]⚠️ ไม่มีข้อมูลในฐานข้อมูล ใช้ --demo เพื่อทดสอบ[/yellow]")
                return
        
        # Print data summary
        console.print(f"\n[cyan]📊 ข้อมูลสำหรับ training:[/cyan]")
        console.print(f"   • จำนวนวิดีโอ: {len(df)}")
        if 'is_high_performer' in df.columns:
            high_perf = df['is_high_performer'].sum()
            console.print(f"   • High performers: {high_perf} ({high_perf/len(df)*100:.1f}%)")
        
        # Initialize trainer
        trainer = PlaybookModelTrainer(model_dir=args.output_dir)
        
        # Determine model type based on task
        if args.task == 'classification':
            if args.model in ['linear', 'ridge']:
                args.model = 'logistic'
            
            results = trainer.fit_classification(
                df,
                target=args.target,
                model_type=args.model,
                max_depth=args.max_depth,
            )
        else:
            if args.model == 'logistic':
                args.model = 'linear'
            
            results = trainer.fit_regression(
                df,
                target=args.target,
                model_type=args.model,
                max_depth=args.max_depth,
            )
        
        # Generate rules
        console.print("\n[cyan]📋 กำลังสร้างกฎภาษาไทย...[/cyan]")
        
        generator = ThaiRuleGenerator()
        rules = generator.generate_rules(
            trainer.feature_importance,
            results['test_metrics'],
            top_n=args.top_rules,
        )
        
        # Print rules
        generator.print_rules(rules)
        
        # Print top factors
        generator.print_top_factors(trainer.feature_importance, top_n=5)
        
        # Generate summary
        summary = generator.generate_summary(rules, args.model, args.target)
        
        # Save outputs
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save summary
        summary_file = output_dir / f"playbook_summary_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        console.print(f"\n[green]✅ บันทึกสรุปกฎ: {summary_file}[/green]")
        
        # Save rules as JSON
        rules_file = output_dir / f"playbook_rules_{timestamp}.json"
        with open(rules_file, 'w', encoding='utf-8') as f:
            json.dump([r.to_dict() for r in rules], f, ensure_ascii=False, indent=2)
        console.print(f"[green]✅ บันทึกกฎ JSON: {rules_file}[/green]")
        
        # Save model
        if args.save_model:
            model_file = trainer.save_model(f"playbook_{args.task}_{args.model}")
            console.print(f"[green]✅ บันทึก model: {model_file}[/green]")
        
        # Save rules to database
        if args.save_rules:
            save_rules_to_db(db, rules, args.model, args.target, results['test_metrics'])
        
        # Log run
        log_run(db, 'success', f'Training completed: {args.model} model', results['test_metrics'], params=vars(args))
        
        # Final summary
        console.print(Panel.fit(
            f"[bold green]✅ Training เสร็จสมบูรณ์![/bold green]\n\n"
            f"📊 Model: {args.model}\n"
            f"🎯 Target: {args.target}\n"
            f"📋 กฎที่สร้าง: {len(rules)} กฎ\n"
            f"📁 Output: {output_dir}",
            border_style="green"
        ))
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาด: {e}")
        console.print(f"[red]❌ เกิดข้อผิดพลาด: {e}[/red]")
        
        if 'db' in locals():
            log_run(db, 'error', str(e), params=vars(args))
        
        raise


if __name__ == '__main__':
    main()
