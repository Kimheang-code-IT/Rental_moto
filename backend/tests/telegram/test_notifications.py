from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.tasks.telegram_notifications import (
    INVOICE_PDF_EVENTS,
    _archive_invoice,
    _deliver_chat_notification,
    _destination_accepts,
    _document_caption,
    _event_enabled,
    _format_message,
    _plain_caption,
)


def test_only_new_and_completed_rentals_use_combined_invoice_document():
    assert INVOICE_PDF_EVENTS == {"rental_created", "rental_completed"}


async def test_invoice_events_send_one_document_with_auto_caption():
    telegram = SimpleNamespace(
        send_direct=AsyncMock(return_value=True),
        send_document=AsyncMock(return_value=True),
    )
    pdf = b"%PDF-invoice"
    caption = "<b>✅ Rental completed</b>\n\n- Ref: RNT-2026-000002"

    ok = await _deliver_chat_notification(
        telegram,
        "-100123",
        caption,
        invoice_content=pdf,
        invoice_filename="Final-Invoice-RNT-2026-000002.pdf",
    )

    assert ok is True
    telegram.send_document.assert_awaited_once_with(
        "-100123",
        "Final-Invoice-RNT-2026-000002.pdf",
        pdf,
        caption=caption,
        parse_mode="HTML",
    )
    telegram.send_direct.assert_not_awaited()


async def test_invoice_retries_plain_caption_when_html_document_fails():
    telegram = SimpleNamespace(
        send_direct=AsyncMock(return_value=True),
        send_document=AsyncMock(side_effect=[False, True]),
    )
    caption = "<b>🆕 New rental</b>\n\n- Ref: RNT-2026-000001"

    ok = await _deliver_chat_notification(
        telegram,
        "-100123",
        caption,
        invoice_content=b"%PDF-invoice",
        invoice_filename="Invoice-RNT-2026-000001.pdf",
    )

    assert ok is True
    assert telegram.send_document.await_count == 2
    first = telegram.send_document.await_args_list[0]
    second = telegram.send_document.await_args_list[1]
    assert first.kwargs["parse_mode"] == "HTML"
    assert "parse_mode" not in second.kwargs
    assert "<b>" not in second.kwargs["caption"]
    telegram.send_direct.assert_not_awaited()


def test_long_caption_is_stripped_to_plain_text():
    caption, parse_mode = _document_caption("x" * 1025)
    assert parse_mode is None
    assert len(caption) <= 1024
    assert _plain_caption("<b>Sok &amp; Dara</b>") == "Sok & Dara"


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


async def test_invoice_text_still_sends_when_pdf_is_missing():
    telegram = SimpleNamespace(
        send_direct=AsyncMock(return_value=True),
        send_document=AsyncMock(return_value=True),
    )

    ok = await _deliver_chat_notification(telegram, "900001", "🆕 New rental")

    assert ok is True
    telegram.send_direct.assert_awaited_once()
    telegram.send_document.assert_not_awaited()


async def test_archive_invoice_stores_pdf_in_minio(monkeypatch):
    stored = SimpleNamespace(
        bucket="rental-files",
        object_name="invoices/2026/09/RNT-2026-000002/Final-Invoice-RNT-2026-000002.pdf",
        size=12,
    )

    class FakeStorage:
        @classmethod
        def from_settings(cls):
            return cls()

        async def archive_invoice(self, rental_no, filename, content):
            assert rental_no == "RNT-2026-000002"
            assert filename.endswith(".pdf")
            assert content.startswith(b"%PDF")
            return stored

    monkeypatch.setattr("app.core.config.settings.minio_enabled", True)
    monkeypatch.setattr("app.services.object_storage_service.ObjectStorageService", FakeStorage)

    object_name = await _archive_invoice(
        "RNT-2026-000002",
        "Final-Invoice-RNT-2026-000002.pdf",
        b"%PDF-invoice",
    )
    assert object_name == stored.object_name


async def test_archive_invoice_failure_does_not_raise(monkeypatch):
    class FakeStorage:
        @classmethod
        def from_settings(cls):
            return cls()

        async def archive_invoice(self, *_args, **_kwargs):
            raise RuntimeError("minio down")

    monkeypatch.setattr("app.core.config.settings.minio_enabled", True)
    monkeypatch.setattr("app.services.object_storage_service.ObjectStorageService", FakeStorage)

    assert await _archive_invoice("RNT-1", "Invoice.pdf", b"%PDF") == ""


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
    assert "End Date: 02/09/2026 17:56" in message
    assert "\n\nBy: System Administrator\nAt: 02/09/2026 17:56" in message
