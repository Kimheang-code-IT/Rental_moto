from datetime import datetime, timedelta, timezone

from app.tasks.deadline_alerts import (
    enqueue_deadline_alerts,
    reminder_delta,
    reminder_label,
    reminder_value,
)


def test_reminder_delta_uses_configured_duration():
    assert reminder_delta({"deadlineReminderValue": 30, "deadlineReminderUnit": "minutes"}) == timedelta(minutes=30)
    assert reminder_delta({"deadlineReminderValue": 2, "deadlineReminderUnit": "hours"}) == timedelta(hours=2)
    assert reminder_delta({"deadlineReminderValue": 3, "deadlineReminderUnit": "days"}) == timedelta(days=3)


def test_reminder_delta_defaults_to_one_day():
    assert reminder_delta({}) == timedelta(days=1)
    assert reminder_delta({"deadlineReminderValue": 1}) == timedelta(days=1)


def test_reminder_delta_can_be_disabled():
    assert reminder_delta({"deadlineReminderEnabled": False}) is None
    assert reminder_delta({"enabled": False}) is None


def test_reminder_label_is_readable():
    assert reminder_label(1, "hours") == "1 hour"
    assert reminder_label(3, "days") == "3 days"


def test_invalid_legacy_value_falls_back_safely():
    assert reminder_value({"deadlineReminderValue": "invalid"}) == 1


async def test_enqueue_deadline_alerts_writes_outbox_once(db_session, client, admin_headers):
    import uuid

    from sqlalchemy import select

    from app.models import OutboxEvent
    from app.tasks.deadline_alerts import enqueue_deadline_alerts

    moto = await client.post(
        "/api/v2/motorcycles",
        headers=admin_headers,
        json={"code": f"MC-D{uuid.uuid4().hex[:6].upper()}", "model": "Deadline Bike", "dailyRate": 10},
    )
    customer = await client.post(
        "/api/v2/customers",
        headers=admin_headers,
        json={"code": f"CUS-D{uuid.uuid4().hex[:6].upper()}", "fullName": "Deadline Customer", "status": "Active"},
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
                    "dueDate": (now + timedelta(minutes=30)).isoformat(),
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    rental = created.json()["data"][0]

    await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={
            "telegram": {
                "enabled": True,
                "deadlineReminderEnabled": True,
                "deadlineReminderValue": 1,
                "deadlineReminderUnit": "hours",
            }
        },
    )

    first = await enqueue_deadline_alerts(db_session)
    assert first["alerted"] >= 1

    events = (
        await db_session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "deadline_approaching"))
    ).scalars().all()
    matching = [event for event in events if event.payload.get("rental_no") == rental["rentalNo"]]
    assert matching
    assert matching[0].queue == "telegram"
    assert matching[0].payload["reminder_label"] == "1 hour"

    second = await enqueue_deadline_alerts(db_session)
    assert second["alerted"] == 0


async def _seed_rental(client, admin_headers, due_delta, tag):
    import uuid

    now = datetime.now(timezone.utc)
    moto = await client.post(
        "/api/v2/motorcycles",
        headers=admin_headers,
        json={
            "code": f"MC-{tag}{uuid.uuid4().hex[:5].upper()}",
            "model": "Deadline Bike",
            "dailyRate": 10,
        },
    )
    customer = await client.post(
        "/api/v2/customers",
        headers=admin_headers,
        json={
            "code": f"CUS-{tag}{uuid.uuid4().hex[:5].upper()}",
            "fullName": "Deadline Customer",
            "status": "Active",
        },
    )
    created = await client.post(
        "/api/v2/rentals",
        headers=admin_headers,
        json={
            "customerId": customer.json()["data"]["id"],
            "lines": [
                {
                    "motorcycleId": moto.json()["data"]["id"],
                    "startDate": now.isoformat(),
                    "dueDate": (now + due_delta).isoformat(),
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["data"][0]


async def _enable_one_day_reminder(client, admin_headers):
    return await client.patch(
        "/api/v2/settings/app-config",
        headers=admin_headers,
        json={
            "telegram": {
                "enabled": True,
                "deadlineReminderEnabled": True,
                "deadlineReminderValue": 1,
                "deadlineReminderUnit": "days",
            }
        },
    )


def _alerted_rental_numbers(events) -> set[str]:
    return {event.payload.get("rental_no") for event in events if event.payload.get("rental_no")}


async def _deadline_events(db_session):
    from sqlalchemy import select

    from app.models import OutboxEvent

    return (
        await db_session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "deadline_approaching"))
    ).scalars().all()


async def test_deadline_alerts_only_fire_for_active_rentals(db_session, client, admin_headers):
    active = await _seed_rental(client, admin_headers, timedelta(hours=12), "A")
    finished = await _seed_rental(client, admin_headers, timedelta(hours=12), "F")
    cancelled = await _seed_rental(client, admin_headers, timedelta(hours=12), "C")

    closed = await client.post(
        f"/api/v2/rentals/{finished['id']}/close",
        headers=admin_headers,
        json={"condition": "Good"},
    )
    assert closed.status_code == 200, closed.text
    cancel = await client.post(
        f"/api/v2/rentals/{cancelled['id']}/cancel",
        headers=admin_headers,
        json={"reason": "test"},
    )
    assert cancel.status_code == 200, cancel.text

    await _enable_one_day_reminder(client, admin_headers)
    await enqueue_deadline_alerts(db_session)

    refs = _alerted_rental_numbers(await _deadline_events(db_session))
    assert active["rentalNo"] in refs
    assert finished["rentalNo"] not in refs
    assert cancelled["rentalNo"] not in refs


async def test_deadline_alerts_use_one_day_default_window(db_session, client, admin_headers):
    soon = await _seed_rental(client, admin_headers, timedelta(hours=23), "S")
    later = await _seed_rental(client, admin_headers, timedelta(hours=25), "L")

    await _enable_one_day_reminder(client, admin_headers)
    await enqueue_deadline_alerts(db_session)

    refs = _alerted_rental_numbers(await _deadline_events(db_session))
    assert soon["rentalNo"] in refs
    assert later["rentalNo"] not in refs


async def test_deadline_alerts_skip_overdue_rentals(db_session, client, admin_headers):
    from sqlalchemy import update

    from app.models import Rental

    rental = await _seed_rental(client, admin_headers, timedelta(hours=12), "O")
    await db_session.execute(
        update(Rental)
        .where(Rental.id == rental["id"])
        .values(due_date=datetime.now(timezone.utc) - timedelta(hours=1))
    )
    await db_session.commit()

    await _enable_one_day_reminder(client, admin_headers)
    await enqueue_deadline_alerts(db_session)

    refs = _alerted_rental_numbers(await _deadline_events(db_session))
    assert rental["rentalNo"] not in refs
