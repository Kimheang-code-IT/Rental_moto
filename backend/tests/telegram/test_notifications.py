
from app.tasks.telegram_notifications import (
    _destination_accepts,
    _event_enabled,
    _format_message,
)
from app.core.config import Settings


def test_settings_defaults_use_redis_celery_dbs():
    field_broker = Settings.model_fields["celery_broker_url"]
    field_backend = Settings.model_fields["celery_result_backend"]
    field_redis = Settings.model_fields["redis_url"]
    assert field_redis.default.endswith("/0")
    assert field_broker.default.startswith("redis://")
    assert field_broker.default.endswith("/3")
    assert field_backend.default.startswith("redis://")
    assert field_backend.default.endswith("/2")
    assert "rabbitmq_url" not in Settings.model_fields


def test_invoice_pdf_helpers_are_removed_from_telegram_module():
    import app.tasks.telegram_notifications as mod

    assert not hasattr(mod, "INVOICE_PDF_EVENTS")
    assert not hasattr(mod, "_archive_invoice")
    assert not hasattr(mod, "send_rental_invoice_pdf")
    assert not hasattr(mod, "_deliver_chat_notification")


def test_interactive_group_accepts_deadline_even_when_event_list_is_stale():
    dest = {
        "chatId": "-100123",
        "enabled": True,
        "isInteractiveGroup": True,
        "enabledEvents": ["rental_created"],
    }
    assert _destination_accepts(dest, "deadline_approaching") is True
    assert _destination_accepts(dest, "rental_created") is True
    assert _destination_accepts({**dest, "enabled": False}, "rental_created") is False


def test_extra_destination_still_filters_enabled_events():
    dest = {"chatId": "900001", "enabled": True, "enabledEvents": ["payment_recorded"]}
    assert _destination_accepts(dest, "payment_recorded") is True
    assert _destination_accepts(dest, "deadline_approaching") is False


def test_deadline_event_uses_deadline_reminder_toggle():
    enabled = {"enabled": True, "deadlineReminderEnabled": True, "notifyOverdueRental": False}
    disabled = {"enabled": True, "deadlineReminderEnabled": False, "notifyOverdueRental": True}
    assert _event_enabled(enabled, "deadline_approaching") is True
    assert _event_enabled(disabled, "deadline_approaching") is False


def test_telegram_service_has_no_document_send_api():
    from app.services.telegram_service import TelegramNotificationService

    assert hasattr(TelegramNotificationService, "send_direct")
    assert not hasattr(TelegramNotificationService, "send_document")


def test_deadline_message_uses_configured_lead_time():
    message = _format_message(
        "deadline_approaching",
        {
            "rental_no": "RNT-2026-001",
            "customer": "Sok & Dara",
            "due_date": "2026-09-03T12:00:00+00:00",
            "reminder_label": "2 hours",
        },
    )
    assert "2 hours before due time" in message
    assert "Sok &amp; Dara" in message
    assert "1 hour" not in message
    assert "- Ref: RNT-2026-001" in message
    assert "Due Date:" in message
    assert "———————————————————" in message


def test_completed_message_uses_readable_business_layout():
    message = _format_message(
        "rental_completed",
        {
            "rental_no": "RNT-2026-000002",
            "customer": "CHHOUN Oudom",
            "motorcycle": "Click 150",
            "plate": "1A-0002",
            "amount": 10,
            "outstanding": 0,
            "currency": "USD",
            "status": "Completed",
            "start_date": "2026-09-01T10:00:00+00:00",
            "return_date": "2026-09-02T10:56:10+00:00",
            "actor": "System Administrator",
            "occurred_at": "2026-09-02T10:56:10+00:00",
        },
    )
    assert message.startswith("<b>✅ Rental completed</b>\n\n- Ref:")
    assert "- Motorcycle: Click 150 ( 1A-0002 )" in message
    assert "- Amount: 10.00 USD" in message
    assert "\n———————————————————\nStart Date:" in message
    assert "Return Date: 02/09/2026 17:56" in message
    assert "\n\nBy: System Administrator\nAt: 02/09/2026 17:56" in message


def test_celery_app_routes_only_telegram_queues():
    from app.tasks.celery_app import celery_app, task_routes

    assert "app.tasks.telegram_notifications.deliver_event" in task_routes
    assert "app.tasks.telegram_notifications.deliver_password_reset" in task_routes
    assert "app.tasks.telegram_notifications.send_rental_invoice_pdf" not in task_routes
    includes = list(celery_app.conf.include or [])
    assert "app.tasks.telegram_notifications" in includes
    assert "app.tasks.deadline_alerts" not in includes
    assert celery_app.conf.task_default_queue == "telegram"
