"""
Analytics Module - วิเคราะห์ข้อมูลและ metrics ของวิดีโอ
รองรับการคำนวณ trends, performance scores, และ insights
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from src.db.models import Video, DailyMetric
from src.db.repository import VideoRepository, DailyMetricRepository
from src.utils.logger import get_logger, TaskLogger

logger = get_logger()


@dataclass
class PerformanceScore:
    """คะแนน performance ของวิดีโอ"""
    video_id: int
    overall_score: float
    view_score: float
    engagement_score: float
    retention_score: float
    growth_score: float
    
    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "overall_score": self.overall_score,
            "view_score": self.view_score,
            "engagement_score": self.engagement_score,
            "retention_score": self.retention_score,
            "growth_score": self.growth_score,
        }


@dataclass
class TrendAnalysis:
    """ผลการวิเคราะห์ trend"""
    metric_name: str
    current_value: float
    previous_value: float
    change_percent: float
    trend_direction: str  # up, down, stable
    is_significant: bool


class AnalyticsModule:
    """
    โมดูลวิเคราะห์ข้อมูล YouTube
    
    รองรับ:
    - การคำนวณ performance scores
    - การวิเคราะห์ trends
    - การสร้าง insights
    - การเปรียบเทียบวิดีโอ
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.video_repo = VideoRepository(session)
        self.metric_repo = DailyMetricRepository(session)
        self.task_logger = TaskLogger("Analytics")
    
    def calculate_performance_score(
        self,
        video_id: int,
        days: int = 30,
    ) -> Optional[PerformanceScore]:
        """
        คำนวณ performance score ของวิดีโอ
        
        Args:
            video_id: ID ของวิดีโอ
            days: จำนวนวันที่จะวิเคราะห์
            
        Returns:
            PerformanceScore หรือ None ถ้าไม่มีข้อมูล
        """
        video = self.video_repo.get_by_id(video_id)
        if not video:
            logger.warning(f"ไม่พบวิดีโอ ID: {video_id}")
            return None
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        metrics = self.metric_repo.get_video_metrics(video_id, start_date, end_date)
        if not metrics:
            logger.warning(f"ไม่มี metrics สำหรับวิดีโอ ID: {video_id}")
            return None
        
        # แปลงเป็น DataFrame
        df = pd.DataFrame([{
            "date": m.date,
            "views": m.views,
            "likes": m.likes,
            "comments": m.comments,
            "watch_time": m.watch_time_minutes,
            "avg_view_percentage": m.average_view_percentage,
        } for m in metrics])
        
        # คำนวณ scores (0-100)
        view_score = self._calculate_view_score(df)
        engagement_score = self._calculate_engagement_score(df)
        retention_score = self._calculate_retention_score(df)
        growth_score = self._calculate_growth_score(df)
        
        # Overall score (weighted average)
        overall_score = (
            view_score * 0.3 +
            engagement_score * 0.3 +
            retention_score * 0.25 +
            growth_score * 0.15
        )
        
        return PerformanceScore(
            video_id=video_id,
            overall_score=round(overall_score, 2),
            view_score=round(view_score, 2),
            engagement_score=round(engagement_score, 2),
            retention_score=round(retention_score, 2),
            growth_score=round(growth_score, 2),
        )
    
    def _calculate_view_score(self, df: pd.DataFrame) -> float:
        """คำนวณ view score"""
        if df.empty or df["views"].sum() == 0:
            return 0.0
        
        total_views = df["views"].sum()
        avg_daily_views = df["views"].mean()
        
        # Normalize to 0-100 (ปรับตามขนาด channel)
        # สมมติว่า 10,000 views/day = 100 score
        score = min(100, (avg_daily_views / 10000) * 100)
        return score
    
    def _calculate_engagement_score(self, df: pd.DataFrame) -> float:
        """คำนวณ engagement score"""
        if df.empty or df["views"].sum() == 0:
            return 0.0
        
        total_views = df["views"].sum()
        total_likes = df["likes"].sum()
        total_comments = df["comments"].sum()
        
        # Engagement rate
        engagement_rate = ((total_likes + total_comments) / total_views) * 100
        
        # Normalize to 0-100 (5% engagement = 100 score)
        score = min(100, (engagement_rate / 5) * 100)
        return score
    
    def _calculate_retention_score(self, df: pd.DataFrame) -> float:
        """คำนวณ retention score"""
        if df.empty:
            return 0.0
        
        avg_view_percentage = df["avg_view_percentage"].mean()
        
        # 50% retention = 100 score
        score = min(100, (avg_view_percentage / 50) * 100)
        return score
    
    def _calculate_growth_score(self, df: pd.DataFrame) -> float:
        """คำนวณ growth score"""
        if len(df) < 7:
            return 50.0  # Neutral score if not enough data
        
        # เปรียบเทียบ 7 วันแรกกับ 7 วันหลัง
        first_week = df.head(7)["views"].sum()
        last_week = df.tail(7)["views"].sum()
        
        if first_week == 0:
            return 50.0
        
        growth_rate = ((last_week - first_week) / first_week) * 100
        
        # Normalize: -50% to +50% growth = 0-100 score
        score = 50 + growth_rate
        score = max(0, min(100, score))
        return score
    
    def analyze_trends(
        self,
        video_id: int,
        period_days: int = 7,
    ) -> List[TrendAnalysis]:
        """
        วิเคราะห์ trends ของวิดีโอ
        
        Args:
            video_id: ID ของวิดีโอ
            period_days: จำนวนวันในแต่ละ period
            
        Returns:
            List ของ TrendAnalysis
        """
        end_date = date.today()
        mid_date = end_date - timedelta(days=period_days)
        start_date = mid_date - timedelta(days=period_days)
        
        # ดึง metrics สำหรับทั้ง 2 periods
        current_metrics = self.metric_repo.get_video_metrics(video_id, mid_date, end_date)
        previous_metrics = self.metric_repo.get_video_metrics(video_id, start_date, mid_date)
        
        trends = []
        metrics_to_analyze = ["views", "likes", "comments", "watch_time_minutes"]
        
        for metric_name in metrics_to_analyze:
            current_sum = sum(getattr(m, metric_name, 0) for m in current_metrics)
            previous_sum = sum(getattr(m, metric_name, 0) for m in previous_metrics)
            
            if previous_sum > 0:
                change_percent = ((current_sum - previous_sum) / previous_sum) * 100
            else:
                change_percent = 100.0 if current_sum > 0 else 0.0
            
            # กำหนด trend direction
            if change_percent > 5:
                direction = "up"
            elif change_percent < -5:
                direction = "down"
            else:
                direction = "stable"
            
            trends.append(TrendAnalysis(
                metric_name=metric_name,
                current_value=current_sum,
                previous_value=previous_sum,
                change_percent=round(change_percent, 2),
                trend_direction=direction,
                is_significant=abs(change_percent) > 20,
            ))
        
        return trends
    
    def get_channel_summary(self, channel_id: Optional[str] = None) -> Dict[str, Any]:
        """
        สรุปข้อมูลของ channel
        
        Args:
            channel_id: ID ของ channel (ถ้าไม่ระบุจะใช้ทุก videos)
            
        Returns:
            Dictionary ของข้อมูลสรุป
        """
        self.task_logger.start("กำลังสรุปข้อมูล channel")
        
        # ดึงวิดีโอ
        if channel_id:
            videos = self.video_repo.get_by_channel(channel_id)
        else:
            videos = self.video_repo.get_all(limit=1000)
        
        if not videos:
            return {"error": "ไม่พบวิดีโอ"}
        
        # คำนวณสถิติ
        total_videos = len(videos)
        total_views = sum(v.view_count for v in videos)
        total_likes = sum(v.like_count for v in videos)
        total_comments = sum(v.comment_count for v in videos)
        
        avg_views = total_views / total_videos if total_videos > 0 else 0
        avg_likes = total_likes / total_videos if total_videos > 0 else 0
        
        # Top videos
        top_by_views = sorted(videos, key=lambda v: v.view_count, reverse=True)[:5]
        top_by_engagement = sorted(
            videos,
            key=lambda v: (v.like_count + v.comment_count) / max(v.view_count, 1),
            reverse=True
        )[:5]
        
        self.task_logger.complete("สรุปข้อมูลเสร็จสิ้น")
        
        return {
            "total_videos": total_videos,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "average_views": round(avg_views, 2),
            "average_likes": round(avg_likes, 2),
            "engagement_rate": round((total_likes + total_comments) / max(total_views, 1) * 100, 2),
            "top_by_views": [{"id": v.id, "title": v.title, "views": v.view_count} for v in top_by_views],
            "top_by_engagement": [{"id": v.id, "title": v.title} for v in top_by_engagement],
        }
    
    def compare_videos(self, video_ids: List[int]) -> pd.DataFrame:
        """
        เปรียบเทียบ performance ของหลายวิดีโอ
        
        Args:
            video_ids: List ของ video IDs
            
        Returns:
            DataFrame ของการเปรียบเทียบ
        """
        comparisons = []
        
        for video_id in video_ids:
            video = self.video_repo.get_by_id(video_id)
            if not video:
                continue
            
            score = self.calculate_performance_score(video_id)
            stats = self.metric_repo.get_aggregate_stats(video_id)
            
            comparisons.append({
                "video_id": video_id,
                "title": video.title[:50],
                "view_count": video.view_count,
                "like_count": video.like_count,
                "comment_count": video.comment_count,
                "overall_score": score.overall_score if score else 0,
                "engagement_score": score.engagement_score if score else 0,
                **stats,
            })
        
        return pd.DataFrame(comparisons)
    
    def get_best_posting_times(self, days: int = 90) -> Dict[str, List[int]]:
        """
        วิเคราะห์เวลาที่ดีที่สุดในการโพสต์
        
        Args:
            days: จำนวนวันที่จะวิเคราะห์
            
        Returns:
            Dictionary ของวันและชั่วโมงที่ดีที่สุด
        """
        videos = self.video_repo.get_recent(days=days, limit=100)
        
        if not videos:
            return {"best_days": [], "best_hours": []}
        
        # วิเคราะห์ตามวันและเวลา
        day_performance = {i: [] for i in range(7)}  # 0=Monday
        hour_performance = {i: [] for i in range(24)}
        
        for video in videos:
            if not video.published_at:
                continue
            
            day = video.published_at.weekday()
            hour = video.published_at.hour
            
            # ใช้ engagement rate เป็น metric
            if video.view_count > 0:
                engagement = (video.like_count + video.comment_count) / video.view_count
                day_performance[day].append(engagement)
                hour_performance[hour].append(engagement)
        
        # หาวันและเวลาที่ดีที่สุด
        best_days = sorted(
            day_performance.keys(),
            key=lambda d: np.mean(day_performance[d]) if day_performance[d] else 0,
            reverse=True
        )[:3]
        
        best_hours = sorted(
            hour_performance.keys(),
            key=lambda h: np.mean(hour_performance[h]) if hour_performance[h] else 0,
            reverse=True
        )[:5]
        
        return {
            "best_days": best_days,
            "best_hours": best_hours,
            "day_names": ["จันทร์", "อังคาร", "พุธ", "พฤหัส", "ศุกร์", "เสาร์", "อาทิตย์"],
        }
    
    def generate_insights(self, video_id: Optional[int] = None) -> List[str]:
        """
        สร้าง insights อัตโนมัติ
        
        Args:
            video_id: ID ของวิดีโอ (ถ้าไม่ระบุจะวิเคราะห์ทั้ง channel)
            
        Returns:
            List ของ insights
        """
        insights = []
        
        if video_id:
            # Insights สำหรับวิดีโอเดียว
            score = self.calculate_performance_score(video_id)
            trends = self.analyze_trends(video_id)
            
            if score:
                if score.overall_score >= 70:
                    insights.append(f"🎉 วิดีโอนี้มี performance ดีมาก (คะแนน: {score.overall_score})")
                elif score.overall_score < 30:
                    insights.append(f"⚠️ วิดีโอนี้ต้องการการปรับปรุง (คะแนน: {score.overall_score})")
                
                if score.engagement_score < score.view_score:
                    insights.append("💡 มี views ดีแต่ engagement ต่ำ - ลองปรับปรุง CTA")
                
                if score.retention_score < 50:
                    insights.append("📉 Retention ต่ำ - ลองปรับปรุงเนื้อหาช่วงเปิด")
            
            for trend in trends:
                if trend.is_significant and trend.trend_direction == "up":
                    insights.append(f"📈 {trend.metric_name} เพิ่มขึ้น {trend.change_percent:.1f}%")
                elif trend.is_significant and trend.trend_direction == "down":
                    insights.append(f"📉 {trend.metric_name} ลดลง {abs(trend.change_percent):.1f}%")
        else:
            # Insights สำหรับทั้ง channel
            summary = self.get_channel_summary()
            posting_times = self.get_best_posting_times()
            
            if summary.get("engagement_rate", 0) > 5:
                insights.append("🎯 Engagement rate ดีมาก!")
            elif summary.get("engagement_rate", 0) < 2:
                insights.append("💡 ลองเพิ่ม engagement ด้วย CTA และ community posts")
            
            if posting_times["best_days"]:
                day_names = posting_times["day_names"]
                best_day = day_names[posting_times["best_days"][0]]
                insights.append(f"📅 วัน{best_day}เป็นวันที่ดีที่สุดในการโพสต์")
            
            if posting_times["best_hours"]:
                best_hour = posting_times["best_hours"][0]
                insights.append(f"⏰ เวลา {best_hour}:00 น. เป็นเวลาที่ดีที่สุดในการโพสต์")
        
        return insights
