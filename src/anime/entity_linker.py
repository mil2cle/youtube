"""
Entity Linker - Normalize ชื่ออนิเมะและ map กับ series

ใช้สำหรับ:
- ดึงชื่ออนิเมะจากข้อความ (entity extraction)
- Normalize ชื่อให้เป็นมาตรฐาน
- Map กับ AniList ID เพื่อเชื่อมโยงข้อมูล
- จัดการ aliases และชื่อภาษาต่างๆ

วิธีการทำงาน:
1. ใช้ AniList Search API เพื่อค้นหาและ verify ชื่ออนิเมะ
2. Cache ผลลัพธ์เพื่อลดการเรียก API
3. ใช้ fuzzy matching สำหรับชื่อที่ไม่ตรงกันทั้งหมด
"""

import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from rich.console import Console

from src.anime.anilist import AniListClient, AnimeData

console = Console()


@dataclass
class LinkedEntity:
    """โครงสร้างข้อมูล entity ที่ถูก link แล้ว"""
    
    original_text: str  # ข้อความต้นฉบับ
    normalized_title: str  # ชื่อที่ normalize แล้ว
    anilist_id: Optional[int] = None
    mal_id: Optional[int] = None
    confidence: float = 0.0  # 0.0-1.0
    match_type: str = "none"  # exact, fuzzy, partial, none
    anime_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """แปลงเป็น dictionary"""
        return {
            "original_text": self.original_text,
            "normalized_title": self.normalized_title,
            "anilist_id": self.anilist_id,
            "mal_id": self.mal_id,
            "confidence": self.confidence,
            "match_type": self.match_type,
            "anime_data": self.anime_data,
        }


