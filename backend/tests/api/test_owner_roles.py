"""Operator-owned roles and the roleless system owner.

The application and seed never insert Role rows: every role is created by the
operator through POST /api/v2/roles after the first administrator completes
setup. The setup user (users.is_owner) gets ALL_PAGES without any role.
"""

import pytest_asyncio
from sqlalchemy import text

from tests.conftest import create_bootstrap_users

SETUP_EMAIL = "founder2@example.com"
SETUP_PASSWORD = "bootstrap-password-1"


@pytest_asyncio.fixture
async def cleared_auth(db_session):
    """Remove all users and roles; restore test fixtures afterwards."""
    await db_session.execute(text("DELETE FROM refresh_token_sessions"))
    await db_session.execute(text("DELETE FROM users"))
    await db_session.execute(text("DELETE FROM roles"))
    await db_session.commit()
    yield
    await create_bootstrap_users()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, email: str, password: str) -> dict:
    response = await client.post("/api/v2/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return _bearer(response.json()["data"]["accessToken"])


async def test_seed_leaves_roles_and_users_empty(client, cleared_auth, db_session):
    """Boot/seed must not re-create SuperAdmin, Rental Staff, or Report Viewer."""
    from app import seed as seed_module
    from app.core.database import SessionFactory

    # seed.py binds SessionFactory at import time; point it at the canonical
    # test factory so seed_bootstrap writes to the test database.
    seed_module.SessionFactory = SessionFactory
    await seed_module.seed_bootstrap()

    roles = (await db_session.execute(text("SELECT count(*) FROM roles"))).scalar()
    users = (await db_session.execute(text("SELECT count(*) FROM users"))).scalar()
    assert roles == 0
    assert users == 0

    status = await client.get("/api/v2/auth/setup-status")
    assert status.status_code == 200
    assert status.json()["data"]["needsSetup"] is True


async def test_setup_creates_owner_without_role(client, cleared_auth):
    setup = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    assert setup.status_code == 200, setup.text
    user = setup.json()["data"]["user"]
    assert user["roleId"] is None
    assert user["role"] is None
    assert user["isOwner"] is True
    assert user["effectivePermissions"] == ["ALL_PAGES"]

    roles = await client.get("/api/v2/roles", headers=_bearer(setup.json()["data"]["accessToken"]))
    assert roles.status_code == 200
    assert roles.json()["data"] == []


async def test_owner_creates_role_with_operator_chosen_name(client, cleared_auth):
    """Creating a role named SuperAdmin is allowed: it is just a name."""
    setup = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    headers = _bearer(setup.json()["data"]["accessToken"])

    created = await client.post(
        "/api/v2/roles",
        headers=headers,
        json={
            "name": "SuperAdmin",
            "description": "Operator-chosen name, ordinary role",
            "permissions": ["dashboard.view", "rental.rentals.create"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    assert body["name"] == "SuperAdmin"
    assert body["isSystem"] is False
    # non-view action implies view
    assert "rental.rentals.view" in body["permissions"]

    # Operator renames and edits it freely.
    updated = await client.put(
        f"/api/v2/roles/{body['id']}",
        headers=headers,
        json={"name": "Front Desk", "permissions": ["dashboard.view"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "Front Desk"


async def test_role_permissions_isolate_second_user(client, cleared_auth):
    setup = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    owner_headers = _bearer(setup.json()["data"]["accessToken"])

    created = await client.post(
        "/api/v2/roles",
        headers=owner_headers,
        json={"name": "Clerk", "permissions": ["rental.rentals.create"]},
    )
    role_id = created.json()["data"]["id"]

    staff = await client.post(
        "/api/v2/users",
        headers=owner_headers,
        json={
            "username": "clerk",
            "displayName": "Clerk",
            "email": "clerk@example.com",
            "password": "secret123",
            "roleId": role_id,
        },
    )
    assert staff.status_code == 201, staff.text
    assert staff.json()["data"]["isOwner"] is False

    clerk_headers = await _login(client, "clerk@example.com", "secret123")
    allowed = await client.get("/api/v2/rentals", headers=clerk_headers)
    assert allowed.status_code == 200
    denied = await client.get("/api/v2/roles", headers=clerk_headers)
    assert denied.status_code == 403
    denied_create = await client.post(
        "/api/v2/roles",
        headers=clerk_headers,
        json={"name": "Escalated", "permissions": ["admin.roles.create"]},
    )
    assert denied_create.status_code == 403


async def test_role_delete_rules(client, cleared_auth):
    setup = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    owner_headers = _bearer(setup.json()["data"]["accessToken"])

    assigned = await client.post(
        "/api/v2/roles",
        headers=owner_headers,
        json={"name": "Busy", "permissions": ["dashboard.view"]},
    )
    assigned_id = assigned.json()["data"]["id"]
    empty = await client.post(
        "/api/v2/roles",
        headers=owner_headers,
        json={"name": "Empty", "permissions": []},
    )
    empty_id = empty.json()["data"]["id"]

    user = await client.post(
        "/api/v2/users",
        headers=owner_headers,
        json={
            "username": "holder",
            "displayName": "Holder",
            "email": "holder@example.com",
            "password": "secret123",
            "roleId": assigned_id,
        },
    )
    assert user.status_code == 201, user.text

    blocked = await client.delete(f"/api/v2/roles/{assigned_id}", headers=owner_headers)
    assert blocked.status_code == 409

    # Operator-created roles with no users are deletable.
    deletable = await client.delete(f"/api/v2/roles/{empty_id}", headers=owner_headers)
    assert deletable.status_code == 200


async def test_owner_account_cannot_be_deleted(client, cleared_auth):
    setup = await client.post(
        "/api/v2/auth/setup",
        json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD},
    )
    data = setup.json()["data"]
    owner_headers = _bearer(data["accessToken"])
    owner_id = data["user"]["id"]

    deleted = await client.delete(f"/api/v2/users/{owner_id}", headers=owner_headers)
    assert deleted.status_code == 409
