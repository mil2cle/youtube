"""
Content Module - จัดการไอเดียเนื้อหาและการวางแผน
รองรับการสร้าง, จัดการ, และติดตามไอเดียวิดีโอ
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.db.models import ContentIdea, Video, ResearchItem
from src.db.repository import ContentIdeaRepository, VideoRepository, ResearchItemRepository
from src.utils.logger import get_logger, TaskLogger

logger = get_logger()


@dataclass
class IdeaSuggestion:
    """คำแนะนำไอเดียเนื้อหา"""
    title: str
    category: str
    description: str
    potential_score: float
    keywords: List[str] = field(default_factory=list)
    based_on: Optional[str] = None  # research_item, trending, competitor


@dataclass
class ContentCalendarItem:
    """รายการใน content calendar"""
    idea_id: int
    title: str
    scheduled_date: date
    status: str
    priority: str
    category: str


class ContentModule:
    """
    โมดูลจัดการเนื้อหา
    
    รองรับ:
    - การสร้างและจัดการไอเดีย
    - การวางแผน content calendar
    - การติดตามสถานะ
    - การสร้างคำแนะนำอัตโนมัติ
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.idea_repo = ContentIdeaRepository(session)
        self.video_repo = VideoRepository(session)
        self.research_repo = ResearchItemRepository(session)
        self.task_logger = TaskLogger("Content")
    
    def create_idea(
        self,
        title: str,
        category: str,
        description: Optional[str] = None,
        priority: str = "medium",
        tags: Optional[List[str]] = None,
        target_audience: Optional[str] = None,
        estimated_duration: Optional[int] = None,
        research_item_id: Optional[int] = None,
    ) -> ContentIdea:
        """
        สร้างไอเดียเนื้อหาใหม่
        
        Args:
            title: ชื่อไอเดีย
            category: หมวดหมู่
            description: คำอธิบาย
            priority: ความสำคัญ (high, medium, low)
            tags: แท็ก
            target_audience: กลุ่มเป้าหมาย
            estimated_duration: ความยาวโดยประมาณ (นาที)
            research_item_id: ID ของ research item ที่เกี่ยวข้อง
            
        Returns:
            ContentIdea ที่สร้างใหม่
        """
        self.task_logger.start(f"สร้างไอเดีย: {title}")
        
        idea = self.idea_repo.create(
            title=title,
            category=category,
            description=description,
            priority=priority,
            tags={"tags": tags or []},
            target_audience=target_audience,
            estimated_duration_minutes=estimated_duration,
            research_item_id=research_item_id,
            status="draft",
        )
        
        self.session.commit()
        self.task_logger.complete(f"สร้างไอเดีย ID: {idea.id} สำเร็จ")
        
        return idea
    
    def update_idea_status(
        self,
        idea_id: int,
        status: str,
        notes: Optional[str] = None,
    ) -> Optional[ContentIdea]:
        """
        อัพเดทสถานะไอเดีย
        
        Args:
            idea_id: ID ของไอเดีย
            status: สถานะใหม่
            notes: หมายเหตุ
            
        Returns:
            ContentIdea ที่อัพเดทแล้ว
        """
        valid_statuses = ["draft", "in_progress", "scheduled", "published", "archived"]
        if status not in valid_statuses:
            logger.error(f"สถานะไม่ถูกต้อง: {status}")
            return None
        
        update_data = {"status": status}
        if notes:
            update_data["notes"] = notes
        
        idea = self.idea_repo.update(idea_id, **update_data)
        if idea:
            self.session.commit()
            logger.info(f"อัพเดทสถานะไอเดีย {idea_id} เป็น {status}")
        
        return idea
    
    def schedule_idea(
        self,
        idea_id: int,
        scheduled_date: date,
    ) -> Optional[ContentIdea]:
        """
        กำหนดวันที่สำหรับไอเดีย
        
        Args:
            idea_id: ID ของไอเดีย
            scheduled_date: วันที่กำหนด
            
        Returns:
            ContentIdea ที่อัพเดทแล้ว
        """
        idea = self.idea_repo.update(
            idea_id,
            scheduled_date=scheduled_date,
            status="scheduled",
        )
        
        if idea:
            self.session.commit()
            logger.info(f"กำหนดไอเดีย {idea_id} ในวันที่ {scheduled_date}")
        
        return idea
    
    def link_to_video(
        self,
        idea_id: int,
        video_id: int,
    ) -> Optional[ContentIdea]:
        """
        เชื่อมโยงไอเดียกับวิดีโอที่เผยแพร่แล้ว
        
        Args:
            idea_id: ID ของไอเดีย
            video_id: ID ของวิดีโอ
            
        Returns:
            ContentIdea ที่อัพเดทแล้ว
        """
        idea = self.idea_repo.update(
            idea_id,
            video_id=video_id,
            status="published",
        )
        
        if idea:
            self.session.commit()
            logger.info(f"เชื่อมโยงไอเดีย {idea_id} กับวิดีโอ {video_id}")
        
        return idea
    
    def get_content_calendar(
        self,
        start_date: date,
        end_date: date,
    ) -> List[ContentCalendarItem]:
        """
        ดึง content calendar
        
        Args:
            start_date: วันเริ่มต้น
            end_date: วันสิ้นสุด
            
        Returns:
            List ของ ContentCalendarItem
        """
        ideas = self.idea_repo.get_scheduled(start_date, end_date)
        
        calendar_items = []
        for idea in ideas:
            calendar_items.append(ContentCalendarItem(
                idea_id=idea.id,
                title=idea.title,
                scheduled_date=idea.scheduled_date,
                status=idea.status,
                priority=idea.priority,
                category=idea.category,
            ))
        
        return calendar_items
    
    def get_ideas_by_status(self, status: str) -> List[ContentIdea]:
        """
        ดึงไอเดียตามสถานะ
        
        Args:
            status: สถานะที่ต้องการ
            
        Returns:
            List ของ ContentIdea
        """
        return self.idea_repo.get_by_status(status)
    
    def get_top_ideas(self, limit: int = 10) -> List[ContentIdea]:
        """
        ดึงไอเดียที่มี potential สูงสุด
        
        Args:
            limit: จำนวนที่ต้องการ
            
        Returns:
            List ของ ContentIdea
        """
        return self.idea_repo.get_top_ideas(limit)
    
    def calculate_potential_score(
        self,
        idea_id: int,
    ) -> float:
        """
        คำนวณ potential score ของไอเดีย
        
        Args:
            idea_id: ID ของไอเดีย
            
        Returns:
            Potential score (0-100)
        """
        idea = self.idea_repo.get_by_id(idea_id)
        if not idea:
            return 0.0
        
        score = 50.0  # Base score
        
        # Priority bonus
        priority_bonus = {"high": 20, "medium": 10, "low": 0}
        score += priority_bonus.get(idea.priority, 0)
        
        # Research backing bonus
        if idea.research_item_id:
            research = self.research_repo.get_by_id(idea.research_item_id)
            if research:
                score += research.relevance_score * 10
                score += research.trend_score * 10
        
        # Completeness bonus
        if idea.description:
            score += 5
        if idea.outline:
            score += 10
        if idea.target_audience:
            score += 5
        
        # Normalize to 0-100
        score = max(0, min(100, score))
        
        # Update the idea
        self.idea_repo.update(idea_id, potential_score=score)
        self.session.commit()
        
        return score
    
    def generate_suggestions(
        self,
        count: int = 5,
        categories: Optional[List[str]] = None,
    ) -> List[IdeaSuggestion]:
        """
        สร้างคำแนะนำไอเดียอัตโนมัติ
        
        Args:
            count: จำนวนคำแนะนำ
            categories: หมวดหมู่ที่ต้องการ
            
        Returns:
            List ของ IdeaSuggestion
        """
        self.task_logger.start("กำลังสร้างคำแนะนำไอเดีย")
        
        suggestions = []
        
        # ดึง actionable research items
        research_items = self.research_repo.get_actionable(limit=count * 2)
        
        for item in research_items[:count]:
            if categories and item.category not in categories:
                continue
            
            suggestion = IdeaSuggestion(
                title=f"วิดีโอเกี่ยวกับ: {item.title}",
                category=item.category or "general",
                description=item.summary or "",
                potential_score=item.relevance_score * 100,
                keywords=item.keywords.get("keywords", []) if item.keywords else [],
                based_on="research_item",
            )
            suggestions.append(suggestion)
        
        # ดึง trending topics
        trending = self.research_repo.get_trending(min_score=0.7, limit=count)
        
        for item in trending:
            if len(suggestions) >= count:
                break
            
            suggestion = IdeaSuggestion(
                title=f"Trending: {item.title}",
                category=item.category or "trending",
                description=f"กำลังเป็นที่นิยม (score: {item.trend_score:.2f})",
                potential_score=item.trend_score * 100,
                keywords=item.keywords.get("keywords", []) if item.keywords else [],
                based_on="trending",
            )
            suggestions.append(suggestion)
        
        self.task_logger.complete(f"สร้างคำแนะนำ {len(suggestions)} รายการ")
        
        return suggestions[:count]
    
    def get_idea_stats(self) -> Dict[str, Any]:
        """
        สรุปสถิติไอเดีย
        
        Returns:
            Dictionary ของสถิติ
        """
        all_ideas = self.idea_repo.get_all(limit=1000)
        
        status_counts = {}
        priority_counts = {}
        category_counts = {}
        
        for idea in all_ideas:
            status_counts[idea.status] = status_counts.get(idea.status, 0) + 1
            priority_counts[idea.priority] = priority_counts.get(idea.priority, 0) + 1
            category_counts[idea.category] = category_counts.get(idea.category, 0) + 1
        
        return {
            "total_ideas": len(all_ideas),
            "by_status": status_counts,
            "by_priority": priority_counts,
            "by_category": category_counts,
            "avg_potential_score": sum(i.potential_score for i in all_ideas) / len(all_ideas) if all_ideas else 0,
        }
    
    def archive_old_ideas(self, days: int = 90) -> int:
        """
        Archive ไอเดียเก่าที่ยังเป็น draft
        
        Args:
            days: จำนวนวันที่ถือว่าเก่า
            
        Returns:
            จำนวนไอเดียที่ถูก archive
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        draft_ideas = self.idea_repo.get_by_status("draft")
        
        archived_count = 0
        for idea in draft_ideas:
            if idea.created_at < cutoff_date:
                self.idea_repo.update(idea.id, status="archived")
                archived_count += 1
        
        if archived_count > 0:
            self.session.commit()
            logger.info(f"Archive ไอเดียเก่า {archived_count} รายการ")
        
        return archived_count
    
    def export_ideas(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export ไอเดียเป็น dictionary
        
        Args:
            status: กรองตามสถานะ
            
        Returns:
            List ของ dictionary
        """
        if status:
            ideas = self.idea_repo.get_by_status(status)
        else:
            ideas = self.idea_repo.get_all(limit=1000)
        
        return [
            {
                "id": idea.id,
                "title": idea.title,
                "category": idea.category,
                "description": idea.description,
                "priority": idea.priority,
                "status": idea.status,
                "potential_score": idea.potential_score,
                "scheduled_date": str(idea.scheduled_date) if idea.scheduled_date else None,
                "created_at": str(idea.created_at),
            }
            for idea in ideas
        ]
