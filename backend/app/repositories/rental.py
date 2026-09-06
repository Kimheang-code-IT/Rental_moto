from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Motorcycle, Rental, RentalCharge, RentalCustomer, RentalExpense, RentalLine, RentalPayment
from app.repositories.base import apply_sorting, build_q_filter, paginate


class MotorcycleRepository:
    SORTABLE = {
        "code": Motorcycle.code,
        "model": Motorcycle.model,
        "plate": Motorcycle.plate,
        "dailyRate": Motorcycle.daily_rate,
        "daily_rate": Motorcycle.daily_rate,
        "status": Motorcycle.status,
        "createdAt": Motorcycle.created_at,
        "created_at": Motorcycle.created_at,
        "updatedAt": Motorcycle.updated_at,
        "updated_at": Motorcycle.updated_at,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, moto_id: str) -> Motorcycle | None:
        return await self.session.get(Motorcycle, moto_id)

    async def get_by_code(self, code: str) -> Motorcycle | None:
        result = await self.session.execute(select(Motorcycle).where(func.lower(Motorcycle.code) == code.lower()))
        return result.scalar_one_or_none()

    async def get_by_ids(self, ids: list[str]) -> list[Motorcycle]:
        if not ids:
            return []
        result = await self.session.execute(select(Motorcycle).where(Motorcycle.id.in_(ids)))
        return list(result.scalars().all())

    async def list(
        self, q: str | None, page: int, limit: int, sort: str | None, status: str | None,
        start_date: datetime | None = None, end_date: datetime | None = None,
    ):
        stmt = select(Motorcycle)
        q_filter = build_q_filter(
            q,
            [Motorcycle.code, Motorcycle.model, Motorcycle.brand, Motorcycle.plate, Motorcycle.chassis_no, Motorcycle.engine_no],
        )
        if q_filter is not None:
            stmt = stmt.where(q_filter)
        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if statuses:
                stmt = stmt.where(Motorcycle.status.in_(statuses))
        else:
            stmt = stmt.where(Motorcycle.status != "Deleted")
        if start_date:
            stmt = stmt.where(Motorcycle.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Motorcycle.created_at <= end_date)
        stmt = apply_sorting(stmt, sort, self.SORTABLE, "code")
        return await paginate(self.session, stmt, page, limit)

    async def add(self, moto: Motorcycle) -> Motorcycle:
        self.session.add(moto)
        await self.session.flush()
        return moto

    async def delete(self, moto: Motorcycle) -> None:
        await self.session.delete(moto)

    async def set_status(self, moto_id: str, status: str) -> None:
        await self.session.execute(update(Motorcycle).where(Motorcycle.id == moto_id).values(status=status))

    async def status_counts(self) -> dict[str, int]:
        result = await self.session.execute(
            select(Motorcycle.status, func.count())
            .where(Motorcycle.status != "Deleted")
            .group_by(Motorcycle.status)
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def next_code(self, prefix: str = "MC") -> str:
        count = (await self.session.execute(select(func.count()).select_from(Motorcycle))).scalar() or 0
        return f"{prefix}-{count + 1:03d}"


class CustomerRepository:
    SORTABLE = {
        "code": RentalCustomer.code,
        "fullName": RentalCustomer.full_name,
        "full_name": RentalCustomer.full_name,
        "status": RentalCustomer.status,
        "createdAt": RentalCustomer.created_at,
        "created_at": RentalCustomer.created_at,
        "updatedAt": RentalCustomer.updated_at,
        "updated_at": RentalCustomer.updated_at,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, customer_id: str) -> RentalCustomer | None:
        return await self.session.get(RentalCustomer, customer_id)

    async def get_by_code(self, code: str) -> RentalCustomer | None:
        result = await self.session.execute(select(RentalCustomer).where(func.lower(RentalCustomer.code) == code.lower()))
        return result.scalar_one_or_none()

    async def list(
        self, q: str | None, page: int, limit: int, sort: str | None, status: str | None,
        start_date: datetime | None = None, end_date: datetime | None = None,
    ):
        stmt = select(RentalCustomer)
        q_filter = build_q_filter(
            q,
            [RentalCustomer.code, RentalCustomer.full_name, RentalCustomer.company, RentalCustomer.phone, RentalCustomer.email, RentalCustomer.identity_number],
        )
        if q_filter is not None:
            stmt = stmt.where(q_filter)
        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if statuses:
                stmt = stmt.where(RentalCustomer.status.in_(statuses))
        else:
            stmt = stmt.where(RentalCustomer.status != "Deleted")
        if start_date:
            stmt = stmt.where(RentalCustomer.created_at >= start_date)
        if end_date:
            stmt = stmt.where(RentalCustomer.created_at <= end_date)
        stmt = apply_sorting(stmt, sort, self.SORTABLE, "code")
        return await paginate(self.session, stmt, page, limit)

    async def add(self, customer: RentalCustomer) -> RentalCustomer:
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def delete(self, customer: RentalCustomer) -> None:
        await self.session.delete(customer)

    async def has_active_rentals(self, customer_id: str) -> bool:
        result = await self.session.execute(
            select(func.count()).select_from(Rental).where(
                Rental.customer_id == customer_id, Rental.status.in_(["Active", "Overdue"])
            )
        )
        return int(result.scalar() or 0) > 0

    async def has_rentals(self, customer_id: str) -> bool:
        """True when any rental row still references this customer (blocks hard delete)."""
        result = await self.session.execute(
            select(func.count()).select_from(Rental).where(Rental.customer_id == customer_id)
        )
        return int(result.scalar() or 0) > 0

    async def next_code(self, prefix: str = "CUS") -> str:
        count = (await self.session.execute(select(func.count()).select_from(RentalCustomer))).scalar() or 0
        return f"{prefix}-{count + 1:03d}"


class RentalRepository:
    SORTABLE = {
        "rentalNo": Rental.rental_no,
        "rental_no": Rental.rental_no,
        "startDate": Rental.start_date,
        "start_date": Rental.start_date,
        "dueDate": Rental.due_date,
        "due_date": Rental.due_date,
        "returnDate": Rental.return_date,
        "return_date": Rental.return_date,
        "totalDue": Rental.total_due,
        "total_due": Rental.total_due,
        "paid": Rental.paid,
        "outstanding": Rental.outstanding,
        "status": Rental.status,
        "createdAt": Rental.created_at,
        "created_at": Rental.created_at,
    }

    _LOAD = (
        selectinload(Rental.payments),
        selectinload(Rental.charges),
        selectinload(Rental.lines),
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, rental_id: str) -> Rental | None:
        result = await self.session.execute(
            select(Rental).options(*self._LOAD).where(Rental.id == rental_id)
        )
        return result.scalar_one_or_none()

    async def get_by_no(self, rental_no: str) -> Rental | None:
        result = await self.session.execute(
            select(Rental).options(*self._LOAD).where(Rental.rental_no == rental_no)
        )
        return result.scalar_one_or_none()

    def _base_stmt(self) -> Select:
        return select(Rental).options(*self._LOAD)

    async def list(
        self, q: str | None, page: int, limit: int, sort: str | None, status: str | None,
        customer_id: str | None = None, motorcycle_id: str | None = None,
        start_date: datetime | None = None, end_date: datetime | None = None,
        date_field: str = "start_date",
    ):
        stmt = self._base_stmt()
        q_filter = build_q_filter(q, [Rental.rental_no, Rental.customer, Rental.motorcycle, Rental.phone, Rental.plate])
        if q_filter is not None:
            stmt = stmt.where(q_filter)
        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if statuses:
                stmt = stmt.where(Rental.status.in_(statuses))
        if customer_id:
            stmt = stmt.where(Rental.customer_id == customer_id)
        if motorcycle_id:
            stmt = stmt.where(
                or_(
                    Rental.motorcycle_id == motorcycle_id,
                    exists().where(
                        RentalLine.rental_id == Rental.id,
                        RentalLine.motorcycle_id == motorcycle_id,
                    ),
                )
            )
        date_col = Rental.return_date if date_field == "return_date" else Rental.start_date
        if start_date:
            stmt = stmt.where(date_col >= start_date)
        if end_date:
            stmt = stmt.where(date_col <= end_date)
        stmt = apply_sorting(stmt, sort, self.SORTABLE, "createdAt")
        return await paginate(self.session, stmt, page, limit)

    async def add(self, rental: Rental) -> Rental:
        self.session.add(rental)
        await self.session.flush()
        return rental

    async def delete(self, rental: Rental) -> None:
        await self.session.delete(rental)

    async def for_update(self, rental_id: str) -> Rental | None:
        result = await self.session.execute(select(Rental).where(Rental.id == rental_id).with_for_update())
        return result.scalar_one_or_none()

    async def mark_overdue(self, now: datetime, batch_limit: int = 200) -> int:
        result = await self.session.execute(
            update(Rental)
            .where(Rental.status == "Active", Rental.due_date < now)
            .values(status="Overdue")
            .returning(Rental.id)
        )
        rows = result.scalars().all()
        return len(rows)

    async def overdue_list(self, now: datetime, limit: int = 100) -> list[Rental]:
        result = await self.session.execute(
            select(Rental).where(Rental.status == "Overdue", Rental.overdue_notified_at.is_(None)).limit(limit)
        )
        return list(result.scalars().all())

    async def set_overdue_notified(self, rental_id: str, at: datetime) -> None:
        await self.session.execute(update(Rental).where(Rental.id == rental_id).values(overdue_notified_at=at))

    async def status_counts(self) -> dict[str, int]:
        result = await self.session.execute(select(Rental.status, func.count()).group_by(Rental.status))
        return {row[0]: int(row[1]) for row in result.all()}

    async def next_id_number(self, prefix: str = "rt") -> int:
        count = (await self.session.execute(select(func.count()).select_from(Rental))).scalar() or 0
        return count + 1


class PaymentRepository:
    SORTABLE = {
        "paymentNo": RentalPayment.payment_no,
        "payment_no": RentalPayment.payment_no,
        "amount": RentalPayment.amount,
        "paidAt": RentalPayment.paid_at,
        "paid_at": RentalPayment.paid_at,
        "createdAt": RentalPayment.created_at,
        "created_at": RentalPayment.created_at,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, payment_id: str) -> RentalPayment | None:
        return await self.session.get(RentalPayment, payment_id)

    async def list(
        self, q: str | None, page: int, limit: int, sort: str | None, rental_id: str | None = None,
        start_date: datetime | None = None, end_date: datetime | None = None, payment_method: str | None = None,
    ):
        stmt = select(RentalPayment)
        q_filter = build_q_filter(q, [RentalPayment.payment_no, RentalPayment.reference])
        if q_filter is not None:
            stmt = stmt.where(q_filter)
        if rental_id:
            stmt = stmt.where(RentalPayment.rental_id == rental_id)
        if payment_method:
            stmt = stmt.where(RentalPayment.payment_method == payment_method)
        if start_date:
            stmt = stmt.where(RentalPayment.paid_at >= start_date)
        if end_date:
            stmt = stmt.where(RentalPayment.paid_at <= end_date)
        stmt = apply_sorting(stmt, sort, self.SORTABLE, "paidAt")
        return await paginate(self.session, stmt, page, limit)

    async def add(self, payment: RentalPayment) -> RentalPayment:
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def delete(self, payment: RentalPayment) -> None:
        await self.session.delete(payment)

    async def sum_between(self, start: datetime | None, end: datetime | None) -> Decimal:
        stmt = select(func.coalesce(func.sum(RentalPayment.amount), 0))
        if start:
            stmt = stmt.where(RentalPayment.paid_at >= start)
        if end:
            stmt = stmt.where(RentalPayment.paid_at <= end)
        return Decimal(str((await self.session.execute(stmt)).scalar() or 0))

    async def daily_series(self, start: datetime, end: datetime) -> list[tuple[str, Decimal]]:
        day = func.date_trunc("day", RentalPayment.paid_at).label("day")
        result = await self.session.execute(
            select(day, func.coalesce(func.sum(RentalPayment.amount), 0))
            .where(RentalPayment.paid_at >= start, RentalPayment.paid_at <= end)
            .group_by(day)
            .order_by(day)
        )
        return [(row[0].strftime("%Y-%m-%d"), Decimal(str(row[1]))) for row in result.all()]


class ChargeRepository:
    SORTABLE = {
        "chargeNo": RentalCharge.charge_no,
        "charge_no": RentalCharge.charge_no,
        "amount": RentalCharge.amount,
        "createdAt": RentalCharge.created_at,
        "created_at": RentalCharge.created_at,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, charge_id: str) -> RentalCharge | None:
        return await self.session.get(RentalCharge, charge_id)

    async def list(
        self, q: str | None, page: int, limit: int, sort: str | None, rental_id: str | None = None,
        charge_type: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None,
    ):
        stmt = select(RentalCharge)
        q_filter = build_q_filter(q, [RentalCharge.charge_no, RentalCharge.description, RentalCharge.charge_type])
        if q_filter is not None:
            stmt = stmt.where(q_filter)
        if rental_id:
            stmt = stmt.where(RentalCharge.rental_id == rental_id)
        if charge_type:
            stmt = stmt.where(RentalCharge.charge_type == charge_type)
        if start_date:
            stmt = stmt.where(RentalCharge.created_at >= start_date)
        if end_date:
            stmt = stmt.where(RentalCharge.created_at <= end_date)
        stmt = apply_sorting(stmt, sort, self.SORTABLE, "createdAt")
        return await paginate(self.session, stmt, page, limit)

    async def add(self, charge: RentalCharge) -> RentalCharge:
        self.session.add(charge)
        await self.session.flush()
        return charge

    async def delete(self, charge: RentalCharge) -> None:
        await self.session.delete(charge)


class ExpenseRepository:
    SORTABLE = {
        "expenseNo": RentalExpense.expense_no,
        "expense_no": RentalExpense.expense_no,
        "date": RentalExpense.date,
        "amount": RentalExpense.amount,
        "expenseType": RentalExpense.expense_type,
        "expense_type": RentalExpense.expense_type,
        "createdAt": RentalExpense.created_at,
        "created_at": RentalExpense.created_at,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, expense_id: str) -> RentalExpense | None:
        return await self.session.get(RentalExpense, expense_id)

    async def list(
        self, q: str | None, page: int, limit: int, sort: str | None, expense_type: str | None = None,
        start_date: datetime | None = None, end_date: datetime | None = None,
    ):
        stmt = select(RentalExpense)
        q_filter = build_q_filter(q, [RentalExpense.expense_no, RentalExpense.description, RentalExpense.expense_type])
        if q_filter is not None:
            stmt = stmt.where(q_filter)
        if expense_type:
            types = [s.strip() for s in expense_type.split(",") if s.strip()]
            if types:
                stmt = stmt.where(RentalExpense.expense_type.in_(types))
        if start_date:
            stmt = stmt.where(RentalExpense.date >= start_date)
        if end_date:
            stmt = stmt.where(RentalExpense.date <= end_date)
        stmt = apply_sorting(stmt, sort, self.SORTABLE, "date")
        return await paginate(self.session, stmt, page, limit)

    async def add(self, expense: RentalExpense) -> RentalExpense:
        self.session.add(expense)
        await self.session.flush()
        return expense

    async def delete(self, expense: RentalExpense) -> None:
        await self.session.delete(expense)

    async def sum_between(self, start: datetime | None, end: datetime | None) -> Decimal:
        stmt = select(func.coalesce(func.sum(RentalExpense.amount), 0))
        if start:
            stmt = stmt.where(RentalExpense.date >= start)
        if end:
            stmt = stmt.where(RentalExpense.date <= end)
        return Decimal(str((await self.session.execute(stmt)).scalar() or 0))

    async def daily_series(self, start: datetime, end: datetime) -> list[tuple[str, Decimal]]:
        day = func.date_trunc("day", RentalExpense.date).label("day")
        result = await self.session.execute(
            select(day, func.coalesce(func.sum(RentalExpense.amount), 0))
            .where(RentalExpense.date >= start, RentalExpense.date <= end)
            .group_by(day)
            .order_by(day)
        )
        return [(row[0].strftime("%Y-%m-%d"), Decimal(str(row[1]))) for row in result.all()]

    async def next_id_number(self) -> int:
        count = (await self.session.execute(select(func.count()).select_from(RentalExpense))).scalar() or 0
        return count + 1

