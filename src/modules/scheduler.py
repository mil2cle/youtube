"""
Scheduler Module - จัดการ scheduled jobs
รองรับการรัน tasks อัตโนมัติตามเวลาที่กำหนด
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
import traceback

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from sqlalchemy.orm import Session

from src.db.models import RunLog
from src.db.repository import RunLogRepository
from src.db.connection import session_scope
from src.utils.logger import get_logger, TaskLogger
from src.utils.config import get_config

logger = get_logger()


@dataclass
class JobInfo:
    """ข้อมูล job"""
    job_id: str
    name: str
    trigger_type: str
    next_run: Optional[datetime]
    is_running: bool


class SchedulerModule:
    """
    โมดูลจัดการ Scheduler
    
    รองรับ:
    - การสร้างและจัดการ scheduled jobs
    - การรัน jobs แบบ cron หรือ interval
    - การติดตามและ log การทำงาน
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self.scheduler = BackgroundScheduler(timezone="Asia/Bangkok")
        self.task_logger = TaskLogger("Scheduler")
        self._jobs: Dict[str, Callable] = {}
        self._is_running = False
        
        # Setup event listeners
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
    
    def start(self) -> None:
        """เริ่มต้น scheduler"""
        if not self._is_running:
            self.scheduler.start()
            self._is_running = True
            logger.info("Scheduler เริ่มทำงาน")
    
    def stop(self) -> None:
        """หยุด scheduler"""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Scheduler หยุดทำงาน")
    
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str,
        name: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        เพิ่ม job แบบ cron
        
        Args:
            job_id: ID ของ job
            func: function ที่จะรัน
            cron_expression: cron expression (minute hour day month day_of_week)
            name: ชื่อ job
            **kwargs: arguments สำหรับ function
            
        Returns:
            True ถ้าสำเร็จ
        """
        try:
            # Parse cron expression
            parts = cron_expression.split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
            else:
                logger.error(f"Cron expression ไม่ถูกต้อง: {cron_expression}")
                return False
            
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            )
            
            self.scheduler.add_job(
                func,
                trigger,
                id=job_id,
                name=name or job_id,
                kwargs=kwargs,
                replace_existing=True,
            )
            
            self._jobs[job_id] = func
            logger.info(f"เพิ่ม cron job: {job_id} ({cron_expression})")
            return True
            
        except Exception as e:
            logger.error(f"ไม่สามารถเพิ่ม cron job: {e}")
            return False
    
    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        name: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        เพิ่ม job แบบ interval
        
        Args:
            job_id: ID ของ job
            func: function ที่จะรัน
            seconds: interval ในหน่วยวินาที
            minutes: interval ในหน่วยนาที
            hours: interval ในหน่วยชั่วโมง
            name: ชื่อ job
            **kwargs: arguments สำหรับ function
            
        Returns:
            True ถ้าสำเร็จ
        """
        try:
            trigger = IntervalTrigger(
                seconds=seconds or 0,
                minutes=minutes or 0,
                hours=hours or 0,
            )
            
            self.scheduler.add_job(
                func,
                trigger,
                id=job_id,
                name=name or job_id,
                kwargs=kwargs,
                replace_existing=True,
            )
            
            self._jobs[job_id] = func
            logger.info(f"เพิ่ม interval job: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"ไม่สามารถเพิ่ม interval job: {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """
        ลบ job
        
        Args:
            job_id: ID ของ job
            
        Returns:
            True ถ้าสำเร็จ
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self._jobs:
                del self._jobs[job_id]
            logger.info(f"ลบ job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"ไม่สามารถลบ job: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """หยุด job ชั่วคราว"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"หยุด job ชั่วคราว: {job_id}")
            return True
        except Exception as e:
            logger.error(f"ไม่สามารถหยุด job: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """เริ่ม job ที่หยุดไว้"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"เริ่ม job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"ไม่สามารถเริ่ม job: {e}")
            return False
    
    def run_job_now(self, job_id: str) -> bool:
        """
        รัน job ทันที
        
        Args:
            job_id: ID ของ job
            
        Returns:
            True ถ้าสำเร็จ
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                logger.info(f"รัน job ทันที: {job_id}")
                return True
            else:
                logger.warning(f"ไม่พบ job: {job_id}")
                return False
        except Exception as e:
            logger.error(f"ไม่สามารถรัน job: {e}")
            return False
    
    def get_jobs(self) -> List[JobInfo]:
        """
        ดึงรายการ jobs ทั้งหมด
        
        Returns:
            List ของ JobInfo
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(JobInfo(
                job_id=job.id,
                name=job.name,
                trigger_type=type(job.trigger).__name__,
                next_run=job.next_run_time,
                is_running=job.pending,
            ))
        return jobs
    
    def get_job_info(self, job_id: str) -> Optional[JobInfo]:
        """
        ดึงข้อมูล job
        
        Args:
            job_id: ID ของ job
            
        Returns:
            JobInfo หรือ None
        """
        job = self.scheduler.get_job(job_id)
        if job:
            return JobInfo(
                job_id=job.id,
                name=job.name,
                trigger_type=type(job.trigger).__name__,
                next_run=job.next_run_time,
                is_running=job.pending,
            )
        return None
    
    def _on_job_executed(self, event) -> None:
        """Callback เมื่อ job ทำงานสำเร็จ"""
        logger.info(f"Job {event.job_id} ทำงานสำเร็จ")
        self._log_run(event.job_id, "completed")
    
    def _on_job_error(self, event) -> None:
        """Callback เมื่อ job เกิด error"""
        logger.error(f"Job {event.job_id} เกิด error: {event.exception}")
        self._log_run(
            event.job_id,
            "failed",
            error_message=str(event.exception),
            error_traceback=traceback.format_exc(),
        )
    
    def _log_run(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
    ) -> None:
        """
        บันทึก run log
        
        Args:
            job_id: ID ของ job
            status: สถานะ
            error_message: ข้อความ error
            error_traceback: traceback
        """
        try:
            with session_scope() as session:
                repo = RunLogRepository(session)
                run = repo.create_run(
                    run_type=job_id,
                    triggered_by="scheduler",
                )
                
                if status == "completed":
                    repo.complete_run(run.id, status="completed")
                else:
                    repo.fail_run(run.id, error_message or "Unknown error", error_traceback)
        except Exception as e:
            logger.error(f"ไม่สามารถบันทึก run log: {e}")
    
    def setup_default_jobs(self) -> None:
        """ตั้งค่า jobs เริ่มต้นจาก config"""
        config = get_config()
        
        if not config.scheduler.enabled:
            logger.info("Scheduler ถูกปิดใช้งาน")
            return
        
        for job_config in config.scheduler.jobs:
            # สร้าง placeholder function
            def job_placeholder(job_name=job_config.name):
                logger.info(f"Running scheduled job: {job_name}")
            
            self.add_cron_job(
                job_id=job_config.name,
                func=job_placeholder,
                cron_expression=job_config.cron,
                name=job_config.name,
            )
        
        logger.info(f"ตั้งค่า {len(config.scheduler.jobs)} default jobs")


# Singleton instance
_scheduler_instance: Optional[SchedulerModule] = None


def get_scheduler() -> SchedulerModule:
    """
    ดึง scheduler instance (singleton)
    
    Returns:
        SchedulerModule instance
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerModule()
    return _scheduler_instance


# Pre-defined job functions
def daily_metrics_collection_job() -> None:
    """Job สำหรับเก็บ metrics รายวัน"""
    task_logger = TaskLogger("DailyMetricsCollection")
    task_logger.start("เริ่มเก็บ metrics รายวัน")
    
    try:
        with session_scope() as session:
            from src.modules.analytics import AnalyticsModule
            analytics = AnalyticsModule(session)
            
            # TODO: Implement actual metrics collection
            task_logger.step("กำลังดึงข้อมูลจาก YouTube API")
            task_logger.step("กำลังบันทึกลงฐานข้อมูล")
            
        task_logger.complete("เก็บ metrics สำเร็จ")
    except Exception as e:
        task_logger.fail(str(e))
        raise


def weekly_analysis_job() -> None:
    """Job สำหรับวิเคราะห์รายสัปดาห์"""
    task_logger = TaskLogger("WeeklyAnalysis")
    task_logger.start("เริ่มวิเคราะห์รายสัปดาห์")
    
    try:
        with session_scope() as session:
            from src.modules.analytics import AnalyticsModule
            from src.modules.playbook import PlaybookModule
            
            analytics = AnalyticsModule(session)
            playbook = PlaybookModule(session)
            
            task_logger.step("กำลังวิเคราะห์ performance")
            summary = analytics.get_channel_summary()
            
            task_logger.step("กำลังเรียนรู้กฎใหม่")
            new_rules = playbook.learn_from_performance()
            
        task_logger.complete(f"วิเคราะห์สำเร็จ, สร้างกฎใหม่ {len(new_rules)} กฎ")
    except Exception as e:
        task_logger.fail(str(e))
        raise


def research_update_job() -> None:
    """Job สำหรับอัพเดท research"""
    task_logger = TaskLogger("ResearchUpdate")
    task_logger.start("เริ่มอัพเดท research")
    
    try:
        with session_scope() as session:
            from src.modules.research import ResearchModule
            
            research = ResearchModule(session)
            
            task_logger.step("กำลังดึง trending topics")
            # TODO: Implement actual research update
            
            task_logger.step("กำลังวิเคราะห์การแข่งขัน")
            analysis = research.analyze_competition()
            
        task_logger.complete("อัพเดท research สำเร็จ")
    except Exception as e:
        task_logger.fail(str(e))
        raise
