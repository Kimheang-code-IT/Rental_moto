from datetime import datetime, timedelta, timezone

from app.tasks.deadline_alerts import reminder_delta, reminder_label, reminder_value


def test_reminder_delta_uses_configured_duration():
    assert reminder_delta({"deadlineReminderValue": 30, "deadlineReminderUnit": "minutes"}) == timedelta(minutes=30)
    assert reminder_delta({"deadlineReminderValue": 2, "deadlineReminderUnit": "hours"}) == timedelta(hours=2)
    assert reminder_delta({"deadlineReminderValue": 3, "deadlineReminderUnit": "days"}) == timedelta(days=3)


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
