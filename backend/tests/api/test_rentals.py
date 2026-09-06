import uuid
from datetime import datetime, timedelta, timezone
from tests.conftest import TEST_VIEWER_EMAIL, TEST_VIEWER_PASSWORD


async def _setup(client, admin_headers):
    moto = await client.post(
        "/api/v2/motorcycles",
        headers=admin_headers,
        json={
            "code": f"MC-R{uuid.uuid4().hex[:6].upper()}",
            "model": "Rental Test Bike",
            "plate": "PP-TEST-001",
            "dailyRate": 10,
            "threeDayRate": 27,
            "weeklyRate": 60,
            "monthlyRate": 200,
        },
    )
    customer = await client.post(
        "/api/v2/customers",
        headers=admin_headers,
        json={
            "code": f"CUS-R{uuid.uuid4().hex[:6].upper()}",
            "fullName": "Rental Test Customer",
            "identityNumber": "KH-9999",
            "phone": "+855 99 999 999",
            "status": "Active",
        },
    )
    return moto.json()["data"], customer.json()["data"]


def _rental_payload(moto, customer, start=None, due=None, paid=0):
    now = datetime.now(timezone.utc)
    start = start or now
    due = due or now + timedelta(days=3)
    return {
        "customerId": customer["id"],
        "lines": [{"motorcycleId": moto["id"], "startDate": start.isoformat(), "dueDate": due.isoformat(), "deposit": 100}],
        "paidAmount": paid,
        "paymentMethod": "Cash",
    }


async def test_create_rental_sets_progressing_and_payment(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    response = await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer, paid=15))
    assert response.status_code == 201, response.text
    rentals = response.json()["data"]
    assert len(rentals) == 1
    rental = rentals[0]
    assert rental["rentalNo"].startswith("RNT-2026-")
    assert rental["status"] == "Active"
    assert rental["rentalCharge"] == "27.00"
    assert rental["paid"] == "15.00"
    assert rental["outstanding"] == "12.00"

    moto_after = await client.get(f"/api/v2/motorcycles/{moto['id']}", headers=admin_headers)
    assert moto_after.json()["data"]["status"] == "Progressing"


async def test_create_rental_applies_line_discount(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    payload = _rental_payload(moto, customer)
    payload["lines"][0]["discount"] = 5
    payload["discount"] = 2
    response = await client.post("/api/v2/rentals", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    rental = response.json()["data"][0]
    # 3-day package 27 - line 5 - document share 2 = 20
    assert rental["rateAmount"] == "27.00"
    assert rental["discount"] == "7.00"
    assert rental["rentalCharge"] == "20.00"


async def test_double_rental_blocked(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    first = await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer))
    assert first.status_code == 201
    second = await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer))
    assert second.status_code == 409


async def test_inactive_customer_rejected(client, admin_headers):
    moto, _ = await _setup(client, admin_headers)
    inactive = await client.post(
        "/api/v2/customers",
        headers=admin_headers,
        json={"code": f"CUS-I{uuid.uuid4().hex[:6].upper()}", "fullName": "Inactive", "status": "Inactive"},
    )
    response = await client.post(
        "/api/v2/rentals",
        headers=admin_headers,
        json=_rental_payload(moto, inactive.json()["data"]),
    )
    assert response.status_code == 422


async def test_close_rental_completes_and_frees_motorcycle(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer, paid=10))
    rental = created.json()["data"][0]

    closed = await client.post(
        f"/api/v2/rentals/{rental['id']}/close",
        headers=admin_headers,
        json={
            "condition": "Good",
            "returnNote": "All good",
            "lateFee": 5,
            "charges": [{"chargeType": "Cleaning", "amount": 3, "description": "wash"}],
            "finalPayment": {"amount": 15, "paymentMethod": "Cash"},
        },
    )
    assert closed.status_code == 200, closed.text
    data = closed.json()["data"]
    assert data["status"] == "Completed"
    assert data["paymentStatus"] == "Partial"
    assert data["additionalCharges"] == "3.00"
    assert data["lateFee"] == "5.00"
    assert data["totalDue"] == "35.00"
    assert data["paid"] == "25.00"
    assert data["outstanding"] == "10.00"
    assert data["returnDate"] is not None

    moto_after = await client.get(f"/api/v2/motorcycles/{moto['id']}", headers=admin_headers)
    assert moto_after.json()["data"]["status"] == "Available"

    duplicate = await client.post(
        f"/api/v2/rentals/{rental['id']}/close",
        headers=admin_headers,
        json={"condition": "Good"},
    )
    assert duplicate.status_code == 409


