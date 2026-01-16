"""
Configuration Module - จัดการการโหลดและเข้าถึง configuration
รองรับ YAML config files และ environment variables
"""

import os
from pathlib import Path
from typing import Any, Optional, List
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from rich.console import Console

console = Console()

# Default config path
DEFAULT_CONFIG_PATH = "configs/default.yaml"

# Global config storage
_config: dict = {}


class DatabaseConfig(BaseModel):
    """การตั้งค่าฐานข้อมูล"""
    type: str = "sqlite"
    path: str = "data/youtube_assistant.db"
    echo: bool = False


class YouTubeOAuthConfig(BaseModel):
    """การตั้งค่า YouTube OAuth"""
    client_secrets_file: str = ".secrets/client_secrets.json"
    token_file: str = ".secrets/token.json"
    scopes: List[str] = Field(default_factory=lambda: [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ])
    redirect_uri: str = "http://localhost:8080/"


class YouTubeFetchConfig(BaseModel):
    """การตั้งค่าการดึงข้อมูล YouTube"""
    default_days: int = 30
    incremental: bool = True
    batch_size: int = 50
    rate_limit_delay: float = 0.5


class YouTubeConfig(BaseModel):
    """การตั้งค่า YouTube API"""
    oauth: YouTubeOAuthConfig = Field(default_factory=YouTubeOAuthConfig)
    channel_id: str = ""
    max_results: int = 50
    quota_limit: int = 10000
    fetch: YouTubeFetchConfig = Field(default_factory=YouTubeFetchConfig)


class AnalyticsConfig(BaseModel):
    """การตั้งค่าการวิเคราะห์"""
    metrics_retention_days: int = 365
    trending_threshold: float = 1.5
    performance_window_days: int = 30
    metrics: List[str] = Field(default_factory=lambda: [
        "views",
        "estimatedMinutesWatched",
        "averageViewDuration",
        "averageViewPercentage",
        "likes",
        "dislikes",
        "comments",
        "shares",
        "subscribersGained",
        "subscribersLost",
    ])


class ContentConfig(BaseModel):
    """การตั้งค่า Content"""
    idea_categories: list[str] = Field(default_factory=lambda: ["tutorial", "review", "vlog", "shorts", "livestream"])
    priority_levels: list[str] = Field(default_factory=lambda: ["high", "medium", "low"])
    status_options: list[str] = Field(default_factory=lambda: ["draft", "in_progress", "scheduled", "published", "archived"])


class PlaybookConfig(BaseModel):
    """การตั้งค่า Playbook"""
    auto_learn: bool = True
    min_confidence_score: float = 0.7
    rule_categories: list[str] = Field(default_factory=lambda: [
        "title_optimization",
        "thumbnail_strategy",
        "posting_time",
        "content_length",
        "engagement_tactics",
    ])


class SchedulerJobConfig(BaseModel):
    """การตั้งค่า Scheduler Job"""
    name: str
    cron: str


class SchedulerConfig(BaseModel):
    """การตั้งค่า Scheduler"""
    enabled: bool = True
    timezone: str = "Asia/Bangkok"
    jobs: list[SchedulerJobConfig] = Field(default_factory=list)


class DashboardChartConfig(BaseModel):
    """การตั้งค่า Dashboard Charts"""
    default_days: int = 30
    colors: dict = Field(default_factory=lambda: {
        "primary": "#FF0000",
        "secondary": "#282828",
        "accent": "#AAAAAA",
    })


class DashboardConfig(BaseModel):
    """การตั้งค่า Dashboard"""
    host: str = "0.0.0.0"
    port: int = 8501
    theme: str = "dark"
    refresh_interval: int = 60
    charts: DashboardChartConfig = Field(default_factory=DashboardChartConfig)


class AnimeResearchConfig(BaseModel):
    """การตั้งค่า Anime Research"""
    enabled: bool = True
    default_days: int = 7
    incremental: bool = True
    
    # AniList API settings
    anilist_enabled: bool = True
    anilist_rate_limit_delay: float = 0.7
    anilist_trending_limit: int = 20
    anilist_seasonal_limit: int = 30
    anilist_top_limit: int = 20
    
    # RSS Feed settings
    rss_enabled: bool = True
    rss_sources: List[str] = Field(default_factory=lambda: ["ann", "ann_interest", "crunchyroll", "mal_news"])
    rss_limit_per_source: int = 50
    
    # Entity Linker settings
    entity_linking_enabled: bool = True
    entity_cache_ttl_hours: int = 24
    entity_min_confidence: float = 0.6


