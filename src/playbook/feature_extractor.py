"""
Feature Extractor - ดึง features จาก YouTube videos สำหรับ Playbook Learning

Features ที่ดึง:
1. Title Features:
   - ความยาว (characters, words)
   - มีตัวเลขหรือไม่
   - มีวงเล็บ [], () หรือไม่
   - มี emoji หรือไม่
   - มีคำถามหรือไม่
   - Keywords ที่พบบ่อย

2. Description Features:
   - ความยาว
   - จำนวน links
   - มี timestamps หรือไม่
   - มี hashtags หรือไม่

3. Publish Time Features:
   - วันในสัปดาห์
   - ชั่วโมง
   - ช่วงเวลา (เช้า/บ่าย/เย็น/ดึก)

4. Duration Features:
   - ความยาววิดีโอ (วินาที)
   - Duration bucket (Short/Medium/Long)
   - เป็น YouTube Shorts หรือไม่

5. Format Features:
   - ประเภทเนื้อหา (tutorial, review, vlog, etc.)
"""

import re
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd
from rich.console import Console

console = Console()


# Thai keywords ที่มักพบใน titles ที่ประสบความสำเร็จ
POSITIVE_KEYWORDS_TH = [
    "วิธี", "ทำยังไง", "สอน", "แนะนำ", "รีวิว", "เปรียบเทียบ",
    "ดีที่สุด", "ที่สุด", "อันดับ", "Top", "ฟรี", "ง่าย",
    "เร็ว", "ใหม่", "อัพเดท", "2024", "2025", "2026",
    "ครบ", "จบ", "ทุกอย่าง", "ต้องรู้", "ห้ามพลาด",
]

POSITIVE_KEYWORDS_EN = [
    "how to", "tutorial", "guide", "review", "best", "top",
    "free", "easy", "fast", "new", "update", "complete",
    "ultimate", "beginner", "advanced", "tips", "tricks",
    "vs", "comparison", "explained", "breakdown",
]

# Anime-specific keywords
ANIME_KEYWORDS = [
    "อนิเมะ", "anime", "manga", "มังงะ", "รีวิว", "สปอย",
    "ตอนจบ", "ending", "ซีซั่น", "season", "ep", "ตอน",
    "ตัวละคร", "character", "theory", "ทฤษฎี", "พากย์",
]

# Brackets patterns
BRACKET_PATTERNS = [
    (r'\[.*?\]', 'square_bracket'),
    (r'\(.*?\)', 'round_bracket'),
    (r'【.*?】', 'japanese_bracket'),
    (r'「.*?」', 'japanese_quote'),
    (r'『.*?』', 'japanese_double_quote'),
]

# Time periods (Thai timezone, GMT+7)
TIME_PERIODS = {
    'early_morning': (5, 8),    # 05:00 - 08:00
    'morning': (8, 12),          # 08:00 - 12:00
    'afternoon': (12, 17),       # 12:00 - 17:00
    'evening': (17, 21),         # 17:00 - 21:00
    'night': (21, 24),           # 21:00 - 24:00
    'late_night': (0, 5),        # 00:00 - 05:00
}

# Duration buckets
DURATION_BUCKETS = {
    'shorts': (0, 60),           # 0-60 seconds (YouTube Shorts)
    'very_short': (60, 180),     # 1-3 minutes
    'short': (180, 480),         # 3-8 minutes
    'medium': (480, 900),        # 8-15 minutes
    'long': (900, 1800),         # 15-30 minutes
    'very_long': (1800, float('inf')),  # 30+ minutes
}


