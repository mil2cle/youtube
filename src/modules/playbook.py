"""
Playbook Module - จัดการกฎการปรับปรุงตัวเอง
ระบบเรียนรู้จาก patterns และสร้างกฎสำหรับปรับปรุง content strategy
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.db.models import PlaybookRule, Video, DailyMetric
from src.db.repository import PlaybookRuleRepository, VideoRepository, DailyMetricRepository
from src.utils.logger import get_logger, TaskLogger

logger = get_logger()


@dataclass
class RuleCondition:
    """เงื่อนไขของกฎ"""
    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, contains, in
    value: Any


@dataclass
class RuleAction:
    """การกระทำของกฎ"""
    action_type: str  # suggest, warn, auto_apply
    target: str
    recommendation: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleEvaluation:
    """ผลการประเมินกฎ"""
    rule_id: int
    rule_name: str
    is_applicable: bool
    recommendation: str
    confidence: float


class PlaybookModule:
    """
    โมดูลจัดการ Playbook Rules
    
    รองรับ:
    - การสร้างและจัดการกฎ
    - การประเมินและใช้งานกฎ
    - การเรียนรู้อัตโนมัติ
    - การติดตามประสิทธิภาพของกฎ
    """
    
    # Categories ที่รองรับ
    CATEGORIES = [
        "title_optimization",
        "thumbnail_strategy",
        "posting_time",
        "content_length",
        "engagement_tactics",
    ]
    
    def __init__(self, session: Session):
        self.session = session
        self.rule_repo = PlaybookRuleRepository(session)
        self.video_repo = VideoRepository(session)
        self.metric_repo = DailyMetricRepository(session)
        self.task_logger = TaskLogger("Playbook")
    
    def create_rule(
        self,
        name: str,
        description: str,
        category: str,
        condition: Dict[str, Any],
        action: Dict[str, Any],
        confidence_score: float = 0.5,
        is_auto_generated: bool = False,
    ) -> PlaybookRule:
        """
        สร้างกฎใหม่
        
        Args:
            name: ชื่อกฎ
            description: คำอธิบาย
            category: หมวดหมู่
            condition: เงื่อนไข
            action: การกระทำ
            confidence_score: คะแนนความมั่นใจ
            is_auto_generated: สร้างอัตโนมัติหรือไม่
            
        Returns:
            PlaybookRule ที่สร้างใหม่
        """
        if category not in self.CATEGORIES:
            logger.warning(f"หมวดหมู่ไม่ถูกต้อง: {category}")
        
        self.task_logger.start(f"สร้างกฎ: {name}")
        
        rule = self.rule_repo.create(
            name=name,
            description=description,
            category=category,
            condition=condition,
            action=action,
            confidence_score=confidence_score,
            is_auto_generated=is_auto_generated,
            is_active=True,
        )
        
        self.session.commit()
        self.task_logger.complete(f"สร้างกฎ ID: {rule.id} สำเร็จ")
        
        return rule
    
    def update_rule(
        self,
        rule_id: int,
        **kwargs,
    ) -> Optional[PlaybookRule]:
        """
        อัพเดทกฎ
        
        Args:
            rule_id: ID ของกฎ
            **kwargs: fields ที่ต้องการอัพเดท
            
        Returns:
            PlaybookRule ที่อัพเดทแล้ว
        """
        # Increment version if condition or action changes
        if "condition" in kwargs or "action" in kwargs:
            rule = self.rule_repo.get_by_id(rule_id)
            if rule:
                kwargs["version"] = rule.version + 1
        
        rule = self.rule_repo.update(rule_id, **kwargs)
        if rule:
            self.session.commit()
        
        return rule
    
    def activate_rule(self, rule_id: int) -> Optional[PlaybookRule]:
        """เปิดใช้งานกฎ"""
        return self.update_rule(rule_id, is_active=True)
    
    def deactivate_rule(self, rule_id: int) -> Optional[PlaybookRule]:
        """ปิดใช้งานกฎ"""
        return self.update_rule(rule_id, is_active=False)
    
    def get_active_rules(
        self,
        category: Optional[str] = None,
    ) -> List[PlaybookRule]:
        """
        ดึงกฎที่ active
        
        Args:
            category: กรองตามหมวดหมู่
            
        Returns:
            List ของ PlaybookRule
        """
        return self.rule_repo.get_active_rules(category)
    
    def get_high_confidence_rules(
        self,
        min_confidence: float = 0.7,
    ) -> List[PlaybookRule]:
        """
        ดึงกฎที่มี confidence สูง
        
        Args:
            min_confidence: คะแนนขั้นต่ำ
            
        Returns:
            List ของ PlaybookRule
        """
        return self.rule_repo.get_high_confidence_rules(min_confidence)
    
    def evaluate_rules(
        self,
        context: Dict[str, Any],
        category: Optional[str] = None,
    ) -> List[RuleEvaluation]:
        """
        ประเมินกฎทั้งหมดกับ context ที่กำหนด
        
        Args:
            context: ข้อมูล context สำหรับประเมิน
            category: กรองตามหมวดหมู่
            
        Returns:
            List ของ RuleEvaluation
        """
        self.task_logger.start("ประเมินกฎ")
        
        rules = self.get_active_rules(category)
        evaluations = []
        
        for rule in rules:
            is_applicable = self._check_condition(rule.condition, context)
            
            if is_applicable:
                recommendation = rule.action.get("recommendation", "")
                evaluations.append(RuleEvaluation(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    is_applicable=True,
                    recommendation=recommendation,
                    confidence=rule.confidence_score,
                ))
        
        # Sort by confidence
        evaluations.sort(key=lambda x: x.confidence, reverse=True)
        
        self.task_logger.complete(f"พบกฎที่ใช้ได้ {len(evaluations)} กฎ")
        
        return evaluations
    
    def _check_condition(
        self,
        condition: Dict[str, Any],
        context: Dict[str, Any],
    ) -> bool:
        """
        ตรวจสอบเงื่อนไข
        
        Args:
            condition: เงื่อนไขที่ต้องตรวจสอบ
            context: ข้อมูล context
            
        Returns:
            True ถ้าเงื่อนไขเป็นจริง
        """
        field = condition.get("field")
        operator = condition.get("operator", "eq")
        value = condition.get("value")
        
        if field not in context:
            return False
        
        context_value = context[field]
        
        operators = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
            "gte": lambda a, b: a >= b,
            "lte": lambda a, b: a <= b,
            "contains": lambda a, b: b in str(a),
            "in": lambda a, b: a in b,
        }
        
        op_func = operators.get(operator, operators["eq"])
        
        try:
            return op_func(context_value, value)
        except Exception:
            return False
    
    def record_rule_application(
        self,
        rule_id: int,
        success: bool,
        video_id: Optional[int] = None,
    ) -> Optional[PlaybookRule]:
        """
        บันทึกการใช้งานกฎ
        
        Args:
            rule_id: ID ของกฎ
            success: สำเร็จหรือไม่
            video_id: ID ของวิดีโอที่เกี่ยวข้อง
            
        Returns:
            PlaybookRule ที่อัพเดทแล้ว
        """
        rule = self.rule_repo.record_application(rule_id, success)
        
        if rule and video_id:
            # Update sample_videos
            sample_videos = rule.sample_videos or {"videos": []}
            if video_id not in sample_videos["videos"]:
                sample_videos["videos"].append(video_id)
                sample_videos["videos"] = sample_videos["videos"][-20:]  # Keep last 20
                self.rule_repo.update(rule_id, sample_videos=sample_videos)
        
        if rule:
            self.session.commit()
        
        return rule
    
    def learn_from_performance(
        self,
        min_videos: int = 10,
        performance_threshold: float = 0.7,
    ) -> List[PlaybookRule]:
        """
        เรียนรู้กฎใหม่จาก performance ของวิดีโอ
        
        Args:
            min_videos: จำนวนวิดีโอขั้นต่ำสำหรับการเรียนรู้
            performance_threshold: threshold สำหรับ high performance
            
        Returns:
            List ของกฎที่สร้างใหม่
        """
        self.task_logger.start("เรียนรู้กฎใหม่จาก performance")
        
        new_rules = []
        
        # ดึงวิดีโอทั้งหมด
        videos = self.video_repo.get_all(limit=500)
        
        if len(videos) < min_videos:
            self.task_logger.warning(f"วิดีโอไม่เพียงพอ ({len(videos)} < {min_videos})")
            return new_rules
        
        # วิเคราะห์ patterns
        patterns = self._analyze_patterns(videos)
        
        for pattern in patterns:
            if pattern["confidence"] >= performance_threshold:
                rule = self._create_rule_from_pattern(pattern)
                if rule:
                    new_rules.append(rule)
        
        self.task_logger.complete(f"สร้างกฎใหม่ {len(new_rules)} กฎ")
        
        return new_rules
    
    def _analyze_patterns(
        self,
        videos: List[Video],
    ) -> List[Dict[str, Any]]:
        """
        วิเคราะห์ patterns จากวิดีโอ
        
        Args:
            videos: List ของวิดีโอ
            
        Returns:
            List ของ patterns
        """
        patterns = []
        
        # Pattern 1: Title length
        title_lengths = [(v, len(v.title)) for v in videos]
        avg_views_by_length = {}
        
        for video, length in title_lengths:
            bucket = (length // 10) * 10  # Group by 10 characters
            if bucket not in avg_views_by_length:
                avg_views_by_length[bucket] = []
            avg_views_by_length[bucket].append(video.view_count)
        
        best_length_bucket = max(
            avg_views_by_length.keys(),
            key=lambda k: sum(avg_views_by_length[k]) / len(avg_views_by_length[k])
            if avg_views_by_length[k] else 0
        )
        
        if len(avg_views_by_length.get(best_length_bucket, [])) >= 5:
            patterns.append({
                "type": "title_length",
                "category": "title_optimization",
                "condition": {"field": "title_length", "operator": "gte", "value": best_length_bucket},
                "recommendation": f"ใช้ title ความยาว {best_length_bucket}-{best_length_bucket + 10} ตัวอักษร",
                "confidence": 0.6,
                "sample_count": len(avg_views_by_length[best_length_bucket]),
            })
        
        # Pattern 2: Publishing time
        hour_performance = {}
        for video in videos:
            if video.published_at:
                hour = video.published_at.hour
                if hour not in hour_performance:
                    hour_performance[hour] = []
                hour_performance[hour].append(video.view_count)
        
        if hour_performance:
            best_hour = max(
                hour_performance.keys(),
                key=lambda h: sum(hour_performance[h]) / len(hour_performance[h])
                if hour_performance[h] else 0
            )
            
            if len(hour_performance.get(best_hour, [])) >= 3:
                patterns.append({
                    "type": "posting_time",
                    "category": "posting_time",
                    "condition": {"field": "publish_hour", "operator": "eq", "value": best_hour},
                    "recommendation": f"โพสต์วิดีโอเวลา {best_hour}:00 น.",
                    "confidence": 0.5,
                    "sample_count": len(hour_performance[best_hour]),
                })
        
        # Pattern 3: Video duration
        duration_performance = {}
        for video in videos:
            if video.duration_seconds:
                # Group by 5-minute buckets
                bucket = (video.duration_seconds // 300) * 5
                if bucket not in duration_performance:
                    duration_performance[bucket] = []
                duration_performance[bucket].append(video.view_count)
        
        if duration_performance:
            best_duration = max(
                duration_performance.keys(),
                key=lambda d: sum(duration_performance[d]) / len(duration_performance[d])
                if duration_performance[d] else 0
            )
            
            if len(duration_performance.get(best_duration, [])) >= 3:
                patterns.append({
                    "type": "content_length",
                    "category": "content_length",
                    "condition": {"field": "duration_minutes", "operator": "gte", "value": best_duration},
                    "recommendation": f"สร้างวิดีโอความยาว {best_duration}-{best_duration + 5} นาที",
                    "confidence": 0.55,
                    "sample_count": len(duration_performance[best_duration]),
                })
        
        return patterns
    
    def _create_rule_from_pattern(
        self,
        pattern: Dict[str, Any],
    ) -> Optional[PlaybookRule]:
        """
        สร้างกฎจาก pattern
        
        Args:
            pattern: pattern ที่วิเคราะห์ได้
            
        Returns:
            PlaybookRule หรือ None
        """
        # Check if similar rule exists
        existing_rules = self.get_active_rules(pattern["category"])
        for rule in existing_rules:
            if rule.condition.get("field") == pattern["condition"]["field"]:
                # Update existing rule instead
                self.update_rule(
                    rule.id,
                    condition=pattern["condition"],
                    confidence_score=max(rule.confidence_score, pattern["confidence"]),
                )
                return None
        
        # Create new rule
        return self.create_rule(
            name=f"Auto: {pattern['type']}",
            description=f"กฎที่เรียนรู้อัตโนมัติจาก {pattern['sample_count']} วิดีโอ",
            category=pattern["category"],
            condition=pattern["condition"],
            action={
                "action_type": "suggest",
                "target": pattern["type"],
                "recommendation": pattern["recommendation"],
            },
            confidence_score=pattern["confidence"],
            is_auto_generated=True,
        )
    
    def get_recommendations(
        self,
        video_context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        ดึงคำแนะนำจากกฎทั้งหมด
        
        Args:
            video_context: context ของวิดีโอ
            
        Returns:
            List ของคำแนะนำ
        """
        recommendations = []
        
        if video_context:
            evaluations = self.evaluate_rules(video_context)
            for eval in evaluations:
                if eval.is_applicable and eval.confidence >= 0.5:
                    recommendations.append(f"[{eval.confidence:.0%}] {eval.recommendation}")
        else:
            # Get general recommendations from high confidence rules
            rules = self.get_high_confidence_rules(0.6)
            for rule in rules:
                rec = rule.action.get("recommendation", "")
                if rec:
                    recommendations.append(f"[{rule.confidence_score:.0%}] {rec}")
        
        return recommendations
    
    def get_rule_stats(self) -> Dict[str, Any]:
        """
        สรุปสถิติกฎ
        
        Returns:
            Dictionary ของสถิติ
        """
        all_rules = self.rule_repo.get_all(limit=500)
        active_rules = [r for r in all_rules if r.is_active]
        auto_rules = [r for r in all_rules if r.is_auto_generated]
        
        category_counts = {}
        for rule in all_rules:
            category_counts[rule.category] = category_counts.get(rule.category, 0) + 1
        
        return {
            "total_rules": len(all_rules),
            "active_rules": len(active_rules),
            "auto_generated": len(auto_rules),
            "by_category": category_counts,
            "avg_confidence": sum(r.confidence_score for r in all_rules) / len(all_rules) if all_rules else 0,
            "avg_success_rate": sum(r.success_rate for r in all_rules) / len(all_rules) if all_rules else 0,
            "total_applications": sum(r.times_applied for r in all_rules),
        }
    
    def export_playbook(self) -> List[Dict[str, Any]]:
        """
        Export playbook เป็น dictionary
        
        Returns:
            List ของ dictionary
        """
        rules = self.rule_repo.get_all(limit=500)
        
        return [
            {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "category": rule.category,
                "condition": rule.condition,
                "action": rule.action,
                "confidence_score": rule.confidence_score,
                "success_rate": rule.success_rate,
                "times_applied": rule.times_applied,
                "is_active": rule.is_active,
                "is_auto_generated": rule.is_auto_generated,
                "version": rule.version,
                "created_at": str(rule.created_at),
            }
            for rule in rules
        ]
