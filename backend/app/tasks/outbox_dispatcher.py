import logging

from app.core.database import SessionFactory
from app.repositories.admin import OutboxRepository
from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks.outbox")


async def dispatch_pending_outbox(limit: int = 50) -> dict:
    """Publish pending outbox rows onto Redis/Celery Telegram queues."""
    published = 0
    failed = 0
    async with SessionFactory() as session:
        repo = OutboxRepository(session)
        events = await repo.pending(limit)
        for event in events:
            try:
                if event.event_type == "password_reset_requested":
                    email = (event.payload or {}).get("email", "")
                    celery_app.send_task(
                        "app.tasks.telegram_notifications.deliver_password_reset",
                        kwargs={"email": email, "event_id": event.id},
                        queue="critical",
                    )
                else:
                    celery_app.send_task(
                        "app.tasks.telegram_notifications.deliver_event",
                        kwargs={
                            "event_id": event.id,
                            "event_type": event.event_type,
                            "payload": event.payload,
                        },
                        queue=event.queue or "telegram",
                    )
                await repo.mark_published(event.id)
                published += 1
            except Exception as exc:
                backoff = min(2**event.attempts * 30, 3600)
                await repo.mark_failed(event.id, str(exc)[:500], backoff)
                failed += 1
                logger.warning("Outbox dispatch failed event_id=%s: %s", event.id, exc)
        await session.commit()
    return {"published": published, "failed": failed}
