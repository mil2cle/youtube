"""
Anime Research Module - ดึงข้อมูลอนิเมะจากแหล่งที่เป็นทางการ

รองรับแหล่งข้อมูล:
- AniList GraphQL API (หลัก): trending, seasonal, top, relations, characters/staff
- Anime News Network RSS (รอง): ข่าวสารอนิเมะล่าสุด

การใช้งาน:
    from src.anime import AniListClient, RSSFeedParser, EntityLinker
"""

from src.anime.anilist import AniListClient
from src.anime.rss_parser import RSSFeedParser
from src.anime.entity_linker import EntityLinker

__all__ = [
    "AniListClient",
    "RSSFeedParser",
    "EntityLinker",
]
