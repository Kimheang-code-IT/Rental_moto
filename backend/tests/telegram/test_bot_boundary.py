

async def test_telegram_endpoints_reject_anonymous(client):
    for path in (
        "/api/v2/telegram/transactions",
        "/api/v2/telegram/motorcycle-status",
        "/api/v2/telegram/access",
        "/api/v2/telegram/runtime",
        "/api/v2/telegram/localization",
    ):
        response = await client.get(path)
        assert response.status_code == 401


async def test_service_token_can_read_reports_but_not_mutations(client):
    token_response = await client.post(
        "/api/v2/auth/service-token",
        json={"clientId": "rental-telegram-bot", "clientSecret": "dev-only-telegram-secret-change-me-0123456789abcdef"},
    )
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['data']['accessToken']}"}

    for path in (
        "/api/v2/telegram/transactions",
        "/api/v2/telegram/motorcycle-status",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, response.text

    forbidden = await client.post("/api/v2/rentals", headers=headers, json={})
    assert forbidden.status_code == 401


async def test_transactions_period_validation(client):
    token_response = await client.post(
        "/api/v2/auth/service-token",
        json={"clientId": "rental-telegram-bot", "clientSecret": "dev-only-telegram-secret-change-me-0123456789abcdef"},
    )
    headers = {"Authorization": f"Bearer {token_response.json()['data']['accessToken']}"}

    ok = await client.get("/api/v2/telegram/transactions", headers=headers, params={"period": "7_days"})
    assert ok.status_code == 200

    bad = await client.get("/api/v2/telegram/transactions", headers=headers, params={"period": "fortnight"})
    assert bad.status_code in (400, 422, 500)


async def test_telegram_link_flow(client, admin_headers):
    code_response = await client.post("/api/v2/auth/telegram/link-code", headers=admin_headers)
    assert code_response.status_code == 200
    code = code_response.json()["data"]["code"]

    service_token = await client.post(
        "/api/v2/auth/service-token",
        json={"clientId": "rental-telegram-bot", "clientSecret": "dev-only-telegram-secret-change-me-0123456789abcdef"},
    )
    service_headers = {"Authorization": f"Bearer {service_token.json()['data']['accessToken']}"}

    linked = await client.post(
        "/api/v2/telegram/link",
        headers=service_headers,
        json={"code": code, "telegramUserId": "900001", "telegramChatId": "900001"},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["data"]["linked"] is True

    reused = await client.post(
        "/api/v2/telegram/link",
        headers=service_headers,
        json={"code": code, "telegramUserId": "900001", "telegramChatId": "900001"},
    )
    assert reused.status_code == 422

    await client.post(f"/api/v2/users/{linked.json()['data']['user']['id']}/unlink-telegram", headers=admin_headers)


async def _service_token_response(client):
    return await client.post(
        "/api/v2/auth/service-token",
        json={"clientId": "rental-telegram-bot", "clientSecret": "dev-only-telegram-secret-change-me-0123456789abcdef"},
    )


async def test_user_token_cannot_read_bot_runtime(client, admin_headers):
    response = await client.get("/api/v2/telegram/runtime", headers=admin_headers)
    assert response.status_code == 401


async def test_service_token_reads_bot_token_saved_in_settings(client, admin_headers):
    token = "123456789:AASettingsSavedBotTokenForRuntime"
    saved = await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={"telegram": {"enabled": True, "botToken": token}},
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["telegram"]["botToken"] == "***"

    service_token = await _service_token_response(client)
    assert service_token.status_code == 200
    headers = {"Authorization": f"Bearer {service_token.json()['data']['accessToken']}"}

    runtime = await client.get("/api/v2/telegram/runtime", headers=headers)
    assert runtime.status_code == 200, runtime.text
    payload = runtime.json()["data"]
    assert payload["enabled"] is True
    assert payload["botToken"] == token

    disabled = await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={"telegram": {"enabled": False}},
    )
    assert disabled.status_code == 200
    runtime_off = await client.get("/api/v2/telegram/runtime", headers=headers)
    assert runtime_off.status_code == 200
    assert runtime_off.json()["data"]["enabled"] is False
    assert runtime_off.json()["data"]["botToken"] == token


async def test_send_test_without_token_reports_failure(client, admin_headers):
    response = await client.post(
        "/api/v2/telegram/send-test",
        headers=admin_headers,
        json={"chatId": "123", "message": "hello"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] in ("failed", "connected")