async def test_cancel_rental(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer))
    rental = created.json()["data"][0]

    cancelled = await client.post(
        f"/api/v2/rentals/{rental['id']}/cancel",
        headers=admin_headers,
        json={"reason": "Customer changed mind"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "Cancelled"

    moto_after = await client.get(f"/api/v2/motorcycles/{moto['id']}", headers=admin_headers)
    assert moto_after.json()["data"]["status"] == "Available"

    close_cancelled = await client.post(
        f"/api/v2/rentals/{rental['id']}/close", headers=admin_headers, json={}
    )
    assert close_cancelled.status_code == 409


async def test_rental_list_filters_and_reports(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer))

    active = await client.get("/api/v2/rentals", headers=admin_headers, params={"status": "Active", "q": "Rental Test Customer"})
    assert active.status_code == 200
    assert active.json()["meta"]["total"] >= 1

    reports = await client.get("/api/v2/rentals/reports", headers=admin_headers, params={"status": "Completed"})
    assert reports.status_code == 200
    for item in reports.json()["data"]:
        assert item["status"] == "Completed"


async def test_overdue_detection_on_list(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    past = datetime.now(timezone.utc) - timedelta(days=5)
    created = await client.post(
        "/api/v2/rentals",
        headers=admin_headers,
        json=_rental_payload(moto, customer, start=past - timedelta(days=3), due=past),
    )
    rental_id = created.json()["data"][0]["id"]

    listing = await client.get("/api/v2/rentals", headers=admin_headers, params={"limit": 100})
    assert listing.status_code == 200
    statuses = {item["id"]: item["status"] for item in listing.json()["data"]}
    assert statuses.get(rental_id) == "Overdue"


async def test_rental_update_active(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer))
    rental = created.json()["data"][0]

    new_due = datetime.now(timezone.utc) + timedelta(days=7)
    updated = await client.put(
        f"/api/v2/rentals/{rental['id']}",
        headers=admin_headers,
        json={"dueDate": new_due.isoformat(), "discount": 2},
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["discount"] == "2.00"
    assert data["durationDays"] == 7


async def test_rental_delete_only_when_cancelled(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer))
    rental = created.json()["data"][0]

    deleted = await client.delete(f"/api/v2/rentals/{rental['id']}", headers=admin_headers)
    assert deleted.status_code == 409

    await client.post(f"/api/v2/rentals/{rental['id']}/cancel", headers=admin_headers, json={})
    deleted = await client.delete(f"/api/v2/rentals/{rental['id']}", headers=admin_headers)
    assert deleted.status_code == 200


async def test_create_rental_multiple_motorcycles_one_row(client, admin_headers):
    moto_a, customer = await _setup(client, admin_headers)
    moto_b = (
        await client.post(
            "/api/v2/motorcycles",
            headers=admin_headers,
            json={
                "code": f"MC-R{uuid.uuid4().hex[:6].upper()}",
                "model": "Second Test Bike",
                "plate": "PP-TEST-002",
                "dailyRate": 10,
                "threeDayRate": 27,
                "weeklyRate": 60,
                "monthlyRate": 200,
            },
        )
    ).json()["data"]
    now = datetime.now(timezone.utc)
    payload = {
        "customerId": customer["id"],
        "lines": [
            {
                "motorcycleId": moto_a["id"],
                "startDate": now.isoformat(),
                "dueDate": (now + timedelta(days=3)).isoformat(),
                "deposit": 50,
                "discount": 2,
            },
            {
                "motorcycleId": moto_b["id"],
                "startDate": now.isoformat(),
                "dueDate": (now + timedelta(days=3)).isoformat(),
                "deposit": 25,
            },
        ],
        "discount": 4,
        "paidAmount": 20,
        "paymentMethod": "Cash",
    }
    response = await client.post("/api/v2/rentals", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    rentals = response.json()["data"]
    assert len(rentals) == 1
    rental = rentals[0]
    assert rental["rentalNo"].startswith("RNT-2026-")
    assert len(rental["lines"]) == 2
    assert {line["motorcycleId"] for line in rental["lines"]} == {moto_a["id"], moto_b["id"]}
    # 27 + 27 gross, line discount 2 + document 4 = 6, charge 48, paid 20
    assert rental["rateAmount"] == "54.00"
    assert rental["discount"] == "6.00"
    assert rental["rentalCharge"] == "48.00"
    assert rental["paid"] == "20.00"
    assert rental["outstanding"] == "28.00"
    assert rental["deposit"] == "75.00"
    assert "Second Test Bike" in rental["motorcycle"]
    assert "PP-TEST-002" in (rental["plate"] or "")

    listing = await client.get(
        "/api/v2/rentals", headers=admin_headers, params={"motorcycleId": moto_b["id"], "limit": 50}
    )
    assert listing.status_code == 200
    assert any(item["id"] == rental["id"] for item in listing.json()["data"])

    for moto_id in (moto_a["id"], moto_b["id"]):
        moto_after = await client.get(f"/api/v2/motorcycles/{moto_id}", headers=admin_headers)
        assert moto_after.json()["data"]["status"] == "Progressing"

    closed = await client.post(
        f"/api/v2/rentals/{rental['id']}/close",
        headers=admin_headers,
        json={"condition": "Good", "finalPayment": {"amount": 28, "paymentMethod": "Cash"}},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"] == "Completed"
    assert len(closed.json()["data"]["lines"]) == 2
    for moto_id in (moto_a["id"], moto_b["id"]):
        moto_after = await client.get(f"/api/v2/motorcycles/{moto_id}", headers=admin_headers)
        assert moto_after.json()["data"]["status"] == "Available"


async def test_create_rental_keeps_independent_line_durations(client, admin_headers):
    moto_a, customer = await _setup(client, admin_headers)
    moto_b = (
        await client.post(
            "/api/v2/motorcycles",
            headers=admin_headers,
            json={
                "code": f"MC-R{uuid.uuid4().hex[:6].upper()}",
                "model": "Week Test Bike",
                "plate": "PP-TEST-007",
                "dailyRate": 10,
                "threeDayRate": 27,
                "weeklyRate": 60,
                "monthlyRate": 200,
            },
        )
    ).json()["data"]
    now = datetime.now(timezone.utc)
    start = now.replace(microsecond=0)
    payload = {
        "customerId": customer["id"],
        "lines": [
            {
                "motorcycleId": moto_a["id"],
                "startDate": start.isoformat(),
                "dueDate": (start + timedelta(days=3)).isoformat(),
            },
            {
                "motorcycleId": moto_b["id"],
                "startDate": start.isoformat(),
                "dueDate": (start + timedelta(days=7)).isoformat(),
            },
        ],
    }
    response = await client.post("/api/v2/rentals", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    rentals = response.json()["data"]
    assert len(rentals) == 1
    rental = rentals[0]
    assert len(rental["lines"]) == 2
    by_moto = {line["motorcycleId"]: line for line in rental["lines"]}
    assert by_moto[moto_a["id"]]["durationDays"] == 3
    assert by_moto[moto_a["id"]]["rateType"] == "ThreeDay"
    assert by_moto[moto_b["id"]]["durationDays"] == 7
    assert by_moto[moto_b["id"]]["rateType"] == "Weekly"
    assert rental["durationDays"] == 7
    assert rental["rateAmount"] == "87.00"
    assert rental["rentalCharge"] == "87.00"


async def test_viewer_cannot_create_rental(client, admin_headers):
    login = await client.post("/api/v2/auth/login", json={"email": TEST_VIEWER_EMAIL, "password": TEST_VIEWER_PASSWORD})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    moto, customer = await _setup(client, admin_headers)
    response = await client.post("/api/v2/rentals", headers=viewer_headers, json=_rental_payload(moto, customer))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ACCESS_DENIED"



