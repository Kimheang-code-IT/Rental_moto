import logging

from app.core.database import SessionFactory
from app.core.security import utcnow
from app.services.rental_service import RentalService
from app.tasks.base import BaseTask, run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks.overdue")


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.overdue_rentals.scan_overdue")
def scan_overdue(self) -> dict:
    async def _run() -> dict:
        async with SessionFactory() as session:
            service = RentalService(session)
            overdue_ids = await service.detect_overdue(utcnow(), notify=True)
            return {"overdue": len(overdue_ids), "ids": overdue_ids}

    return run_async(_run())
