import uuid


async def test_export_creation_and_status_flow(client, admin_headers):
    created = await client.post(
        "/api/v2/exports",
        headers=admin_headers,
        json={"resource": "motorcycles", "format": "csv", "scope": "all_matching", "fieldCodes": ["code", "model"]},
    )
    assert created.status_code in (202, 201), created.text
    job = created.json()["data"]
    assert job["resource"] == "motorcycles"
    assert job["status"] in ("queued", "processing", "completed", "failed")

    if created.status_code == 202 and job["status"] != "failed":
        status = await client.get(f"/api/v2/exports/{job['id']}", headers=admin_headers)
        assert status.status_code == 200
        assert status.json()["data"]["status"] in ("queued", "processing", "completed", "failed")

    unknown = await client.post(
        "/api/v2/exports",
        headers=admin_headers,
        json={"resource": "unknown_resource", "format": "csv"},
    )
    assert unknown.status_code == 422


async def test_task_status_endpoint(client, admin_headers):
    missing = await client.get("/api/v2/tasks/nonexistent", headers=admin_headers)
    assert missing.status_code == 404


async def test_exports_viewers_can_create_but_not_others(client):
    login = await client.post("/api/v2/auth/login", json={"email": "viewer@example.com", "password": "123456"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    response = await client.post(
        "/api/v2/exports",
        headers=viewer_headers,
        json={"resource": "motorcycles", "format": "csv"},
    )
    assert response.status_code == 202

    denied = await client.post(
        "/api/v2/users",
        headers=viewer_headers,
        json={"username": "nope", "displayName": "Nope", "email": "nope@example.com", "password": "secret1"},
    )
    assert denied.status_code == 403
