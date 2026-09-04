import logging
from datetime import timedelta

from sqlalchemy import select

from app.core.database import SessionFactory
from app.core.security import utcnow
from app.models import OutboxEvent, Rental
from app.tasks.base import BaseTask, run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks.deadline")


def reminder_delta(config: dict) -> timedelta | None:
    """Return the configured lead time, or None when deadline alerts are disabled."""
    if not config.get("enabled", True) or not config.get("deadlineReminderEnabled", True):
        return None
    try:
        value = int(config.get("deadlineReminderValue", 1))
    except (TypeError, ValueError):
        value = 1
    value = min(max(value, 1), 10_080)
    unit = config.get("deadlineReminderUnit", "hours")
    if unit == "minutes":
        return timedelta(minutes=value)
    if unit == "days":
        return timedelta(days=value)
    return timedelta(hours=value)


def reminder_value(config: dict) -> int:
    try:
        return min(max(int(config.get("deadlineReminderValue", 1)), 1), 10_080)
    except (TypeError, ValueError):
        return 1


def reminder_label(value: int, unit: str) -> str:
    singular = unit[:-1] if value == 1 else unit
    return f"{value} {singular}"


async def enqueue_deadline_alerts(session, batch_limit: int = 100) -> dict:
    now = utcnow()
    from app.services.admin_service import SettingService

    app_config = await SettingService(session).get_app_config(mask=False)
    telegram_config = app_config.get("telegram") or {}
    lead_time = reminder_delta(telegram_config)
    if lead_time is None:
        return {"alerted": 0, "status": "disabled"}
    window_end = now + lead_time
    configured_value = reminder_value(telegram_config)
    configured_unit = telegram_config.get("deadlineReminderUnit", "hours")
    result = await session.execute(
        select(Rental)
        .where(
            Rental.status == "Active",
            Rental.due_date > now,
            Rental.due_date <= window_end,
            Rental.deadline_alerted_at.is_(None),
        )
        .with_for_update(skip_locked=True)
        .limit(batch_limit)
    )
    rentals = list(result.scalars().all())
    alerted = 0
    for rental in rentals:
        rental.deadline_alerted_at = now
        session.add(
            OutboxEvent(
                event_type="deadline_approaching",
                payload={
                    "rental_no": rental.rental_no,
                    "customer": rental.customer,
                    "motorcycle": rental.motorcycle,
                    "plate": rental.plate,
                    "start_date": rental.start_date.isoformat() if rental.start_date else None,
                    "due_date": rental.due_date.isoformat() if rental.due_date else None,
                    "outstanding": float(rental.outstanding),
                    "currency": rental.currency,
                    "status": rental.status,
                    "reminder_value": configured_value,
                    "reminder_unit": configured_unit,
                    "reminder_label": reminder_label(configured_value, configured_unit),
                },
                queue="telegram",
            )
        )
        alerted += 1
    await session.commit()
    return {"alerted": alerted}


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.deadline_alerts.scan_deadline_alerts")
def scan_deadline_alerts(self, batch_limit: int = 100) -> dict:
    async def _run() -> dict:
        async with SessionFactory() as session:
            return await enqueue_deadline_alerts(session, batch_limit)

    return run_async(_run())
