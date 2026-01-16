"""
Database Models - โมเดลฐานข้อมูลทั้งหมด
รวม tables: videos, daily_metrics, research_items, content_ideas, playbook_rules, runs_log
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class สำหรับ models ทั้งหมด"""
    pass


class Video(Base):
    """
    ตาราง videos - เก็บข้อมูลวิดีโอ YouTube
    
    เก็บข้อมูลพื้นฐานของวิดีโอ รวมถึง metadata และ performance metrics
    """
    __tablename__ = "videos"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # YouTube Video Info
    youtube_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Video Metadata
    channel_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # List of tags
    
    # Video Stats (snapshot at creation)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Publishing Info
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Internal Tracking
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, archived, deleted
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    daily_metrics: Mapped[List["DailyMetric"]] = relationship("DailyMetric", back_populates="video", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Video(id={self.id}, youtube_id='{self.youtube_id}', title='{self.title[:30]}...')>"


class DailyMetric(Base):
    """
    ตาราง daily_metrics - เก็บ metrics รายวันของแต่ละวิดีโอ
    
    ใช้สำหรับติดตาม performance และวิเคราะห์ trend
    """
    __tablename__ = "daily_metrics"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    video_id: Mapped[int] = mapped_column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    
    # Date
    date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    
    # Daily Stats
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    dislikes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    
    # Engagement Metrics
    watch_time_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    average_view_duration: Mapped[float] = mapped_column(Float, default=0.0)
    average_view_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Traffic Sources (JSON)
    traffic_sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Subscriber Impact
    subscribers_gained: Mapped[int] = mapped_column(Integer, default=0)
    subscribers_lost: Mapped[int] = mapped_column(Integer, default=0)
    
    # Revenue (if monetized)
    estimated_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    cpm: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Impressions & CTR (จาก YouTube Analytics API)
    # impressions: จำนวนครั้งที่ thumbnail แสดงบน YouTube
    # impressions_ctr: Click-through rate เป็นเปอร์เซ็นต์ (เช่น 5.5 หมายถึง 5.5%)
    impressions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    impressions_ctr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="daily_metrics")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("video_id", "date", name="uq_video_date"),
        Index("ix_daily_metrics_video_date", "video_id", "date"),
    )
    
    def __repr__(self) -> str:
        return f"<DailyMetric(video_id={self.video_id}, date={self.date}, views={self.views})>"


class ResearchItem(Base):
    """
    ตาราง research_items - เก็บข้อมูลการวิจัยและ trends
    
    ใช้สำหรับเก็บ insights จากการวิเคราะห์ตลาดและคู่แข่ง
    รองรับข้อมูลจาก AniList API, Anime News Network RSS และแหล่งอื่นๆ
    """
    __tablename__ = "research_items"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Research Info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)  # anilist, ann_rss, youtube_trending, google_trends, etc.
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Content
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # English summary
    summary_th: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Thai summary
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # raw_text
    keywords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # List of keywords
    
    # Entity Linking (Anime specific)
    entities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # List of anime titles/entities
    linked_series: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Normalized series data with AniList IDs
    
    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    topic: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    item_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # anime, news, trend, character, etc.
    
    # Metrics
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    trend_score: Mapped[float] = mapped_column(Float, default=0.0)
    reliability_score: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 - 1.0, source reliability
    competition_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # low, medium, high
    
    # AniList specific fields
    anilist_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    mal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # MyAnimeList ID
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="new")  # new, reviewed, applied, archived
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_linked: Mapped[bool] = mapped_column(Boolean, default=False)  # Entity linking completed
    
    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Original publish date
    researched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ResearchItem(id={self.id}, title='{self.title[:30]}...', source='{self.source}')>"


class ContentIdea(Base):
    """
    ตาราง content_ideas - เก็บไอเดียเนื้อหา
    
    ใช้สำหรับวางแผนและติดตามไอเดียวิดีโอ
    """
    __tablename__ = "content_ideas"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Basic Info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Categorization
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # tutorial, review, vlog, shorts, etc.
    sub_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Priority & Status
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # high, medium, low
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, in_progress, scheduled, published, archived
    
    # Planning
    target_audience: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    estimated_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    
    # Content Details
    outline: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Structured outline
    scripts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_ideas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Scoring
    potential_score: Mapped[float] = mapped_column(Float, default=0.0)  # Predicted performance
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Research Reference
    research_item_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("research_items.id", ondelete="SET NULL"), nullable=True)
    
    # Published Video Reference
    video_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ContentIdea(id={self.id}, title='{self.title[:30]}...', status='{self.status}')>"


class PlaybookRule(Base):
    """
    ตาราง playbook_rules - เก็บกฎการปรับปรุงตัวเอง
    
    ระบบจะเรียนรู้จาก patterns และสร้างกฎสำหรับปรับปรุง content strategy
    """
    __tablename__ = "playbook_rules"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Rule Info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Categorization
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Categories: title_optimization, thumbnail_strategy, posting_time, content_length, engagement_tactics
    
    # Rule Definition
    condition: Mapped[dict] = mapped_column(JSON, nullable=False)  # When to apply this rule
    action: Mapped[dict] = mapped_column(JSON, nullable=False)  # What to do
    
    # Learning Metrics
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 - 1.0
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)  # Historical success rate
    times_applied: Mapped[int] = mapped_column(Integer, default=0)
    times_successful: Mapped[int] = mapped_column(Integer, default=0)
    
    # Evidence
    supporting_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Data that supports this rule
    sample_videos: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Video IDs that demonstrate this rule
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)  # Generated by AI vs manual
    
    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("playbook_rules.id", ondelete="SET NULL"), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<PlaybookRule(id={self.id}, name='{self.name}', confidence={self.confidence_score:.2f})>"


class RunLog(Base):
    """
    ตาราง runs_log - เก็บ log การทำงานของระบบ
    
    ใช้สำหรับติดตาม jobs, tasks, และ system events
    """
    __tablename__ = "runs_log"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Run Info
    run_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    run_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Types: daily_metrics_collection, weekly_analysis, research_update, content_generation, rule_learning, manual
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="running")  # running, completed, failed, cancelled
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Details
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Input parameters
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Output/result data
    
    # Metrics
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    items_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error Handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Context
    triggered_by: Mapped[str] = mapped_column(String(100), default="system")  # system, scheduler, user, api
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Related Records
    related_videos: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # List of video IDs
    related_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # List of rule IDs
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("ix_runs_log_type_status", "run_type", "status"),
        Index("ix_runs_log_started_at", "started_at"),
    )
    
    def __repr__(self) -> str:
        return f"<RunLog(run_id='{self.run_id}', type='{self.run_type}', status='{self.status}')>"


# Helper function to get all models
def get_all_models() -> list:
    """คืนค่า list ของ models ทั้งหมด"""
    return [Video, DailyMetric, ResearchItem, ContentIdea, PlaybookRule, RunLog]
