import logging

from app.core.database import SessionFactory
from app.services.reports_service import TransactionsReportService
from app.services.telegram_service import TelegramNotificationService
from app.tasks.base import BaseTask, run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks.summaries")


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.scheduled_summaries.daily_summary")
def daily_summary(self) -> dict:
    async def _run() -> dict:
        from datetime import datetime, timedelta, timezone

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
            from app.services.admin_service import SettingService

            config = await SettingService(session).telegram_config()
            if not config.get("dailySummaryEnabled", False):
                return {"status": "disabled"}
            chat_id = None
            for destination in config.get("destinations") or []:
                if destination.get("enabled", True) and destination.get("chatId"):
                    chat_id = str(destination["chatId"])
                    break
            if not chat_id:
                return {"status": "skipped", "reason": "no chat"}
            ok = await telegram.send_direct(chat_id, "\n".join(lines))
            return {"status": "sent" if ok else "failed"}

    return run_async(_run())
