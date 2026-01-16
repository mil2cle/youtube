"""
Logger Module - จัดการ logging สำหรับระบบ
รองรับทั้ง file logging และ console output ด้วย rich
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Custom theme สำหรับ console
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "success": "green",
})

console = Console(theme=custom_theme)

# Global logger storage
_loggers: dict[str, logging.Logger] = {}


def setup_logger(
    name: str = "youtube_assistant",
    log_file: str = "logs/app.log",
    level: str = "INFO",
    max_size_mb: int = 10,
    backup_count: int = 5,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    ตั้งค่า logger พร้อม file handler และ console handler
    
    Args:
        name: ชื่อ logger
        log_file: path ไปยังไฟล์ log
        level: log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_size_mb: ขนาดสูงสุดของไฟล์ log (MB)
        backup_count: จำนวน backup files
        log_format: รูปแบบ log message
        
    Returns:
        Configured logger
    """
    # ถ้ามี logger อยู่แล้ว ให้คืนค่าเดิม
    if name in _loggers:
        return _loggers[name]
    
    # สร้าง logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # ป้องกันการ duplicate handlers
    if logger.handlers:
        return logger
    
    # Default format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    formatter = logging.Formatter(log_format)
    
    # File Handler
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    logger.addHandler(file_handler)
    
    # Rich Console Handler
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.addHandler(rich_handler)
    
    # เก็บ logger
    _loggers[name] = logger
    
    logger.info(f"Logger '{name}' ถูกตั้งค่าสำเร็จ (level: {level})")
    return logger


def get_logger(name: str = "youtube_assistant") -> logging.Logger:
    """
    ดึง logger ที่มีอยู่หรือสร้างใหม่
    
    Args:
        name: ชื่อ logger
        
    Returns:
        Logger instance
    """
    if name not in _loggers:
        return setup_logger(name)
    return _loggers[name]


class TaskLogger:
    """
    Logger สำหรับ task-specific logging
    รองรับการ track progress และ timing
    """
    
    def __init__(self, task_name: str, logger: Optional[logging.Logger] = None):
        self.task_name = task_name
        self.logger = logger or get_logger()
        self.start_time: Optional[datetime] = None
        self.step_count = 0
    
    def start(self, message: str = "เริ่มต้น task") -> None:
        """เริ่ม task และบันทึกเวลา"""
        self.start_time = datetime.now()
        self.step_count = 0
        self.logger.info(f"[{self.task_name}] {message}")
        console.print(f"[success]▶[/success] [{self.task_name}] {message}")
    
    def step(self, message: str) -> None:
        """บันทึก step ของ task"""
        self.step_count += 1
        self.logger.info(f"[{self.task_name}] Step {self.step_count}: {message}")
        console.print(f"  [info]→[/info] Step {self.step_count}: {message}")
    
    def progress(self, current: int, total: int, message: str = "") -> None:
        """แสดง progress"""
        percentage = (current / total * 100) if total > 0 else 0
        progress_msg = f"[{self.task_name}] Progress: {current}/{total} ({percentage:.1f}%)"
        if message:
            progress_msg += f" - {message}"
        self.logger.info(progress_msg)
    
    def warning(self, message: str) -> None:
        """บันทึก warning"""
        self.logger.warning(f"[{self.task_name}] {message}")
        console.print(f"  [warning]⚠[/warning] {message}")
    
    def error(self, message: str, exc_info: bool = False) -> None:
        """บันทึก error"""
        self.logger.error(f"[{self.task_name}] {message}", exc_info=exc_info)
        console.print(f"  [error]✗[/error] {message}")
    
    def complete(self, message: str = "เสร็จสิ้น") -> float:
        """
        จบ task และคืนค่าเวลาที่ใช้
        
        Returns:
            เวลาที่ใช้ในหน่วยวินาที
        """
        duration = 0.0
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
        
        complete_msg = f"[{self.task_name}] {message} (ใช้เวลา {duration:.2f} วินาที, {self.step_count} steps)"
        self.logger.info(complete_msg)
        console.print(f"[success]✓[/success] [{self.task_name}] {message} ({duration:.2f}s)")
        
        return duration
    
    def fail(self, message: str, exc_info: bool = True) -> float:
        """
        บันทึกว่า task ล้มเหลว
        
        Returns:
            เวลาที่ใช้ในหน่วยวินาที
        """
        duration = 0.0
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
        
        fail_msg = f"[{self.task_name}] ล้มเหลว: {message} (ใช้เวลา {duration:.2f} วินาที)"
        self.logger.error(fail_msg, exc_info=exc_info)
        console.print(f"[error]✗[/error] [{self.task_name}] ล้มเหลว: {message}")
        
        return duration


def log_function_call(func):
    """
    Decorator สำหรับ log function calls
    
    Example:
        @log_function_call
        def my_function(arg1, arg2):
            pass
    """
    def wrapper(*args, **kwargs):
        logger = get_logger()
        func_name = func.__name__
        
        logger.debug(f"เรียก {func_name} ด้วย args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func_name} สำเร็จ")
            return result
        except Exception as e:
            logger.error(f"{func_name} ล้มเหลว: {e}", exc_info=True)
            raise
    
    return wrapper


def print_banner(title: str, subtitle: str = "") -> None:
    """
    แสดง banner สำหรับ CLI
    
    Args:
        title: หัวข้อหลัก
        subtitle: หัวข้อรอง
    """
    console.print()
    console.print("=" * 60, style="cyan")
    console.print(f"  {title}", style="bold cyan")
    if subtitle:
        console.print(f"  {subtitle}", style="dim")
    console.print("=" * 60, style="cyan")
    console.print()


def print_success(message: str) -> None:
    """แสดงข้อความสำเร็จ"""
    console.print(f"[success]✓[/success] {message}")


def print_error(message: str) -> None:
    """แสดงข้อความ error"""
    console.print(f"[error]✗[/error] {message}")


def print_warning(message: str) -> None:
    """แสดงข้อความ warning"""
    console.print(f"[warning]![/warning] {message}")


def print_info(message: str) -> None:
    """แสดงข้อความ info"""
    console.print(f"[info]ℹ[/info] {message}")
