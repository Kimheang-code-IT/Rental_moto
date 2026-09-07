import uuid
from datetime import datetime, timedelta, timezone


async def _make_active_overdue_rental(client, admin_headers):
    moto = await client.post(
        "/api/v2/motorcycles",
        headers=admin_headers,
        json={"code": f"MC-O{uuid.uuid4().hex[:6].upper()}", "model": "Overdue Bike", "dailyRate": 10},
    )
    customer = await client.post(
        "/api/v2/customers",
        headers=admin_headers,
        json={"code": f"CUS-O{uuid.uuid4().hex[:6].upper()}", "fullName": "Overdue Customer", "status": "Active"},
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
                    "startDate": (now - timedelta(days=10)).isoformat(),
                    "dueDate": (now - timedelta(days=2)).isoformat(),
                }
            ],
        },
    )
    return created.json()["data"][0]


async def test_rental_creation_writes_outbox_and_audit(db_session, client, admin_headers):
    from sqlalchemy import select

    from app.models import AuditLog, OutboxEvent

    rental = await _make_active_overdue_rental(client, admin_headers)

    events = (
        await db_session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "rental_created"))
    ).scalars().all()
    matching = [e for e in events if e.payload.get("rental_no") == rental["rentalNo"]]
    assert len(matching) >= 1
    assert matching[0].status == "pending"
    assert matching[0].queue == "telegram"

    logs = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == rental["id"], AuditLog.action == "rental_created")
        )
    ).scalars().all()
    assert len(logs) == 1


async def test_detect_overdue_updates_status_and_notifies_once(db_session, client, admin_headers):
    from app.services.rental_service import RentalService

    rental = await _make_active_overdue_rental(client, admin_headers)

    service = RentalService(db_session)
    overdue_ids = await service.detect_overdue(notify=True)
    assert rental["id"] in overdue_ids

    from app.repositories.rental import RentalRepository

    refreshed = await RentalRepository(db_session).get(rental["id"])
    assert refreshed.status == "Overdue"

    again = await service.detect_overdue(notify=True)
    assert rental["id"] not in again


async def test_outbox_pending_and_publish_flow(db_session):
    from app.models import OutboxEvent
    from app.repositories.admin import OutboxRepository

    repo = OutboxRepository(db_session)
    event = OutboxEvent(event_type="payment_recorded", payload={"rental_no": "RNT-X", "amount": 5}, queue="telegram")
    await repo.add(event)
    await db_session.commit()

    pending = await repo.pending(50)
    assert any(e.id == event.id for e in pending)

    await repo.mark_published(event.id)
    await db_session.commit()

    still_pending = await repo.pending(50)
    assert all(e.id != event.id for e in still_pending)


async def test_task_progress_upsert_and_get(db_session):
    from app.models import TaskProgress
    from app.repositories.admin import TaskProgressRepository

    repo = TaskProgressRepository(db_session)
    task = TaskProgress(id=f"t-{uuid.uuid4().hex[:8]}", task_type="export:rentals", status="queued", progress=0)
    await repo.upsert(task)
    await db_session.commit()

    task.status = "running"
    task.progress = 50
    await repo.upsert(task)
    await db_session.commit()

    fetched = await repo.get(task.id)
    assert fetched.status == "running"
    assert fetched.progress == 50
