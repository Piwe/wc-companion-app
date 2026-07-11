import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app import ingestion
from app.config import get_settings
from app.database import SessionLocal

logger = logging.getLogger("scheduler")
_scheduler: AsyncIOScheduler | None = None


def _run_refresh() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        message = ingestion.refresh(db, settings)
        logger.info("Scheduled refresh: %s", message)
    except Exception as exc:  # noqa: BLE001
        logger.error("Scheduled refresh failed: %s", exc)
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the daily refresh job (idempotent)."""
    global _scheduler
    if _scheduler is not None:
        return
    settings = get_settings()
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_refresh,
        CronTrigger(hour=settings.refresh_hour, minute=0),
        id="daily_refresh",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started; daily refresh at %02d:00", settings.refresh_hour)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
