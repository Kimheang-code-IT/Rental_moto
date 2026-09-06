import logging

from app.core.database import SessionFactory
from app.core.redis import get_redis
from app.services.auth_service import AuthService
from app.services.telegram_context import NOTIFICATION_EVENTS_EXCLUDE_RESET
from app.services.telegram_service import TelegramNotificationService
from app.tasks.base import BaseTask, run_async
from app.tasks.celery_app import celery_app
from telegram_bot.formatter import Formatter

logger = logging.getLogger("hollywing.tasks.telegram")

IDEMPOTENCY_PREFIX = "task:telegram:event:"

EVENT_TOGGLE_MAP = {
    "rental_created": "notifyNewRental",
    "rental_completed": "notifyRentalCompleted",
    "rental_overdue": "notifyOverdueRental",
    "rental_cancelled": "notifyOverdueRental",
    "payment_recorded": "notifyPayment",
    "charge_recorded": "notifyCharge",
    "expense_recorded": "notifyExpense",
    "deadline_approaching": "deadlineReminderEnabled",
}

MESSAGE_SEPARATOR = "———————————————————"


def _display_value(value) -> str:
    from html import escape

    return escape(str(value)) if value not in (None, "") else "—"


def _money(value, currency: str) -> str:
    from html import escape

    try:
        return f"{float(value):,.2f} {escape(str(currency))}"
    except (TypeError, ValueError):
        return f"{_display_value(value)} {escape(str(currency))}"


def _format_message(
    event_type: str,
    payload: dict,
    language: str = "en",
    localization: dict | None = None,
) -> str:
    fmt = Formatter({**(localization or {}), "defaultLanguage": language})
    amount = payload.get("amount")
    currency = payload.get("currency", "USD")
    rental_no = payload.get("rental_no", "")
    customer = payload.get("customer", "")
    title_map_en = {
        "rental_created": "🆕 New rental",
        "rental_completed": "✅ Rental completed",
        "rental_cancelled": "❌ Rental cancelled",
        "rental_overdue": "⚠️ Rental overdue",
        "payment_recorded": "💵 Payment recorded",
        "charge_recorded": "➕ Charge recorded",
        "expense_recorded": "📤 Expense recorded",
        "deadline_approaching": "⏰ Rental return deadline approaching",
    }
    title_map_km = {
        "rental_created": "🆕 ការជួលថ្មី",
        "rental_completed": "✅ ការជួលបានបញ្ចប់",
        "rental_cancelled": "❌ ការជួលត្រូវបានលុបចោល",
        "rental_overdue": "⚠️ ការជួលហួសកំណត់",
        "payment_recorded": "💵 ការទូទាត់ត្រូវបានកត់ត្រា",
        "charge_recorded": "➕ ការគិតថ្លៃត្រូវបានកត់ត្រា",
        "expense_recorded": "📤 ចំណាយត្រូវបានកត់ត្រា",
        "deadline_approaching": "⏰ ជិតដល់កំណត់ត្រឡប់ម៉ូតូ",
    }
    titles = title_map_km if language == "km" else title_map_en
    lines = [f"<b>{titles.get(event_type, event_type)}</b>", ""]
    if rental_no:
        lines.append(f"- Ref: {_display_value(rental_no)}")
    if customer:
        lines.append(f"- Customer: {_display_value(customer)}")
    if payload.get("motorcycle"):
        moto = payload["motorcycle"]
        if payload.get("plate"):
            moto = f"{moto} ( {payload['plate']} )"
        lines.append(f"- Motorcycle: {_display_value(moto)}")
    if event_type == "deadline_approaching" and payload.get("reminder_label"):
        lines.append(f"- Reminder: {_display_value(payload['reminder_label'])} before due time")
    if payload.get("expense_no"):
        lines.append(f"- Expense: {_display_value(payload['expense_no'])}")
    if payload.get("payment_no"):
        lines.append(f"- Payment: {_display_value(payload['payment_no'])}")
    if payload.get("payment_method"):
        lines.append(f"- Method: {_display_value(payload['payment_method'])}")
    if payload.get("charge_no"):
        lines.append(f"- Charge: {_display_value(payload['charge_no'])}")
    if payload.get("charge_type"):
        lines.append(f"- Charge Type: {_display_value(payload['charge_type'])}")
    if payload.get("description"):
        lines.append(f"- Description: {_display_value(payload['description'])}")
    if amount is not None:
        lines.append(f"- Amount: {_money(amount, currency)}")
    if payload.get("paid") is not None:
        lines.append(f"- Paid: {_money(payload['paid'], currency)}")
    if payload.get("outstanding") is not None:
        lines.append(f"- Outstanding: {_money(payload['outstanding'], currency)}")
    if payload.get("status"):
        lines.append(f"- Status: {_display_value(payload['status'])}")
    if payload.get("reason"):
        lines.append(f"- Reason: {_display_value(payload['reason'])}")

    start_date = payload.get("start_date") or payload.get("startDate")
    due_date = payload.get("due_date") or payload.get("dueDate")
    return_date = payload.get("return_date") or payload.get("returnDate")
    end_date = return_date or due_date
    if start_date or due_date or return_date or payload.get("actor") or payload.get("occurred_at"):
        lines.extend(["", MESSAGE_SEPARATOR])
    if start_date:
        lines.append(f"Start Date: {_display_value(fmt.format_datetime(str(start_date)))}")
    if due_date and (event_type == "deadline_approaching" or not return_date):
        lines.append(f"Due Date: {_display_value(fmt.format_datetime(str(due_date)))}")
    if return_date:
        lines.append(f"Return Date: {_display_value(fmt.format_datetime(str(return_date)))}")
    elif end_date and event_type not in ("deadline_approaching",) and not due_date:
        lines.append(f"End Date: {_display_value(fmt.format_datetime(str(end_date)))}")
    if payload.get("actor"):
        lines.extend(["", f"By: {_display_value(payload['actor'])}"])
    if payload.get("occurred_at"):
        lines.append(f"At: {_display_value(fmt.format_datetime(str(payload['occurred_at'])))}")
    return "\n".join(str(line) for line in lines)


