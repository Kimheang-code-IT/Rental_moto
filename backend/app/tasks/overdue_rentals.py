import logging

from app.core.database import SessionFactory
from app.core.security import utcnow
from app.services.rental_service import RentalService

logger = logging.getLogger("hollywing.tasks.overdue")


async def scan_overdue_rentals() -> dict:
    async with SessionFactory() as session:
        service = RentalService(session)
        overdue_ids = await service.detect_overdue(utcnow(), notify=True)
        return {"overdue": len(overdue_ids), "ids": overdue_ids}
