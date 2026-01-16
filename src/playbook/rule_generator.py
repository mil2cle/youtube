"""
Thai Rule Generator - สร้างกฎภาษาไทยจาก ML Model

แปลง feature importance และ model insights เป็นกฎภาษาไทยที่เข้าใจง่าย
พร้อมค่า confidence และคำแนะนำที่นำไปใช้ได้จริง
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


# Feature name translations (English -> Thai)
FEATURE_TRANSLATIONS = {
    # Title features
    'title_length_chars': 'ความยาว title (ตัวอักษร)',
    'title_length_words': 'ความยาว title (คำ)',
    'title_has_number': 'มีตัวเลขใน title',
    'title_has_year': 'มีปีใน title',
    'title_has_square_bracket': 'มีวงเล็บเหลี่ยม [] ใน title',
    'title_has_round_bracket': 'มีวงเล็บกลม () ใน title',
    'title_has_japanese_bracket': 'มีวงเล็บญี่ปุ่น 【】 ใน title',
    'title_has_emoji': 'มี emoji ใน title',
    'title_has_question': 'มีเครื่องหมายคำถามใน title',
    'title_has_exclamation': 'มีเครื่องหมายตกใจใน title',
    'title_has_colon': 'มี colon (:) ใน title',
    'title_has_pipe': 'มี pipe (|) ใน title',
    'title_caps_ratio': 'สัดส่วนตัวพิมพ์ใหญ่ใน title',
    'title_positive_keywords_count': 'จำนวน keywords เชิงบวกใน title',
    'title_anime_keywords_count': 'จำนวน keywords อนิเมะใน title',
    
    # Description features
    'desc_length_chars': 'ความยาว description (ตัวอักษร)',
    'desc_length_words': 'ความยาว description (คำ)',
    'desc_has_links': 'มี links ใน description',
    'desc_link_count': 'จำนวน links ใน description',
    'desc_has_timestamps': 'มี timestamps ใน description',
    'desc_timestamp_count': 'จำนวน timestamps ใน description',
    'desc_has_hashtags': 'มี hashtags ใน description',
    'desc_hashtag_count': 'จำนวน hashtags ใน description',
    
    # Publish time features
    'publish_hour': 'ชั่วโมงที่เผยแพร่',
    'publish_day_of_week': 'วันในสัปดาห์ที่เผยแพร่',
    'publish_is_weekend': 'เผยแพร่ช่วงวันหยุด',
    'publish_is_morning': 'เผยแพร่ช่วงเช้า',
    'publish_is_afternoon': 'เผยแพร่ช่วงบ่าย',
    'publish_is_evening': 'เผยแพร่ช่วงเย็น',
    'publish_is_night': 'เผยแพร่ช่วงกลางคืน',
    
    # Duration features
    'duration_seconds': 'ความยาววิดีโอ (วินาที)',
    'duration_minutes': 'ความยาววิดีโอ (นาที)',
    'is_shorts': 'เป็น YouTube Shorts',
    'is_very_short': 'วิดีโอสั้นมาก (1-3 นาที)',
    'is_short': 'วิดีโอสั้น (3-8 นาที)',
    'is_medium': 'วิดีโอปานกลาง (8-15 นาที)',
    'is_long': 'วิดีโอยาว (15-30 นาที)',
    'is_very_long': 'วิดีโอยาวมาก (30+ นาที)',
    
    # Tags features
    'tags_count': 'จำนวน tags',
    'tags_avg_length': 'ความยาวเฉลี่ยของ tags',
}

# Rule templates for different features
RULE_TEMPLATES = {
    # Positive rules
    'title_has_number': {
        'positive': '✅ ใส่ตัวเลขใน title (เช่น "5 วิธี...", "Top 10...")',
        'negative': '⚠️ หลีกเลี่ยงการใส่ตัวเลขใน title',
    },
    'title_has_year': {
        'positive': '✅ ใส่ปีปัจจุบันใน title เพื่อความสดใหม่',
        'negative': '⚠️ ไม่จำเป็นต้องใส่ปีใน title',
    },
    'title_has_square_bracket': {
        'positive': '✅ ใช้วงเล็บเหลี่ยม [] สำหรับ tags หรือ categories',
        'negative': '⚠️ หลีกเลี่ยงวงเล็บเหลี่ยม [] ใน title',
    },
    'title_has_question': {
        'positive': '✅ ใช้คำถามใน title เพื่อดึงดูดความสนใจ',
        'negative': '⚠️ หลีกเลี่ยงการใช้คำถามใน title',
    },
    'title_has_emoji': {
        'positive': '✅ ใช้ emoji ใน title เพื่อดึงดูดสายตา',
        'negative': '⚠️ หลีกเลี่ยง emoji ใน title',
    },
    'title_positive_keywords_count': {
        'positive': '✅ ใช้ keywords เชิงบวก (วิธี, สอน, รีวิว, ดีที่สุด)',
        'negative': '⚠️ ลดการใช้ keywords เชิงบวก',
    },
    'desc_has_timestamps': {
        'positive': '✅ ใส่ timestamps ใน description สำหรับวิดีโอยาว',
        'negative': '⚠️ ไม่จำเป็นต้องใส่ timestamps',
    },
    'desc_has_hashtags': {
        'positive': '✅ ใส่ hashtags ใน description เพื่อเพิ่ม discoverability',
        'negative': '⚠️ ลดการใช้ hashtags',
    },
    'publish_is_evening': {
        'positive': '✅ เผยแพร่วิดีโอช่วงเย็น (17:00-21:00)',
        'negative': '⚠️ หลีกเลี่ยงการเผยแพร่ช่วงเย็น',
    },
    'publish_is_weekend': {
        'positive': '✅ เผยแพร่วิดีโอช่วงวันหยุดสุดสัปดาห์',
        'negative': '⚠️ เผยแพร่วิดีโอช่วงวันธรรมดา',
    },
    'is_shorts': {
        'positive': '✅ สร้าง YouTube Shorts (< 60 วินาที)',
        'negative': '⚠️ เน้นวิดีโอยาวแทน Shorts',
    },
    'is_medium': {
        'positive': '✅ ทำวิดีโอความยาว 8-15 นาที',
        'negative': '⚠️ หลีกเลี่ยงวิดีโอความยาว 8-15 นาที',
    },
    'tags_count': {
        'positive': '✅ ใส่ tags จำนวนมาก (10-15 tags)',
        'negative': '⚠️ ลดจำนวน tags',
    },
}


@dataclass
class PlaybookRule:
    """โครงสร้างข้อมูลกฎ Playbook"""
    
    rule_id: str = ""
    rule_text_th: str = ""
    rule_text_en: str = ""
    feature_name: str = ""
    importance_score: float = 0.0
    confidence: float = 0.0
    direction: str = ""  # positive, negative
    category: str = ""  # title, description, timing, duration, tags
    priority: str = "medium"  # high, medium, low
    actionable: bool = True
    evidence: str = ""
    created_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """แปลงเป็น dictionary"""
        return asdict(self)


class ThaiRuleGenerator:
    """
    Thai Rule Generator - สร้างกฎภาษาไทยจาก ML Model
    
    การใช้งาน:
        generator = ThaiRuleGenerator()
        rules = generator.generate_rules(feature_importance, model_metrics)
        generator.print_rules(rules)
    """
    
    def __init__(self):
        """สร้าง Thai Rule Generator"""
        self.feature_translations = FEATURE_TRANSLATIONS
        self.rule_templates = RULE_TEMPLATES
    
    def _get_feature_category(self, feature_name: str) -> str:
        """หา category ของ feature"""
        if feature_name.startswith('title_'):
            return 'title'
        elif feature_name.startswith('desc_'):
            return 'description'
        elif feature_name.startswith('publish_'):
            return 'timing'
        elif feature_name.startswith('duration_') or feature_name.startswith('is_'):
            return 'duration'
        elif feature_name.startswith('tags_'):
            return 'tags'
        else:
            return 'other'
    
    def _get_priority(self, importance: float, rank: int) -> str:
        """กำหนด priority จาก importance และ rank"""
        if rank <= 3 or abs(importance) > 0.5:
            return 'high'
        elif rank <= 7 or abs(importance) > 0.2:
            return 'medium'
        else:
            return 'low'
    
    def _generate_rule_text(
        self,
        feature_name: str,
        importance: float,
        direction: str,
    ) -> Tuple[str, str]:
        """สร้างข้อความกฎภาษาไทยและอังกฤษ"""
        
        # Check if we have a template
        if feature_name in self.rule_templates:
            template = self.rule_templates[feature_name]
            rule_th = template[direction]
        else:
            # Generate generic rule
            feature_th = self.feature_translations.get(feature_name, feature_name)
            
            if direction == 'positive':
                if importance > 0:
                    rule_th = f"✅ เพิ่ม/ใช้: {feature_th}"
                else:
                    rule_th = f"✅ ลด/หลีกเลี่ยง: {feature_th}"
            else:
                if importance > 0:
                    rule_th = f"⚠️ ลด/หลีกเลี่ยง: {feature_th}"
                else:
                    rule_th = f"⚠️ เพิ่ม/ใช้: {feature_th}"
        
        # English version
        rule_en = f"{'Increase' if importance > 0 else 'Decrease'} {feature_name}"
        
        return rule_th, rule_en
    
    def generate_rules(
        self,
        feature_importance: Dict[str, float],
        model_metrics: Optional[Dict[str, float]] = None,
        top_n: int = 10,
        min_importance: float = 0.01,
    ) -> List[PlaybookRule]:
        """
        สร้างกฎจาก feature importance
        
        Args:
            feature_importance: Dictionary ของ feature -> importance score
            model_metrics: Metrics ของ model (accuracy, r2, etc.)
            top_n: จำนวนกฎที่ต้องการ
            min_importance: importance ขั้นต่ำ
            
        Returns:
            รายการ PlaybookRule
        """
        rules = []
        timestamp = datetime.now().isoformat()
        
        # Sort by absolute importance
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        
        # Calculate confidence from model metrics
        base_confidence = 0.5
        if model_metrics:
            if 'accuracy' in model_metrics:
                base_confidence = model_metrics['accuracy']
            elif 'r2' in model_metrics:
                base_confidence = max(0.5, model_metrics['r2'])
        
        for rank, (feature_name, importance) in enumerate(sorted_features[:top_n], 1):
            if abs(importance) < min_importance:
                continue
            
            direction = 'positive' if importance > 0 else 'negative'
            rule_th, rule_en = self._generate_rule_text(feature_name, importance, direction)
            
            # Calculate confidence (based on importance and model performance)
            confidence = min(0.99, base_confidence * (1 + abs(importance)))
            
            rule = PlaybookRule(
                rule_id=f"rule_{rank:03d}_{feature_name}",
                rule_text_th=rule_th,
                rule_text_en=rule_en,
                feature_name=feature_name,
                importance_score=importance,
                confidence=confidence,
                direction=direction,
                category=self._get_feature_category(feature_name),
                priority=self._get_priority(importance, rank),
                actionable=True,
                evidence=f"Feature importance: {importance:.4f}",
                created_at=timestamp,
            )
            
            rules.append(rule)
        
        return rules
    
    def generate_summary(
        self,
        rules: List[PlaybookRule],
        model_type: str = "",
        target: str = "",
    ) -> str:
        """
        สร้างสรุปกฎภาษาไทย
        
        Args:
            rules: รายการกฎ
            model_type: ประเภท model
            target: target variable
            
        Returns:
            ข้อความสรุปภาษาไทย
        """
        lines = []
        lines.append("=" * 60)
        lines.append("📋 สรุปกฎ Playbook")
        lines.append("=" * 60)
        lines.append(f"📅 วันที่สร้าง: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if model_type:
            lines.append(f"🤖 Model: {model_type}")
        if target:
            lines.append(f"🎯 Target: {target}")
        lines.append(f"📊 จำนวนกฎ: {len(rules)}")
        lines.append("")
        
        # Group by category
        categories = {}
        for rule in rules:
            cat = rule.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(rule)
        
        category_names = {
            'title': '📝 Title',
            'description': '📄 Description',
            'timing': '⏰ Timing',
            'duration': '⏱️ Duration',
            'tags': '🏷️ Tags',
            'other': '📦 Other',
        }
        
        for cat, cat_rules in categories.items():
            lines.append(f"\n{category_names.get(cat, cat)}")
            lines.append("-" * 40)
            
            for rule in sorted(cat_rules, key=lambda x: x.importance_score, reverse=True):
                priority_icon = "🔴" if rule.priority == 'high' else "🟡" if rule.priority == 'medium' else "🟢"
                lines.append(f"  {priority_icon} {rule.rule_text_th}")
                lines.append(f"      ความมั่นใจ: {rule.confidence:.1%}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def print_rules(self, rules: List[PlaybookRule]):
        """แสดงกฎในรูปแบบ rich table"""
        
        console.print(Panel.fit(
            "[bold cyan]📋 Playbook Rules[/bold cyan]",
            border_style="cyan"
        ))
        
        # High priority rules
        high_priority = [r for r in rules if r.priority == 'high']
        if high_priority:
            console.print("\n[bold red]🔴 กฎสำคัญ (High Priority)[/bold red]")
            for rule in high_priority:
                console.print(f"  {rule.rule_text_th}")
                console.print(f"    [dim]ความมั่นใจ: {rule.confidence:.1%} | {rule.evidence}[/dim]")
        
        # Medium priority rules
        medium_priority = [r for r in rules if r.priority == 'medium']
        if medium_priority:
            console.print("\n[bold yellow]🟡 กฎทั่วไป (Medium Priority)[/bold yellow]")
            for rule in medium_priority:
                console.print(f"  {rule.rule_text_th}")
                console.print(f"    [dim]ความมั่นใจ: {rule.confidence:.1%}[/dim]")
        
        # Low priority rules
        low_priority = [r for r in rules if r.priority == 'low']
        if low_priority:
            console.print("\n[bold green]🟢 กฎเสริม (Low Priority)[/bold green]")
            for rule in low_priority:
                console.print(f"  {rule.rule_text_th}")
    
    def print_top_factors(
        self,
        feature_importance: Dict[str, float],
        top_n: int = 5,
    ):
        """แสดง top positive/negative factors"""
        
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Positive factors
        console.print("\n[bold green]🔼 Top Positive Factors[/bold green]")
        table_pos = Table()
        table_pos.add_column("Rank", style="dim")
        table_pos.add_column("Feature", style="green")
        table_pos.add_column("คำอธิบาย", style="cyan")
        table_pos.add_column("Score", justify="right")
        
        for i, (name, score) in enumerate([f for f in sorted_features if f[1] > 0][:top_n], 1):
            desc = self.feature_translations.get(name, name)
            table_pos.add_row(str(i), name, desc, f"+{score:.4f}")
        
        console.print(table_pos)
        
        # Negative factors
        console.print("\n[bold red]🔽 Top Negative Factors[/bold red]")
        table_neg = Table()
        table_neg.add_column("Rank", style="dim")
        table_neg.add_column("Feature", style="red")
        table_neg.add_column("คำอธิบาย", style="cyan")
        table_neg.add_column("Score", justify="right")
        
        negative_features = [f for f in sorted_features if f[1] < 0]
        negative_features.reverse()  # Most negative first
        
        for i, (name, score) in enumerate(negative_features[:top_n], 1):
            desc = self.feature_translations.get(name, name)
            table_neg.add_row(str(i), name, desc, f"{score:.4f}")
        
        console.print(table_neg)
    
    def to_database_format(
        self,
        rules: List[PlaybookRule],
        model_type: str = "",
        target: str = "",
        model_metrics: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        แปลงกฎเป็น format สำหรับบันทึกลง database
        
        Args:
            rules: รายการกฎ
            model_type: ประเภท model
            target: target variable
            model_metrics: metrics ของ model
            
        Returns:
            รายการ dict สำหรับบันทึกลง playbook_rules table
        """
        records = []
        timestamp = datetime.now()
        
        for rule in rules:
            record = {
                'name': rule.rule_id,
                'description': rule.rule_text_th,
                'rule_type': 'ml_generated',
                'category': rule.category,
                'condition': json.dumps({
                    'feature': rule.feature_name,
                    'direction': rule.direction,
                    'importance': rule.importance_score,
                }),
                'action': rule.rule_text_th,
                'priority': rule.priority,
                'confidence_score': rule.confidence,
                'success_rate': model_metrics.get('accuracy', 0.0) if model_metrics else 0.0,
                'times_applied': 0,
                'times_successful': 0,
                'source': f'ml_model_{model_type}',
                'evidence': json.dumps({
                    'model_type': model_type,
                    'target': target,
                    'importance_score': rule.importance_score,
                    'model_metrics': model_metrics,
                }),
                'is_active': True,
                'created_at': timestamp,
                'updated_at': timestamp,
            }
            records.append(record)
        
        return records
