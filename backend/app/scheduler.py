import logging

from app.core.database import SessionFactory
from app.tasks.deadline_alerts import enqueue_deadline_alerts
from app.tasks.maintenance import cleanup_expired_data
from app.tasks.outbox_dispatcher import dispatch_pending_outbox
from app.tasks.overdue_rentals import scan_overdue_rentals
from app.tasks.reports import precompute_dashboard_summary
from app.tasks.scheduled_summaries import send_daily_summary

logger = logging.getLogger("hollywing.scheduler")


async def _safe(name: str, coro):
    try:
        result = await coro
        logger.debug("Scheduled job %s finished: %s", name, result)
        return result
    except Exception:
        logger.exception("Scheduled job %s failed", name)
        return None


async def job_scan_deadline_alerts() -> None:
    async with SessionFactory() as session:
        await _safe("scan_deadline_alerts", enqueue_deadline_alerts(session))


async def job_dispatch_outbox() -> None:
    await _safe("dispatch_outbox", dispatch_pending_outbox())


async def job_scan_overdue() -> None:
    await _safe("scan_overdue", scan_overdue_rentals())


async def job_cleanup() -> None:
    await _safe("cleanup", cleanup_expired_data())


async def job_precompute_dashboard() -> None:
    await _safe("precompute_dashboard", precompute_dashboard_summary())


async def job_daily_summary() -> None:
    await _safe("daily_summary", send_daily_summary())


def create_scheduler():
    """AsyncIOScheduler for the single local API process.

    max_instances=1 + coalesce: a slow run never overlaps the next one, and
    missed ticks collapse into one catch-up execution instead of a burst.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1})
    scheduler.add_job(job_scan_deadline_alerts, "interval", seconds=60, id="scan-deadline-alerts", replace_existing=True)
    scheduler.add_job(job_dispatch_outbox, "interval", seconds=30, id="dispatch-outbox", replace_existing=True)
    scheduler.add_job(job_scan_overdue, "interval", seconds=300, id="scan-overdue-rentals", replace_existing=True)
    scheduler.add_job(job_precompute_dashboard, "interval", seconds=120, id="precompute-dashboard", replace_existing=True)
    scheduler.add_job(job_cleanup, "interval", hours=6, id="cleanup-expired-data", replace_existing=True)
    scheduler.add_job(job_daily_summary, "interval", hours=24, id="daily-telegram-summary", replace_existing=True)
    return scheduler
