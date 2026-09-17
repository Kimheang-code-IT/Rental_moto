from pathlib import Path

from tests.conftest import TEST_VIEWER_EMAIL, TEST_VIEWER_PASSWORD


async def test_export_creation_and_status_flow(client, admin_headers, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.export_dir", str(tmp_path))
    monkeypatch.setattr("app.services.export_service.settings.export_dir", str(tmp_path))

    created = await client.post(
        "/api/v2/exports",
        headers=admin_headers,
        json={"resource": "motorcycles", "format": "csv", "scope": "all_matching", "fieldCodes": ["code", "model"]},
    )
    assert created.status_code == 202, created.text
    job = created.json()["data"]
    assert job["resource"] == "motorcycles"
    assert job["status"] == "completed"
    assert job["downloadUrl"] == f"/api/v2/exports/{job['id']}/download"

    status = await client.get(f"/api/v2/exports/{job['id']}", headers=admin_headers)
    assert status.status_code == 200
    assert status.json()["data"]["status"] == "completed"

    download = await client.get(f"/api/v2/exports/{job['id']}/download", headers=admin_headers)
    assert download.status_code == 200
    assert "text/csv" in download.headers.get("content-type", "") or download.content

    files = list(Path(tmp_path).rglob("*.csv"))
    assert len(files) == 1
    assert files[0].exists()

    unknown = await client.post(
        "/api/v2/exports",
        headers=admin_headers,
        json={"resource": "unknown_resource", "format": "csv"},
    )
    assert unknown.status_code == 422


async def test_task_status_endpoint(client, admin_headers):
    missing = await client.get("/api/v2/tasks/nonexistent", headers=admin_headers)
    assert missing.status_code == 404


async def test_exports_require_resource_permission_and_scoped_ownership(client, admin_headers, tmp_path, monkeypatch):
    """Exports are gated by resource export permissions; ownership scopes access."""
    monkeypatch.setattr("app.core.config.settings.export_dir", str(tmp_path))
    monkeypatch.setattr("app.services.export_service.settings.export_dir", str(tmp_path))

    # Viewer role has view/print permissions only — no `.export` permission,
    # so creating a motorcycles export must be denied.
    login = await client.post("/api/v2/auth/login", json={"email": TEST_VIEWER_EMAIL, "password": TEST_VIEWER_PASSWORD})
    viewer = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    denied = await client.post(
        "/api/v2/exports",
        headers=viewer,
        json={"resource": "motorcycles", "format": "csv"},
    )
    assert denied.status_code == 403

    # An admin-created export is invisible to other users (ownership scoping).
    created = await client.post(
        "/api/v2/exports",
        headers=admin_headers,
        json={"resource": "motorcycles", "format": "csv"},
    )
    assert created.status_code == 202
    job = created.json()["data"]
    foreign = await client.get(f"/api/v2/exports/{job['id']}", headers=viewer)
    assert foreign.status_code == 404

    denied_user_create = await client.post(
        "/api/v2/users",
        headers=viewer,
        json={"username": "nope", "displayName": "Nope", "email": "nope@example.com", "password": "secret1"},
    )
    assert denied_user_create.status_code == 403
