"""
Playbook Learning Module - เรียนรู้จาก YouTube metrics และสร้างกฎภาษาไทย

โมดูลนี้ประกอบด้วย:
- feature_extractor: ดึง features จาก title, description, publish time, duration
- model_trainer: ฝึก interpretable models (sklearn)
- rule_generator: สร้างกฎภาษาไทยจากโมเดล
"""

from .feature_extractor import FeatureExtractor, VideoFeatures
from .model_trainer import PlaybookModelTrainer
from .rule_generator import ThaiRuleGenerator

__all__ = [
    "FeatureExtractor",
    "VideoFeatures",
    "PlaybookModelTrainer",
    "ThaiRuleGenerator",
]
