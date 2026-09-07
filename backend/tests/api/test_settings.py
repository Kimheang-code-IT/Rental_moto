import uuid
from tests.conftest import TEST_VIEWER_EMAIL, TEST_VIEWER_PASSWORD


async def test_app_info_get_update_reset(client, admin_headers):
    info = await client.get("/api/v2/settings/app-info", headers=admin_headers)
    assert info.status_code == 200
    original = info.json()["data"]
    assert original["applicationName"]

    updated = await client.patch(
        "/api/v2/settings/app-info",
        headers=admin_headers,
        json={"applicationName": "HollyWing Motor Test", "businessName": "Test Business"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["applicationName"] == "HollyWing Motor Test"

    reset = await client.post("/api/v2/settings/app-info/reset", headers=admin_headers)
    assert reset.status_code == 200
    assert reset.json()["data"]["applicationName"] == "HollyWing Motor"


async def test_app_config_telegram_chat_id_and_user_access(client, admin_headers):
    updated = await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={
            "telegram": {
                "enabled": True,
                "chatId": "-5378646026",
                "dailySummaryEnabled": True,
                "monthlySummaryEnabled": True,
                "deadlineReminderEnabled": True,
                "deadlineReminderValue": 2,
                "deadlineReminderUnit": "hours",
                "userAccess": [
                    {
                        "id": "tua-1",
                        "userId": 1,
                        "userName": "System Administrator",
                        "chatId": "1489002750",
                        "chatbotEnabled": True,
                        "groupEnabled": True,
                    }
                ],
            }
        },
    )
    assert updated.status_code == 200, updated.text
    telegram = updated.json()["data"]["telegram"]
    assert telegram["chatId"] == "-5378646026"
    assert telegram["deadlineReminderValue"] == 2
    assert telegram["deadlineReminderUnit"] == "hours"
    assert "deadline_approaching" in telegram["destinations"][0]["enabledEvents"]
    assert "rental_created" in telegram["destinations"][0]["enabledEvents"]
    assert len(telegram["userAccess"]) >= 1
    assert telegram["userAccess"][0]["userId"] == 1


async def test_app_config_masks_secrets(client, admin_headers):
    token = f"123:ABC{uuid.uuid4().hex}"
    updated = await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={"telegram": {"botToken": token, "botDisplayName": "TestBot"}},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["telegram"]["botToken"] == "***"

    fetched = await client.get("/api/v2/settings/app-config", headers=admin_headers)
    assert fetched.json()["data"]["telegram"]["botToken"] == "***"

    # A repeated read comes from cache and must remain masked.
    fetched_again = await client.get("/api/v2/settings/app-config", headers=admin_headers)
    assert fetched_again.json()["data"]["telegram"]["botToken"] == "***"

    settings_config = await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={"localization": {"defaultLanguage": "km", "currency": "KHR"}},
    )
    assert settings_config.status_code == 200
    assert settings_config.json()["data"]["localization"]["defaultLanguage"] == "km"


async def test_reset_data_permission_boundary(client):
    login = await client.post("/api/v2/auth/login", json={"email": TEST_VIEWER_EMAIL, "password": TEST_VIEWER_PASSWORD})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    denied = await client.post("/api/v2/settings/reset-data", headers=viewer_headers)
    assert denied.status_code == 403


