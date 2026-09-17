"""Resolve the Telegram bot token from env or System Settings."""

from __future__ import annotations

import logging
import os
from typing import NamedTuple

from telegram_bot.api_client import ApiClient

logger = logging.getLogger("hollywing.bot")
MASKED = "***"
RUNTIME_PATH = "/api/v2/telegram/runtime"


class ResolvedBotToken(NamedTuple):
    token: str
    ok: bool


def _clean_token(value: object) -> str:
    token = str(value or "").strip()
    if not token or token == MASKED:
        return ""
    return token


async def resolve_bot_token(api: ApiClient, env_token: str | None = None) -> ResolvedBotToken:
    """Prefer TELEGRAM_BOT_TOKEN; otherwise use the token saved in System Settings.

    ``ok`` is False only when the API lookup fails. Callers should keep the
    current poller running in that case instead of treating the token as empty.
    """
    env = _clean_token(env_token if env_token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    if env:
        return ResolvedBotToken(env, True)
    try:
        response = await api.get(RUNTIME_PATH)
        payload = response.get("data") or {}
        if payload.get("enabled") is False:
            return ResolvedBotToken("", True)
        return ResolvedBotToken(_clean_token(payload.get("botToken")), True)
    except Exception:
        logger.exception("Could not load Telegram bot token from System Settings")
        return ResolvedBotToken("", False)