@dataclass
class VideoFeatures:
    """โครงสร้างข้อมูล features ของวิดีโอ"""
    
    # Video ID
    video_id: str = ""
    youtube_video_id: str = ""
    
    # Title Features
    title_length_chars: int = 0
    title_length_words: int = 0
    title_has_number: bool = False
    title_has_year: bool = False
    title_has_square_bracket: bool = False
    title_has_round_bracket: bool = False
    title_has_japanese_bracket: bool = False
    title_has_emoji: bool = False
    title_has_question: bool = False
    title_has_exclamation: bool = False
    title_has_colon: bool = False
    title_has_pipe: bool = False
    title_is_all_caps: bool = False
    title_caps_ratio: float = 0.0
    title_positive_keywords_count: int = 0
    title_anime_keywords_count: int = 0
    
    # Description Features
    desc_length_chars: int = 0
    desc_length_words: int = 0
    desc_has_links: bool = False
    desc_link_count: int = 0
    desc_has_timestamps: bool = False
    desc_timestamp_count: int = 0
    desc_has_hashtags: bool = False
    desc_hashtag_count: int = 0
    desc_has_social_links: bool = False
    
    # Publish Time Features
    publish_hour: int = 0
    publish_day_of_week: int = 0  # 0=Monday, 6=Sunday
    publish_is_weekend: bool = False
    publish_time_period: str = "unknown"
    
    # Duration Features
    duration_seconds: int = 0
    duration_minutes: float = 0.0
    duration_bucket: str = "unknown"
    is_shorts: bool = False
    
    # Format Features
    format_type: str = "unknown"  # shorts, standard, long_form
    
    # Tags Features
    tags_count: int = 0
    tags_avg_length: float = 0.0
    
    # Target Variables (for training)
    views: int = 0
    likes: int = 0
    comments: int = 0
    ctr: float = 0.0  # Click-through rate
    avg_view_duration: float = 0.0
    avg_view_percentage: float = 0.0
    engagement_rate: float = 0.0
    
    # Performance Labels
    is_high_performer: bool = False
    performance_tier: str = "unknown"  # low, medium, high, viral
    
    def to_dict(self) -> Dict[str, Any]:
        """แปลงเป็น dictionary"""
        return asdict(self)
    
    def to_feature_vector(self) -> Dict[str, Any]:
        """แปลงเป็น feature vector สำหรับ ML model"""
        return {
            # Title features
            'title_length_chars': self.title_length_chars,
            'title_length_words': self.title_length_words,
            'title_has_number': int(self.title_has_number),
            'title_has_year': int(self.title_has_year),
            'title_has_square_bracket': int(self.title_has_square_bracket),
            'title_has_round_bracket': int(self.title_has_round_bracket),
            'title_has_japanese_bracket': int(self.title_has_japanese_bracket),
            'title_has_emoji': int(self.title_has_emoji),
            'title_has_question': int(self.title_has_question),
            'title_has_exclamation': int(self.title_has_exclamation),
            'title_has_colon': int(self.title_has_colon),
            'title_has_pipe': int(self.title_has_pipe),
            'title_caps_ratio': self.title_caps_ratio,
            'title_positive_keywords_count': self.title_positive_keywords_count,
            'title_anime_keywords_count': self.title_anime_keywords_count,
            
            # Description features
            'desc_length_chars': self.desc_length_chars,
            'desc_length_words': self.desc_length_words,
            'desc_has_links': int(self.desc_has_links),
            'desc_link_count': self.desc_link_count,
            'desc_has_timestamps': int(self.desc_has_timestamps),
            'desc_timestamp_count': self.desc_timestamp_count,
            'desc_has_hashtags': int(self.desc_has_hashtags),
            'desc_hashtag_count': self.desc_hashtag_count,
            
            # Publish time features (one-hot encoded)
            'publish_hour': self.publish_hour,
            'publish_day_of_week': self.publish_day_of_week,
            'publish_is_weekend': int(self.publish_is_weekend),
            'publish_is_morning': int(self.publish_time_period == 'morning'),
            'publish_is_afternoon': int(self.publish_time_period == 'afternoon'),
            'publish_is_evening': int(self.publish_time_period == 'evening'),
            'publish_is_night': int(self.publish_time_period == 'night'),
            
            # Duration features
            'duration_seconds': self.duration_seconds,
            'duration_minutes': self.duration_minutes,
            'is_shorts': int(self.is_shorts),
            'is_very_short': int(self.duration_bucket == 'very_short'),
            'is_short': int(self.duration_bucket == 'short'),
            'is_medium': int(self.duration_bucket == 'medium'),
            'is_long': int(self.duration_bucket == 'long'),
            'is_very_long': int(self.duration_bucket == 'very_long'),
            
            # Tags features
            'tags_count': self.tags_count,
            'tags_avg_length': self.tags_avg_length,
        }