class EntityLinker:
    """
    Entity Linker สำหรับ normalize ชื่ออนิเมะและ map กับ series
    
    การใช้งาน:
        linker = EntityLinker()
        
        # Link ชื่อเดียว
        result = linker.link_entity("Attack on Titan")
        
        # Link หลายชื่อ
        results = linker.link_entities(["AOT", "Demon Slayer", "One Piece"])
        
        # Extract และ link จากข้อความ
        entities = linker.extract_and_link("New episode of Attack on Titan announced!")
    """
    
    # Common anime title patterns
    TITLE_PATTERNS = [
        r'"([^"]+)"',  # Quoted titles
        r"'([^']+)'",  # Single quoted titles
        r"「([^」]+)」",  # Japanese quotes
        r"『([^』]+)』",  # Japanese double quotes
    ]
    
    # Common abbreviations and aliases
    KNOWN_ALIASES = {
        "aot": "Attack on Titan",
        "snk": "Shingeki no Kyojin",
        "mha": "My Hero Academia",
        "bnha": "Boku no Hero Academia",
        "kny": "Kimetsu no Yaiba",
        "ds": "Demon Slayer",
        "op": "One Piece",
        "jjk": "Jujutsu Kaisen",
        "csm": "Chainsaw Man",
        "sao": "Sword Art Online",
        "re:zero": "Re:Zero kara Hajimeru Isekai Seikatsu",
        "konosuba": "Kono Subarashii Sekai ni Shukufuku wo!",
        "oregairu": "Yahari Ore no Seishun Love Comedy wa Machigatteiru",
        "danmachi": "Dungeon ni Deai wo Motomeru no wa Machigatteiru Darou ka",
        "fate/stay night": "Fate/stay night",
        "fate/zero": "Fate/Zero",
        "fgo": "Fate/Grand Order",
        "fma": "Fullmetal Alchemist",
        "fmab": "Fullmetal Alchemist: Brotherhood",
        "hxh": "Hunter x Hunter",
        "yyh": "Yu Yu Hakusho",
        "dbz": "Dragon Ball Z",
        "dbs": "Dragon Ball Super",
        "naruto shippuden": "Naruto: Shippuuden",
        "boruto": "Boruto: Naruto Next Generations",
        "bleach tybw": "Bleach: Thousand-Year Blood War",
        "spy x family": "SPY×FAMILY",
        "spyxfamily": "SPY×FAMILY",
        "oshi no ko": "Oshi no Ko",
        "frieren": "Sousou no Frieren",
        "solo leveling": "Solo Leveling",
    }
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 24,
        min_confidence: float = 0.6
    ):
        """
        สร้าง Entity Linker
        
        Args:
            cache_dir: โฟลเดอร์สำหรับเก็บ cache (default: data/entity_cache)
            cache_ttl_hours: อายุของ cache (ชั่วโมง)
            min_confidence: ค่า confidence ขั้นต่ำสำหรับการ link
        """
        self.anilist = AniListClient()
        self.min_confidence = min_confidence
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        
        # Setup cache
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path(__file__).parent.parent.parent / "data" / "entity_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "entity_cache.json"
        
        # Load cache
        self._cache: Dict[str, Dict] = {}
        self._load_cache()
    
    def _load_cache(self):
        """โหลด cache จากไฟล์"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # Filter expired entries
                now = datetime.now()
                for key, entry in data.items():
                    cached_at = datetime.fromisoformat(entry.get("cached_at", "2000-01-01"))
                    if now - cached_at < self.cache_ttl:
                        self._cache[key] = entry
                
                console.print(f"[dim]📦 โหลด entity cache: {len(self._cache)} รายการ[/dim]")
            except Exception as e:
                console.print(f"[yellow]⚠️ ไม่สามารถโหลด cache: {e}[/yellow]")
    
    def _save_cache(self):
        """บันทึก cache ลงไฟล์"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(f"[yellow]⚠️ ไม่สามารถบันทึก cache: {e}[/yellow]")
    
    def _normalize_text(self, text: str) -> str:
        """Normalize ข้อความสำหรับการเปรียบเทียบ"""
        # Lowercase
        text = text.lower()
        
        # Remove special characters except basic punctuation
        text = re.sub(r'[^\w\s\-:!?]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """คำนวณความคล้ายคลึงระหว่างสองข้อความ"""
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def _get_cache_key(self, text: str) -> str:
        """สร้าง cache key จากข้อความ"""
        return self._normalize_text(text)
    
    def _check_cache(self, text: str) -> Optional[LinkedEntity]:
        """ตรวจสอบว่ามีใน cache หรือไม่"""
        key = self._get_cache_key(text)
        
        if key in self._cache:
            entry = self._cache[key]
            return LinkedEntity(
                original_text=text,
                normalized_title=entry.get("normalized_title", ""),
                anilist_id=entry.get("anilist_id"),
                mal_id=entry.get("mal_id"),
                confidence=entry.get("confidence", 0.0),
                match_type=entry.get("match_type", "cached"),
                anime_data=entry.get("anime_data"),
            )
        
        return None
    
    def _add_to_cache(self, text: str, entity: LinkedEntity):
        """เพิ่มผลลัพธ์ลง cache"""
        key = self._get_cache_key(text)
        
        self._cache[key] = {
            "normalized_title": entity.normalized_title,
            "anilist_id": entity.anilist_id,
            "mal_id": entity.mal_id,
            "confidence": entity.confidence,
            "match_type": entity.match_type,
            "anime_data": entity.anime_data,
            "cached_at": datetime.now().isoformat(),
        }
        
        self._save_cache()
    
    def _resolve_alias(self, text: str) -> str:
        """แปลง alias เป็นชื่อเต็ม"""
        normalized = self._normalize_text(text)
        
        if normalized in self.KNOWN_ALIASES:
            return self.KNOWN_ALIASES[normalized]
        
        return text
    
    def link_entity(self, text: str, use_cache: bool = True) -> LinkedEntity:
        """
        Link ชื่ออนิเมะเดียวกับ AniList
        
        Args:
            text: ชื่อหรือข้อความที่ต้องการ link
            use_cache: ใช้ cache หรือไม่
            
        Returns:
            LinkedEntity พร้อมข้อมูลที่ link แล้ว
        """
        # Check cache first
        if use_cache:
            cached = self._check_cache(text)
            if cached:
                console.print(f"[dim]📦 Cache hit: {text}[/dim]")
                return cached
        
        # Resolve aliases
        resolved_text = self._resolve_alias(text)
        
        # Search on AniList
        results = self.anilist.search_anime(resolved_text, limit=5)
        
        if not results:
            entity = LinkedEntity(
                original_text=text,
                normalized_title=text,
                confidence=0.0,
                match_type="none",
            )
            self._add_to_cache(text, entity)
            return entity
        
        # Find best match
        best_match: Optional[AnimeData] = None
        best_confidence = 0.0
        match_type = "none"
        
        for anime in results:
            # Check all title variants
            titles = [
                anime.title_romaji,
                anime.title_english,
                anime.title_native,
            ]
            
            for title in titles:
                if not title:
                    continue
                
                similarity = self._calculate_similarity(resolved_text, title)
                
                if similarity > best_confidence:
                    best_confidence = similarity
                    best_match = anime
                    
                    if similarity >= 0.95:
                        match_type = "exact"
                    elif similarity >= 0.7:
                        match_type = "fuzzy"
                    else:
                        match_type = "partial"
        
        # Create result
        if best_match and best_confidence >= self.min_confidence:
            entity = LinkedEntity(
                original_text=text,
                normalized_title=best_match.get_best_title(),
                anilist_id=best_match.anilist_id,
                mal_id=best_match.mal_id,
                confidence=best_confidence,
                match_type=match_type,
                anime_data=best_match.to_dict(),
            )
        else:
            entity = LinkedEntity(
                original_text=text,
                normalized_title=text,
                confidence=best_confidence,
                match_type="none",
            )
        
        # Cache result
        self._add_to_cache(text, entity)
        
        return entity
    
    def link_entities(
        self,
        texts: List[str],
        use_cache: bool = True
    ) -> List[LinkedEntity]:
        """
        Link หลายชื่ออนิเมะ
        
        Args:
            texts: รายการชื่อที่ต้องการ link
            use_cache: ใช้ cache หรือไม่
            
        Returns:
            รายการ LinkedEntity
        """
        results = []
        
        for text in texts:
            result = self.link_entity(text, use_cache=use_cache)
            results.append(result)
        
        return results
    
    def extract_entities(self, text: str) -> List[str]:
        """
        ดึงชื่ออนิเมะจากข้อความ
        
        Args:
            text: ข้อความที่ต้องการดึง entities
            
        Returns:
            รายการชื่อที่พบ
        """
        entities = []
        
        # Extract quoted titles
        for pattern in self.TITLE_PATTERNS:
            matches = re.findall(pattern, text)
            entities.extend(matches)
        
        # Check for known aliases in text
        text_lower = text.lower()
        for alias, full_name in self.KNOWN_ALIASES.items():
            # Use word boundary to avoid partial matches
            if re.search(rf'\b{re.escape(alias)}\b', text_lower):
                entities.append(full_name)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            normalized = self._normalize_text(entity)
            if normalized not in seen:
                seen.add(normalized)
                unique_entities.append(entity)
        
        return unique_entities
    
    def extract_and_link(
        self,
        text: str,
        use_cache: bool = True
    ) -> List[LinkedEntity]:
        """
        ดึงชื่ออนิเมะจากข้อความและ link กับ AniList
        
        Args:
            text: ข้อความที่ต้องการประมวลผล
            use_cache: ใช้ cache หรือไม่
            
        Returns:
            รายการ LinkedEntity ที่พบและ link แล้ว
        """
        entities = self.extract_entities(text)
        
        if not entities:
            return []
        
        return self.link_entities(entities, use_cache=use_cache)
    
    def add_alias(self, alias: str, full_name: str):
        """
        เพิ่ม alias ใหม่
        
        Args:
            alias: ชื่อย่อหรือ alias
            full_name: ชื่อเต็ม
        """
        self.KNOWN_ALIASES[alias.lower()] = full_name
        console.print(f"[green]✅ เพิ่ม alias: {alias} -> {full_name}[/green]")
    
    def get_aliases(self) -> Dict[str, str]:
        """คืนค่ารายการ aliases ทั้งหมด"""
        return self.KNOWN_ALIASES.copy()
    
    def clear_cache(self):
        """ล้าง cache ทั้งหมด"""
        self._cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        console.print("[green]✅ ล้าง entity cache สำเร็จ[/green]")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """คืนค่าสถิติของ cache"""
        return {
            "total_entries": len(self._cache),
            "cache_file": str(self.cache_file),
            "cache_ttl_hours": self.cache_ttl.total_seconds() / 3600,
        }
