import logging

from app.core.database import SessionFactory
from app.services.admin_service import DashboardService
from app.tasks.base import BaseTask, run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks.reports")


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.reports.precompute_dashboard")
def precompute_dashboard(self) -> dict:
    async def _run() -> dict:
        async with SessionFactory() as session:
            service = DashboardService(session)
            summary = await service.summary(None, None)
            return {"income": summary.get("income"), "outstanding": summary.get("outstanding")}

    return run_async(_run())
