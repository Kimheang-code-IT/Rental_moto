import uuid


async def _create_customer(client, headers, code=None, status="Active"):
    code = code or f"CUS-T{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "code": code,
        "fullName": "Test Customer",
        "identityType": "National ID",
        "identityNumber": f"KH-{uuid.uuid4().hex[:8]}",
        "phone": "+855 10 000 000",
        "status": status,
    }
    return await client.post("/api/v2/customers", headers=headers, json=payload), code


async def test_customer_crud_flow(client, admin_headers):
    created, code = await _create_customer(client, admin_headers)
    assert created.status_code == 201, created.text
    customer = created.json()["data"]
    assert customer["status"] == "Active"

    updated = await client.put(
        f"/api/v2/customers/{customer['id']}",
        headers=admin_headers,
        json={"fullName": "Renamed Customer", "company": "Acme Shop"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["fullName"] == "Renamed Customer"
    assert updated.json()["data"]["company"] == "Acme Shop"

    inactive = await client.put(
        f"/api/v2/customers/{customer['id']}",
        headers=admin_headers,
        json={"status": "Inactive"},
    )
    assert inactive.status_code == 200

    deleted = await client.delete(f"/api/v2/customers/{customer['id']}", headers=admin_headers)
    assert deleted.status_code == 200


async def test_customer_delete_blocked_when_active(client, admin_headers):
    created, _ = await _create_customer(client, admin_headers)
    customer = created.json()["data"]
    response = await client.delete(f"/api/v2/customers/{customer['id']}", headers=admin_headers)
    assert response.status_code == 409


async def test_customer_list_status_filter(client, admin_headers):
    await _create_customer(client, admin_headers, status="Inactive")
    response = await client.get("/api/v2/customers", headers=admin_headers, params={"status": "Inactive", "limit": 100})
    assert response.status_code == 200
    for item in response.json()["data"]:
        assert item["status"] == "Inactive"
