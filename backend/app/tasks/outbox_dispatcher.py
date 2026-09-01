import logging

from app.core.database import SessionFactory
from app.repositories.admin import OutboxRepository
from app.tasks.base import BaseTask, run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks.outbox")


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.outbox_dispatcher.dispatch_outbox")
def dispatch_outbox(self, limit: int = 50) -> dict:
    async def _run() -> dict:
        published = 0
        failed = 0
        async with SessionFactory() as session:
            repo = OutboxRepository(session)
            events = await repo.pending(limit)
            for event in events:
                try:
                    celery_app.send_task(
                        "app.tasks.telegram_notifications.deliver_event",
                        kwargs={"event_id": event.id, "event_type": event.event_type, "payload": event.payload},
                        queue=event.queue or "telegram",
                    )
                    await repo.mark_published(event.id)
                    published += 1
                except Exception as exc:
                    backoff = min(2**event.attempts * 30, 3600)
                    await repo.mark_failed(event.id, str(exc)[:500], backoff)
                    failed += 1
            await session.commit()
        return {"published": published, "failed": failed}

    return run_async(_run())
