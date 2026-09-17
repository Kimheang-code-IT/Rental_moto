from __future__ import annotations
import socket

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.settings import ConnectionResult
from app.services.admin_service import SettingService

MASKED = "***"


async def test_telegram_connection(session: AsyncSession, destination_id: str | None = None, send_message: bool = False) -> dict:
    settings_service = SettingService(session)
    config = await settings_service.telegram_config()
    token = config.get("botToken") or settings.telegram_bot_token
    if not token or token == MASKED:
        token = settings.telegram_bot_token
    if not token:
        return ConnectionResult(status="failed", message="Telegram bot token is not configured").model_dump()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            if response.status_code != 200:
                return ConnectionResult(status="failed", message=f"Telegram API error {response.status_code}").model_dump()
            data = response.json().get("result", {})
            username = data.get("username", "")
            bot_label = f"@{username}" if username else "Telegram bot"
            if not send_message:
                return ConnectionResult(status="connected", message=f"Connected to {bot_label}").model_dump()
            chat_id = str(destination_id or config.get("chatId") or "").strip()
            if not chat_id:
                return ConnectionResult(
                    status="failed",
                    message=f"Connected to {bot_label}, but Group ID is not configured",
                ).model_dump()
            sent = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": "HollyWing Motor connection test"},
            )
            if sent.status_code != 200:
                detail = sent.text[:200] if sent.text else f"HTTP {sent.status_code}"
                return ConnectionResult(
                    status="failed",
                    message=f"Bot is valid, but the test message was not delivered: {detail}",
                ).model_dump()
            return ConnectionResult(
                status="connected",
                message=f"Test message sent to {chat_id} via {bot_label}",
            ).model_dump()
    except Exception as exc:
        return ConnectionResult(status="failed", message=str(exc)).model_dump()


async def test_email_connection(session: AsyncSession, send_to: str | None = None) -> dict:
    settings_service = SettingService(session)
    config = await settings_service.get_app_config(mask=False)
    email_config = config.get("email", {})
    host = email_config.get("smtpHost") or ""
    port = int(email_config.get("smtpPort") or 587)
    if not host:
        return ConnectionResult(status="failed", message="SMTP host is not configured").model_dump()
    try:
        with socket.create_connection((host, port), timeout=5):
            pass
        return ConnectionResult(status="connected", message=f"Reached {host}:{port}").model_dump()
    except Exception as exc:
        return ConnectionResult(status="failed", message=f"SMTP connection failed: {exc}").model_dump()
