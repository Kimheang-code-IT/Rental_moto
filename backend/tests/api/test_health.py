import pytest


async def test_health_endpoints(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"

    response = await client.get("/health/live")
    assert response.status_code == 200

    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["checks"]["postgres"] == "ok"
    assert data["checks"]["redis"] == "ok"


async def test_openapi_available(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v2/auth/login" in paths
    assert "/api/v2/rentals" in paths
    assert "/api/v2/motorcycles" in paths


async def test_error_envelope_shape(client):
    response = await client.get("/api/v2/motorcycles/nonexistent-id")
    assert response.status_code in (401, 403, 404)
    if response.status_code == 401:
        assert response.json()["detail"]["code"] == "AUTH_REQUIRED"
