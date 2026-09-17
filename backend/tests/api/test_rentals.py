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
        "lines": [{"motorcycleId": moto["id"], "startDate": start.isoformat(), "dueDate": due.isoformat(), "deposit": 0}],
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
    assert rental["identityNumber"] == "KH-9999"
    assert rental["rentalCharge"] == "27.00"
    # Full price is collected automatically at rental time (no outstanding).
    assert rental["paid"] == "27.00"
    assert rental["outstanding"] == "0.00"

    moto_after = await client.get(f"/api/v2/motorcycles/{moto['id']}", headers=admin_headers)
    assert moto_after.json()["data"]["status"] == "Progressing"


async def test_create_rental_credits_deposit_then_payment(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    now = datetime.now(timezone.utc)
    payload = {
        "customerId": customer["id"],
        "lines": [
            {
                "motorcycleId": moto["id"],
                "startDate": now.isoformat(),
                "dueDate": (now + timedelta(days=1)).isoformat(),
                "deposit": 5,
            }
        ],
        "paidAmount": 0,
        "paymentMethod": "Cash",
        "taxPercent": 10,
    }
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    rental = created.json()["data"][0]
    assert rental["rentalCharge"] == "10.00"
    assert rental["deposit"] == "5.00"
    assert rental["taxPercent"] == "0.00"
    assert rental["tax"] == "0.00"
    assert rental["paid"] == "10.00"
    assert rental["outstanding"] == "0.00"

    payments = await client.get(
        "/api/v2/payments",
        headers=admin_headers,
        params={"rentalId": rental["id"]},
    )
    assert payments.status_code == 200, payments.text
    rows = payments.json()["data"]
    assert len(rows) == 1
    assert rows[0]["amount"] == "10.00"


async def test_create_rental_applies_line_discount(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    payload = _rental_payload(moto, customer)
    payload["lines"][0]["discount"] = 5
    payload["discount"] = 2
    response = await client.post("/api/v2/rentals", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    rental = response.json()["data"][0]
    # 3-day package 27 - line discount 5; document/extra discount is ignored
    assert rental["rateAmount"] == "27.00"
    assert rental["discount"] == "5.00"
    assert rental["rentalCharge"] == "22.00"
    assert rental["tax"] == "0.00"


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
            "lateFee": 0,
            "charges": [{"chargeType": "Cleaning", "amount": 3, "description": "wash"}],
            "finalPayment": {"amount": 3, "paymentMethod": "Cash"},
        },
    )
    assert closed.status_code == 200, closed.text
    data = closed.json()["data"]
    assert data["status"] == "Completed"
    assert data["paymentStatus"] == "Paid"
    assert data["additionalCharges"] == "3.00"
    assert data["lateFee"] == "0.00"
    assert data["totalDue"] == "30.00"
    assert data["paid"] == "30.00"
    assert data["outstanding"] == "0.00"
    assert data["returnDate"] is not None

    moto_after = await client.get(f"/api/v2/motorcycles/{moto['id']}", headers=admin_headers)
    assert moto_after.json()["data"]["status"] == "Available"

    duplicate = await client.post(
        f"/api/v2/rentals/{rental['id']}/close",
        headers=admin_headers,
        json={"condition": "Good"},
    )
    assert duplicate.status_code == 409


async def test_close_rental_refunds_deposit_after_charges(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    payload = _rental_payload(moto, customer, paid=27)
    payload["lines"][0]["deposit"] = 20
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=payload)
    rental = created.json()["data"][0]
    assert rental["deposit"] == "20.00"
    assert rental["paid"] == "27.00"

    closed = await client.post(
        f"/api/v2/rentals/{rental['id']}/close",
        headers=admin_headers,
        json={
            "condition": "Good",
            "charges": [{"chargeType": "Cleaning", "amount": 5}],
            "depositRefund": 15,
        },
    )
    assert closed.status_code == 200, closed.text
    data = closed.json()["data"]
    assert data["status"] == "Completed"
    assert data["depositRefund"] == "15.00"
    assert data["totalDue"] == "32.00"
    assert data["paid"] == "32.00"
    assert data["outstanding"] == "0.00"

    payments = await client.get(
        "/api/v2/payments",
        headers=admin_headers,
        params={"rentalId": rental["id"]},
    )
    assert payments.status_code == 200, payments.text
    deposit_income = [
        row for row in payments.json()["data"]
        if row["paymentMethod"] == "Security Deposit"
    ]
    assert len(deposit_income) == 1
    assert deposit_income[0]["amount"] == "5.00"
    assert deposit_income[0]["note"] == "Security deposit applied to return charges"


async def test_close_rental_refund_is_capped_at_deposit(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    payload = _rental_payload(moto, customer, paid=27)
    payload["lines"][0]["deposit"] = 20
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=payload)
    rental = created.json()["data"][0]

    closed = await client.post(
        f"/api/v2/rentals/{rental['id']}/close",
        headers=admin_headers,
        json={"condition": "Good", "depositRefund": 999},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["depositRefund"] == "20.00"


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

    rental_start = datetime.fromisoformat(rental["startDate"].replace("Z", "+00:00"))
    new_due = rental_start + timedelta(days=7)
    updated = await client.put(
        f"/api/v2/rentals/{rental['id']}",
        headers=admin_headers,
        json={
            "dueDate": new_due.isoformat(),
            "discount": 2,
            "paymentMethod": "Bank Transfer",
            "paymentCurrency": "KHR",
            "exchangeRate": 4100,
            "syncRentalPayment": True,
        },
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["discount"] == "2.00"
    assert data["durationDays"] == 7
    assert data["rentalCharge"] == "58.00"
    assert data["paid"] == "58.00"
    assert data["outstanding"] == "0.00"

    payments = await client.get(
        "/api/v2/payments",
        headers=admin_headers,
        params={"rentalId": rental["id"]},
    )
    assert payments.status_code == 200, payments.text
    rows = payments.json()["data"]
    assert len(rows) == 1
    assert rows[0]["amount"] == "58.00"
    assert rows[0]["paymentMethod"] == "Bank Transfer"
    assert rows[0]["currency"] == "KHR"
    assert rows[0]["tenderedAmount"] == "237800.00"
    assert rows[0]["exchangeRate"] == "4100.0000"
    assert rows[0]["note"] == "Full payment"


async def test_rental_update_paid_amount(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    created = await client.post(
        "/api/v2/rentals",
        headers=admin_headers,
        json=_rental_payload(moto, customer, paid=10),
    )
    rental = created.json()["data"][0]
    assert rental["paid"] == "27.00"
    assert rental["outstanding"] == "0.00"

    increased = await client.put(
        f"/api/v2/rentals/{rental['id']}",
        headers=admin_headers,
        json={"paidAmount": 20, "paymentMethod": "QR Payment"},
    )
    assert increased.status_code == 200, increased.text
    data = increased.json()["data"]
    assert data["paid"] == "20.00"
    assert data["outstanding"] == "7.00"
    assert data["paymentMethod"] == "QR Payment"

    payments = await client.get(
        "/api/v2/payments",
        headers=admin_headers,
        params={"rentalId": rental["id"]},
    )
    assert payments.status_code == 200, payments.text
    payment_rows = payments.json()["data"]
    assert len(payment_rows) == 1
    assert payment_rows[0]["amount"] == "20.00"
    assert payment_rows[0]["paymentMethod"] == "QR Payment"

    khr_update = await client.put(
        f"/api/v2/rentals/{rental['id']}",
        headers=admin_headers,
        json={
            "paidAmount": 5,
            "paymentCurrency": "KHR",
            "exchangeRate": 4100,
            "tenderedAmount": 20500,
            "paymentMethod": "Cash",
        },
    )
    assert khr_update.status_code == 200, khr_update.text
    khr_data = khr_update.json()["data"]
    assert khr_data["paid"] == "5.00"
    khr_payments = await client.get(
        "/api/v2/payments",
        headers=admin_headers,
        params={"rentalId": rental["id"]},
    )
    khr_rows = khr_payments.json()["data"]
    assert len(khr_rows) == 1
    assert khr_rows[0]["currency"] == "KHR"
    assert khr_rows[0]["tenderedAmount"] == "20500.00"
    assert float(khr_rows[0]["exchangeRate"]) == 4100.0

    cleared = await client.put(
        f"/api/v2/rentals/{rental['id']}",
        headers=admin_headers,
        json={"paidAmount": 0},
    )
    assert cleared.status_code == 200, cleared.text
    cleared_data = cleared.json()["data"]
    assert cleared_data["paid"] == "0.00"
    assert cleared_data["outstanding"] == "27.00"

    payments_after = await client.get(
        "/api/v2/payments",
        headers=admin_headers,
        params={"rentalId": rental["id"]},
    )
    assert payments_after.json()["data"] == []


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
    # 27 + 27 gross, line discount 2 only (document/extra discount ignored).
    # Security deposits are preserved in full and do not reduce rental charges.
    assert rental["rateAmount"] == "54.00"
    assert rental["discount"] == "2.00"
    assert rental["rentalCharge"] == "52.00"
    assert rental["paid"] == "52.00"
    assert rental["deposit"] == "75.00"
    assert rental["outstanding"] == "0.00"
    assert rental["tax"] == "0.00"
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
        json={"condition": "Good", "finalPayment": {"amount": 0, "paymentMethod": "Cash"}},
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


async def test_create_rental_persists_currency(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    payload = _rental_payload(moto, customer)
    payload["currency"] = "KHR"
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["data"][0]["currency"] == "KHR"


async def test_rental_update_persists_currency(client, admin_headers):
    moto, customer = await _setup(client, admin_headers)
    created = await client.post("/api/v2/rentals", headers=admin_headers, json=_rental_payload(moto, customer))
    rental = created.json()["data"][0]
    assert rental["currency"] == "USD"

    updated = await client.put(
        f"/api/v2/rentals/{rental['id']}",
        headers=admin_headers,
        json={"currency": "KHR"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["currency"] == "KHR"

    # Reopening the rental keeps the saved currency (no silent reset to USD).
    fetched = await client.get(f"/api/v2/rentals/{rental['id']}", headers=admin_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["data"]["currency"] == "KHR"
