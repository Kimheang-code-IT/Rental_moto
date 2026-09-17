import logging

from app.core.database import SessionFactory
from app.services.admin_service import DashboardService

logger = logging.getLogger("hollywing.tasks.reports")


async def precompute_dashboard_summary() -> dict:
    async with SessionFactory() as session:
        service = DashboardService(session)
        summary = await service.summary(None, None)
        return {"income": summary.get("income"), "outstanding": summary.get("outstanding")}
