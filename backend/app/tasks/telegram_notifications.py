import logging

from app.core.database import SessionFactory
from app.core.redis import get_redis
from app.services.auth_service import AuthService
from app.services.telegram_service import TelegramNotificationService
from app.tasks.base import BaseTask, run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks.telegram")

IDEMPOTENCY_PREFIX = "task:telegram:event:"


def _localize(payload: dict) -> str:
    amount = payload.get("amount")
    currency = payload.get("currency", "USD")
    rental_no = payload.get("rental_no", "")
    customer = payload.get("customer", "")
    event_type = payload.get("__event_type__", "")
    lines = []
    title_map = {
        "rental_created": "New rental",
        "rental_completed": "Rental completed",
        "rental_cancelled": "Rental cancelled",
        "rental_overdue": "Rental overdue",
        "payment_recorded": "Payment recorded",
        "charge_recorded": "Charge recorded",
        "expense_recorded": "Expense recorded",
    }
    title = title_map.get(event_type, event_type)
    lines.append(f"<b>{title}</b>")
    if rental_no:
        lines.append(f"Ref: {rental_no}")
    if customer:
        lines.append(f"Customer: {customer}")
    if payload.get("motorcycle"):
        moto = payload["motorcycle"]
        if payload.get("plate"):
            moto = f"{moto} ({payload['plate']})"
        lines.append(f"Motorcycle: {moto}")
    if payload.get("expense_no"):
        lines.append(f"Expense: {payload['expense_no']} {payload.get('description') or ''}")
    if amount is not None:
        lines.append(f"Amount: {amount:,.2f} {currency}")
    if payload.get("status"):
        lines.append(f"Status: {payload['status']}")
    if payload.get("actor"):
        lines.append(f"By: {payload['actor']}")
    if payload.get("occurred_at"):
        lines.append(f"At: {payload['occurred_at']}")
    return "\n".join(str(line) for line in lines)


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
        enriched["__event_type__"] = event_type
        message = _localize(enriched)

        async with SessionFactory() as session:
            telegram = TelegramNotificationService(session, redis)
            chat_id = await _default_chat_id(session)
            if not chat_id:
                return {"status": "skipped", "reason": "no configured chat"}
            ok = await telegram.send_direct(chat_id, message)
            if not ok and redis is not None:
                try:
                    await redis.delete(idempotency_key)
                except Exception:
                    pass
            async with SessionFactory() as mark_session:
                if ok:
                    from app.repositories.admin import OutboxRepository

                    await OutboxRepository(mark_session).mark_published(event_id)
                    await mark_session.commit()
                else:
                    from app.repositories.admin import OutboxRepository

                    repo = OutboxRepository(mark_session)
                    await repo.mark_failed(event_id, "Telegram delivery failed", 60)
                    await mark_session.commit()
            return {"status": "sent" if ok else "failed", "event_id": event_id}

    return run_async(_run())


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.telegram_notifications.deliver_password_reset")
def deliver_password_reset(self, email: str) -> dict:
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


async def _default_chat_id(session) -> str | None:

    from app.services.admin_service import SettingService

    try:
        config = await SettingService(session).telegram_config()
        destinations = config.get("destinations") or []
        for destination in destinations:
            if destination.get("enabled", True) and destination.get("chatId"):
                return str(destination["chatId"])
        chat_id = config.get("chatId")
        return str(chat_id) if chat_id else None
    except Exception:
        return None


def _safe_redis():
    try:
        return get_redis()
    except Exception:
        return None
