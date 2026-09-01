import uuid


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

    settings_config = await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={"localization": {"defaultLanguage": "km", "currency": "KHR"}},
    )
    assert settings_config.status_code == 200
    assert settings_config.json()["data"]["localization"]["defaultLanguage"] == "km"


async def test_app_config_permission_boundary(client):
    login = await client.post("/api/v2/auth/login", json={"email": "viewer@example.com", "password": "123456"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    response = await client.get("/api/v2/settings/app-config", headers=viewer_headers)
    assert response.status_code == 200

    denied = await client.patch(
        "/api/v2/settings/app-config",
        headers=viewer_headers,
        json={"general": {"defaultPageSize": 50}},
    )
    assert denied.status_code == 403


async def test_storage_provider_crud(client, admin_headers):
    created = await client.post(
        "/api/v2/settings/storage",
        headers=admin_headers,
        json={"name": "Test S3", "type": "amazon_s3", "bucket": "test-bucket", "region": "ap-southeast-1", "maxFileSizeMb": 5},
    )
    assert created.status_code == 201, created.text
    provider = created.json()["data"]

    fetched = await client.get(f"/api/v2/settings/storage/{provider['id']}", headers=admin_headers)
    assert fetched.status_code == 200

    updated = await client.put(
        f"/api/v2/settings/storage/{provider['id']}",
        headers=admin_headers,
        json={"name": "Renamed Storage"},
    )
    assert updated.json()["data"]["name"] == "Renamed Storage"

    test = await client.post(f"/api/v2/settings/storage/{provider['id']}/test-connection", headers=admin_headers)
    assert test.status_code == 200
    assert test.json()["data"]["status"] == "connected"

    listing = await client.get("/api/v2/settings/storage", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] >= 1

    deleted = await client.delete(f"/api/v2/settings/storage/{provider['id']}", headers=admin_headers)
    assert deleted.status_code == 200


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
    email = f"user-{uuid.uuid4().hex[:6]}@example.com"
    created = await client.post(
        "/api/v2/users",
        headers=admin_headers,
        json={
            "username": f"tester{uuid.uuid4().hex[:6]}",
            "displayName": "API Tester",
            "email": email,
            "password": "secret123",
            "role": "Rental Staff",
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()["data"]
    assert user["role"] == "Rental Staff"

    updated = await client.put(
        f"/api/v2/users/{user['id']}",
        headers=admin_headers,
        json={"role": "Report Viewer", "status": "Inactive"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["role"] == "Report Viewer"

    deleted = await client.delete(f"/api/v2/users/{user['id']}", headers=admin_headers)
    assert deleted.status_code == 200


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

