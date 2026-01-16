"""
RSS Feed Parser - ดึงข่าวสารอนิเมะจาก RSS feeds ที่เป็นทางการ

รองรับแหล่งข้อมูล:
- Anime News Network (ANN) - ข่าวสารอนิเมะหลัก
- Crunchyroll News - ข่าวสารจาก Crunchyroll
- MyAnimeList News - ข่าวสารจาก MAL

หมายเหตุ: ใช้เฉพาะ RSS feeds ที่เป็นทางการ ไม่มีการ scrape เว็บไซต์
"""

import re
import html
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

import requests
from xml.etree import ElementTree as ET
from rich.console import Console

console = Console()


# Whitelisted RSS sources พร้อม reliability score
RSS_SOURCES = {
    "ann": {
        "name": "Anime News Network",
        "url": "https://www.animenewsnetwork.com/all/rss.xml",
        "reliability_score": 0.95,
        "category": "news",
    },
    "ann_interest": {
        "name": "ANN Interest",
        "url": "https://www.animenewsnetwork.com/interest/rss.xml",
        "reliability_score": 0.90,
        "category": "interest",
    },
    "crunchyroll": {
        "name": "Crunchyroll News",
        "url": "https://www.crunchyroll.com/newsrss",
        "reliability_score": 0.90,
        "category": "news",
    },
    "mal_news": {
        "name": "MyAnimeList News",
        "url": "https://myanimelist.net/rss/news.xml",
        "reliability_score": 0.85,
        "category": "news",
    },
}


@dataclass
class RSSItem:
    """โครงสร้างข้อมูลข่าวจาก RSS"""
    
    title: str
    link: str
    source: str
    source_name: str
    published_at: Optional[datetime] = None
    description: Optional[str] = None
    raw_text: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    author: Optional[str] = None
    guid: Optional[str] = None
    reliability_score: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """แปลงเป็น dictionary"""
        return {
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "source_name": self.source_name,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "description": self.description,
            "raw_text": self.raw_text,
            "categories": self.categories,
            "author": self.author,
            "guid": self.guid,
            "reliability_score": self.reliability_score,
        }


