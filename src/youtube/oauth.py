"""
OAuth Module - จัดการ OAuth 2.0 สำหรับ YouTube API
รองรับ:
- Local OAuth flow
- Token caching
- Refresh token
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource

from src.utils.logger import get_logger
from src.utils.config import get_config

logger = get_logger()

# Default scopes สำหรับ YouTube API
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


@dataclass
class AuthStatus:
    """สถานะการ authentication"""
    is_authenticated: bool
    has_valid_token: bool
    scopes: List[str]
    token_expiry: Optional[str]
    channel_id: Optional[str]
    channel_title: Optional[str]
    error: Optional[str] = None


class YouTubeAuth:
    """
    จัดการ OAuth 2.0 สำหรับ YouTube API
    
    รองรับ:
    - Local OAuth flow ผ่าน browser
    - Token caching ใน JSON file
    - Automatic refresh token
    
    Usage:
        auth = YouTubeAuth()
        credentials = auth.get_credentials()
        youtube = auth.get_youtube_service()
        analytics = auth.get_analytics_service()
    """
    
    def __init__(
        self,
        client_secrets_file: Optional[str] = None,
        token_file: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ):
        """
        Initialize YouTubeAuth
        
        Args:
            client_secrets_file: Path ไปยังไฟล์ client_secrets.json
            token_file: Path ไปยังไฟล์ token.json (จะถูกสร้างอัตโนมัติ)
            scopes: List ของ OAuth scopes
        """
        config = get_config()
        
        self.client_secrets_file = client_secrets_file or config.youtube.oauth.client_secrets_file
        self.token_file = token_file or config.youtube.oauth.token_file
        self.scopes = scopes or config.youtube.oauth.scopes or DEFAULT_SCOPES
        
        self._credentials: Optional[Credentials] = None
        self._youtube_service: Optional[Resource] = None
        self._analytics_service: Optional[Resource] = None
        
        # สร้าง directory สำหรับ secrets ถ้ายังไม่มี
        Path(self.token_file).parent.mkdir(parents=True, exist_ok=True)
    
    def get_credentials(self, force_refresh: bool = False) -> Optional[Credentials]:
        """
        ดึง credentials พร้อม refresh อัตโนมัติ
        
        Args:
            force_refresh: บังคับ refresh token
            
        Returns:
            Credentials object หรือ None ถ้าไม่สามารถ authenticate ได้
        """
        if self._credentials and self._credentials.valid and not force_refresh:
            return self._credentials
        
        # ลองโหลด token จากไฟล์
        if os.path.exists(self.token_file):
            try:
                self._credentials = Credentials.from_authorized_user_file(
                    self.token_file,
                    self.scopes,
                )
                logger.info("โหลด token จากไฟล์สำเร็จ")
            except Exception as e:
                logger.warning(f"ไม่สามารถโหลด token จากไฟล์: {e}")
                self._credentials = None
        
        # ถ้า token หมดอายุ ให้ refresh
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            try:
                logger.info("กำลัง refresh token...")
                self._credentials.refresh(Request())
                self._save_token()
                logger.info("Refresh token สำเร็จ")
            except Exception as e:
                logger.error(f"ไม่สามารถ refresh token: {e}")
                self._credentials = None
        
        return self._credentials
    
    def authenticate(self, headless: bool = False) -> bool:
        """
        ทำ OAuth flow เพื่อขอ credentials ใหม่
        
        Args:
            headless: ใช้ console-based flow แทน browser
            
        Returns:
            True ถ้าสำเร็จ
        """
        if not os.path.exists(self.client_secrets_file):
            logger.error(f"ไม่พบไฟล์ client_secrets.json: {self.client_secrets_file}")
            logger.error("กรุณาดาวน์โหลดไฟล์จาก Google Cloud Console")
            return False
        
        try:
            logger.info("เริ่ม OAuth flow...")
            logger.info(f"Scopes: {self.scopes}")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secrets_file,
                self.scopes,
            )
            
            if headless:
                # Console-based flow
                self._credentials = flow.run_console()
            else:
                # Browser-based flow
                self._credentials = flow.run_local_server(
                    port=8080,
                    prompt="consent",
                    success_message="การยืนยันตัวตนสำเร็จ! คุณสามารถปิดหน้าต่างนี้ได้",
                )
            
            self._save_token()
            logger.info("Authentication สำเร็จ!")
            return True
            
        except Exception as e:
            logger.error(f"Authentication ล้มเหลว: {e}")
            return False
    
    def _save_token(self) -> None:
        """บันทึก token ลงไฟล์"""
        if self._credentials:
            try:
                with open(self.token_file, "w") as f:
                    f.write(self._credentials.to_json())
                logger.info(f"บันทึก token ไปยัง: {self.token_file}")
            except Exception as e:
                logger.error(f"ไม่สามารถบันทึก token: {e}")
    
    def revoke_token(self) -> bool:
        """
        ยกเลิก token
        
        Returns:
            True ถ้าสำเร็จ
        """
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info("ลบ token file สำเร็จ")
            
            self._credentials = None
            self._youtube_service = None
            self._analytics_service = None
            
            return True
        except Exception as e:
            logger.error(f"ไม่สามารถ revoke token: {e}")
            return False
    
    def get_youtube_service(self) -> Optional[Resource]:
        """
        ดึง YouTube Data API service
        
        Returns:
            YouTube API Resource หรือ None
        """
        credentials = self.get_credentials()
        if not credentials:
            logger.error("ไม่มี credentials สำหรับ YouTube API")
            return None
        
        if not self._youtube_service:
            try:
                self._youtube_service = build(
                    "youtube",
                    "v3",
                    credentials=credentials,
                )
                logger.info("สร้าง YouTube Data API service สำเร็จ")
            except Exception as e:
                logger.error(f"ไม่สามารถสร้าง YouTube service: {e}")
                return None
        
        return self._youtube_service
    
    def get_analytics_service(self) -> Optional[Resource]:
        """
        ดึง YouTube Analytics API service
        
        Returns:
            YouTube Analytics API Resource หรือ None
        """
        credentials = self.get_credentials()
        if not credentials:
            logger.error("ไม่มี credentials สำหรับ Analytics API")
            return None
        
        if not self._analytics_service:
            try:
                self._analytics_service = build(
                    "youtubeAnalytics",
                    "v2",
                    credentials=credentials,
                )
                logger.info("สร้าง YouTube Analytics API service สำเร็จ")
            except Exception as e:
                logger.error(f"ไม่สามารถสร้าง Analytics service: {e}")
                return None
        
        return self._analytics_service
    
    def get_auth_status(self) -> AuthStatus:
        """
        ตรวจสอบสถานะการ authentication
        
        Returns:
            AuthStatus object
        """
        credentials = self.get_credentials()
        
        if not credentials:
            return AuthStatus(
                is_authenticated=False,
                has_valid_token=False,
                scopes=[],
                token_expiry=None,
                channel_id=None,
                channel_title=None,
                error="ไม่พบ credentials - กรุณารัน authenticate() ก่อน",
            )
        
        # ตรวจสอบ scopes
        current_scopes = list(credentials.scopes) if credentials.scopes else []
        
        # ดึงข้อมูล channel
        channel_id = None
        channel_title = None
        
        try:
            youtube = self.get_youtube_service()
            if youtube:
                response = youtube.channels().list(
                    part="snippet",
                    mine=True,
                ).execute()
                
                if response.get("items"):
                    channel = response["items"][0]
                    channel_id = channel["id"]
                    channel_title = channel["snippet"]["title"]
        except Exception as e:
            logger.warning(f"ไม่สามารถดึงข้อมูล channel: {e}")
        
        return AuthStatus(
            is_authenticated=True,
            has_valid_token=credentials.valid,
            scopes=current_scopes,
            token_expiry=str(credentials.expiry) if credentials.expiry else None,
            channel_id=channel_id,
            channel_title=channel_title,
        )
    
    def check_scopes(self, required_scopes: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        ตรวจสอบว่ามี scopes ที่ต้องการหรือไม่
        
        Args:
            required_scopes: List ของ scopes ที่ต้องการ (default: self.scopes)
            
        Returns:
            Dictionary ของ scope -> bool
        """
        required = required_scopes or self.scopes
        credentials = self.get_credentials()
        
        if not credentials or not credentials.scopes:
            return {scope: False for scope in required}
        
        current_scopes = set(credentials.scopes)
        return {scope: scope in current_scopes for scope in required}


# Singleton instance
_auth_instance: Optional[YouTubeAuth] = None


def get_youtube_auth() -> YouTubeAuth:
    """
    ดึง YouTubeAuth instance (singleton)
    
    Returns:
        YouTubeAuth instance
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = YouTubeAuth()
    return _auth_instance


def reset_youtube_auth() -> None:
    """รีเซ็ต YouTubeAuth instance"""
    global _auth_instance
    _auth_instance = None
