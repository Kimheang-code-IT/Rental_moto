from unittest.mock import AsyncMock

import pytest

from telegram_bot.runtime import resolve_bot_token


@pytest.mark.asyncio
async def test_env_token_wins_over_settings():
    api = AsyncMock()
    resolved = await resolve_bot_token(api, env_token="env-token")
    assert resolved == ("env-token", True)
    api.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_env_uses_settings_token():
    api = AsyncMock()
    api.get.return_value = {"data": {"enabled": True, "botToken": "ui-token"}}
    resolved = await resolve_bot_token(api, env_token="")
    assert resolved == ("ui-token", True)
    api.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_masked_or_disabled_settings_yield_no_token():
    api = AsyncMock()
    api.get.return_value = {"data": {"enabled": True, "botToken": "***"}}
    masked = await resolve_bot_token(api, env_token="")
    assert masked == ("", True)

    api.get.return_value = {"data": {"enabled": False, "botToken": "ui-token"}}
    disabled = await resolve_bot_token(api, env_token="")
    assert disabled == ("", True)


@pytest.mark.asyncio
async def test_api_failure_is_not_treated_as_empty_token():
    api = AsyncMock()
    api.get.side_effect = RuntimeError("api down")
    resolved = await resolve_bot_token(api, env_token="")
    assert resolved.ok is False
    assert resolved.token == ""
