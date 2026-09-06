from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings

# Lean Redis queues for Telegram delivery only. Periodic scans run in the API
# via APScheduler and enqueue work onto these queues through the outbox.
task_routes = {
    "app.tasks.telegram_notifications.deliver_password_reset": {"queue": "critical"},
    "app.tasks.telegram_notifications.deliver_event": {"queue": "telegram"},
    "app.tasks.telegram_notifications.send_test_message": {"queue": "telegram"},
}

celery_app = Celery(
    "hollywing",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.telegram_notifications",
    ],
)

celery_app.conf.update(
    task_default_queue="telegram",
    task_routes=task_routes,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=4,
    task_track_started=True,
    result_expires=settings.task_result_expire_seconds,
    broker_connection_retry_on_startup=True,
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 3,
        "interval_start": 0.5,
        "interval_step": 1.0,
        "interval_max": 5.0,
    },
    timezone="UTC",
    enable_utc=True,
)


@worker_process_init.connect
def _dispose_db_engine_after_fork(**kwargs) -> None:
    """Drop asyncpg connections inherited from the Celery parent process."""
    import asyncio

    from app.core.database import engine

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(engine.dispose())
    except Exception:
        pass
    finally:
        loop.close()
