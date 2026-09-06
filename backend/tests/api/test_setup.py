"""First-administrator setup endpoint tests.

The application and seed never create users; these tests cover the public
`/auth/setup-status` and `/auth/setup` bootstrap flow. The `no_users` fixture
clears users (with their refresh sessions) and restores the test bootstrap
users afterwards so other API tests keep working regardless of file order.
"""

import pytest_asyncio
from sqlalchemy import text

from tests.conftest import (
    TEST_ADMIN_EMAIL,
    TEST_VIEWER_EMAIL,
    create_bootstrap_users,
)

SETUP_EMAIL = "founder@example.com"
SETUP_PASSWORD = "bootstrap-password-1"


@pytest_asyncio.fixture
async def no_users(db_session):
    await db_session.execute(text("DELETE FROM refresh_token_sessions"))
    await db_session.execute(text("DELETE FROM users"))
    await db_session.commit()
    yield
    await create_bootstrap_users()


async def test_seed_creates_no_default_admin(client, db_session):
    """Boot/seed must not create a user from admin@gmail.com / 123456 or any fixed pair."""

    result = await db_session.execute(
        text("SELECT email, password_hash FROM users WHERE email = 'admin@gmail.com'")
    )
    assert result.all() == []

    response = await client.post(
        "/api/v2/auth/login", json={"email": "admin@gmail.com", "password": "123456"}
    )
    assert response.status_code == 403


async def test_setup_status_true_with_zero_users(client, no_users):
    response = await client.get("/api/v2/auth/setup-status")
    assert response.status_code == 200
    assert response.json()["data"] == {"needsSetup": True}


async def test_setup_status_false_once_users_exist(client):
    response = await client.get("/api/v2/auth/setup-status")
    assert response.status_code == 200
    assert response.json()["data"] == {"needsSetup": False}


async def test_setup_creates_superadmin_and_returns_tokens(client, no_users):
    response = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["tokenType"] == "Bearer"
    assert data["accessToken"] and data["refreshToken"]

    user = data["user"]
    assert user["email"] == SETUP_EMAIL
    assert user["roleId"] is None
    assert user["role"] is None
    assert user["isOwner"] is True
    assert user["effectivePermissions"] == ["ALL_PAGES"]
    # Role-derived only: no denormalized grants on the user row.
    assert user["permissions"] == ["ALL_PAGES"]
    assert user["pageAccess"] == ["ALL_PAGES"]

    me = await client.get(
        "/api/v2/auth/me", headers={"Authorization": f"Bearer {data['accessToken']}"}
    )
    assert me.status_code == 200
    assert me.json()["data"]["email"] == SETUP_EMAIL


async def test_setup_rejects_short_password(client, no_users):
    response = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": "123"},
    )
    assert response.status_code == 422


async def test_setup_rejects_invalid_email(client, no_users):
    response = await client.post(
        "/api/v2/auth/setup",
        json={"email": "not-an-email", "password": SETUP_PASSWORD},
    )
    assert response.status_code == 422


async def test_second_setup_conflicts(client, no_users):
    first = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v2/auth/setup",
        json={"email": "other@example.com", "password": SETUP_PASSWORD},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "CONFLICT"


async def test_setup_conflicts_when_users_exist(client):
    """Without the no_users fixture the bootstrap users exist -> 409, generically."""
    response = await client.post(
        "/api/v2/auth/setup",
        json={"email": "other@example.com", "password": SETUP_PASSWORD},
    )
    assert response.status_code == 409


async def test_login_works_after_setup(client, no_users):
    setup = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    assert setup.status_code == 200

    login = await client.post(
        "/api/v2/auth/login",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["data"]["user"]["role"] is None
    assert login.json()["data"]["user"]["effectivePermissions"] == ["ALL_PAGES"]


async def test_setup_created_admin_is_not_the_test_viewer(client, no_users):
    """The setup user is new; pre-existing fixture emails are unrelated."""
    setup = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    assert setup.status_code == 200
    assert setup.json()["data"]["user"]["email"] != TEST_ADMIN_EMAIL
    assert setup.json()["data"]["user"]["email"] != TEST_VIEWER_EMAIL
