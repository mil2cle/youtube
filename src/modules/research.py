"""
Research Module - จัดการการวิจัยและติดตาม trends
รองรับการเก็บข้อมูลจากหลายแหล่ง
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.db.models import ResearchItem
from src.db.repository import ResearchItemRepository
from src.utils.logger import get_logger, TaskLogger

logger = get_logger()


@dataclass
class TrendingTopic:
    """หัวข้อที่กำลังเป็นที่นิยม"""
    title: str
    source: str
    trend_score: float
    keywords: List[str]
    category: Optional[str] = None
    url: Optional[str] = None


@dataclass
class CompetitorInsight:
    """ข้อมูลเชิงลึกจากคู่แข่ง"""
    channel_name: str
    video_title: str
    performance_indicator: str
    takeaway: str


class ResearchModule:
    """
    โมดูลวิจัยและติดตาม trends
    
    รองรับ:
    - การเก็บข้อมูลจากหลายแหล่ง
    - การวิเคราะห์ trends
    - การติดตามคู่แข่ง
    - การสร้าง insights
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.research_repo = ResearchItemRepository(session)
        self.task_logger = TaskLogger("Research")
    
    def add_research_item(
        self,
        title: str,
        source: str,
        summary: Optional[str] = None,
        content: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        category: Optional[str] = None,
        source_url: Optional[str] = None,
        relevance_score: float = 0.5,
        trend_score: float = 0.5,
        is_actionable: bool = False,
    ) -> ResearchItem:
        """
        เพิ่ม research item ใหม่
        
        Args:
            title: หัวข้อ
            source: แหล่งที่มา
            summary: สรุป
            content: เนื้อหาเต็ม
            keywords: คำสำคัญ
            category: หมวดหมู่
            source_url: URL ต้นทาง
            relevance_score: คะแนนความเกี่ยวข้อง (0-1)
            trend_score: คะแนน trend (0-1)
            is_actionable: สามารถนำไปใช้ได้หรือไม่
            
        Returns:
            ResearchItem ที่สร้างใหม่
        """
        self.task_logger.start(f"เพิ่ม research: {title}")
        
        item = self.research_repo.create(
            title=title,
            source=source,
            summary=summary,
            content=content,
            keywords={"keywords": keywords or []},
            category=category,
            source_url=source_url,
            relevance_score=relevance_score,
            trend_score=trend_score,
            is_actionable=is_actionable,
            status="new",
        )
        
        self.session.commit()
        self.task_logger.complete(f"เพิ่ม research ID: {item.id} สำเร็จ")
        
        return item
    
    def update_scores(
        self,
        item_id: int,
        relevance_score: Optional[float] = None,
        trend_score: Optional[float] = None,
    ) -> Optional[ResearchItem]:
        """
        อัพเดทคะแนนของ research item
        
        Args:
            item_id: ID ของ item
            relevance_score: คะแนนความเกี่ยวข้องใหม่
            trend_score: คะแนน trend ใหม่
            
        Returns:
            ResearchItem ที่อัพเดทแล้ว
        """
        update_data = {}
        if relevance_score is not None:
            update_data["relevance_score"] = max(0, min(1, relevance_score))
        if trend_score is not None:
            update_data["trend_score"] = max(0, min(1, trend_score))
        
        if not update_data:
            return self.research_repo.get_by_id(item_id)
        
        item = self.research_repo.update(item_id, **update_data)
        if item:
            self.session.commit()
        
        return item
    
    def mark_as_actionable(self, item_id: int) -> Optional[ResearchItem]:
        """
        ทำเครื่องหมายว่า actionable
        
        Args:
            item_id: ID ของ item
            
        Returns:
            ResearchItem ที่อัพเดทแล้ว
        """
        item = self.research_repo.update(item_id, is_actionable=True)
        if item:
            self.session.commit()
        return item
    
    def mark_as_reviewed(self, item_id: int) -> Optional[ResearchItem]:
        """
        ทำเครื่องหมายว่า reviewed แล้ว
        
        Args:
            item_id: ID ของ item
            
        Returns:
            ResearchItem ที่อัพเดทแล้ว
        """
        item = self.research_repo.mark_as_reviewed(item_id)
        if item:
            self.session.commit()
        return item
    
    def get_trending_topics(
        self,
        min_score: float = 0.5,
        limit: int = 20,
    ) -> List[TrendingTopic]:
        """
        ดึง trending topics
        
        Args:
            min_score: คะแนน trend ขั้นต่ำ
            limit: จำนวนที่ต้องการ
            
        Returns:
            List ของ TrendingTopic
        """
        items = self.research_repo.get_trending(min_score, limit)
        
        return [
            TrendingTopic(
                title=item.title,
                source=item.source,
                trend_score=item.trend_score,
                keywords=item.keywords.get("keywords", []) if item.keywords else [],
                category=item.category,
                url=item.source_url,
            )
            for item in items
        ]
    
    def get_actionable_items(self, limit: int = 20) -> List[ResearchItem]:
        """
        ดึง items ที่ actionable
        
        Args:
            limit: จำนวนที่ต้องการ
            
        Returns:
            List ของ ResearchItem
        """
        return self.research_repo.get_actionable(limit)
    
    def get_by_source(self, source: str, limit: int = 50) -> List[ResearchItem]:
        """
        ดึง items ตาม source
        
        Args:
            source: แหล่งที่มา
            limit: จำนวนที่ต้องการ
            
        Returns:
            List ของ ResearchItem
        """
        return self.research_repo.get_by_source(source, limit)
    
    def search_keywords(
        self,
        keywords: List[str],
        limit: int = 20,
    ) -> List[ResearchItem]:
        """
        ค้นหา items ด้วย keywords
        
        Args:
            keywords: คำค้นหา
            limit: จำนวนที่ต้องการ
            
        Returns:
            List ของ ResearchItem
        """
        all_items = self.research_repo.get_all(limit=500)
        
        matched_items = []
        for item in all_items:
            item_keywords = item.keywords.get("keywords", []) if item.keywords else []
            title_lower = item.title.lower()
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in title_lower or keyword_lower in [k.lower() for k in item_keywords]:
                    matched_items.append(item)
                    break
        
        # Sort by relevance score
        matched_items.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return matched_items[:limit]
    
    def analyze_competition(
        self,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        วิเคราะห์การแข่งขัน
        
        Args:
            category: หมวดหมู่ที่ต้องการวิเคราะห์
            
        Returns:
            Dictionary ของผลการวิเคราะห์
        """
        self.task_logger.start("วิเคราะห์การแข่งขัน")
        
        # ดึง research items จาก competitor source
        competitor_items = self.research_repo.get_by_source("competitor", limit=100)
        
        if category:
            competitor_items = [i for i in competitor_items if i.category == category]
        
        # วิเคราะห์
        analysis = {
            "total_items": len(competitor_items),
            "avg_trend_score": 0.0,
            "top_keywords": {},
            "categories": {},
            "insights": [],
        }
        
        if competitor_items:
            analysis["avg_trend_score"] = sum(i.trend_score for i in competitor_items) / len(competitor_items)
            
            # รวบรวม keywords
            for item in competitor_items:
                keywords = item.keywords.get("keywords", []) if item.keywords else []
                for kw in keywords:
                    analysis["top_keywords"][kw] = analysis["top_keywords"].get(kw, 0) + 1
                
                if item.category:
                    analysis["categories"][item.category] = analysis["categories"].get(item.category, 0) + 1
            
            # Sort keywords by frequency
            analysis["top_keywords"] = dict(
                sorted(analysis["top_keywords"].items(), key=lambda x: x[1], reverse=True)[:20]
            )
        
        self.task_logger.complete("วิเคราะห์การแข่งขันเสร็จสิ้น")
        
        return analysis
    
    def generate_research_report(self) -> Dict[str, Any]:
        """
        สร้างรายงานการวิจัย
        
        Returns:
            Dictionary ของรายงาน
        """
        self.task_logger.start("สร้างรายงานการวิจัย")
        
        all_items = self.research_repo.get_all(limit=500)
        trending = self.research_repo.get_trending(min_score=0.6, limit=10)
        actionable = self.research_repo.get_actionable(limit=10)
        
        # Group by source
        by_source = {}
        for item in all_items:
            by_source[item.source] = by_source.get(item.source, 0) + 1
        
        # Group by status
        by_status = {}
        for item in all_items:
            by_status[item.status] = by_status.get(item.status, 0) + 1
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_items": len(all_items),
                "trending_count": len(trending),
                "actionable_count": len(actionable),
            },
            "by_source": by_source,
            "by_status": by_status,
            "top_trending": [
                {
                    "title": item.title,
                    "trend_score": item.trend_score,
                    "source": item.source,
                }
                for item in trending[:5]
            ],
            "top_actionable": [
                {
                    "title": item.title,
                    "relevance_score": item.relevance_score,
                    "category": item.category,
                }
                for item in actionable[:5]
            ],
        }
        
        self.task_logger.complete("สร้างรายงานเสร็จสิ้น")
        
        return report
    
    def cleanup_old_items(self, days: int = 90) -> int:
        """
        ลบ research items เก่า
        
        Args:
            days: จำนวนวันที่ถือว่าเก่า
            
        Returns:
            จำนวน items ที่ถูกลบ
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        all_items = self.research_repo.get_all(limit=1000)
        
        deleted_count = 0
        for item in all_items:
            if item.created_at < cutoff_date and item.status == "archived":
                self.research_repo.delete(item.id)
                deleted_count += 1
        
        if deleted_count > 0:
            self.session.commit()
            logger.info(f"ลบ research items เก่า {deleted_count} รายการ")
        
        return deleted_count
    
    def export_research(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Export research items เป็น dictionary
        
        Args:
            source: กรองตาม source
            status: กรองตาม status
            
        Returns:
            List ของ dictionary
        """
        if source:
            items = self.research_repo.get_by_source(source)
        else:
            items = self.research_repo.get_all(limit=1000)
        
        if status:
            items = [i for i in items if i.status == status]
        
        return [
            {
                "id": item.id,
                "title": item.title,
                "source": item.source,
                "category": item.category,
                "summary": item.summary,
                "keywords": item.keywords.get("keywords", []) if item.keywords else [],
                "relevance_score": item.relevance_score,
                "trend_score": item.trend_score,
                "is_actionable": item.is_actionable,
                "status": item.status,
                "created_at": str(item.created_at),
            }
            for item in items
        ]