class ResearchConfig(BaseModel):
    """การตั้งค่า Research"""
    sources: list[str] = Field(default_factory=lambda: ["youtube_trending", "google_trends", "social_media"])
    keywords_limit: int = 100
    update_frequency_hours: int = 24
    anime: AnimeResearchConfig = Field(default_factory=AnimeResearchConfig)


class LoggingConfig(BaseModel):
    """การตั้งค่า Logging"""
    file: str = "logs/app.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class ExportConfig(BaseModel):
    """การตั้งค่า Export"""
    formats: list[str] = Field(default_factory=lambda: ["csv", "json", "xlsx"])
    output_dir: str = "exports"


class AppConfig(BaseModel):
    """การตั้งค่าแอปพลิเคชันหลัก"""
    name: str = "YouTube Content Assistant"
    version: str = "1.1.0"
    debug: bool = True
    log_level: str = "INFO"


class Config(BaseModel):
    """Configuration หลักของระบบ"""
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    content: ContentConfig = Field(default_factory=ContentConfig)
    playbook: PlaybookConfig = Field(default_factory=PlaybookConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)


def load_yaml_config(config_path: str) -> dict:
    """
    โหลด configuration จากไฟล์ YAML
    
    Args:
        config_path: path ไปยังไฟล์ config
        
    Returns:
        Dictionary ของ configuration
    """
    path = Path(config_path)
    if not path.exists():
        console.print(f"[yellow]![/yellow] ไม่พบไฟล์ config: {config_path}, ใช้ค่าเริ่มต้น")
        return {}
    
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    
    console.print(f"[green]✓[/green] โหลด config สำเร็จ: {config_path}")
    return config


def merge_configs(base: dict, override: dict) -> dict:
    """
    รวม configuration โดย override จะมีความสำคัญกว่า
    
    Args:
        base: config พื้นฐาน
        override: config ที่จะ override
        
    Returns:
        Merged configuration
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result


def load_config(
    config_path: str = DEFAULT_CONFIG_PATH,
    env_prefix: str = "YT_ASSISTANT_",
) -> Config:
    """
    โหลด configuration จากไฟล์และ environment variables
    
    Args:
        config_path: path ไปยังไฟล์ config
        env_prefix: prefix สำหรับ environment variables
        
    Returns:
        Config object
    """
    global _config
    
    # โหลดจากไฟล์ YAML
    yaml_config = load_yaml_config(config_path)
    
    # Override ด้วย environment variables
    env_overrides = {}
    for key, value in os.environ.items():
        if key.startswith(env_prefix):
            # แปลง YT_ASSISTANT_DATABASE_PATH เป็น database.path
            config_key = key[len(env_prefix):].lower().replace("_", ".", 1)
            parts = config_key.split(".", 1)
            if len(parts) == 2:
                section, setting = parts
                if section not in env_overrides:
                    env_overrides[section] = {}
                env_overrides[section][setting] = value
    
    # รวม configs
    merged = merge_configs(yaml_config, env_overrides)
    _config = merged
    
    # สร้าง Config object
    return Config(**merged)


@lru_cache()
def get_config() -> Config:
    """
    คืนค่า configuration (cached)
    
    Returns:
        Config object
    """
    return load_config()


def get_config_value(path: str, default: Any = None) -> Any:
    """
    ดึงค่า config ด้วย dot notation path
    
    Args:
        path: path เช่น "database.path"
        default: ค่าเริ่มต้นถ้าไม่พบ
        
    Returns:
        ค่า config หรือ default
        
    Example:
        db_path = get_config_value("database.path", "data/default.db")
    """
    config = get_config()
    
    parts = path.split(".")
    value = config.model_dump()
    
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default
    
    return value


def update_config(updates: dict) -> Config:
    """
    อัพเดท configuration ในหน่วยความจำ
    
    Args:
        updates: dictionary ของการอัพเดท
        
    Returns:
        Updated Config object
    """
    global _config
    _config = merge_configs(_config, updates)
    
    # Clear cache และสร้างใหม่
    get_config.cache_clear()
    return Config(**_config)


def save_config(config_path: str = DEFAULT_CONFIG_PATH) -> None:
    """
    บันทึก configuration ปัจจุบันลงไฟล์
    
    Args:
        config_path: path ไปยังไฟล์ config
    """
    config = get_config()
    
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)
    
    console.print(f"[green]✓[/green] บันทึก config สำเร็จ: {config_path}")
