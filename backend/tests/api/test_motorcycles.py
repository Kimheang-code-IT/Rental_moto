

async def _create_moto(client, headers, code, **overrides):
    payload = {
        "code": code,
        "model": "Test Model",
        "brand": "Honda",
        "year": 2024,
        "plate": f"{code}-PLATE",
        "dailyRate": 10,
        "threeDayRate": 30,
        "weeklyRate": 60,
        "monthlyRate": 200,
    }
    payload.update(overrides)
    return await client.post("/api/v2/motorcycles", headers=headers, json=payload)


async def test_motorcycle_crud_flow(client, admin_headers):
    created = await _create_moto(client, admin_headers, f"MC-T{__import__('uuid').uuid4().hex[:6].upper()}")
    assert created.status_code == 201, created.text
    moto = created.json()["data"]
    assert moto["status"] == "Available"
    assert moto["dailyRate"] == "10.00"

    moto_id = moto["id"]
    updated = await client.put(
        f"/api/v2/motorcycles/{moto_id}",
        headers=admin_headers,
        json={"model": "Updated Model", "dailyRate": 12},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["model"] == "Updated Model"
    assert updated.json()["data"]["dailyRate"] == "12.00"

    status = await client.patch(
        f"/api/v2/motorcycles/{moto_id}/status",
        headers=admin_headers,
        json={"status": "Maintenance"},
    )
    assert status.status_code == 200
    assert status.json()["data"]["status"] == "Maintenance"

    deleted = await client.delete(f"/api/v2/motorcycles/{moto_id}", headers=admin_headers)
    assert deleted.status_code == 200

    missing = await client.get(f"/api/v2/motorcycles/{moto_id}", headers=admin_headers)
    assert missing.status_code == 404


async def test_motorcycle_duplicate_code_rejected(client, admin_headers):
    import uuid

    code = f"MC-D{uuid.uuid4().hex[:6].upper()}"
    first = await _create_moto(client, admin_headers, code)
    assert first.status_code == 201
    second = await _create_moto(client, admin_headers, code)
    assert second.status_code == 409


async def test_motorcycle_list_filters_and_pagination(client, admin_headers):
    response = await client.get(
        "/api/v2/motorcycles", headers=admin_headers, params={"page": 1, "limit": 5, "status": "Available", "sort": "code:asc"}
    )
    assert response.status_code == 200
    meta = response.json()["meta"]
    assert meta["page"] == 1
    assert meta["limit"] == 5
    assert meta["total"] >= 1
    codes = [item["code"] for item in response.json()["data"]]
    assert codes == sorted(codes)


async def test_motorcycle_sort_validation(client, admin_headers):
    response = await client.get(
        "/api/v2/motorcycles", headers=admin_headers, params={"sort": "password_hash; DROP TABLE users"}
    )
    assert response.status_code == 422


async def test_motorcycle_q_search(client, admin_headers):
    response = await client.get("/api/v2/motorcycles", headers=admin_headers, params={"q": "Test Model"})
    assert response.status_code == 200
    assert response.json()["meta"]["total"] >= 1