def _event_enabled(config: dict, event_type: str) -> bool:
    if not config.get("enabled", True):
        return False
    toggle_key = EVENT_TOGGLE_MAP.get(event_type)
    if toggle_key and not config.get(toggle_key, True):
        return False
    notifications = config.get("__notifications__") or {}
    if notifications.get("telegramEnabled") is False:
        return False
    return True


def _destination_accepts(dest: dict, event_type: str) -> bool:
    if not dest.get("enabled", True):
        return False
    if event_type in NOTIFICATION_EVENTS_EXCLUDE_RESET:
        return False
    if not dest.get("chatId"):
        return False
    # The configured Group ID destination receives every notification type.
    # Event on/off switches live on the Telegram settings toggles.
    if dest.get("isInteractiveGroup"):
        return True
    enabled_events = dest.get("enabledEvents") or []
    if enabled_events and event_type not in enabled_events:
        return False
    return True


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.telegram_notifications.deliver_event")
def deliver_event(self, event_id: str, event_type: str, payload: dict) -> dict:
    async def _run() -> dict:
        redis = _safe_redis()
        idempotency_key = f"{IDEMPOTENCY_PREFIX}{event_id}"
        if redis is not None:
            try:
                set_result = await redis.set(idempotency_key, "1", ex=7 * 24 * 3600, nx=True)
                if not set_result:
                    return {"status": "duplicate", "event_id": event_id}
            except Exception:
                pass

        enriched = dict(payload or {})
        sent = 0
        failed = 0

        async with SessionFactory() as session:
            from app.services.admin_service import SettingService

            app_config = await SettingService(session).get_app_config(mask=False)
            telegram_cfg = dict(app_config.get("telegram") or {})
            telegram_cfg["__notifications__"] = app_config.get("notifications") or {}
            if not _event_enabled(telegram_cfg, event_type):
                return {"status": "skipped", "reason": "event disabled"}

            language = telegram_cfg.get("messageLanguage") or "en"
            message = _format_message(
                event_type,
                enriched,
                language,
                app_config.get("localization") or {},
            )
            service = TelegramNotificationService(session, redis)
            destinations = list(telegram_cfg.get("destinations") or [])
            if not destinations and telegram_cfg.get("chatId"):
                destinations = [{"chatId": telegram_cfg["chatId"], "enabled": True, "enabledEvents": []}]

            targets = [d for d in destinations if _destination_accepts(d, event_type)]
            if not targets:
                return {"status": "skipped", "reason": "no matching destinations"}

            for dest in targets:
                chat_id = str(dest["chatId"])
                ok = await service.send_direct(chat_id, message)
                if ok:
                    sent += 1
                else:
                    failed += 1

            async with SessionFactory() as mark_session:
                from app.repositories.admin import OutboxRepository

                repo = OutboxRepository(mark_session)
                if sent > 0:
                    await repo.mark_published(event_id)
                else:
                    await repo.mark_failed(event_id, "Telegram delivery failed", 60)
                await mark_session.commit()

            if failed and sent == 0 and redis is not None:
                try:
                    await redis.delete(idempotency_key)
                except Exception:
                    pass

            return {
                "status": "sent" if sent else "failed",
                "event_id": event_id,
                "sent": sent,
                "failed": failed,
            }

    return run_async(_run())


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.telegram_notifications.deliver_password_reset")
def deliver_password_reset(self, email: str, event_id: str | None = None) -> dict:
    async def _run() -> dict:
        redis = _safe_redis()
        async with SessionFactory() as session:
            service = AuthService(session, redis)
            delivery = await service.take_reset_delivery(email)
            if not delivery:
                return {"status": "no_delivery"}
            telegram = TelegramNotificationService(session, redis)
            code = delivery["code"]
            message = (
                f"Your HollyWing Motor password reset code is: {code}\n"
                f"It expires in 10 minutes. If you did not request this, ignore this message."
            )
            ok = await telegram.send_direct(delivery.get("chat_id"), message)
            if event_id:
                from app.repositories.admin import OutboxRepository

                repo = OutboxRepository(session)
                if ok:
                    await repo.mark_published(event_id)
                else:
                    await repo.mark_failed(event_id, "Password reset Telegram delivery failed", 60)
                await session.commit()
            return {"status": "sent" if ok else "failed"}

    return run_async(_run())


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.telegram_notifications.send_test_message")
def send_test_message(self, chat_id: str, message: str) -> dict:
    async def _run() -> dict:
        async with SessionFactory() as session:
            telegram = TelegramNotificationService(session, _safe_redis())
            ok = await telegram.send_direct(chat_id, message)
            return {"status": "sent" if ok else "failed"}

    return run_async(_run())


def _safe_redis():
    try:
        return get_redis()
    except Exception:
        return None
