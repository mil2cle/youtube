"""
YouTube Client Module - ดึงข้อมูลจาก YouTube Data API และ Analytics API
รองรับ:
- ดึงรายการวิดีโอจาก channel
- ดึง metrics รายวันสำหรับแต่ละวิดีโอ
- Incremental fetch (ดึงเฉพาะข้อมูลใหม่)
"""

import time
import re
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple, Generator
from dataclasses import dataclass, field

import isodate
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from src.youtube.oauth import YouTubeAuth, get_youtube_auth
from src.db.models import Video, DailyMetric
from src.db.repository import VideoRepository, DailyMetricRepository
from src.db.connection import session_scope
from src.utils.logger import get_logger, TaskLogger
from src.utils.config import get_config

logger = get_logger()


@dataclass
class VideoData:
    """ข้อมูลวิดีโอจาก YouTube API"""
    youtube_id: str
    title: str
    description: str
    channel_id: str
    channel_name: str
    published_at: datetime
    duration_seconds: int
    tags: List[str] = field(default_factory=list)
    category_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0


@dataclass
class MetricData:
    """ข้อมูล metrics รายวันจาก YouTube Analytics API"""
    video_id: str
    date: date
    views: int = 0
    estimated_minutes_watched: float = 0.0
    average_view_duration: float = 0.0
    average_view_percentage: float = 0.0
    likes: int = 0
    dislikes: int = 0
    comments: int = 0
    shares: int = 0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    annotation_ctr: float = 0.0
    card_click_rate: float = 0.0
    impressions: int = 0
    impressions_ctr: float = 0.0


