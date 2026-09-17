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

    missing = await client.get(f"/api/v2/customers/{customer['id']}", headers=admin_headers)
    assert missing.status_code == 404

    listed = await client.get("/api/v2/customers", headers=admin_headers, params={"limit": 100})
    assert listed.status_code == 200
    assert all(item["id"] != customer["id"] for item in listed.json()["data"])


async def test_customer_delete_blocked_when_active_rental(client, admin_headers):
    from datetime import datetime, timedelta, timezone

    moto = await client.post(
        "/api/v2/motorcycles",
        headers=admin_headers,
        json={
            "code": f"MC-A{uuid.uuid4().hex[:6].upper()}",
            "model": "Active Rental Bike",
            "plate": f"PP-A{uuid.uuid4().hex[:4].upper()}",
            "dailyRate": 10,
        },
    )
    assert moto.status_code == 201, moto.text
    created, _ = await _create_customer(client, admin_headers)
    customer = created.json()["data"]
    now = datetime.now(timezone.utc)
    rental = await client.post(
        "/api/v2/rentals",
        headers=admin_headers,
        json={
            "customerId": customer["id"],
            "lines": [{
                "motorcycleId": moto.json()["data"]["id"],
                "startDate": now.isoformat(),
                "dueDate": (now + timedelta(days=1)).isoformat(),
                "deposit": 0,
            }],
            "paidAmount": 0,
            "paymentMethod": "Cash",
        },
    )
    assert rental.status_code == 201, rental.text
    response = await client.delete(f"/api/v2/customers/{customer['id']}", headers=admin_headers)
    assert response.status_code == 409
    assert "active rentals" in response.json()["detail"]["message"].lower()


async def test_customer_soft_delete_keeps_rental_history(client, admin_headers):
    from datetime import datetime, timedelta, timezone

    moto = await client.post(
        "/api/v2/motorcycles",
        headers=admin_headers,
        json={
            "code": f"MC-C{uuid.uuid4().hex[:6].upper()}",
            "model": "Customer History Bike",
            "plate": f"PP-C{uuid.uuid4().hex[:4].upper()}",
            "dailyRate": 10,
        },
    )
    assert moto.status_code == 201, moto.text
    created, _ = await _create_customer(client, admin_headers)
    customer = created.json()["data"]
    now = datetime.now(timezone.utc)
    rental = await client.post(
        "/api/v2/rentals",
        headers=admin_headers,
        json={
            "customerId": customer["id"],
            "lines": [{
                "motorcycleId": moto.json()["data"]["id"],
                "startDate": now.isoformat(),
                "dueDate": (now + timedelta(days=1)).isoformat(),
                "deposit": 0,
            }],
            "paidAmount": 0,
            "paymentMethod": "Cash",
        },
    )
    assert rental.status_code == 201, rental.text
    rental_id = rental.json()["data"][0]["id"]
    await client.post(f"/api/v2/rentals/{rental_id}/cancel", headers=admin_headers, json={})

    deleted = await client.delete(f"/api/v2/customers/{customer['id']}", headers=admin_headers)
    assert deleted.status_code == 200

    history = await client.get(f"/api/v2/rentals/{rental_id}", headers=admin_headers)
    assert history.status_code == 200
    assert history.json()["data"]["customerId"] == customer["id"]
    assert history.json()["data"]["customer"] == customer["fullName"]


async def test_customer_list_status_filter(client, admin_headers):
    await _create_customer(client, admin_headers, status="Inactive")
    response = await client.get("/api/v2/customers", headers=admin_headers, params={"status": "Inactive", "limit": 100})
    assert response.status_code == 200
    for item in response.json()["data"]:
        assert item["status"] == "Inactive"
