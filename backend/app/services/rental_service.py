from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.fx import exchange_rate_for_currencies, normalize_exchange_rate, normalize_payment_currency, resolve_payment_money
from app.core.money import distribute_document_discount, money
from app.core.pricing import (
    duration_days,
    line_charge,
    rate_type_for,
    resolve_motorcycle_rates,
    security_deposit_settlement,
)
from app.models import (
    AuditLog,
    Motorcycle,
    OutboxEvent,
    Rental,
    RentalCharge,
    RentalExpense,
    RentalLine,
    RentalPayment,
    User,
)
from app.repositories.admin import AuditRepository, DocumentSequenceRepository
from app.repositories.rental import (
    ChargeRepository,
    CustomerRepository,
    ExpenseRepository,
    MotorcycleRepository,
    PaymentRepository,
    RentalRepository,
)

VALID_MOTORCYCLE_STATUSES = ["Available", "Progressing", "Maintenance"]
VALID_RENTAL_STATUSES = ["Active", "Overdue", "Completed", "Cancelled"]
VALID_CONDITIONS = ["Good", "Minor issues", "Damaged"]

OUTBOX_QUEUE = "telegram"


def _actor_label(user: User | None) -> str | None:
    return user.display_name if user else None


def normalize_option_label(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > 40:
        raise ValidationError(f"{label} must be 40 characters or fewer")
    return text


def normalize_expense_type(value: str) -> str:
    return normalize_option_label(value, "Expense type")


def normalize_charge_type(value: str) -> str:
    return normalize_option_label(value, "Charge type")


def normalize_payment_method(value: str) -> str:
    return normalize_option_label(value, "Payment method")


def _outbox(event_type: str, payload: dict) -> OutboxEvent:
    return OutboxEvent(event_type=event_type, payload=payload, queue=OUTBOX_QUEUE)


async def _get_motorcycles_locked(session: AsyncSession, ids: list[str]) -> list[Motorcycle]:
    result = await session.execute(select(Motorcycle).where(Motorcycle.id.in_(ids)).with_for_update())
    rows = list(result.scalars().all())
    found = {m.id for m in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        raise NotFoundError(f"Motorcycle not found: {', '.join(missing)}")
    return rows


def _join_display(parts: list[str | None], limit: int) -> str:
    text = ", ".join(str(part).strip() for part in parts if part and str(part).strip())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _price_line_rows(moto_map: dict[str, Motorcycle], lines) -> list[dict]:
    priced: list[dict] = []
    for line in lines:
        moto = moto_map[line.motorcycle_id]
        if line.due_date <= line.start_date:
            raise ValidationError("Due date must be after start date")
        days = duration_days(line.start_date, line.due_date)
        rates = resolve_motorcycle_rates(moto.daily_rate, moto.three_day_rate, moto.weekly_rate, moto.monthly_rate)
        charge = line_charge(rates, days, line.start_date, line.due_date)
        if charge <= 0:
            raise ValidationError(f"Cannot compute charge for motorcycle {moto.code}")
        priced.append(
            {
                "moto": moto,
                "start_date": line.start_date,
                "due_date": line.due_date,
                "days": days,
                "charge": charge,
                "line_discount": max(money(getattr(line, "discount", 0)), Decimal("0")),
                "deposit": money(getattr(line, "deposit", 0)),
                "note": getattr(line, "note", None),
            }
        )
    return priced


def _apply_line_discounts(priced: list[dict], doc_discount) -> list[dict]:
    charges = [row["charge"] for row in priced]
    shares = distribute_document_discount(charges, doc_discount)
    built: list[dict] = []
    for index, row in enumerate(priced):
        discount = money(min(row["line_discount"] + shares[index], row["charge"]))
        built.append({**row, "discount": discount, "rental_charge": money(row["charge"] - discount)})
    return built


def _apply_rental_header(rental: Rental, customer, built: list[dict], deposit: Decimal | None = None) -> None:
    first = built[0]
    start_date = min(row["start_date"] for row in built)
    due_date = max(row["due_date"] for row in built)
    duration = duration_days(start_date, due_date)
    rental_charge = money(sum((row["rental_charge"] for row in built), Decimal("0")))
    rate_types = {rate_type_for(row["days"], row["start_date"], row["due_date"]) for row in built}
    rental.customer_id = customer.id
    rental.customer = customer.full_name
    rental.phone = customer.phone
    rental.motorcycle_id = first["moto"].id
    rental.motorcycle = _join_display([row["moto"].model for row in built], 500)
    rental.plate = _join_display([row["moto"].plate for row in built], 200) or None
    rental.start_date = start_date
    rental.due_date = due_date
    rental.duration_days = duration
    rental.rate_type = rate_types.pop() if len(rate_types) == 1 else rate_type_for(duration, start_date, due_date)
    rental.rate_amount = money(sum((row["charge"] for row in built), Decimal("0")))
    rental.deposit = money(deposit) if deposit is not None else money(sum((row["deposit"] for row in built), Decimal("0")))
    rental.discount = money(sum((row["discount"] for row in built), Decimal("0")))
    rental.rental_charge = rental_charge
    rental.total_due = money(rental_charge + rental.late_fee + rental.additional_charges)


def _with_header_deposit(built: list[dict], deposit) -> list[dict]:
    """Store the rental deposit on the first line; other lines keep zero deposit."""
    amount = max(money(deposit), Decimal("0.00"))
    rows: list[dict] = []
    for index, row in enumerate(built):
        rows.append({**row, "deposit": amount if index == 0 else Decimal("0.00")})
    return rows


def _apply_deposit_tendered(rental: Rental, request) -> None:
    """Persist the entered deposit amount/currency so invoices can show exact KHR."""
    payment_currency = normalize_payment_currency(
        getattr(request, "payment_currency", None)
        or getattr(request, "deposit_currency", None)
        or rental.currency
    )
    rate = exchange_rate_for_currencies(
        getattr(request, "exchange_rate", None),
        payment_currency,
        rental.currency,
    )
    tendered = getattr(request, "deposit_tendered_amount", None)
    if tendered is None:
        if payment_currency == normalize_payment_currency(rental.currency):
            tendered = rental.deposit
    if tendered is not None:
        rental.deposit_tendered_amount = money(tendered)
        rental.deposit_currency = payment_currency
    if getattr(request, "exchange_rate", None) is not None or payment_currency == "KHR":
        rental.exchange_rate = rate


class RentalService:
    def __init__(self, session: AsyncSession, actor: User | None = None) -> None:
        self.session = session
        self.actor = actor
        self.rentals = RentalRepository(session)
        self.motorcycles = MotorcycleRepository(session)
        self.customers = CustomerRepository(session)
        self.payments = PaymentRepository(session)
        self.charges = ChargeRepository(session)
        self.expenses = ExpenseRepository(session)
        self.audit = AuditRepository(session)
        self.sequences = DocumentSequenceRepository(session)

    async def _line_motorcycle_ids(self, rental: Rental) -> list[str]:
        result = await self.session.execute(
            select(RentalLine.motorcycle_id)
            .where(RentalLine.rental_id == rental.id)
            .order_by(RentalLine.sort_order)
        )
        ids = [row[0] for row in result.all()]
        if ids:
            return list(dict.fromkeys(ids))
        return [rental.motorcycle_id]

    async def _replace_rental_lines(self, rental: Rental, built: list[dict]) -> None:
        await self.session.execute(delete(RentalLine).where(RentalLine.rental_id == rental.id))
        await self.session.flush()
        for index, row in enumerate(built):
            line_id = await self._next_entity_id("rl", RentalLine)
            self.session.add(
                RentalLine(
                    id=line_id,
                    rental_id=rental.id,
                    motorcycle_id=row["moto"].id,
                    sort_order=index,
                    motorcycle=row["moto"].model,
                    plate=row["moto"].plate,
                    start_date=row["start_date"],
                    due_date=row["due_date"],
                    duration_days=row["days"],
                    rate_type=rate_type_for(row["days"], row["start_date"], row["due_date"]),
                    rate_amount=money(row["charge"]),
                    deposit=money(row["deposit"]),
                    discount=money(row["discount"]),
                    rental_charge=money(row["rental_charge"]),
                    note=row["note"],
                )
            )
        self.session.expire(rental, ["lines"])

    async def create_rentals(self, request) -> list[Rental]:
        now = datetime.now(timezone.utc)
        customer = await self.customers.get(request.customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        if customer.status != "Active":
            raise ValidationError("Customer must be Active to create a rental")

        moto_ids = [line.motorcycle_id for line in request.lines]
        if len(set(moto_ids)) != len(moto_ids):
            raise ValidationError("Duplicate motorcycles in rental lines")
        motorcycles = await _get_motorcycles_locked(self.session, moto_ids)
        moto_map = {m.id: m for m in motorcycles}
        not_available = [m.id for m in motorcycles if m.status != "Available"]
        if not_available:
            raise ConflictError(f"Motorcycles not Available: {', '.join(not_available)}")

        priced = _apply_line_discounts(
            _price_line_rows(moto_map, request.lines),
            Decimal("0"),
        )
        deposit = money(sum((money(getattr(line, "deposit", 0)) for line in request.lines), Decimal("0")))
        built = _with_header_deposit(priced, deposit)
        initial_payment_method = normalize_payment_method(request.payment_method or "Cash")

        year = now.year
        rental_no = await self.sequences.next_value("RENTAL", f"RNT-{year}-", 6, year)
        rental_id = await self._next_entity_id("rt", Rental)
        rental = Rental(
            id=rental_id,
            rental_no=rental_no,
            currency=normalize_payment_currency(request.currency),
            late_fee=Decimal("0.00"),
            additional_charges=Decimal("0.00"),
            payment_method=initial_payment_method,
            note=request.note or next((row["note"] for row in built if row["note"]), None),
            created_by=_actor_label(self.actor),
            created_by_user_id=self.actor.id if self.actor else None,
            status="Active",
        )
        _apply_rental_header(rental, customer, built, deposit)
        _apply_deposit_tendered(rental, request)
        # Customers settle the full rental price up front; outstanding stays 0.
        initial_paid = money(rental.total_due)
        self.session.add(rental)
        await self.session.flush()
        await self._replace_rental_lines(rental, built)

        if initial_paid > 0:
            payment_no = await self.sequences.next_value("PAYMENT", "RNP-", 6, None)
            payment_id = await self._next_entity_id("rp", RentalPayment)
            self.session.add(
                RentalPayment(
                    id=payment_id,
                    payment_no=payment_no,
                    rental_id=rental.id,
                    amount=initial_paid,
                    currency=rental.currency,
                    tendered_amount=initial_paid,
                    exchange_rate=Decimal("1.0000"),
                    payment_method=initial_payment_method,
                    paid_at=now,
                    note="Full payment",
                    created_by=_actor_label(self.actor),
                    created_by_user_id=self.actor.id if self.actor else None,
                )
            )

        for moto in motorcycles:
            moto.status = "Progressing"

        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="rental_created",
                entity_type="rental",
                entity_id=rental.id,
                entity_label=rental.rental_no,
                details={
                    "customer": rental.customer,
                    "motorcycle": rental.motorcycle,
                    "motorcycles": len(built),
                    "totalDue": float(rental.total_due),
                },
            )
        )
        self.session.add(
            _outbox(
                "rental_created",
                {
                    "rental_no": rental.rental_no,
                    "customer": rental.customer,
                    "motorcycle": rental.motorcycle,
                    "plate": rental.plate,
                    "amount": float(rental.total_due),
                    "paid": float(initial_paid),
                    "currency": rental.currency,
                    "status": rental.status,
                    "start_date": rental.start_date.isoformat(),
                    "due_date": rental.due_date.isoformat(),
                    "actor": _actor_label(self.actor),
                    "occurred_at": now.isoformat(),
                },
            )
        )
        await self.session.commit()
        loaded = await self.rentals.get(rental.id)
        return [await self._reload_with_payments(loaded or rental)]

    async def update_rental(self, rental_id: str, request) -> Rental:
        rental = await self.rentals.for_update(rental_id)
        if rental is None:
            raise NotFoundError("Rental not found")
        if rental.status not in ("Active", "Overdue"):
            raise ConflictError(f"Rental in status {rental.status} cannot be edited")

        customer_id = request.customer_id or rental.customer_id
        customer = await self.customers.get(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        if customer.status != "Active":
            raise ValidationError("Customer must be Active to update a rental")

        previous_due = rental.due_date
        previous_ids = await self._line_motorcycle_ids(rental)
        line_inputs = list(request.lines or [])
        if not line_inputs:
            existing_result = await self.session.execute(
                select(RentalLine).where(RentalLine.rental_id == rental.id).order_by(RentalLine.sort_order)
            )
            existing = list(existing_result.scalars().all())
            if not existing:
                existing = [
                    SimpleNamespace(
                        motorcycle_id=rental.motorcycle_id,
                        start_date=rental.start_date,
                        due_date=rental.due_date,
                        deposit=rental.deposit,
                        discount=rental.discount,
                        note=rental.note,
                    )
                ]
            if request.motorcycle_id and request.motorcycle_id != rental.motorcycle_id and len(existing) > 1:
                raise ValidationError("Send lines to change motorcycles on a multi-bike rental")
            start_date = request.start_date or rental.start_date
            due_date = request.due_date or rental.due_date
            single_discount = request.discount if request.discount is not None and len(existing) == 1 else None
            line_inputs = [
                SimpleNamespace(
                    motorcycle_id=(request.motorcycle_id or line.motorcycle_id) if index == 0 else line.motorcycle_id,
                    start_date=start_date,
                    due_date=due_date,
                    deposit=line.deposit,
                    discount=single_discount if single_discount is not None else line.discount,
                    note=line.note,
                )
                for index, line in enumerate(existing)
            ]

        moto_ids = [line.motorcycle_id for line in line_inputs]
        if len(set(moto_ids)) != len(moto_ids):
            raise ValidationError("Duplicate motorcycles in rental lines")

        lock_ids = list(dict.fromkeys([*previous_ids, *moto_ids]))
        motorcycles = await _get_motorcycles_locked(self.session, lock_ids)
        moto_map = {m.id: m for m in motorcycles}
        added_ids = set(moto_ids) - set(previous_ids)
        not_available = [moto_id for moto_id in added_ids if moto_map[moto_id].status != "Available"]
        if not_available:
            raise ConflictError(f"Motorcycles not Available: {', '.join(not_available)}")

        doc_discount = Decimal("0")
        priced = _apply_line_discounts(_price_line_rows(moto_map, line_inputs), doc_discount)
        if request.deposit is not None:
            deposit = money(request.deposit)
        else:
            deposit = money(sum((money(getattr(line, "deposit", 0)) for line in line_inputs), Decimal("0")))
        built = _with_header_deposit(priced, deposit)
        if getattr(request, "currency", None) is not None:
            rental.currency = normalize_payment_currency(request.currency)
        _apply_rental_header(rental, customer, built, deposit)
        _apply_deposit_tendered(rental, request)
        await self._replace_rental_lines(rental, built)

        for moto_id in set(previous_ids) - set(moto_ids):
            moto_map[moto_id].status = "Available"
        for moto_id in added_ids:
            moto_map[moto_id].status = "Progressing"

        if rental.due_date != previous_due:
            rental.deadline_alerted_at = None
        if request.note is not None:
            rental.note = request.note
        if rental.status == "Overdue" and rental.due_date > datetime.now(timezone.utc):
            rental.status = "Active"

        if request.paid_amount is not None:
            paid_credit, paid_tendered, paid_rate, paid_currency = resolve_payment_money(
                rental_currency=rental.currency,
                payment_currency=getattr(request, "payment_currency", None) or rental.currency,
                amount=request.paid_amount,
                tendered_amount=getattr(request, "tendered_amount", None),
                exchange_rate=getattr(request, "exchange_rate", None),
            )
            await self._sync_rental_paid(
                rental,
                paid_credit,
                request.payment_method,
                currency=paid_currency,
                exchange_rate=paid_rate,
                tendered_amount=paid_tendered,
            )
        elif request.payment_method is not None:
            rental.payment_method = normalize_payment_method(request.payment_method)
        else:
            current_paid = money(sum((row.amount for row in rental.payments), Decimal("0")))
            if current_paid > money(rental.total_due):
                await self._sync_rental_paid(rental, rental.total_due, rental.payment_method)

        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="rental_updated",
                entity_type="rental",
                entity_id=rental.id,
                entity_label=rental.rental_no,
                details={
                    "customer": rental.customer,
                    "motorcycle": rental.motorcycle,
                    "totalDue": float(rental.total_due),
                    "paid": float(rental.paid),
                },
            )
        )
        await self.session.commit()
        loaded = await self.rentals.get(rental.id)
        return await self._reload_with_payments(loaded or rental)

    async def close_rental(self, rental_id: str, request) -> Rental:
        rental = await self.rentals.for_update(rental_id)
        if rental is None:
            raise NotFoundError("Rental not found")
        if rental.status == "Completed":
            raise ConflictError("Rental is already completed")
        if rental.status == "Cancelled":
            raise ConflictError("Rental is cancelled and cannot be completed")

        motorcycles = await _get_motorcycles_locked(self.session, await self._line_motorcycle_ids(rental))

        now = datetime.now(timezone.utc)
        return_date = request.return_date or now
        new_charges_total = Decimal("0.00")
        for charge_input in request.charges or []:
            charge_type = normalize_charge_type(charge_input.charge_type)
            amount = money(charge_input.amount)
            charge_no = await self.sequences.next_value("CHARGE", "RNC-", 6, None)
            charge_id = await self._next_entity_id("rg", RentalCharge)
            self.session.add(
                RentalCharge(
                    id=charge_id,
                    charge_no=charge_no,
                    rental_id=rental.id,
                    charge_type=charge_type,
                    description=charge_input.description,
                    amount=amount,
                    currency=rental.currency,
                    charge_to_customer=charge_input.charge_to_customer,
                    created_by=_actor_label(self.actor),
                    created_by_user_id=self.actor.id if self.actor else None,
                )
            )
            if charge_input.charge_to_customer == "Yes":
                new_charges_total += amount

        late_fee = money(request.late_fee)
        final_payment_amount = Decimal("0.00")
        if request.final_payment:
            final_credit, final_tendered, final_rate, final_currency = resolve_payment_money(
                rental_currency=rental.currency,
                payment_currency=getattr(request.final_payment, "currency", None) or rental.currency,
                amount=request.final_payment.amount,
                tendered_amount=getattr(request.final_payment, "tendered_amount", None),
                exchange_rate=getattr(request.final_payment, "exchange_rate", None),
            )
            final_payment_amount = final_credit
            if final_payment_amount > 0:
                payment_no = await self.sequences.next_value("PAYMENT", "RNP-", 6, None)
                payment_id = await self._next_entity_id("rp", RentalPayment)
                paid_at = request.final_payment.paid_at or now
                final_payment_method = normalize_payment_method(request.final_payment.payment_method)
                self.session.add(
                    RentalPayment(
                        id=payment_id,
                        payment_no=payment_no,
                        rental_id=rental.id,
                        amount=final_payment_amount,
                        currency=final_currency,
                        tendered_amount=final_tendered,
                        exchange_rate=final_rate,
                        payment_method=final_payment_method,
                        paid_at=paid_at,
                        reference=request.final_payment.reference,
                        note=request.final_payment.note,
                        created_by=_actor_label(self.actor),
                        created_by_user_id=self.actor.id if self.actor else None,
                    )
                )

        existing_charges = sum(
            (c.amount for c in rental.charges if c.charge_to_customer == "Yes"), Decimal("0")
        )
        rental.late_fee = money(rental.late_fee + late_fee)
        rental.additional_charges = money(existing_charges + new_charges_total)
        rental.return_date = return_date
        rental.condition = request.condition
        rental.return_note = request.return_note
        rental.duration_days = max(duration_days(rental.start_date, return_date), 1)
        rental.total_due = money(rental.rental_charge + rental.late_fee + rental.additional_charges)
        # The deposit is security held separately from rental payment.  Only
        # return charges/fines may consume it; refund every unused amount.
        security_charges = money(rental.late_fee + rental.additional_charges)
        deposit_settlement = security_deposit_settlement(rental.deposit, security_charges)
        deposit_applied = deposit_settlement.applied_to_charges
        deposit_refund = deposit_settlement.refund_to_customer
        rental.deposit_refund = deposit_refund
        payments_sum = money(sum((p.amount for p in rental.payments), Decimal("0")) + final_payment_amount)
        completed_outstanding = money(
            max(rental.total_due - deposit_applied - payments_sum, Decimal("0"))
        )
        rental.status = "Completed"
        rental.completed_at = now

        if motorcycles:
            target = request.motorcycle_status or "Available"
            if target not in ("Available", "Maintenance"):
                raise ValidationError("Return motorcycle status must be Available or Maintenance")
            for moto in motorcycles:
                moto.status = target

        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="rental_completed",
                entity_type="rental",
                entity_id=rental.id,
                entity_label=rental.rental_no,
                details={"totalDue": float(rental.total_due), "paid": float(payments_sum), "outstanding": float(completed_outstanding), "depositRefund": float(deposit_refund)},
            )
        )
        self.session.add(
            _outbox(
                "rental_completed",
                {
                    "rental_no": rental.rental_no,
                    "customer": rental.customer,
                    "motorcycle": rental.motorcycle,
                    "plate": rental.plate,
                    "amount": float(rental.total_due),
                    "paid": float(payments_sum),
                    "outstanding": float(completed_outstanding),
                    "deposit_refund": float(deposit_refund),
                    "currency": rental.currency,
                    "status": "Completed",
                    "start_date": rental.start_date.isoformat(),
                    "due_date": rental.due_date.isoformat(),
                    "return_date": return_date.isoformat(),
                    "condition": rental.condition,
                    "actor": _actor_label(self.actor),
                    "occurred_at": now.isoformat(),
                },
            )
        )
        await self.session.commit()
        loaded = await self.rentals.get(rental.id)
        return await self._reload_with_payments(loaded or rental)

    async def cancel_rental(self, rental_id: str, reason: str | None) -> Rental:
        rental = await self.rentals.for_update(rental_id)
        if rental is None:
            raise NotFoundError("Rental not found")
        if rental.status not in ("Active", "Overdue"):
            raise ConflictError(f"Rental in status {rental.status} cannot be cancelled")

        motorcycles = await _get_motorcycles_locked(self.session, await self._line_motorcycle_ids(rental))
        now = datetime.now(timezone.utc)
        rental.status = "Cancelled"
        rental.cancelled_at = now
        rental.cancel_reason = reason
        for moto in motorcycles:
            moto.status = "Available"

        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="rental_cancelled",
                entity_type="rental",
                entity_id=rental.id,
                entity_label=rental.rental_no,
                details={"reason": reason},
            )
        )
        self.session.add(
            _outbox(
                "rental_cancelled",
                {
                    "rental_no": rental.rental_no,
                    "customer": rental.customer,
                    "motorcycle": rental.motorcycle,
                    "currency": rental.currency,
                    "status": "Cancelled",
                    "start_date": rental.start_date.isoformat(),
                    "due_date": rental.due_date.isoformat(),
                    "reason": reason,
                    "actor": _actor_label(self.actor),
                    "occurred_at": now.isoformat(),
                },
            )
        )
        await self.session.commit()
        loaded = await self.rentals.get(rental.id)
        return loaded if loaded is not None else rental

    async def detect_overdue(self, now: datetime | None = None, notify: bool = True) -> list[str]:
        now = now or datetime.now(timezone.utc)
        stale = await self.session.execute(
            select(Rental).where(Rental.status == "Active", Rental.due_date < now).with_for_update(skip_locked=True)
        )
        rentals = list(stale.scalars().all())
        overdue_ids: list[str] = []
        for rental in rentals:
            rental.status = "Overdue"
            overdue_ids.append(rental.id)
            await self.audit.add(
                AuditLog(
                    action="rental_overdue",
                    entity_type="rental",
                    entity_id=rental.id,
                    entity_label=rental.rental_no,
                    details={"due_date": rental.due_date.isoformat()},
                )
            )
            if notify:
                self.session.add(
                    _outbox(
                        "rental_overdue",
                        {
                            "rental_no": rental.rental_no,
                            "customer": rental.customer,
                            "motorcycle": rental.motorcycle,
                            "plate": rental.plate,
                            "currency": rental.currency,
                            "outstanding": float(rental.outstanding),
                            "due_date": rental.due_date.isoformat(),
                            "status": "Overdue",
                            "start_date": rental.start_date.isoformat(),
                            "occurred_at": now.isoformat(),
                        },
                    )
                )
        if rentals:
            await self.session.commit()
        return overdue_ids

    async def mark_overdue_notified(self, rental_id: str) -> None:
        rental = await self.rentals.get(rental_id)
        if rental:
            rental.overdue_notified_at = datetime.now(timezone.utc)
            await self.session.commit()

    async def record_payment(self, request) -> tuple[RentalPayment, Rental]:
        rental = await self.rentals.for_update(request.rental_id)
        if rental is None:
            raise NotFoundError("Rental not found")
        if rental.status in ("Completed", "Cancelled"):
            raise ConflictError(f"Cannot record payment on a {rental.status.lower()} rental")
        now = datetime.now(timezone.utc)
        payment_no = await self.sequences.next_value("PAYMENT", "RNP-", 6, None)
        payment_id = await self._next_entity_id("rp", RentalPayment)
        payment_method = normalize_payment_method(request.payment_method)
        credited, tendered, rate, payment_currency = resolve_payment_money(
            rental_currency=rental.currency,
            payment_currency=getattr(request, "currency", None) or rental.currency,
            amount=request.amount,
            tendered_amount=getattr(request, "tendered_amount", None),
            exchange_rate=getattr(request, "exchange_rate", None),
        )
        payment = RentalPayment(
            id=payment_id,
            payment_no=payment_no,
            rental_id=rental.id,
            amount=credited,
            currency=payment_currency,
            tendered_amount=tendered,
            exchange_rate=rate,
            payment_method=payment_method,
            paid_at=request.paid_at or now,
            reference=request.reference,
            note=request.note,
            created_by=_actor_label(self.actor),
            created_by_user_id=self.actor.id if self.actor else None,
        )
        self.session.add(payment)
        payment_total = money(sum((p.amount for p in rental.payments), Decimal("0")) + payment.amount)
        payment_outstanding = money(max(rental.total_due - payment_total, Decimal("0")))
        rental.payment_method = payment_method
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="payment_recorded",
                entity_type="payment",
                entity_id=payment.id,
                entity_label=payment.payment_no,
                details={"rentalNo": rental.rental_no, "amount": float(payment.amount)},
            )
        )
        self.session.add(
            _outbox(
                "payment_recorded",
                {
                    "rental_no": rental.rental_no,
                    "customer": rental.customer,
                    "payment_no": payment.payment_no,
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "payment_method": payment.payment_method,
                    "motorcycle": rental.motorcycle,
                    "plate": rental.plate,
                    "paid": float(payment_total),
                    "outstanding": float(payment_outstanding),
                    "start_date": rental.start_date.isoformat(),
                    "due_date": rental.due_date.isoformat(),
                    "status": rental.status,
                    "actor": _actor_label(self.actor),
                    "occurred_at": payment.paid_at.isoformat(),
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(payment)
        await self.session.refresh(rental, ["payments"])
        return payment, rental

    async def record_charge(self, request) -> tuple[RentalCharge, Rental]:
        rental = await self.rentals.for_update(request.rental_id)
        if rental is None:
            raise NotFoundError("Rental not found")
        charge_type = normalize_charge_type(request.charge_type)
        now = datetime.now(timezone.utc)
        charge_no = await self.sequences.next_value("CHARGE", "RNC-", 6, None)
        charge_id = await self._next_entity_id("rg", RentalCharge)
        charge = RentalCharge(
            id=charge_id,
            charge_no=charge_no,
            rental_id=rental.id,
            charge_type=charge_type,
            description=request.description,
            amount=money(request.amount),
            currency=rental.currency,
            charge_to_customer=request.charge_to_customer,
            created_by=_actor_label(self.actor),
            created_by_user_id=self.actor.id if self.actor else None,
        )
        self.session.add(charge)
        if charge.charge_to_customer == "Yes" and rental.status != "Completed":
            rental.additional_charges = money(rental.additional_charges + charge.amount)
            rental.total_due = money(rental.rental_charge + rental.late_fee + rental.additional_charges)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="charge_recorded",
                entity_type="charge",
                entity_id=charge.id,
                entity_label=charge.charge_no,
                details={"rentalNo": rental.rental_no, "amount": float(charge.amount)},
            )
        )
        self.session.add(
            _outbox(
                "charge_recorded",
                {
                    "rental_no": rental.rental_no,
                    "customer": rental.customer,
                    "charge_no": charge.charge_no,
                    "charge_type": charge.charge_type,
                    "description": charge.description,
                    "amount": float(charge.amount),
                    "currency": charge.currency,
                    "motorcycle": rental.motorcycle,
                    "plate": rental.plate,
                    "outstanding": float(rental.outstanding),
                    "start_date": rental.start_date.isoformat(),
                    "due_date": rental.due_date.isoformat(),
                    "status": rental.status,
                    "actor": _actor_label(self.actor),
                    "occurred_at": now.isoformat(),
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(charge)
        await self.session.refresh(rental)
        return charge, rental

    async def record_expense(self, request) -> RentalExpense:
        expense_type = normalize_expense_type(request.expense_type)
        expense_no = await self.sequences.next_value("EXPENSE", "RNX-", 6, None)
        expense_id = await self._next_entity_id("rx", RentalExpense)
        expense = RentalExpense(
            id=expense_id,
            expense_no=expense_no,
            date=request.date,
            expense_type=expense_type,
            description=request.description,
            amount=money(request.amount),
            currency=request.currency,
            created_by=_actor_label(self.actor),
            created_by_user_id=self.actor.id if self.actor else None,
        )
        self.session.add(expense)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="expense_recorded",
                entity_type="expense",
                entity_id=expense.id,
                entity_label=expense.expense_no,
                details={"amount": float(expense.amount), "expenseType": expense.expense_type},
            )
        )
        self.session.add(
            _outbox(
                "expense_recorded",
                {
                    "expense_no": expense.expense_no,
                    "expense_type": expense.expense_type,
                    "description": expense.description,
                    "amount": float(expense.amount),
                    "currency": expense.currency,
                    "actor": _actor_label(self.actor),
                    "occurred_at": expense.date.isoformat(),
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(expense)
        return expense

    async def _sync_rental_paid(
        self,
        rental: Rental,
        paid_amount,
        payment_method: str | None = None,
        *,
        currency: str | None = None,
        exchange_rate=None,
        tendered_amount=None,
    ) -> None:
        """Set rental.paid to the requested total and keep rental_payments in sync."""
        now = datetime.now(timezone.utc)
        cap = money(rental.total_due)
        target = min(max(money(paid_amount), Decimal("0")), cap)
        method = normalize_payment_method(payment_method or rental.payment_method or "Cash")
        pay_currency = currency or rental.currency
        pay_rate = normalize_exchange_rate(exchange_rate if exchange_rate is not None else Decimal("1"))
        pay_tendered = money(tendered_amount) if tendered_amount is not None else target

        payments = sorted(
            list(rental.payments or []),
            key=lambda row: (row.paid_at or now, row.id),
        )
        current = money(sum((row.amount for row in payments), Decimal("0")))

        def _apply_fx(payment: RentalPayment, amount) -> None:
            credited = money(amount)
            payment.amount = credited
            payment.currency = pay_currency
            payment.exchange_rate = pay_rate
            payment.tendered_amount = (
                pay_tendered
                if credited == target
                else money((pay_tendered / target) * credited if target > 0 else 0)
            )
            payment.payment_method = method

        if target > current:
            if len(payments) == 1:
                _apply_fx(payments[0], target)
            else:
                amount = target if not payments else money(target - current)
                tendered = pay_tendered if not payments else (
                    money((pay_tendered / target) * amount) if target > 0 else amount
                )
                payment_no = await self.sequences.next_value("PAYMENT", "RNP-", 6, None)
                payment_id = await self._next_entity_id("rp", RentalPayment)
                self.session.add(
                    RentalPayment(
                        id=payment_id,
                        payment_no=payment_no,
                        rental_id=rental.id,
                        amount=amount,
                        currency=pay_currency,
                        tendered_amount=tendered,
                        exchange_rate=pay_rate,
                        payment_method=method,
                        paid_at=now,
                        note="Payment update" if payments else "Initial payment",
                        created_by=_actor_label(self.actor),
                        created_by_user_id=self.actor.id if self.actor else None,
                    )
                )
        elif target < current:
            remaining_cut = money(current - target)
            for payment in reversed(payments):
                if remaining_cut <= 0:
                    break
                if payment.amount <= remaining_cut:
                    remaining_cut = money(remaining_cut - payment.amount)
                    await self.session.delete(payment)
                else:
                    remaining = money(payment.amount - remaining_cut)
                    _apply_fx(payment, remaining)
                    remaining_cut = Decimal("0")
        elif payments and (
            payment_method is not None
            or currency is not None
            or tendered_amount is not None
            or exchange_rate is not None
        ):
            if len(payments) == 1:
                _apply_fx(payments[0], target)
            else:
                latest = payments[-1]
                if payment_method is not None:
                    latest.payment_method = method
                if currency is not None or tendered_amount is not None or exchange_rate is not None:
                    latest.currency = pay_currency
                    latest.exchange_rate = pay_rate
                    latest.tendered_amount = pay_tendered

        if target > 0 or payment_method is not None:
            rental.payment_method = method
        await self.session.flush()
        await self.session.refresh(rental, ["payments"])

    async def _reload_with_payments(self, rental: Rental) -> Rental:
        """Reload payments so derived paid/outstanding reflect newly written rows."""
        await self.session.refresh(rental, ["payments"])
        return rental

    async def _next_entity_id(self, prefix: str, model_cls) -> str:
        return await self.sequences.next_value(f"{prefix.upper()}_ID", prefix, 3, None)
