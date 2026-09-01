from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

default_exchange = Exchange("rental.tasks", type="topic", durable=True)
events_exchange = Exchange("rental.events", type="topic", durable=True)

task_queues = [
    Queue("critical", default_exchange, routing_key="critical.#", durable=True),
    Queue("telegram", default_exchange, routing_key="telegram.#", durable=True),
    Queue("exports", default_exchange, routing_key="exports.#", durable=True),
    Queue("reports", default_exchange, routing_key="reports.#", durable=True),
    Queue("maintenance", default_exchange, routing_key="maintenance.#", durable=True),
    Queue("critical.dlq", default_exchange, routing_key="critical.dlq", durable=True),
    Queue("telegram.dlq", default_exchange, routing_key="telegram.dlq", durable=True),
    Queue("exports.dlq", default_exchange, routing_key="exports.dlq", durable=True),
    Queue("reports.dlq", default_exchange, routing_key="reports.dlq", durable=True),
    Queue("maintenance.dlq", default_exchange, routing_key="maintenance.dlq", durable=True),
]

task_default_queue = "maintenance"
task_default_exchange = "rental.tasks"
task_default_routing_key = "maintenance.#"
task_routes = {
    "app.tasks.telegram_notifications.deliver_password_reset": {"queue": "critical"},
    "app.tasks.telegram_notifications.deliver_event": {"queue": "telegram"},
    "app.tasks.telegram_notifications.send_test_message": {"queue": "telegram"},
    "app.tasks.exports.export_resource": {"queue": "exports"},
    "app.tasks.overdue_rentals.scan_overdue": {"queue": "maintenance"},
    "app.tasks.outbox_dispatcher.dispatch_outbox": {"queue": "maintenance"},
    "app.tasks.reports.precompute_dashboard": {"queue": "reports"},
    "app.tasks.scheduled_summaries.daily_summary": {"queue": "reports"},
    "app.tasks.maintenance.cleanup": {"queue": "maintenance"},
}

celery_app = Celery(
    "hollywing",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.overdue_rentals",
        "app.tasks.telegram_notifications",
        "app.tasks.exports",
        "app.tasks.reports",
        "app.tasks.outbox_dispatcher",
        "app.tasks.scheduled_summaries",
        "app.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_queues=task_queues,
    task_default_queue=task_default_queue,
    task_default_exchange=task_default_exchange,
    task_default_exchange_type="topic",
    task_default_routing_key=task_default_routing_key,
    task_routes=task_routes,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=4,
    task_track_started=True,
    result_expires=settings.task_result_expire_seconds,
    broker_transport_options={"confirm_publish": True},
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 3,
        "interval_start": 0.5,
        "interval_step": 1.0,
        "interval_max": 5.0,
    },
    beat_schedule={
        "scan-overdue-rentals": {
            "task": "app.tasks.overdue_rentals.scan_overdue",
            "schedule": 300.0,
        },
        "dispatch-outbox": {
            "task": "app.tasks.outbox_dispatcher.dispatch_outbox",
            "schedule": 30.0,
        },
        "daily-telegram-summary": {
            "task": "app.tasks.scheduled_summaries.daily_summary",
            "schedule": 86400.0,
        },
        "cleanup-expired-data": {
            "task": "app.tasks.maintenance.cleanup",
            "schedule": 21600.0,
        },
        "precompute-dashboard": {
            "task": "app.tasks.reports.precompute_dashboard",
            "schedule": 120.0,
        },
    },
    timezone="UTC",
    enable_utc=True,
)