class FeatureExtractor:
    """
    Feature Extractor สำหรับดึง features จาก YouTube videos
    
    การใช้งาน:
        extractor = FeatureExtractor()
        features = extractor.extract(video_data)
        df = extractor.extract_batch(videos_list)
    """
    
    def __init__(self):
        """สร้าง Feature Extractor"""
        self.positive_keywords = set(
            [k.lower() for k in POSITIVE_KEYWORDS_TH] +
            [k.lower() for k in POSITIVE_KEYWORDS_EN]
        )
        self.anime_keywords = set([k.lower() for k in ANIME_KEYWORDS])
        
        # Compile regex patterns
        self.emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        self.url_pattern = re.compile(r'https?://\S+')
        self.timestamp_pattern = re.compile(r'\d{1,2}:\d{2}(?::\d{2})?')
        self.hashtag_pattern = re.compile(r'#\w+')
        self.year_pattern = re.compile(r'\b(20[1-3]\d)\b')
        self.number_pattern = re.compile(r'\d+')
        
    def _extract_title_features(self, title: str) -> Dict[str, Any]:
        """ดึง features จาก title"""
        if not title:
            return {}
        
        title_lower = title.lower()
        words = title.split()
        
        # Basic length
        features = {
            'title_length_chars': len(title),
            'title_length_words': len(words),
        }
        
        # Number and year
        features['title_has_number'] = bool(self.number_pattern.search(title))
        features['title_has_year'] = bool(self.year_pattern.search(title))
        
        # Brackets
        features['title_has_square_bracket'] = '[' in title and ']' in title
        features['title_has_round_bracket'] = '(' in title and ')' in title
        features['title_has_japanese_bracket'] = '【' in title or '】' in title or '「' in title or '」' in title
        
        # Special characters
        features['title_has_emoji'] = bool(self.emoji_pattern.search(title))
        features['title_has_question'] = '?' in title or '？' in title
        features['title_has_exclamation'] = '!' in title or '！' in title
        features['title_has_colon'] = ':' in title or '：' in title
        features['title_has_pipe'] = '|' in title
        
        # Caps analysis
        alpha_chars = [c for c in title if c.isalpha()]
        if alpha_chars:
            upper_count = sum(1 for c in alpha_chars if c.isupper())
            features['title_caps_ratio'] = upper_count / len(alpha_chars)
            features['title_is_all_caps'] = features['title_caps_ratio'] > 0.8
        else:
            features['title_caps_ratio'] = 0.0
            features['title_is_all_caps'] = False
        
        # Keywords count
        positive_count = sum(1 for kw in self.positive_keywords if kw in title_lower)
        anime_count = sum(1 for kw in self.anime_keywords if kw in title_lower)
        features['title_positive_keywords_count'] = positive_count
        features['title_anime_keywords_count'] = anime_count
        
        return features
    
    def _extract_description_features(self, description: str) -> Dict[str, Any]:
        """ดึง features จาก description"""
        if not description:
            return {
                'desc_length_chars': 0,
                'desc_length_words': 0,
                'desc_has_links': False,
                'desc_link_count': 0,
                'desc_has_timestamps': False,
                'desc_timestamp_count': 0,
                'desc_has_hashtags': False,
                'desc_hashtag_count': 0,
                'desc_has_social_links': False,
            }
        
        words = description.split()
        
        # Links
        links = self.url_pattern.findall(description)
        social_domains = ['twitter.com', 'instagram.com', 'facebook.com', 'tiktok.com', 'discord.gg']
        has_social = any(any(domain in link for domain in social_domains) for link in links)
        
        # Timestamps
        timestamps = self.timestamp_pattern.findall(description)
        
        # Hashtags
        hashtags = self.hashtag_pattern.findall(description)
        
        return {
            'desc_length_chars': len(description),
            'desc_length_words': len(words),
            'desc_has_links': len(links) > 0,
            'desc_link_count': len(links),
            'desc_has_timestamps': len(timestamps) > 0,
            'desc_timestamp_count': len(timestamps),
            'desc_has_hashtags': len(hashtags) > 0,
            'desc_hashtag_count': len(hashtags),
            'desc_has_social_links': has_social,
        }
    
    def _extract_publish_time_features(self, published_at: datetime) -> Dict[str, Any]:
        """ดึง features จาก publish time"""
        if not published_at:
            return {
                'publish_hour': 0,
                'publish_day_of_week': 0,
                'publish_is_weekend': False,
                'publish_time_period': 'unknown',
            }
        
        # Adjust to Thai timezone (GMT+7)
        hour = (published_at.hour + 7) % 24
        day_of_week = published_at.weekday()
        
        # Determine time period
        time_period = 'unknown'
        for period, (start, end) in TIME_PERIODS.items():
            if period == 'late_night':
                if hour >= 0 and hour < 5:
                    time_period = period
                    break
            elif start <= hour < end:
                time_period = period
                break
        
        return {
            'publish_hour': hour,
            'publish_day_of_week': day_of_week,
            'publish_is_weekend': day_of_week >= 5,
            'publish_time_period': time_period,
        }
    
    def _extract_duration_features(self, duration_seconds: int) -> Dict[str, Any]:
        """ดึง features จาก duration"""
        if not duration_seconds or duration_seconds <= 0:
            return {
                'duration_seconds': 0,
                'duration_minutes': 0.0,
                'duration_bucket': 'unknown',
                'is_shorts': False,
                'format_type': 'unknown',
            }
        
        duration_minutes = duration_seconds / 60.0
        
        # Determine bucket
        duration_bucket = 'unknown'
        for bucket, (min_sec, max_sec) in DURATION_BUCKETS.items():
            if min_sec <= duration_seconds < max_sec:
                duration_bucket = bucket
                break
        
        is_shorts = duration_seconds <= 60
        
        # Format type
        if is_shorts:
            format_type = 'shorts'
        elif duration_seconds <= 600:  # 10 minutes
            format_type = 'standard'
        else:
            format_type = 'long_form'
        
        return {
            'duration_seconds': duration_seconds,
            'duration_minutes': duration_minutes,
            'duration_bucket': duration_bucket,
            'is_shorts': is_shorts,
            'format_type': format_type,
        }
    
    def _extract_tags_features(self, tags: List[str]) -> Dict[str, Any]:
        """ดึง features จาก tags"""
        if not tags:
            return {
                'tags_count': 0,
                'tags_avg_length': 0.0,
            }
        
        avg_length = sum(len(tag) for tag in tags) / len(tags)
        
        return {
            'tags_count': len(tags),
            'tags_avg_length': avg_length,
        }
    
    def _calculate_performance_metrics(
        self,
        views: int,
        likes: int,
        comments: int,
        impressions: int = 0,
        avg_view_duration: float = 0.0,
        duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """คำนวณ performance metrics"""
        
        # CTR
        ctr = (views / impressions * 100) if impressions > 0 else 0.0
        
        # Average view percentage
        avg_view_percentage = 0.0
        if duration_seconds > 0 and avg_view_duration > 0:
            avg_view_percentage = (avg_view_duration / duration_seconds) * 100
        
        # Engagement rate
        engagement_rate = 0.0
        if views > 0:
            engagement_rate = ((likes + comments) / views) * 100
        
        return {
            'ctr': ctr,
            'avg_view_duration': avg_view_duration,
            'avg_view_percentage': avg_view_percentage,
            'engagement_rate': engagement_rate,
        }
    
    def extract(
        self,
        video_data: Dict[str, Any],
        metrics_data: Optional[Dict[str, Any]] = None,
    ) -> VideoFeatures:
        """
        ดึง features จากข้อมูลวิดีโอ
        
        Args:
            video_data: ข้อมูลวิดีโอ (dict หรือ Video model)
            metrics_data: ข้อมูล metrics (optional)
            
        Returns:
            VideoFeatures object
        """
        features = VideoFeatures()
        
        # Video IDs
        features.video_id = str(video_data.get('id', ''))
        features.youtube_video_id = video_data.get('youtube_video_id', '')
        
        # Title features
        title = video_data.get('title', '')
        title_features = self._extract_title_features(title)
        for key, value in title_features.items():
            setattr(features, key, value)
        
        # Description features
        description = video_data.get('description', '')
        desc_features = self._extract_description_features(description)
        for key, value in desc_features.items():
            setattr(features, key, value)
        
        # Publish time features
        published_at = video_data.get('published_at')
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            except:
                published_at = None
        publish_features = self._extract_publish_time_features(published_at)
        for key, value in publish_features.items():
            setattr(features, key, value)
        
        # Duration features
        duration = video_data.get('duration_seconds', 0)
        if not duration:
            # Try to parse from duration string (ISO 8601)
            duration_str = video_data.get('duration', '')
            if duration_str:
                duration = self._parse_duration(duration_str)
        duration_features = self._extract_duration_features(duration)
        for key, value in duration_features.items():
            setattr(features, key, value)
        
        # Tags features
        tags = video_data.get('tags', [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except:
                tags = []
        tags_features = self._extract_tags_features(tags)
        for key, value in tags_features.items():
            setattr(features, key, value)
        
        # Metrics
        features.views = video_data.get('view_count', 0) or 0
        features.likes = video_data.get('like_count', 0) or 0
        features.comments = video_data.get('comment_count', 0) or 0
        
        # Additional metrics from metrics_data
        if metrics_data:
            impressions = metrics_data.get('impressions', 0)
            avg_view_duration = metrics_data.get('average_view_duration', 0.0)
            
            perf_metrics = self._calculate_performance_metrics(
                views=features.views,
                likes=features.likes,
                comments=features.comments,
                impressions=impressions,
                avg_view_duration=avg_view_duration,
                duration_seconds=features.duration_seconds,
            )
            
            features.ctr = perf_metrics['ctr']
            features.avg_view_duration = perf_metrics['avg_view_duration']
            features.avg_view_percentage = perf_metrics['avg_view_percentage']
            features.engagement_rate = perf_metrics['engagement_rate']
        
        return features
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration string to seconds"""
        if not duration_str:
            return 0
        
        # PT1H2M3S format
        pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
        match = pattern.match(duration_str)
        
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 3600 + minutes * 60 + seconds
        
        return 0
    
    def extract_batch(
        self,
        videos: List[Dict[str, Any]],
        metrics_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> pd.DataFrame:
        """
        ดึง features จากหลายวิดีโอพร้อมกัน
        
        Args:
            videos: รายการข้อมูลวิดีโอ
            metrics_map: mapping ของ video_id -> metrics_data
            
        Returns:
            DataFrame ของ features
        """
        features_list = []
        
        for video in videos:
            video_id = str(video.get('id', ''))
            metrics = metrics_map.get(video_id) if metrics_map else None
            
            features = self.extract(video, metrics)
            features_list.append(features.to_dict())
        
        return pd.DataFrame(features_list)
    
    def label_performance(
        self,
        df: pd.DataFrame,
        metric: str = 'views',
        percentiles: Tuple[float, float, float] = (25, 75, 95),
    ) -> pd.DataFrame:
        """
        ติด label performance tier ให้กับ DataFrame
        
        Args:
            df: DataFrame ที่มี features
            metric: metric ที่ใช้วัด performance
            percentiles: percentiles สำหรับแบ่ง tier (low, high, viral)
            
        Returns:
            DataFrame ที่มี performance labels
        """
        df = df.copy()
        
        if metric not in df.columns:
            console.print(f"[yellow]⚠️ ไม่พบ column '{metric}' ใน DataFrame[/yellow]")
            return df
        
        # Calculate percentiles
        p25, p75, p95 = np.percentile(df[metric].dropna(), percentiles)
        
        # Assign tiers
        def assign_tier(value):
            if pd.isna(value):
                return 'unknown'
            if value >= p95:
                return 'viral'
            elif value >= p75:
                return 'high'
            elif value >= p25:
                return 'medium'
            else:
                return 'low'
        
        df['performance_tier'] = df[metric].apply(assign_tier)
        df['is_high_performer'] = df['performance_tier'].isin(['high', 'viral'])
        
        console.print(f"[green]✅ ติด label สำเร็จ (metric: {metric})[/green]")
        console.print(f"   - Low: < {p25:.0f}")
        console.print(f"   - Medium: {p25:.0f} - {p75:.0f}")
        console.print(f"   - High: {p75:.0f} - {p95:.0f}")
        console.print(f"   - Viral: >= {p95:.0f}")
        
        return df
    
    def get_feature_names(self) -> List[str]:
        """คืนค่ารายชื่อ features ทั้งหมด"""
        sample = VideoFeatures()
        return list(sample.to_feature_vector().keys())