@dataclass
class FetchResult:
    """ผลลัพธ์การดึงข้อมูล"""
    success: bool
    videos_fetched: int = 0
    videos_created: int = 0
    videos_updated: int = 0
    metrics_fetched: int = 0
    metrics_created: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class YouTubeClient:
    """
    Client สำหรับดึงข้อมูลจาก YouTube API
    
    รองรับ:
    - ดึงรายการวิดีโอทั้งหมดจาก channel
    - ดึง metrics รายวันสำหรับแต่ละวิดีโอ
    - Incremental fetch
    - Rate limiting
    
    Usage:
        client = YouTubeClient()
        
        # ดึงวิดีโอทั้งหมด
        result = client.fetch_all_videos()
        
        # ดึง metrics 30 วันล่าสุด
        result = client.fetch_daily_metrics(days=30)
    """
    
    def __init__(
        self,
        auth: Optional[YouTubeAuth] = None,
        session: Optional[Session] = None,
    ):
        """
        Initialize YouTubeClient
        
        Args:
            auth: YouTubeAuth instance (default: singleton)
            session: SQLAlchemy session (default: None, จะสร้างใหม่เมื่อต้องการ)
        """
        self.auth = auth or get_youtube_auth()
        self.session = session
        self.config = get_config()
        
        self._youtube: Optional[Resource] = None
        self._analytics: Optional[Resource] = None
        self._channel_id: Optional[str] = None
        
        # Rate limiting
        self.rate_limit_delay = self.config.youtube.fetch.rate_limit_delay
    
    @property
    def youtube(self) -> Resource:
        """ดึง YouTube Data API service"""
        if not self._youtube:
            self._youtube = self.auth.get_youtube_service()
            if not self._youtube:
                raise RuntimeError("ไม่สามารถสร้าง YouTube service - กรุณา authenticate ก่อน")
        return self._youtube
    
    @property
    def analytics(self) -> Resource:
        """ดึง YouTube Analytics API service"""
        if not self._analytics:
            self._analytics = self.auth.get_analytics_service()
            if not self._analytics:
                raise RuntimeError("ไม่สามารถสร้าง Analytics service - กรุณา authenticate ก่อน")
        return self._analytics
    
    @property
    def channel_id(self) -> str:
        """ดึง channel ID ของ authenticated user"""
        if not self._channel_id:
            # ลองใช้จาก config ก่อน
            config_channel_id = self.config.youtube.channel_id
            if config_channel_id:
                self._channel_id = config_channel_id
            else:
                # ดึงจาก API
                response = self.youtube.channels().list(
                    part="id",
                    mine=True,
                ).execute()
                
                if response.get("items"):
                    self._channel_id = response["items"][0]["id"]
                else:
                    raise RuntimeError("ไม่พบ channel สำหรับ authenticated user")
        
        return self._channel_id
    
    def _parse_duration(self, duration_str: str) -> int:
        """
        แปลง ISO 8601 duration เป็นวินาที
        
        Args:
            duration_str: เช่น "PT10M30S"
            
        Returns:
            จำนวนวินาที
        """
        try:
            duration = isodate.parse_duration(duration_str)
            return int(duration.total_seconds())
        except Exception:
            return 0
    
    def _get_uploads_playlist_id(self) -> str:
        """
        ดึง uploads playlist ID ของ channel
        
        Returns:
            Playlist ID
        """
        response = self.youtube.channels().list(
            part="contentDetails",
            id=self.channel_id,
        ).execute()
        
        if not response.get("items"):
            raise RuntimeError(f"ไม่พบ channel: {self.channel_id}")
        
        return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    def _fetch_video_details(self, video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        ดึงรายละเอียดวิดีโอจาก video IDs
        
        Args:
            video_ids: List ของ video IDs (สูงสุด 50)
            
        Returns:
            Dictionary ของ video_id -> video details
        """
        if not video_ids:
            return {}
        
        response = self.youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(video_ids),
        ).execute()
        
        result = {}
        for item in response.get("items", []):
            video_id = item["id"]
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})
            
            result[video_id] = {
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel_id": snippet.get("channelId", ""),
                "channel_name": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "tags": snippet.get("tags", []),
                "category_id": snippet.get("categoryId"),
                "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url"),
                "duration": content_details.get("duration", "PT0S"),
                "view_count": int(statistics.get("viewCount", 0)),
                "like_count": int(statistics.get("likeCount", 0)),
                "comment_count": int(statistics.get("commentCount", 0)),
            }
        
        return result
    
    def fetch_all_videos(
        self,
        max_results: Optional[int] = None,
    ) -> Generator[VideoData, None, None]:
        """
        ดึงวิดีโอทั้งหมดจาก channel
        
        Args:
            max_results: จำนวนวิดีโอสูงสุด (None = ทั้งหมด)
            
        Yields:
            VideoData objects
        """
        task_logger = TaskLogger("FetchVideos")
        task_logger.start("เริ่มดึงรายการวิดีโอจาก YouTube")
        
        try:
            uploads_playlist_id = self._get_uploads_playlist_id()
            task_logger.step(f"พบ uploads playlist: {uploads_playlist_id}")
            
            page_token = None
            total_fetched = 0
            batch_size = min(50, max_results or 50)
            
            while True:
                # ดึงรายการวิดีโอจาก playlist
                response = self.youtube.playlistItems().list(
                    part="snippet",
                    playlistId=uploads_playlist_id,
                    maxResults=batch_size,
                    pageToken=page_token,
                ).execute()
                
                items = response.get("items", [])
                if not items:
                    break
                
                # ดึง video IDs
                video_ids = [
                    item["snippet"]["resourceId"]["videoId"]
                    for item in items
                    if item["snippet"]["resourceId"]["kind"] == "youtube#video"
                ]
                
                # ดึงรายละเอียดวิดีโอ
                video_details = self._fetch_video_details(video_ids)
                
                for video_id, details in video_details.items():
                    # แปลง published_at
                    published_at = datetime.fromisoformat(
                        details["published_at"].replace("Z", "+00:00")
                    )
                    
                    yield VideoData(
                        youtube_id=video_id,
                        title=details["title"],
                        description=details["description"],
                        channel_id=details["channel_id"],
                        channel_name=details["channel_name"],
                        published_at=published_at,
                        duration_seconds=self._parse_duration(details["duration"]),
                        tags=details["tags"],
                        category_id=details["category_id"],
                        thumbnail_url=details["thumbnail_url"],
                        view_count=details["view_count"],
                        like_count=details["like_count"],
                        comment_count=details["comment_count"],
                    )
                    
                    total_fetched += 1
                    
                    if max_results and total_fetched >= max_results:
                        task_logger.complete(f"ดึงวิดีโอครบ {total_fetched} รายการ")
                        return
                
                task_logger.step(f"ดึงวิดีโอแล้ว {total_fetched} รายการ")
                
                # Rate limiting
                time.sleep(self.rate_limit_delay)
                
                # ตรวจสอบ pagination
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            
            task_logger.complete(f"ดึงวิดีโอทั้งหมด {total_fetched} รายการ")
            
        except HttpError as e:
            task_logger.fail(f"YouTube API error: {e}")
            raise
        except Exception as e:
            task_logger.fail(f"Error: {e}")
            raise
    
    def fetch_video_analytics(
        self,
        video_id: str,
        start_date: date,
        end_date: date,
    ) -> List[MetricData]:
        """
        ดึง analytics metrics สำหรับวิดีโอ
        
        Args:
            video_id: YouTube video ID
            start_date: วันที่เริ่มต้น
            end_date: วันที่สิ้นสุด
            
        Returns:
            List ของ MetricData
        """
        try:
            # YouTube Analytics API query
            # เพิ่ม impressions และ impressionsClickThroughRate ใน metrics
            response = self.analytics.reports().query(
                ids=f"channel=={self.channel_id}",
                startDate=start_date.strftime("%Y-%m-%d"),
                endDate=end_date.strftime("%Y-%m-%d"),
                metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,dislikes,comments,shares,subscribersGained,subscribersLost,annotationImpressions,annotationClickThroughRate",
                dimensions="day",
                filters=f"video=={video_id}",
                sort="day",
            ).execute()
            
            # ลองดึง impressions และ CTR จาก query แยกต่างหาก (เพราะบาง metrics ไม่สามารถดึงพร้อมกันได้)
            impressions_data = {}
            try:
                impressions_response = self.analytics.reports().query(
                    ids=f"channel=={self.channel_id}",
                    startDate=start_date.strftime("%Y-%m-%d"),
                    endDate=end_date.strftime("%Y-%m-%d"),
                    metrics="impressions,impressionsClickThroughRate",
                    dimensions="day",
                    filters=f"video=={video_id}",
                    sort="day",
                ).execute()
                
                # Parse impressions response
                imp_headers = [h["name"] for h in impressions_response.get("columnHeaders", [])]
                for row in impressions_response.get("rows", []):
                    row_dict = dict(zip(imp_headers, row))
                    day_str = row_dict.get("day", "")
                    if day_str:
                        impressions_data[day_str] = {
                            "impressions": int(row_dict.get("impressions", 0)) if row_dict.get("impressions") is not None else None,
                            "impressions_ctr": float(row_dict.get("impressionsClickThroughRate", 0)) if row_dict.get("impressionsClickThroughRate") is not None else None,
                        }
            except HttpError as e:
                # Impressions metrics อาจไม่พร้อมใช้งานสำหรับบางวิดีโอ (เช่น Shorts)
                logger.debug(f"ไม่สามารถดึง impressions สำหรับวิดีโอ {video_id}: {e}")
            except Exception as e:
                logger.debug(f"Error fetching impressions for {video_id}: {e}")
            
            results = []
            
            # Parse response
            column_headers = [h["name"] for h in response.get("columnHeaders", [])]
            
            for row in response.get("rows", []):
                row_dict = dict(zip(column_headers, row))
                
                # Parse date
                day_str = row_dict.get("day", "")
                if day_str:
                    metric_date = datetime.strptime(day_str, "%Y-%m-%d").date()
                else:
                    continue
                
                # ดึงข้อมูล impressions สำหรับวันนี้ (ถ้ามี)
                day_impressions = impressions_data.get(day_str, {})
                
                results.append(MetricData(
                    video_id=video_id,
                    date=metric_date,
                    views=int(row_dict.get("views", 0)),
                    estimated_minutes_watched=float(row_dict.get("estimatedMinutesWatched", 0)),
                    average_view_duration=float(row_dict.get("averageViewDuration", 0)),
                    average_view_percentage=float(row_dict.get("averageViewPercentage", 0)),
                    likes=int(row_dict.get("likes", 0)),
                    dislikes=int(row_dict.get("dislikes", 0)),
                    comments=int(row_dict.get("comments", 0)),
                    shares=int(row_dict.get("shares", 0)),
                    subscribers_gained=int(row_dict.get("subscribersGained", 0)),
                    subscribers_lost=int(row_dict.get("subscribersLost", 0)),
                    impressions=day_impressions.get("impressions"),
                    impressions_ctr=day_impressions.get("impressions_ctr"),
                ))
            
            return results
            
        except HttpError as e:
            if e.resp.status == 403:
                logger.warning(f"ไม่มีสิทธิ์ดึง analytics สำหรับวิดีโอ {video_id}")
            else:
                logger.error(f"YouTube Analytics API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching analytics for {video_id}: {e}")
            return []
    
    def fetch_channel_analytics(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        ดึง analytics metrics สำหรับ channel ทั้งหมด
        
        Args:
            start_date: วันที่เริ่มต้น
            end_date: วันที่สิ้นสุด
            
        Returns:
            Dictionary ของ metrics
        """
        try:
            response = self.analytics.reports().query(
                ids=f"channel=={self.channel_id}",
                startDate=start_date.strftime("%Y-%m-%d"),
                endDate=end_date.strftime("%Y-%m-%d"),
                metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost",
                dimensions="day",
                sort="day",
            ).execute()
            
            return response
            
        except HttpError as e:
            logger.error(f"YouTube Analytics API error: {e}")
            return {}
    
    def sync_videos_to_db(
        self,
        session: Session,
        max_results: Optional[int] = None,
    ) -> FetchResult:
        """
        ดึงวิดีโอและบันทึกลงฐานข้อมูล (dedupe by youtube_id)
        
        Args:
            session: SQLAlchemy session
            max_results: จำนวนวิดีโอสูงสุด
            
        Returns:
            FetchResult
        """
        task_logger = TaskLogger("SyncVideos")
        task_logger.start("เริ่ม sync วิดีโอลงฐานข้อมูล")
        
        start_time = time.time()
        result = FetchResult(success=True)
        
        video_repo = VideoRepository(session)
        
        try:
            for video_data in self.fetch_all_videos(max_results=max_results):
                result.videos_fetched += 1
                
                # ตรวจสอบว่ามีอยู่แล้วหรือไม่
                existing = video_repo.get_by_youtube_id(video_data.youtube_id)
                
                if existing:
                    # อัพเดทข้อมูล
                    existing.title = video_data.title
                    existing.description = video_data.description
                    existing.view_count = video_data.view_count
                    existing.like_count = video_data.like_count
                    existing.comment_count = video_data.comment_count
                    existing.thumbnail_url = video_data.thumbnail_url
                    existing.updated_at = datetime.now()
                    result.videos_updated += 1
                else:
                    # สร้างใหม่
                    video = Video(
                        youtube_id=video_data.youtube_id,
                        title=video_data.title,
                        description=video_data.description,
                        channel_id=video_data.channel_id,
                        channel_name=video_data.channel_name,
                        published_at=video_data.published_at,
                        duration_seconds=video_data.duration_seconds,
                        tags={"tags": video_data.tags},
                        category=video_data.category_id,
                        thumbnail_url=video_data.thumbnail_url,
                        view_count=video_data.view_count,
                        like_count=video_data.like_count,
                        comment_count=video_data.comment_count,
                    )
                    session.add(video)
                    result.videos_created += 1
            
            session.commit()
            result.duration_seconds = time.time() - start_time
            
            task_logger.complete(
                f"Sync สำเร็จ: {result.videos_created} สร้างใหม่, "
                f"{result.videos_updated} อัพเดท"
            )
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            task_logger.fail(str(e))
            session.rollback()
        
        return result
    
    def sync_daily_metrics_to_db(
        self,
        session: Session,
        days: int = 30,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        incremental: bool = True,
    ) -> FetchResult:
        """
        ดึง daily metrics และบันทึกลงฐานข้อมูล
        
        Args:
            session: SQLAlchemy session
            days: จำนวนวันที่จะดึง (ใช้ถ้าไม่ระบุ start_date)
            start_date: วันที่เริ่มต้น
            end_date: วันที่สิ้นสุด (default: วันนี้)
            incremental: ดึงเฉพาะข้อมูลใหม่ตั้งแต่วันที่ล่าสุดในฐานข้อมูล
            
        Returns:
            FetchResult
        """
        task_logger = TaskLogger("SyncMetrics")
        task_logger.start("เริ่ม sync daily metrics ลงฐานข้อมูล")
        
        start_time = time.time()
        result = FetchResult(success=True)
        
        video_repo = VideoRepository(session)
        metric_repo = DailyMetricRepository(session)
        
        # กำหนดช่วงวันที่
        if not end_date:
            end_date = date.today() - timedelta(days=1)  # ข้อมูลล่าสุดคือเมื่อวาน
        
        if not start_date:
            start_date = end_date - timedelta(days=days - 1)
        
        try:
            # ดึงวิดีโอทั้งหมดจากฐานข้อมูล
            videos = video_repo.get_all(limit=10000)
            task_logger.step(f"พบวิดีโอในฐานข้อมูล {len(videos)} รายการ")
            
            for video in videos:
                # ถ้า incremental ให้ดึงตั้งแต่วันที่ล่าสุด
                video_start_date = start_date
                
                if incremental:
                    last_metric = metric_repo.get_latest_for_video(video.id)
                    if last_metric:
                        # เริ่มจากวันถัดไป
                        video_start_date = max(
                            start_date,
                            last_metric.date + timedelta(days=1)
                        )
                
                # ข้ามถ้าไม่มีช่วงวันที่ที่ต้องดึง
                if video_start_date > end_date:
                    continue
                
                task_logger.step(
                    f"กำลังดึง metrics สำหรับ: {video.title[:30]}... "
                    f"({video_start_date} - {end_date})"
                )
                
                # ดึง metrics
                metrics = self.fetch_video_analytics(
                    video_id=video.youtube_id,
                    start_date=video_start_date,
                    end_date=end_date,
                )
                
                for metric_data in metrics:
                    result.metrics_fetched += 1
                    
                    # ตรวจสอบว่ามีอยู่แล้วหรือไม่
                    existing = metric_repo.get_by_video_and_date(
                        video.id,
                        metric_data.date,
                    )
                    
                    if not existing:
                        metric = DailyMetric(
                            video_id=video.id,
                            date=metric_data.date,
                            views=metric_data.views,
                            watch_time_minutes=metric_data.estimated_minutes_watched,
                            average_view_duration=metric_data.average_view_duration,
                            average_view_percentage=metric_data.average_view_percentage,
                            likes=metric_data.likes,
                            comments=metric_data.comments,
                            shares=metric_data.shares,
                            subscribers_gained=metric_data.subscribers_gained,
                            impressions=metric_data.impressions,
                            impressions_ctr=metric_data.impressions_ctr,
                        )
                        session.add(metric)
                        result.metrics_created += 1
                
                # Rate limiting
                time.sleep(self.rate_limit_delay)
            
            session.commit()
            result.duration_seconds = time.time() - start_time
            
            task_logger.complete(
                f"Sync metrics สำเร็จ: {result.metrics_created} รายการใหม่"
            )
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            task_logger.fail(str(e))
            session.rollback()
        
        return result


# Singleton instance
_client_instance: Optional[YouTubeClient] = None


def get_youtube_client() -> YouTubeClient:
    """
    ดึง YouTubeClient instance (singleton)
    
    Returns:
        YouTubeClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = YouTubeClient()
    return _client_instance


def reset_youtube_client() -> None:
    """รีเซ็ต YouTubeClient instance"""
    global _client_instance
    _client_instance = None