async def test_reset_data_keeps_users_roles_sequences_and_settings(client, admin_headers):
    from tests.conftest import TEST_ADMIN_EMAIL

    app_name = f"Keep Settings {uuid.uuid4().hex[:6]}"
    patched_info = await client.patch(
        "/api/v2/settings/app-info",
        headers=admin_headers,
        json={"applicationName": app_name},
    )
    assert patched_info.status_code == 200, patched_info.text

    sequences = await client.get("/api/v2/document-sequences", headers=admin_headers)
    assert sequences.status_code == 200
    assert sequences.json()["data"]
    first_seq = sequences.json()["data"][0]
    seq_id = first_seq["id"]
    original_last_value = int(first_seq.get("lastValue") or 0)
    kept_last_value = original_last_value + 7
    updated_seq = await client.put(
        f"/api/v2/document-sequences/{seq_id}",
        headers=admin_headers,
        json={"lastValue": kept_last_value},
    )
    assert updated_seq.status_code == 200, updated_seq.text

    moto = await client.post(
        "/api/v2/motorcycles",
        headers=admin_headers,
        json={
            "code": f"RST-{uuid.uuid4().hex[:6].upper()}",
            "model": "Reset Target",
            "brand": "Honda",
            "year": 2024,
            "plate": f"RST-{uuid.uuid4().hex[:4].upper()}",
            "dailyRate": 10,
        },
    )
    assert moto.status_code == 201, moto.text
    moto_id = moto.json()["data"]["id"]

    response = await client.post("/api/v2/settings/reset-data", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["requiresReauth"] is False
    assert payload["requiresSetup"] is False

    setup_status = await client.get("/api/v2/auth/setup-status")
    assert setup_status.status_code == 200
    assert setup_status.json()["data"]["needsSetup"] is False

    still_authed = await client.get("/api/v2/settings/app-info", headers=admin_headers)
    assert still_authed.status_code == 200
    assert still_authed.json()["data"]["applicationName"] == app_name

    users = await client.get("/api/v2/users", headers=admin_headers)
    assert users.status_code == 200
    emails = {item["email"] for item in users.json()["data"]}
    assert TEST_ADMIN_EMAIL in emails

    roles = await client.get("/api/v2/roles", headers=admin_headers)
    assert roles.status_code == 200
    role_names = {item["name"] for item in roles.json()["data"]}
    assert "Rental Staff" in role_names

    kept_seq = await client.get(f"/api/v2/document-sequences/{seq_id}", headers=admin_headers)
    assert kept_seq.status_code == 200
    assert kept_seq.json()["data"]["lastValue"] == kept_last_value

    missing = await client.get(f"/api/v2/motorcycles/{moto_id}", headers=admin_headers)
    assert missing.status_code == 404

    await client.put(
        f"/api/v2/document-sequences/{seq_id}",
        headers=admin_headers,
        json={"lastValue": original_last_value},
    )
    await client.post("/api/v2/settings/app-info/reset", headers=admin_headers)


async def test_app_config_permission_boundary(client):
    login = await client.post("/api/v2/auth/login", json={"email": TEST_VIEWER_EMAIL, "password": TEST_VIEWER_PASSWORD})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    response = await client.get("/api/v2/settings/app-config", headers=viewer_headers)
    assert response.status_code == 200

    denied = await client.patch(
        "/api/v2/settings/app-config",
        headers=viewer_headers,
        json={"general": {"defaultPageSize": 50}},
    )
    assert denied.status_code == 403


async def test_document_sequences_crud(client, admin_headers):
    listing = await client.get("/api/v2/document-sequences", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] >= 4

    created = await client.post(
        "/api/v2/document-sequences",
        headers=admin_headers,
        json={"documentType": "TEST_DOC", "prefix": "TST-", "paddingLength": 4},
    )
    assert created.status_code == 201, created.text
    seq_id = created.json()["data"]["id"]

    updated = await client.put(
        f"/api/v2/document-sequences/{seq_id}",
        headers=admin_headers,
        json={"lastValue": 10, "status": "INACTIVE"},
    )
    assert updated.json()["data"]["lastValue"] == 10

    duplicate = await client.post(
        "/api/v2/document-sequences",
        headers=admin_headers,
        json={"documentType": "TEST_DOC", "prefix": "TST-"},
    )
    assert duplicate.status_code == 409

    deleted = await client.delete(f"/api/v2/document-sequences/{seq_id}", headers=admin_headers)
    assert deleted.status_code == 200


async def test_search_endpoint(client, admin_headers):
    response = await client.get("/api/v2/search", headers=admin_headers, params={"q": "Bike", "limit": 5})
    assert response.status_code == 200
    data = response.json()["data"]
    assert "hits" in data

    for hit in data["hits"]:
        assert hit["url"].startswith("/")


async def test_users_crud_and_role_enforcement(client, admin_headers):
    options_response = await client.get("/api/v2/roles/options", headers=admin_headers)
    assert options_response.status_code == 200
    roles = {item["name"]: item for item in options_response.json()["data"]}
    email = f"user-{uuid.uuid4().hex[:6]}@example.com"
    created = await client.post(
        "/api/v2/users",
        headers=admin_headers,
        json={
            "username": f"tester{uuid.uuid4().hex[:6]}",
            "displayName": "API Tester",
            "email": email,
            "password": "secret123",
            "roleId": roles["Rental Staff"]["id"],
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()["data"]
    assert user["role"] == "Rental Staff"
    assert user["roleId"] == roles["Rental Staff"]["id"]
    assert user["effectivePermissions"] == roles["Rental Staff"]["permissions"]

    updated = await client.put(
        f"/api/v2/users/{user['id']}",
        headers=admin_headers,
        json={"roleId": roles["Report Viewer"]["id"], "status": "Inactive"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["role"] == "Report Viewer"

    deleted = await client.delete(f"/api/v2/users/{user['id']}", headers=admin_headers)
    assert deleted.status_code == 200


async def test_user_permissions_cannot_be_overridden(client, admin_headers):
    response = await client.post(
        "/api/v2/users",
        headers=admin_headers,
        json={
            "username": f"override{uuid.uuid4().hex[:6]}",
            "displayName": "Override attempt",
            "email": f"override-{uuid.uuid4().hex[:6]}@example.com",
            "password": "secret123",
            "role": "Rental Staff",
            "permissions": ["ALL_PAGES"],
        },
    )
    assert response.status_code == 422


async def test_permission_catalog_is_canonical(client, admin_headers):
    response = await client.get("/api/v2/permissions", headers=admin_headers)
    assert response.status_code == 200
    groups = {item["module"]: item["actions"] for item in response.json()["data"]}
    assert groups["dashboard"] == ["view"]
    assert groups["rental.rentals"] == ["view", "create", "edit", "delete", "return", "print", "export"]
    assert groups["settings.app_config"] == ["view", "edit", "configure"]


async def test_roles_crud(client, admin_headers):
    name = f"Role-{uuid.uuid4().hex[:6]}"
    created = await client.post(
        "/api/v2/roles",
        headers=admin_headers,
        json={"name": name, "description": "Test role", "permissions": ["dashboard.view"]},
    )
    assert created.status_code == 201, created.text
    role = created.json()["data"]

    updated = await client.put(
        f"/api/v2/roles/{role['id']}",
        headers=admin_headers,
        json={"permissions": ["dashboard.view", "reports.view"]},
    )
    assert updated.json()["data"]["permissions"] == ["dashboard.view", "reports.view"]

    deleted = await client.delete(f"/api/v2/roles/{role['id']}", headers=admin_headers)
    assert deleted.status_code == 200


async def test_audit_logs_listed(client, admin_headers):
    response = await client.get("/api/v2/audit-logs", headers=admin_headers, params={"limit": 10})
    assert response.status_code == 200
    assert response.json()["meta"]["total"] >= 1
    entry = response.json()["data"][0]
    assert entry["action"]
    assert entry["entityType"]