class RSSFeedParser:
    """
    RSS Feed Parser สำหรับดึงข่าวสารอนิเมะ
    
    รองรับเฉพาะ RSS feeds ที่เป็นทางการและอยู่ใน whitelist
    
    การใช้งาน:
        parser = RSSFeedParser()
        news = parser.fetch_all_sources(days=7)
        
        # หรือดึงจากแหล่งเฉพาะ
        ann_news = parser.fetch_source("ann", days=7)
    """
    
    def __init__(self, timeout: int = 30, custom_sources: Optional[Dict] = None):
        """
        สร้าง RSS parser
        
        Args:
            timeout: timeout สำหรับ HTTP requests (วินาที)
            custom_sources: แหล่ง RSS เพิ่มเติม (ต้องระบุ reliability_score)
        """
        self.timeout = timeout
        self.sources = RSS_SOURCES.copy()
        
        if custom_sources:
            for key, source in custom_sources.items():
                if self._validate_source(source):
                    self.sources[key] = source
                    console.print(f"[green]✅ เพิ่มแหล่ง RSS: {source.get('name', key)}[/green]")
                else:
                    console.print(f"[yellow]⚠️ แหล่ง RSS ไม่ถูกต้อง: {key}[/yellow]")
    
    def _validate_source(self, source: Dict) -> bool:
        """ตรวจสอบความถูกต้องของแหล่ง RSS"""
        required_fields = ["url", "reliability_score"]
        return all(field in source for field in required_fields)
    
    def _clean_html(self, text: str) -> str:
        """ลบ HTML tags และ decode entities"""
        if not text:
            return ""
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """แปลงวันที่จาก RSS format"""
        if not date_str:
            return None
        
        try:
            # RFC 2822 format (standard RSS)
            return parsedate_to_datetime(date_str)
        except Exception:
            pass
        
        # Try ISO format
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            pass
        
        return None
    
    def _parse_feed(self, xml_content: str, source_key: str) -> List[RSSItem]:
        """แปลง XML เป็นรายการ RSSItem"""
        items = []
        source_info = self.sources.get(source_key, {})
        
        try:
            root = ET.fromstring(xml_content)
            
            # Find all items (RSS 2.0)
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                
                if not title or not link:
                    continue
                
                description = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")
                author = item.findtext("author", "") or item.findtext("{http://purl.org/dc/elements/1.1/}creator", "")
                guid = item.findtext("guid", "")
                
                # Parse categories
                categories = [cat.text for cat in item.findall("category") if cat.text]
                
                rss_item = RSSItem(
                    title=self._clean_html(title),
                    link=link,
                    source=source_key,
                    source_name=source_info.get("name", source_key),
                    published_at=self._parse_date(pub_date),
                    description=self._clean_html(description)[:500] if description else None,
                    raw_text=self._clean_html(description) if description else None,
                    categories=categories,
                    author=author,
                    guid=guid,
                    reliability_score=source_info.get("reliability_score", 0.5),
                )
                
                items.append(rss_item)
            
            # Try Atom format if no items found
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns):
                    title = entry.findtext("atom:title", "", ns)
                    link_elem = entry.find("atom:link", ns)
                    link = link_elem.get("href", "") if link_elem is not None else ""
                    
                    if not title or not link:
                        continue
                    
                    content = entry.findtext("atom:content", "", ns) or entry.findtext("atom:summary", "", ns)
                    updated = entry.findtext("atom:updated", "", ns) or entry.findtext("atom:published", "", ns)
                    author_elem = entry.find("atom:author/atom:name", ns)
                    author = author_elem.text if author_elem is not None else ""
                    
                    rss_item = RSSItem(
                        title=self._clean_html(title),
                        link=link,
                        source=source_key,
                        source_name=source_info.get("name", source_key),
                        published_at=self._parse_date(updated),
                        description=self._clean_html(content)[:500] if content else None,
                        raw_text=self._clean_html(content) if content else None,
                        categories=[],
                        author=author,
                        guid=link,
                        reliability_score=source_info.get("reliability_score", 0.5),
                    )
                    
                    items.append(rss_item)
        
        except ET.ParseError as e:
            console.print(f"[red]❌ XML Parse Error ({source_key}): {e}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Parse Error ({source_key}): {e}[/red]")
        
        return items
    
    def fetch_source(
        self,
        source_key: str,
        days: int = 7,
        limit: Optional[int] = None
    ) -> List[RSSItem]:
        """
        ดึงข่าวจากแหล่ง RSS เฉพาะ
        
        Args:
            source_key: key ของแหล่ง RSS (เช่น "ann", "crunchyroll")
            days: จำนวนวันย้อนหลังที่ต้องการ
            limit: จำนวนข่าวสูงสุดที่ต้องการ
            
        Returns:
            รายการข่าวจากแหล่งที่ระบุ
        """
        if source_key not in self.sources:
            console.print(f"[red]❌ ไม่พบแหล่ง RSS: {source_key}[/red]")
            console.print(f"[yellow]แหล่งที่รองรับ: {list(self.sources.keys())}[/yellow]")
            return []
        
        source = self.sources[source_key]
        console.print(f"[cyan]📰 กำลังดึงข่าวจาก {source['name']}...[/cyan]")
        
        try:
            response = requests.get(source["url"], timeout=self.timeout)
            response.raise_for_status()
            
            items = self._parse_feed(response.text, source_key)
            
            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered_items = []
            
            for item in items:
                if item.published_at:
                    # Make cutoff_date timezone-aware if item.published_at is
                    if item.published_at.tzinfo is not None:
                        from datetime import timezone
                        cutoff_aware = cutoff_date.replace(tzinfo=timezone.utc)
                        if item.published_at >= cutoff_aware:
                            filtered_items.append(item)
                    else:
                        if item.published_at >= cutoff_date:
                            filtered_items.append(item)
                else:
                    # Include items without date
                    filtered_items.append(item)
            
            # Apply limit
            if limit:
                filtered_items = filtered_items[:limit]
            
            console.print(f"[green]✅ ดึงข่าวจาก {source['name']} สำเร็จ: {len(filtered_items)} รายการ[/green]")
            
            return filtered_items
            
        except requests.exceptions.Timeout:
            console.print(f"[red]❌ Timeout: {source['name']}[/red]")
            return []
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ Request Error ({source['name']}): {e}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]❌ Error ({source['name']}): {e}[/red]")
            return []
    
    def fetch_all_sources(
        self,
        days: int = 7,
        limit_per_source: Optional[int] = None,
        sources: Optional[List[str]] = None
    ) -> List[RSSItem]:
        """
        ดึงข่าวจากทุกแหล่ง RSS
        
        Args:
            days: จำนวนวันย้อนหลังที่ต้องการ
            limit_per_source: จำนวนข่าวสูงสุดต่อแหล่ง
            sources: รายการแหล่งที่ต้องการ (ถ้าไม่ระบุจะดึงทั้งหมด)
            
        Returns:
            รายการข่าวจากทุกแหล่ง
        """
        all_items = []
        source_keys = sources or list(self.sources.keys())
        
        console.print(f"[cyan]📰 กำลังดึงข่าวจาก {len(source_keys)} แหล่ง...[/cyan]")
        
        for source_key in source_keys:
            items = self.fetch_source(source_key, days=days, limit=limit_per_source)
            all_items.extend(items)
        
        # Sort by published date (newest first)
        all_items.sort(
            key=lambda x: x.published_at or datetime.min,
            reverse=True
        )
        
        console.print(f"[green]✅ ดึงข่าวทั้งหมดสำเร็จ: {len(all_items)} รายการ[/green]")
        
        return all_items
    
    def get_available_sources(self) -> Dict[str, Dict]:
        """คืนค่ารายการแหล่ง RSS ที่รองรับ"""
        return self.sources.copy()
    
    def add_source(
        self,
        key: str,
        name: str,
        url: str,
        reliability_score: float,
        category: str = "news"
    ) -> bool:
        """
        เพิ่มแหล่ง RSS ใหม่
        
        Args:
            key: key สำหรับอ้างอิงแหล่ง
            name: ชื่อแหล่ง
            url: URL ของ RSS feed
            reliability_score: คะแนนความน่าเชื่อถือ (0.0-1.0)
            category: หมวดหมู่ของแหล่ง
            
        Returns:
            True หากเพิ่มสำเร็จ
        """
        if reliability_score < 0 or reliability_score > 1:
            console.print("[red]❌ reliability_score ต้องอยู่ระหว่าง 0.0-1.0[/red]")
            return False
        
        self.sources[key] = {
            "name": name,
            "url": url,
            "reliability_score": reliability_score,
            "category": category,
        }
        
        console.print(f"[green]✅ เพิ่มแหล่ง RSS: {name}[/green]")
        return True
    
    def remove_source(self, key: str) -> bool:
        """
        ลบแหล่ง RSS
        
        Args:
            key: key ของแหล่งที่ต้องการลบ
            
        Returns:
            True หากลบสำเร็จ
        """
        if key in self.sources:
            del self.sources[key]
            console.print(f"[green]✅ ลบแหล่ง RSS: {key}[/green]")
            return True
        
        console.print(f"[yellow]⚠️ ไม่พบแหล่ง RSS: {key}[/yellow]")
        return False
