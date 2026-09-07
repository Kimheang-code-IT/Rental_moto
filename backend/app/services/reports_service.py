from __future__ import annotations
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Motorcycle, Rental, RentalCharge, RentalPayment


class TransactionsReportService:
    """Aggregated rental transaction report for Telegram and admin use."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def transactions(self, start: datetime, end: datetime, page: int = 1, limit: int = 10) -> dict:
        events: list[dict] = []

        rentals = (
            await self.session.execute(
                select(Rental).where(Rental.start_date >= start, Rental.start_date <= end).order_by(Rental.start_date)
            )
        ).scalars().all()
        for r in rentals:
            events.append(
                {
                    "type": "rental_created",
                    "rental_no": r.rental_no,
                    "at": r.start_date.isoformat(),
                    "customer": r.customer,
                    "motorcycle": r.motorcycle,
                    "plate": r.plate,
                    "amount": float(r.total_due),
                    "paid": float(r.paid),
                    "currency": r.currency,
                    "status": r.status,
                }
            )

        payments = (
            await self.session.execute(
                select(RentalPayment).where(RentalPayment.paid_at >= start, RentalPayment.paid_at <= end).order_by(RentalPayment.paid_at)
            )
        ).scalars().all()
        rental_nos = {r.id: r.rental_no for r in rentals}
        if payments:
            payment_rentals = (await self.session.execute(select(Rental).where(Rental.id.in_([p.rental_id for p in payments])))).scalars().all()
            for rental in payment_rentals:
                rental_nos[rental.id] = rental.rental_no
        for p in payments:
            events.append(
                {
                    "type": "payment_recorded",
                    "rental_no": rental_nos.get(p.rental_id, ""),
                    "at": p.paid_at.isoformat(),
                    "amount": float(p.amount),
                    "currency": p.currency,
                    "payment_method": p.payment_method,
                    "reference": p.reference,
                    "status": "Paid",
                }
            )

        charges = (
            await self.session.execute(
                select(RentalCharge).where(RentalCharge.created_at >= start, RentalCharge.created_at <= end).order_by(RentalCharge.created_at)
            )
        ).scalars().all()
        charge_nos = {r.id: r.rental_no for r in rentals}
        if charges:
            charge_rental_rows = (await self.session.execute(select(Rental).where(Rental.id.in_([c.rental_id for c in charges])))).scalars().all()
            for rental in charge_rental_rows:
                charge_nos[rental.id] = rental.rental_no
        for c in charges:
            events.append(
                {
                    "type": "charge_recorded",
                    "rental_no": charge_nos.get(c.rental_id, ""),
                    "at": c.created_at.isoformat(),
                    "charge_type": c.charge_type,
                    "amount": float(c.amount),
                    "currency": c.currency,
                    "status": "Charge",
                }
            )

        completed = (
            await self.session.execute(
                select(Rental).where(
                    Rental.status == "Completed",
                    Rental.completed_at.is_not(None),
                    Rental.completed_at >= start,
                    Rental.completed_at <= end,
                )
            )
        ).scalars().all()
        for r in completed:
            events.append(
                {
                    "type": "rental_completed",
                    "rental_no": r.rental_no,
                    "at": r.completed_at.isoformat(),
                    "customer": r.customer,
                    "motorcycle": r.motorcycle,
                    "amount": float(r.total_due),
                    "outstanding": float(r.outstanding),
                    "currency": r.currency,
                    "status": "Completed",
                }
            )

        cancelled = (
            await self.session.execute(
                select(Rental).where(
                    Rental.status == "Cancelled",
                    Rental.cancelled_at.is_not(None),
                    Rental.cancelled_at >= start,
                    Rental.cancelled_at <= end,
                )
            )
        ).scalars().all()
        for r in cancelled:
            events.append(
                {
                    "type": "rental_cancelled",
                    "rental_no": r.rental_no,
                    "at": r.cancelled_at.isoformat(),
                    "customer": r.customer,
                    "currency": r.currency,
                    "status": "Cancelled",
                }
            )

        overdue = (
            await self.session.execute(
                select(Rental).where(
                    Rental.status == "Overdue",
                    Rental.overdue_notified_at.is_not(None),
                    Rental.overdue_notified_at >= start,
                    Rental.overdue_notified_at <= end,
                )
            )
        ).scalars().all()
        for r in overdue:
            events.append(
                {
                    "type": "rental_overdue",
                    "rental_no": r.rental_no,
                    "at": r.overdue_notified_at.isoformat(),
                    "customer": r.customer,
                    "motorcycle": r.motorcycle,
                    "outstanding": float(r.outstanding),
                    "currency": r.currency,
                    "status": "Overdue",
                }
            )

        events.sort(key=lambda e: e.get("at") or "", reverse=True)
        total = len(events)
        page = max(1, page)
        limit = max(1, min(limit, 100))
        start_idx = (page - 1) * limit
        return {"items": events[start_idx : start_idx + limit], "page": page, "limit": limit, "total": total}

    async def motorcycle_status(self) -> dict:
        rows = (
            await self.session.execute(select(Motorcycle.status, Motorcycle.model, Motorcycle.code, Motorcycle.plate).order_by(Motorcycle.code))
        ).all()
        groups: dict[str, list[dict]] = {"Available": [], "Progressing": [], "Maintenance": []}
        for status, model, code, plate in rows:
            groups.setdefault(status, []).append({"code": code, "model": model, "plate": plate})
        counts = {status: len(items) for status, items in groups.items()}
        return {"counts": counts, "groups": groups}

    async def finance_summary(self, start: datetime, end: datetime) -> dict:
        income = Decimal(
            str(
                (
                    await self.session.execute(
                        select(func.coalesce(func.sum(RentalPayment.amount), 0)).where(
                            RentalPayment.paid_at >= start, RentalPayment.paid_at <= end
                        )
                    )
                ).scalar()
                or 0
            )
        )
        expense = Decimal(
            str(
                (
                    await self.session.execute(
                        select(func.coalesce(func.sum(RentalCharge.amount), 0)).where(
                            RentalCharge.created_at >= start, RentalCharge.created_at <= end
                        )
                    )
                ).scalar()
                or 0
            )
        )
        overdue_outstanding = Decimal(
            str(
                (
                    await self.session.execute(
                        select(func.coalesce(func.sum(Rental.outstanding), 0)).where(Rental.status.in_(["Active", "Overdue"]))
                    )
                ).scalar()
                or 0
            )
        )
        return {
            "income": float(income),
            "expense": float(expense),
            "net": float(income - expense),
            "outstanding": float(overdue_outstanding),
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

    @staticmethod
    def next_day_bound(value: datetime) -> datetime:
        return (value + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

