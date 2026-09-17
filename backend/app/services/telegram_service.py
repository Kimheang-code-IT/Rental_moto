import logging

import httpx
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.admin_service import SettingService

logger = logging.getLogger("hollywing.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramNotificationService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis | None = None) -> None:
        self.session = session
        self.redis = redis

    async def send_direct(self, chat_id: str | None, message: str) -> bool:
        token = settings.telegram_bot_token
        if not token:
            token = await self._configured_bot_token()
        if not token:
            logger.warning("Telegram bot token is not configured")
            return False
        if not chat_id:
            logger.warning("Telegram chat id is not set")
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                )
                if response.status_code != 200:
                    logger.warning("Telegram sendMessage failed status=%s body=%s", response.status_code, response.text[:500])
                    return False
                return True
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)
            return False

    async def _configured_bot_token(self) -> str | None:
        try:
            settings_service = SettingService(self.session)
            config = await settings_service.telegram_config()
            token = config.get("botToken") or ""
            return token if token and not token.startswith("***") else None
        except Exception:
            return None


def event_queue(event_type: str) -> str:
    if event_type in ("password_reset_requested", "security_alert"):
        return "critical"
    return "telegram"
