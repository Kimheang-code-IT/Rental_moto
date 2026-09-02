import uuid
from datetime import datetime, timedelta, timezone


async def _setup_with_rental(client, admin_headers, paid=10):
    moto = await client.post(
        "/api/v2/motorcycles",
        headers=admin_headers,
        json={
            "code": f"MC-F{uuid.uuid4().hex[:6].upper()}",
            "model": "Finance Test Bike",
            "plate": "PP-FIN-001",
            "dailyRate": 10,
            "threeDayRate": 30,
            "weeklyRate": 60,
            "monthlyRate": 200,
        },
    )
    customer = await client.post(
        "/api/v2/customers",
        headers=admin_headers,
        json={
            "code": f"CUS-F{uuid.uuid4().hex[:6].upper()}",
            "fullName": "Finance Customer",
            "status": "Active",
        },
    )
    now = datetime.now(timezone.utc)
    created = await client.post(
        "/api/v2/rentals",
        headers=admin_headers,
        json={
            "customerId": customer.json()["data"]["id"],
            "lines": [
                {
                    "motorcycleId": moto.json()["data"]["id"],
                    "startDate": now.isoformat(),
                    "dueDate": (now + timedelta(days=3)).isoformat(),
                }
            ],
            "paidAmount": paid,
            "paymentMethod": "Cash",
        },
    )
    return created.json()["data"][0]


async def test_record_payment_updates_balances(client, admin_headers):
    rental = await _setup_with_rental(client, admin_headers, paid=10)
    assert rental["outstanding"] == "20.00"

    payment = await client.post(
        "/api/v2/payments",
        headers=admin_headers,
        json={"rentalId": rental["id"], "amount": 20, "paymentMethod": "QR Payment", "reference": "QR-1"},
    )
    assert payment.status_code == 201, payment.text
    assert payment.json()["data"]["paymentNo"].startswith("RNP-")

    updated = await client.get(f"/api/v2/rentals/{rental['id']}", headers=admin_headers)
    assert updated.json()["data"]["paid"] == "30.00"
    assert updated.json()["data"]["outstanding"] == "0.00"

    listing = await client.get("/api/v2/payments", headers=admin_headers, params={"rentalId": rental["id"]})
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] == 2

    custom_payment = await client.post(
        "/api/v2/payments",
        headers=admin_headers,
        json={"rentalId": rental["id"], "amount": 1, "paymentMethod": "Wing Transfer"},
    )
    assert custom_payment.status_code == 201, custom_payment.text
    assert custom_payment.json()["data"]["paymentMethod"] == "Wing Transfer"


async def test_payment_on_completed_rental_rejected(client, admin_headers):
    rental = await _setup_with_rental(client, admin_headers, paid=0)
    await client.post(f"/api/v2/rentals/{rental['id']}/cancel", headers=admin_headers, json={})
    response = await client.post(
        "/api/v2/payments",
        headers=admin_headers,
        json={"rentalId": rental["id"], "amount": 5},
    )
    assert response.status_code == 409


async def test_record_charge_updates_totals(client, admin_headers):
    rental = await _setup_with_rental(client, admin_headers, paid=0)
    charge = await client.post(
        "/api/v2/charges",
        headers=admin_headers,
        json={"rentalId": rental["id"], "chargeType": "Damage", "amount": 25, "description": "Scratch"},
    )
    assert charge.status_code == 201, charge.text
    assert charge.json()["data"]["chargeNo"].startswith("RNC-")

    updated = await client.get(f"/api/v2/rentals/{rental['id']}", headers=admin_headers)
    assert updated.json()["data"]["additionalCharges"] == "25.00"
    assert updated.json()["data"]["totalDue"] == "55.00"
    assert updated.json()["data"]["outstanding"] == "55.00"

    custom_charge = await client.post(
        "/api/v2/charges",
        headers=admin_headers,
        json={"rentalId": rental["id"], "chargeType": "Helmet replacement", "amount": 10, "description": "Lost helmet"},
    )
    assert custom_charge.status_code == 201, custom_charge.text
    assert custom_charge.json()["data"]["chargeType"] == "Helmet replacement"


async def test_expense_crud_and_listing(client, admin_headers):
    expense = await client.post(
        "/api/v2/expenses",
        headers=admin_headers,
        json={"date": datetime.now(timezone.utc).isoformat(), "expenseType": "Fuel", "amount": 12.5, "description": "Gas"},
    )
    assert expense.status_code == 201, expense.text
    data = expense.json()["data"]
    assert data["expenseNo"].startswith("RNX-")
    assert data["amount"] == "12.50"

    bad_type = await client.post(
        "/api/v2/expenses",
        headers=admin_headers,
        json={"date": datetime.now(timezone.utc).isoformat(), "expenseType": "Party", "amount": 5, "description": "Team event"},
    )
    assert bad_type.status_code == 201, bad_type.text
    assert bad_type.json()["data"]["expenseType"] == "Party"

    empty_type = await client.post(
        "/api/v2/expenses",
        headers=admin_headers,
        json={"date": datetime.now(timezone.utc).isoformat(), "expenseType": "   ", "amount": 5},
    )
    assert empty_type.status_code == 422

    listing = await client.get("/api/v2/expenses", headers=admin_headers, params={"expenseType": "Fuel", "limit": 5})
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] >= 1


async def test_dashboard_and_finance_summary(client, admin_headers):
    await _setup_with_rental(client, admin_headers, paid=7)
    dashboard = await client.get("/api/v2/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200
    data = dashboard.json()["data"]
    assert data["rentalsActive"] >= 1
    assert data["income"] >= 7
    assert "motorcycleStatus" in data
    assert data["netIncome"] == data["income"] - data["expense"]

    ranged = await client.get(
        "/api/v2/dashboard",
        headers=admin_headers,
        params={"startDate": "2026-01-01", "endDate": "2030-01-01"},
    )
    assert ranged.status_code == 200
    ranged_data = ranged.json()["data"]
    assert ranged_data["income"] >= 7
    assert len(ranged_data["incomeByDay"]) > 0
    assert len(ranged_data["expenseByDay"]) == len(ranged_data["incomeByDay"])

    finance = await client.get(
        "/api/v2/finance/summary",
        headers=admin_headers,
        params={"startDate": "2026-01-01", "endDate": "2030-01-01"},
    )
    assert finance.status_code == 200
    assert finance.json()["data"]["income"] >= 7


async def test_viewer_permissions_on_payments(client, admin_headers):
    login = await client.post("/api/v2/auth/login", json={"email": "viewer@example.com", "password": "123456"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    rental = await _setup_with_rental(client, admin_headers, paid=0)

    view = await client.get("/api/v2/payments", headers=viewer_headers)
    assert view.status_code == 200

    create = await client.post(
        "/api/v2/payments",
        headers=viewer_headers,
        json={"rentalId": rental["id"], "amount": 5},
    )
    assert create.status_code == 403


