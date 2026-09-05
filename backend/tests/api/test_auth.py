import pytest

from tests.conftest import (
    TEST_ADMIN_EMAIL,
    TEST_ADMIN_NAME,
    TEST_ADMIN_PASSWORD,
    TEST_STAFF_EMAIL,
    TEST_STAFF_PASSWORD,
)


async def _login(client, email=TEST_ADMIN_EMAIL, password=TEST_ADMIN_PASSWORD):
    return await client.post("/api/v2/auth/login", json={"email": email, "password": password})


async def test_login_success_returns_pair_and_user(client):
    response = await _login(client)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tokenType"] == "Bearer"
    assert data["accessToken"]
    assert data["refreshToken"]
    assert data["user"]["email"] == TEST_ADMIN_EMAIL
    assert data["user"]["role"] is None
    assert data["user"]["isOwner"] is True
    assert data["user"]["pageAccess"] == ["ALL_PAGES"]


async def test_login_invalid_password(client):
    response = await _login(client, password="wrong")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ACCESS_DENIED"


async def test_login_unknown_email(client):
    response = await _login(client, email="nobody@example.com")
    assert response.status_code == 403


async def test_me_requires_token(client):
    response = await client.get("/api/v2/auth/me")
    assert response.status_code == 401


async def test_me_returns_user(client, admin_headers):
    response = await client.get("/api/v2/auth/me", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == TEST_ADMIN_EMAIL
    assert data["name"] == TEST_ADMIN_NAME


async def test_refresh_rotates_and_reuse_is_blocked(client):
    login = await _login(client)
    refresh = login.json()["data"]["refreshToken"]

    first = await client.post("/api/v2/auth/refresh", json={"refreshToken": refresh})
    assert first.status_code == 200
    assert first.json()["data"]["refreshToken"] != refresh

    reuse = await client.post("/api/v2/auth/refresh", json={"refreshToken": refresh})
    assert reuse.status_code == 401


async def test_family_revoked_after_reuse(client):
    login = await _login(client)
    refresh = login.json()["data"]["refreshToken"]
    first = await client.post("/api/v2/auth/refresh", json={"refreshToken": refresh})
    new_refresh = first.json()["data"]["refreshToken"]

    reuse = await client.post("/api/v2/auth/refresh", json={"refreshToken": refresh})
    assert reuse.status_code == 401

    stolen = await client.post("/api/v2/auth/refresh", json={"refreshToken": new_refresh})
    assert stolen.status_code == 401


async def test_logout_revokes_refresh(client):
    login = await _login(client)
    refresh = login.json()["data"]["refreshToken"]

    logout = await client.post("/api/v2/auth/logout", json={"refreshToken": refresh})
    assert logout.status_code == 200

    reuse = await client.post("/api/v2/auth/refresh", json={"refreshToken": refresh})
    assert reuse.status_code == 401


async def test_change_password_revokes_sessions(client):
    login = await _login(client)
    refresh = login.json()["data"]["refreshToken"]
    headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

    response = await client.post(
        "/api/v2/auth/change-password",
        headers=headers,
        json={"currentPassword": TEST_ADMIN_PASSWORD, "newPassword": "newpass123"},
    )
    assert response.status_code == 200

    revoked = await client.post("/api/v2/auth/refresh", json={"refreshToken": refresh})
    assert revoked.status_code == 401

    relogin = await _login(client, password="newpass123")
    assert relogin.status_code == 200

    await client.post(
        "/api/v2/auth/change-password",
        headers={"Authorization": f"Bearer {relogin.json()['data']['accessToken']}"},
        json={"currentPassword": "newpass123", "newPassword": TEST_ADMIN_PASSWORD},
    )


async def test_change_password_requires_correct_current(client, admin_headers):
    response = await client.post(
        "/api/v2/auth/change-password",
        headers=admin_headers,
        json={"currentPassword": "wrong", "newPassword": "whatever1"},
    )
    assert response.status_code == 422


async def test_service_token_success_and_failure(client):
    from app.core.config import settings

    ok = await client.post(
        "/api/v2/auth/service-token",
        json={"clientId": settings.telegram_bot_client_id, "clientSecret": settings.telegram_bot_client_secret},
    )
    assert ok.status_code == 200
    token = ok.json()["data"]["accessToken"]

    bad = await client.post(
        "/api/v2/auth/service-token",
        json={"clientId": "rental-telegram-bot", "clientSecret": "nope"},
    )
    assert bad.status_code == 403

    reports = await client.get(
        "/api/v2/telegram/motorcycle-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reports.status_code == 200

    denied = await client.get(
        "/api/v2/motorcycles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 401


async def test_staff_cannot_administer_users(client):
    login = await client.post("/api/v2/auth/login", json={"email": TEST_STAFF_EMAIL, "password": TEST_STAFF_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    response = await client.get("/api/v2/users", headers=headers)
    assert response.status_code == 403

    denied = await client.post(
        "/api/v2/users",
        headers=headers,
        json={"username": "x", "displayName": "X", "email": "x@example.com", "password": "secret1", "role": "Rental Staff"},
    )
    assert denied.status_code == 403


async def test_forgot_password_generic_response(client):
    response = await client.post("/api/v2/auth/forgot-password", json={"email": TEST_ADMIN_EMAIL})
    assert response.status_code == 200
    assert "reset code" in response.json()["data"]["message"]

    unknown = await client.post("/api/v2/auth/forgot-password", json={"email": "ghost@example.com"})
    assert unknown.status_code == 200
    assert unknown.json()["data"]["message"] == response.json()["data"]["message"]


async def test_verify_reset_code_rejects_bad_code(client):
    response = await client.post(
        "/api/v2/auth/forgot-password/verify",
        json={"email": TEST_ADMIN_EMAIL, "code": "000000"},
    )
    assert response.status_code == 422

