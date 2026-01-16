"""
AniList GraphQL API Client - ดึงข้อมูลอนิเมะจาก AniList

AniList API เป็น public API ที่ไม่ต้องใช้ API key สำหรับการดึงข้อมูลพื้นฐาน
Documentation: https://anilist.gitbook.io/anilist-apiv2-docs/

รองรับการดึงข้อมูล:
- Trending anime
- Seasonal anime
- Top anime (by popularity, score)
- Anime details (relations, characters, staff)
- Search anime by title
"""

import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import requests
from rich.console import Console

console = Console()

# AniList GraphQL endpoint
ANILIST_API_URL = "https://graphql.anilist.co"

# Rate limiting: AniList allows 90 requests per minute
RATE_LIMIT_DELAY = 0.7  # seconds between requests


@dataclass
class AnimeData:
    """โครงสร้างข้อมูลอนิเมะจาก AniList"""
    
    anilist_id: int
    mal_id: Optional[int] = None
    title_romaji: str = ""
    title_english: Optional[str] = None
    title_native: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None  # TV, MOVIE, OVA, ONA, SPECIAL, MUSIC
    status: Optional[str] = None  # FINISHED, RELEASING, NOT_YET_RELEASED, CANCELLED
    episodes: Optional[int] = None
    duration: Optional[int] = None  # minutes per episode
    season: Optional[str] = None  # WINTER, SPRING, SUMMER, FALL
    season_year: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    tags: List[Dict[str, Any]] = field(default_factory=list)
    average_score: Optional[int] = None  # 0-100
    popularity: Optional[int] = None
    trending: Optional[int] = None
    favourites: Optional[int] = None
    studios: List[str] = field(default_factory=list)
    source: Optional[str] = None  # ORIGINAL, MANGA, LIGHT_NOVEL, etc.
    cover_image: Optional[str] = None
    banner_image: Optional[str] = None
    site_url: str = ""
    
    # Relations
    relations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Characters (basic info only)
    characters: List[Dict[str, Any]] = field(default_factory=list)
    
    # Staff (basic info only)
    staff: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_best_title(self) -> str:
        """คืนค่า title ที่ดีที่สุด (English > Romaji > Native)"""
        return self.title_english or self.title_romaji or self.title_native or "Unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """แปลงเป็น dictionary"""
        return {
            "anilist_id": self.anilist_id,
            "mal_id": self.mal_id,
            "title_romaji": self.title_romaji,
            "title_english": self.title_english,
            "title_native": self.title_native,
            "description": self.description,
            "format": self.format,
            "status": self.status,
            "episodes": self.episodes,
            "duration": self.duration,
            "season": self.season,
            "season_year": self.season_year,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "genres": self.genres,
            "tags": self.tags,
            "average_score": self.average_score,
            "popularity": self.popularity,
            "trending": self.trending,
            "favourites": self.favourites,
            "studios": self.studios,
            "source": self.source,
            "cover_image": self.cover_image,
            "banner_image": self.banner_image,
            "site_url": self.site_url,
            "relations": self.relations,
            "characters": self.characters,
            "staff": self.staff,
        }


class AniListClient:
    """
    AniList GraphQL API Client
    
    ใช้สำหรับดึงข้อมูลอนิเมะจาก AniList API
    ไม่ต้องใช้ API key สำหรับการดึงข้อมูลพื้นฐาน
    
    การใช้งาน:
        client = AniListClient()
        trending = client.get_trending_anime(limit=10)
        seasonal = client.get_seasonal_anime(2024, "WINTER")
    """
    
    def __init__(self, timeout: int = 30):
        """
        สร้าง AniList client
        
        Args:
            timeout: timeout สำหรับ API requests (วินาที)
        """
        self.api_url = ANILIST_API_URL
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._last_request_time = 0.0
    
    def _rate_limit(self):
        """ควบคุม rate limit"""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()
    
    def _execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        รัน GraphQL query
        
        Args:
            query: GraphQL query string
            variables: ตัวแปรสำหรับ query
            
        Returns:
            ผลลัพธ์จาก API หรือ None หากเกิดข้อผิดพลาด
        """
        self._rate_limit()
        
        try:
            response = self.session.post(
                self.api_url,
                json={"query": query, "variables": variables or {}},
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                console.print(f"[red]❌ AniList API Error: {data['errors']}[/red]")
                return None
            
            return data.get("data")
            
        except requests.exceptions.Timeout:
            console.print("[red]❌ AniList API Timeout[/red]")
            return None
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ AniList API Request Error: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ AniList API Error: {e}[/red]")
            return None
    
    def _parse_anime(self, media: Dict[str, Any]) -> AnimeData:
        """แปลงข้อมูลจาก API เป็น AnimeData"""
        
        # Parse dates
        start_date = None
        if media.get("startDate"):
            sd = media["startDate"]
            if sd.get("year"):
                month = sd.get('month') or 1
                day = sd.get('day') or 1
                start_date = f"{sd.get('year', '')}-{month:02d}-{day:02d}"
        
        end_date = None
        if media.get("endDate"):
            ed = media["endDate"]
            if ed.get("year"):
                month = ed.get('month') or 1
                day = ed.get('day') or 1
                end_date = f"{ed.get('year', '')}-{month:02d}-{day:02d}"
        
        # Parse studios
        studios = []
        if media.get("studios", {}).get("nodes"):
            studios = [s["name"] for s in media["studios"]["nodes"] if s.get("name")]
        
        # Parse relations
        relations = []
        if media.get("relations", {}).get("edges"):
            for edge in media["relations"]["edges"]:
                if edge.get("node"):
                    relations.append({
                        "relation_type": edge.get("relationType"),
                        "anilist_id": edge["node"].get("id"),
                        "title": edge["node"].get("title", {}).get("romaji"),
                        "format": edge["node"].get("format"),
                    })
        
        # Parse characters
        characters = []
        if media.get("characters", {}).get("edges"):
            for edge in media["characters"]["edges"][:10]:  # Limit to 10
                if edge.get("node"):
                    characters.append({
                        "name": edge["node"].get("name", {}).get("full"),
                        "role": edge.get("role"),
                        "image": edge["node"].get("image", {}).get("medium"),
                    })
        
        # Parse staff
        staff = []
        if media.get("staff", {}).get("edges"):
            for edge in media["staff"]["edges"][:10]:  # Limit to 10
                if edge.get("node"):
                    staff.append({
                        "name": edge["node"].get("name", {}).get("full"),
                        "role": edge.get("role"),
                        "image": edge["node"].get("image", {}).get("medium"),
                    })
        
        return AnimeData(
            anilist_id=media.get("id", 0),
            mal_id=media.get("idMal"),
            title_romaji=media.get("title", {}).get("romaji", ""),
            title_english=media.get("title", {}).get("english"),
            title_native=media.get("title", {}).get("native"),
            description=media.get("description"),
            format=media.get("format"),
            status=media.get("status"),
            episodes=media.get("episodes"),
            duration=media.get("duration"),
            season=media.get("season"),
            season_year=media.get("seasonYear"),
            start_date=start_date,
            end_date=end_date,
            genres=media.get("genres", []),
            tags=[{"name": t["name"], "rank": t.get("rank")} for t in media.get("tags", [])[:10]],
            average_score=media.get("averageScore"),
            popularity=media.get("popularity"),
            trending=media.get("trending"),
            favourites=media.get("favourites"),
            studios=studios,
            source=media.get("source"),
            cover_image=media.get("coverImage", {}).get("large"),
            banner_image=media.get("bannerImage"),
            site_url=media.get("siteUrl", ""),
            relations=relations,
            characters=characters,
            staff=staff,
        )
    
    def get_trending_anime(self, limit: int = 20, page: int = 1) -> List[AnimeData]:
        """
        ดึงอนิเมะที่กำลัง trending
        
        Args:
            limit: จำนวนรายการที่ต้องการ (สูงสุด 50)
            page: หน้าที่ต้องการ
            
        Returns:
            รายการอนิเมะที่กำลัง trending
        """
        console.print(f"[cyan]📊 กำลังดึงข้อมูล Trending Anime (หน้า {page})...[/cyan]")
        
        query = """
        query ($page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                pageInfo {
                    total
                    currentPage
                    hasNextPage
                }
                media(type: ANIME, sort: TRENDING_DESC) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    description(asHtml: false)
                    format
                    status
                    episodes
                    duration
                    season
                    seasonYear
                    startDate { year month day }
                    endDate { year month day }
                    genres
                    tags { name rank }
                    averageScore
                    popularity
                    trending
                    favourites
                    studios { nodes { name } }
                    source
                    coverImage { large }
                    bannerImage
                    siteUrl
                }
            }
        }
        """
        
        data = self._execute_query(query, {"page": page, "perPage": min(limit, 50)})
        
        if not data or not data.get("Page", {}).get("media"):
            return []
        
        anime_list = [self._parse_anime(m) for m in data["Page"]["media"]]
        console.print(f"[green]✅ ดึงข้อมูล Trending Anime สำเร็จ: {len(anime_list)} รายการ[/green]")
        
        return anime_list
    
    def get_seasonal_anime(
        self,
        year: int,
        season: str,
        limit: int = 50,
        page: int = 1
    ) -> List[AnimeData]:
        """
        ดึงอนิเมะตาม season
        
        Args:
            year: ปี (เช่น 2024)
            season: ฤดูกาล (WINTER, SPRING, SUMMER, FALL)
            limit: จำนวนรายการที่ต้องการ
            page: หน้าที่ต้องการ
            
        Returns:
            รายการอนิเมะใน season นั้น
        """
        console.print(f"[cyan]📅 กำลังดึงข้อมูล Seasonal Anime ({season} {year})...[/cyan]")
        
        query = """
        query ($page: Int, $perPage: Int, $season: MediaSeason, $seasonYear: Int) {
            Page(page: $page, perPage: $perPage) {
                pageInfo {
                    total
                    currentPage
                    hasNextPage
                }
                media(type: ANIME, season: $season, seasonYear: $seasonYear, sort: POPULARITY_DESC) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    description(asHtml: false)
                    format
                    status
                    episodes
                    duration
                    season
                    seasonYear
                    startDate { year month day }
                    endDate { year month day }
                    genres
                    tags { name rank }
                    averageScore
                    popularity
                    trending
                    favourites
                    studios { nodes { name } }
                    source
                    coverImage { large }
                    bannerImage
                    siteUrl
                }
            }
        }
        """
        
        data = self._execute_query(query, {
            "page": page,
            "perPage": min(limit, 50),
            "season": season.upper(),
            "seasonYear": year,
        })
        
        if not data or not data.get("Page", {}).get("media"):
            return []
        
        anime_list = [self._parse_anime(m) for m in data["Page"]["media"]]
        console.print(f"[green]✅ ดึงข้อมูล Seasonal Anime สำเร็จ: {len(anime_list)} รายการ[/green]")
        
        return anime_list
    
    def get_top_anime(
        self,
        sort_by: str = "SCORE_DESC",
        limit: int = 50,
        page: int = 1
    ) -> List[AnimeData]:
        """
        ดึงอนิเมะยอดนิยม
        
        Args:
            sort_by: วิธีการเรียงลำดับ (SCORE_DESC, POPULARITY_DESC, FAVOURITES_DESC)
            limit: จำนวนรายการที่ต้องการ
            page: หน้าที่ต้องการ
            
        Returns:
            รายการอนิเมะยอดนิยม
        """
        console.print(f"[cyan]🏆 กำลังดึงข้อมูล Top Anime (sort: {sort_by})...[/cyan]")
        
        query = """
        query ($page: Int, $perPage: Int, $sort: [MediaSort]) {
            Page(page: $page, perPage: $perPage) {
                pageInfo {
                    total
                    currentPage
                    hasNextPage
                }
                media(type: ANIME, sort: $sort) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    description(asHtml: false)
                    format
                    status
                    episodes
                    duration
                    season
                    seasonYear
                    startDate { year month day }
                    endDate { year month day }
                    genres
                    tags { name rank }
                    averageScore
                    popularity
                    trending
                    favourites
                    studios { nodes { name } }
                    source
                    coverImage { large }
                    bannerImage
                    siteUrl
                }
            }
        }
        """
        
        data = self._execute_query(query, {
            "page": page,
            "perPage": min(limit, 50),
            "sort": [sort_by],
        })
        
        if not data or not data.get("Page", {}).get("media"):
            return []
        
        anime_list = [self._parse_anime(m) for m in data["Page"]["media"]]
        console.print(f"[green]✅ ดึงข้อมูล Top Anime สำเร็จ: {len(anime_list)} รายการ[/green]")
        
        return anime_list
    
    def get_anime_details(self, anilist_id: int) -> Optional[AnimeData]:
        """
        ดึงรายละเอียดอนิเมะพร้อม relations, characters, staff
        
        Args:
            anilist_id: AniList ID ของอนิเมะ
            
        Returns:
            ข้อมูลอนิเมะพร้อมรายละเอียด
        """
        console.print(f"[cyan]🔍 กำลังดึงรายละเอียดอนิเมะ ID: {anilist_id}...[/cyan]")
        
        query = """
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                id
                idMal
                title {
                    romaji
                    english
                    native
                }
                description(asHtml: false)
                format
                status
                episodes
                duration
                season
                seasonYear
                startDate { year month day }
                endDate { year month day }
                genres
                tags { name rank }
                averageScore
                popularity
                trending
                favourites
                studios { nodes { name } }
                source
                coverImage { large }
                bannerImage
                siteUrl
                relations {
                    edges {
                        relationType
                        node {
                            id
                            title { romaji }
                            format
                        }
                    }
                }
                characters(sort: ROLE, perPage: 10) {
                    edges {
                        role
                        node {
                            name { full }
                            image { medium }
                        }
                    }
                }
                staff(perPage: 10) {
                    edges {
                        role
                        node {
                            name { full }
                            image { medium }
                        }
                    }
                }
            }
        }
        """
        
        data = self._execute_query(query, {"id": anilist_id})
        
        if not data or not data.get("Media"):
            return None
        
        anime = self._parse_anime(data["Media"])
        console.print(f"[green]✅ ดึงรายละเอียดอนิเมะสำเร็จ: {anime.get_best_title()}[/green]")
        
        return anime
    
    def search_anime(
        self,
        search: str,
        limit: int = 10
    ) -> List[AnimeData]:
        """
        ค้นหาอนิเมะตามชื่อ
        
        Args:
            search: คำค้นหา
            limit: จำนวนผลลัพธ์ที่ต้องการ
            
        Returns:
            รายการอนิเมะที่ตรงกับคำค้นหา
        """
        console.print(f"[cyan]🔎 กำลังค้นหาอนิเมะ: '{search}'...[/cyan]")
        
        query = """
        query ($search: String, $perPage: Int) {
            Page(perPage: $perPage) {
                media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    description(asHtml: false)
                    format
                    status
                    episodes
                    duration
                    season
                    seasonYear
                    startDate { year month day }
                    endDate { year month day }
                    genres
                    tags { name rank }
                    averageScore
                    popularity
                    trending
                    favourites
                    studios { nodes { name } }
                    source
                    coverImage { large }
                    bannerImage
                    siteUrl
                }
            }
        }
        """
        
        data = self._execute_query(query, {"search": search, "perPage": min(limit, 25)})
        
        if not data or not data.get("Page", {}).get("media"):
            return []
        
        anime_list = [self._parse_anime(m) for m in data["Page"]["media"]]
        console.print(f"[green]✅ พบอนิเมะ {len(anime_list)} รายการ[/green]")
        
        return anime_list
    
    def get_current_season(self) -> tuple[int, str]:
        """
        คืนค่า season ปัจจุบัน
        
        Returns:
            tuple ของ (year, season)
        """
        now = datetime.now()
        year = now.year
        month = now.month
        
        if month in [1, 2, 3]:
            season = "WINTER"
        elif month in [4, 5, 6]:
            season = "SPRING"
        elif month in [7, 8, 9]:
            season = "SUMMER"
        else:
            season = "FALL"
        
        return year, season
