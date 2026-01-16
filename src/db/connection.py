"""
Database Connection Module - จัดการการเชื่อมต่อฐานข้อมูล
รองรับ SQLite และสามารถขยายไปยัง database อื่นได้
"""

import os
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from rich.console import Console

console = Console()

class DatabaseConnection:
    """
    Class สำหรับจัดการ Database Connection
    """
    _engine: Engine | None = None
    _SessionLocal: sessionmaker | None = None

    def __init__(self, db_url: str, echo: bool = False):
        self.db_url = db_url
        self.echo = echo
        if DatabaseConnection._engine is None:
            self._initialize_engine()

    def _initialize_engine(self):
        """สร้าง engine และ session factory"""
        db_path = self.db_url.replace("sqlite:///", "")
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        DatabaseConnection._engine = create_engine(
            self.db_url,
            echo=self.echo,
            connect_args={"check_same_thread": False},  # สำหรับ SQLite
            pool_pre_ping=True,
        )

        @event.listens_for(DatabaseConnection._engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        DatabaseConnection._SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=DatabaseConnection._engine,
        )
        console.print(f"[green]✓[/green] เชื่อมต่อฐานข้อมูลสำเร็จ: {db_path}")

    def get_engine(self) -> Engine:
        """คืนค่า engine"""
        if DatabaseConnection._engine is None:
            self._initialize_engine()
        return DatabaseConnection._engine

    def get_session(self) -> Session:
        """คืนค่า session"""
        if DatabaseConnection._SessionLocal is None:
            self._initialize_engine()
        return DatabaseConnection._SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Context manager สำหรับจัดการ database session"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            console.print(f"[red]✗[/red] Database error: {e}")
            raise
        finally:
            session.close()

    def create_tables(self):
        """สร้าง tables ทั้งหมด"""
        from src.db.models import Base
        engine = self.get_engine()
        Base.metadata.create_all(bind=engine)
        console.print("[green]✓[/green] สร้าง tables ทั้งหมดสำเร็จ")

    def reset_database(self):
        """ลบและสร้างฐานข้อมูลใหม่"""
        from src.db.models import Base
        engine = self.get_engine()
        
        # ปิด connections เดิม
        engine.dispose()
        
        # ลบไฟล์ database เดิม
        db_path = self.db_url.replace("sqlite:///", "")
        db_file = Path(db_path)
        if db_file.exists():
            db_file.unlink()
            console.print(f"[yellow]![/yellow] ลบฐานข้อมูลเดิม: {db_path}")
        
        # สร้างใหม่
        Base.metadata.create_all(bind=engine)
        console.print("[green]✓[/green] รีเซ็ตฐานข้อมูลสำเร็จ")

    @staticmethod
    def close_db():
        """ปิด database connections ทั้งหมด"""
        if DatabaseConnection._engine:
            DatabaseConnection._engine.dispose()
            DatabaseConnection._engine = None
            DatabaseConnection._SessionLocal = None
            console.print("[green]✓[/green] ปิดการเชื่อมต่อฐานข้อมูลสำเร็จ")
