import logging
from datetime import datetime, timedelta, timezone

from app.core.database import SessionFactory
from app.services.admin_service import SettingService
from app.services.reports_service import TransactionsReportService
from app.services.telegram_service import TelegramNotificationService

logger = logging.getLogger("hollywing.tasks.summaries")


async def send_daily_summary() -> dict:
    async with SessionFactory() as session:
        config = await SettingService(session).telegram_config()
        if not config.get("dailySummaryEnabled", False):
            return {"status": "disabled"}
        # Match deliver_event: derive the target from the configured Group ID
        # when no explicit destinations exist.
        destinations = list(config.get("destinations") or [])
        if not destinations and config.get("chatId"):
            destinations = [{"chatId": config["chatId"], "enabled": True}]
        chat_id = None
        for destination in destinations:
            if destination.get("enabled", True) and destination.get("chatId"):
                chat_id = str(destination["chatId"])
                break
        if not chat_id:
            return {"status": "skipped", "reason": "no chat"}

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    async with SessionFactory() as session:
        report = TransactionsReportService(session)
        transactions = await report.transactions(start, end, page=1, limit=5)
        lines = ["<b>Daily summary</b>", f"Transactions: {transactions['total']}"]
        for event in transactions["items"][:5]:
            lines.append(f"- {event.get('type')}: {event.get('rental_no') or ''} {event.get('amount') or ''}")
        telegram = TelegramNotificationService(session, None)
        ok = await telegram.send_direct(chat_id, "\n".join(lines))
        return {"status": "sent" if ok else "failed"}
