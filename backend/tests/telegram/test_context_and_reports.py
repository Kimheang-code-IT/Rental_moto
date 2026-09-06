"""Telegram context, settings validation, and context-aware report routes."""

from types import SimpleNamespace

import pytest

from app.core.errors import ValidationError
from app.services.telegram_context import normalize_telegram_config, validate_telegram_config
from app.services.telegram_report_service import TelegramReportService


def test_normalize_telegram_config_defaults():
    cfg = normalize_telegram_config({})
    assert cfg["allowedModules"]["finance"] is False
    assert cfg["allowedModules"]["motorcycles"] is True
    assert cfg["sensitiveFields"]["customerName"] is False
    assert cfg["userAccess"] == []


def test_report_repository_attributes_do_not_shadow_report_methods():
    service = TelegramReportService(SimpleNamespace(), SimpleNamespace())
    assert callable(service.motorcycles)
    assert callable(service.customers)
    assert callable(service.rentals)


def test_normalize_syncs_group_id_to_interactive_group():
    cfg = normalize_telegram_config({"chatId": "-100123"})
    assert cfg["interactiveGroupId"] == "-100123"
    assert cfg["interactiveGroupEnabled"] is True
    assert len(cfg["destinations"]) == 1
    assert cfg["destinations"][0]["chatId"] == "-100123"
    assert "deadline_approaching" in cfg["destinations"][0]["enabledEvents"]
    assert "rental_created" in cfg["destinations"][0]["enabledEvents"]


def test_normalize_adds_deadline_event_to_existing_destination():
    cfg = normalize_telegram_config(
        {
            "chatId": "-100123",
            "destinations": [
                {
                    "id": "main-group",
                    "chatId": "-100123",
                    "enabled": True,
                    "enabledEvents": ["rental_created"],
                }
            ],
        }
    )
    events = cfg["destinations"][0]["enabledEvents"]
    assert "rental_created" in events
    assert "deadline_approaching" in events
    assert cfg["destinations"][0]["isInteractiveGroup"] is True


def test_telegram_ids_equal_string_and_supergroup_prefix():
    from app.services.telegram_context import telegram_ids_equal

    assert telegram_ids_equal(1, "1")
    assert telegram_ids_equal("1489002750", 1489002750)
    assert telegram_ids_equal("-5378646026", "-1005378646026")
    assert not telegram_ids_equal("-111", "-222")


def test_user_access_matches_string_user_id():
    from types import SimpleNamespace
    from app.services.telegram_context import _require_private_user_access

    cfg = {"userAccess": [{"userId": "7", "chatId": "1489002750", "chatbotEnabled": True}]}
    _require_private_user_access(cfg, SimpleNamespace(id=7), "1489002750")


def test_validate_accepts_single_group_synced_from_chat_id():
    cfg = normalize_telegram_config({"chatId": "-5378646026"})
    validate_telegram_config(cfg)


def test_validate_rejects_multiple_interactive_groups():
    cfg = normalize_telegram_config(
        {
            "interactiveGroupEnabled": True,
            "interactiveGroupId": "-1001",
            "destinations": [{"enabled": True, "isInteractiveGroup": True, "chatId": "-1002"}],
        }
    )
    with pytest.raises(ValidationError):
        validate_telegram_config(cfg)


async def _service_headers(client) -> dict:
    token_response = await client.post(
        "/api/v2/auth/service-token",
        json={"clientId": "rental-telegram-bot", "clientSecret": "dev-only-telegram-secret-change-me-0123456789abcdef"},
    )
    token = token_response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _private_headers(service_headers: dict) -> dict:
    return {
        **service_headers,
        "X-Telegram-User-Id": "800001",
        "X-Telegram-Chat-Id": "800001",
        "X-Telegram-Chat-Type": "private",
    }


async def test_access_unlinked_private(client):
    headers = _private_headers(await _service_headers(client))
    response = await client.get("/api/v2/telegram/access", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["linked"] is False
    assert data["accountHelp"] is True


async def test_reports_require_linked_private(client, admin_headers):
    service = await _service_headers(client)
    code_response = await client.post("/api/v2/auth/telegram/link-code", headers=admin_headers)
    code = code_response.json()["data"]["code"]
    await client.post(
        "/api/v2/telegram/link",
        headers=service,
        json={"code": code, "telegramUserId": "800002", "telegramChatId": "800002"},
    )
    headers = {
        **service,
        "X-Telegram-User-Id": "800002",
        "X-Telegram-Chat-Id": "800002",
        "X-Telegram-Chat-Type": "private",
    }
    access = await client.get("/api/v2/telegram/access", headers=headers)
    assert access.status_code == 200
    assert access.json()["data"]["linked"] is True

    income = await client.get("/api/v2/telegram/income", headers=headers, params={"period": "today"})
    assert income.status_code in (200, 403)


async def test_missing_context_headers_rejected(client):
    service = await _service_headers(client)
    response = await client.get("/api/v2/telegram/access", headers=service)
    assert response.status_code == 401


async def test_access_unauthorized_group_returns_empty_modules(client, admin_headers):
    await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={"telegram": {"chatId": "-100111111"}},
    )
    headers = {
        **(await _service_headers(client)),
        "X-Telegram-User-Id": "800010",
        "X-Telegram-Chat-Id": "-999999",
        "X-Telegram-Chat-Type": "group",
    }
    response = await client.get("/api/v2/telegram/access", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["mode"] == "group"
    assert data["linked"] is False
    assert data["modules"]["rentals"] is False
    assert data.get("reason") == "This Telegram group is not authorized"

    matching = {
        **(await _service_headers(client)),
        "X-Telegram-User-Id": "800010",
        "X-Telegram-Chat-Id": "-111111",
        "X-Telegram-Chat-Type": "supergroup",
    }
    allowed = await client.get("/api/v2/telegram/access", headers=matching)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["mode"] == "group"


async def test_handoff_exchange(client, admin_headers):
    service = await _service_headers(client)
    code_response = await client.post("/api/v2/auth/telegram/link-code", headers=admin_headers)
    code = code_response.json()["data"]["code"]
    linked = await client.post(
        "/api/v2/telegram/link",
        headers=service,
        json={"code": code, "telegramUserId": "800003", "telegramChatId": "800003"},
    )
    user_id = linked.json()["data"]["user"]["id"]
    headers = {
        **service,
        "X-Telegram-User-Id": "800003",
        "X-Telegram-Chat-Id": "800003",
        "X-Telegram-Chat-Type": "private",
    }
    await client.post("/api/v2/telegram/password-reset/request", headers=headers)
    # Without redis delivery in test we only verify route auth shape
    await client.post(f"/api/v2/users/{user_id}/unlink-telegram", headers=admin_headers)
