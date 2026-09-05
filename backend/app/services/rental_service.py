from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.money import allocate_payment, distribute_document_discount, money
from app.core.pricing import (
    duration_days,
    line_charge,
    rate_type_for,
    resolve_motorcycle_rates,
)
from app.models import (
    AuditLog,
    Motorcycle,
    OutboxEvent,
    Rental,
    RentalCharge,
    RentalExpense,
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

        line_charges: list[Decimal] = []
        line_infos: list[dict] = []
        for line in request.lines:
            moto = moto_map[line.motorcycle_id]
            if line.due_date <= line.start_date:
                raise ValidationError("Due date must be after start date")
            days = duration_days(line.start_date, line.due_date)
            rates = resolve_motorcycle_rates(moto.daily_rate, moto.three_day_rate, moto.weekly_rate, moto.monthly_rate)
            charge = line_charge(rates, days, line.start_date, line.due_date)
            if charge <= 0:
                raise ValidationError(f"Cannot compute charge for motorcycle {moto.code}")
            line_charges.append(charge)
            line_infos.append({"line": line, "moto": moto, "days": days, "charge": charge})

        doc_discount = max(money(request.discount), Decimal("0"))
        discount_shares = distribute_document_discount(line_charges, doc_discount)
        paid_shares = allocate_payment(line_charges, request.paid_amount)
        initial_payment_method = (
            normalize_payment_method(request.payment_method or "Cash")
            if money(request.paid_amount) > 0
            else None
        )

        rentals: list[Rental] = []
        year = now.year
        for index, info in enumerate(line_infos):
            line = info["line"]
            moto = info["moto"]
            days = info["days"]
            charge = info["charge"]
            discount = money(min(max(money(line.discount), Decimal("0")) + discount_shares[index], charge))
            rental_charge = money(charge - discount)
            tax = money(rental_charge * request.tax_percent / Decimal("100"))
            total_due = money(rental_charge + tax)
            paid = paid_shares[index]
            outstanding = money(total_due - paid)

            rental_no = await self.sequences.next_value("RENTAL", f"RNT-{year}-", 6, year)
            rental_id = await self._next_entity_id("rt", Rental)
            rental = Rental(
                id=rental_id,
                rental_no=rental_no,
                customer_id=customer.id,
                motorcycle_id=moto.id,
                customer=customer.full_name,
                phone=customer.phone,
                motorcycle=moto.model,
                plate=moto.plate,
                start_date=line.start_date,
                due_date=line.due_date,
                duration_days=days,
                rate_type=rate_type_for(days, line.start_date, line.due_date),
                rate_amount=money(charge),
                deposit=money(line.deposit),
                discount=discount,
                tax_percent=money(request.tax_percent),
                tax=tax,
                currency=request.currency,
                rental_charge=rental_charge,
                late_fee=Decimal("0.00"),
                additional_charges=Decimal("0.00"),
                total_due=total_due,
                paid=paid,
                outstanding=outstanding,
                payment_method=initial_payment_method,
                payment_status=None,
                note=line.note or request.note,
                created_by=_actor_label(self.actor),
                created_by_user_id=self.actor.id if self.actor else None,
                status="Active",
            )
            rentals.append(rental)
            self.session.add(rental)

            if paid > 0:
                payment_no = await self.sequences.next_value("PAYMENT", "RNP-", 6, None)
                payment_id = await self._next_entity_id("rp", RentalPayment)
                self.session.add(
                    RentalPayment(
                        id=payment_id,
                        payment_no=payment_no,
                        rental_id=rental.id,
                        amount=paid,
                        currency=request.currency,
                        payment_method=initial_payment_method or "Cash",
                        paid_at=now,
                        note="Initial payment",
                        created_by=_actor_label(self.actor),
                        created_by_user_id=self.actor.id if self.actor else None,
                    )
                )

        for moto in motorcycles:
            moto.status = "Progressing"

        for index, rental in enumerate(rentals):
            await self.audit.add(
                AuditLog(
                    user_id=self.actor.id if self.actor else None,
                    user_name=_actor_label(self.actor),
                    action="rental_created",
                    entity_type="rental",
                    entity_id=rental.id,
                    entity_label=rental.rental_no,
                    details={"customer": rental.customer, "motorcycle": rental.motorcycle, "totalDue": float(rental.total_due)},
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
                        "paid": float(rental.paid),
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
        for rental in rentals:
            await self.session.refresh(rental)
        return rentals

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

        motorcycle_id = request.motorcycle_id or rental.motorcycle_id
        start_date = request.start_date or rental.start_date
        due_date = request.due_date or rental.due_date
        if due_date <= start_date:
            raise ValidationError("Due date must be after start date")

        old_moto = None
        if motorcycle_id != rental.motorcycle_id:
            motorcycles = await _get_motorcycles_locked(self.session, [rental.motorcycle_id, motorcycle_id])
            moto_map = {m.id: m for m in motorcycles}
            old_moto = moto_map.get(rental.motorcycle_id)
            new_moto = moto_map.get(motorcycle_id)
            if new_moto is None:
                raise NotFoundError("Motorcycle not found")
            if new_moto.status != "Available":
                raise ConflictError(f"Motorcycle {new_moto.code} is not Available")
            if old_moto is not None:
                old_moto.status = "Available"
            new_moto.status = "Progressing"
            moto = new_moto
        else:
            result = await self.session.execute(
                select(Motorcycle).where(Motorcycle.id == motorcycle_id).with_for_update()
            )
            moto = result.scalar_one_or_none()
            if moto is None:
                raise NotFoundError("Motorcycle not found")

        days = duration_days(start_date, due_date)
        rates = resolve_motorcycle_rates(moto.daily_rate, moto.three_day_rate, moto.weekly_rate, moto.monthly_rate)
        charge = line_charge(rates, days, start_date, due_date)
        if charge <= 0:
            raise ValidationError(f"Cannot compute charge for motorcycle {moto.code}")

        discount = max(money(request.discount if request.discount is not None else rental.discount), Decimal("0"))
        rental_charge = money(charge - discount)
        tax_percent = money(request.tax_percent if request.tax_percent is not None else rental.tax_percent)
        tax = money(rental_charge * tax_percent / Decimal("100"))
        total_due = money(rental_charge + tax + rental.late_fee + rental.additional_charges)
        paid = money(rental.paid)
        outstanding = money(total_due - paid)

        rental.customer_id = customer.id
        rental.motorcycle_id = moto.id
        rental.customer = customer.full_name
        rental.phone = customer.phone
        rental.motorcycle = moto.model
        rental.plate = moto.plate
        due_date_changed = due_date != rental.due_date
        rental.start_date = start_date
        rental.due_date = due_date
        if due_date_changed:
            rental.deadline_alerted_at = None
        rental.duration_days = days
        rental.rate_type = rate_type_for(days, start_date, due_date)
        rental.rate_amount = money(charge)
        rental.deposit = money(request.deposit if request.deposit is not None else rental.deposit)
        rental.discount = discount
        rental.tax_percent = tax_percent
        rental.tax = tax
        rental.rental_charge = rental_charge
        rental.total_due = total_due
        rental.outstanding = outstanding
        if request.note is not None:
            rental.note = request.note
        if rental.status == "Overdue" and due_date > datetime.now(timezone.utc):
            rental.status = "Active"

        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="rental_updated",
                entity_type="rental",
                entity_id=rental.id,
                entity_label=rental.rental_no,
                details={"customer": rental.customer, "motorcycle": rental.motorcycle, "totalDue": float(rental.total_due)},
            )
        )
        await self.session.commit()
        await self.session.refresh(rental)
        return rental

    async def close_rental(self, rental_id: str, request) -> Rental:
        rental = await self.rentals.for_update(rental_id)
        if rental is None:
            raise NotFoundError("Rental not found")
        if rental.status == "Completed":
            raise ConflictError("Rental is already completed")
        if rental.status == "Cancelled":
            raise ConflictError("Rental is cancelled and cannot be completed")

        result = await self.session.execute(select(Motorcycle).where(Motorcycle.id == rental.motorcycle_id).with_for_update())
        moto = result.scalar_one_or_none()

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
        final_payment_amount = money(request.final_payment.amount) if request.final_payment else Decimal("0.00")
        if request.final_payment and final_payment_amount > 0:
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
                    currency=rental.currency,
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
        rental.total_due = money(rental.rental_charge + rental.tax + rental.late_fee + rental.additional_charges)
        payments_sum = sum((p.amount for p in rental.payments), Decimal("0")) + final_payment_amount
        rental.paid = money(payments_sum)
        rental.outstanding = money(max(rental.total_due - rental.paid, Decimal("0")))
        rental.payment_status = "Paid" if rental.outstanding <= 0 else "Partial"
        rental.status = "Completed"
        rental.completed_at = now

        if moto is not None:
            target = request.motorcycle_status or "Available"
            if target not in ("Available", "Maintenance"):
                raise ValidationError("Return motorcycle status must be Available or Maintenance")
            moto.status = target

        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=_actor_label(self.actor),
                action="rental_completed",
                entity_type="rental",
                entity_id=rental.id,
                entity_label=rental.rental_no,
                details={"totalDue": float(rental.total_due), "paid": float(rental.paid), "outstanding": float(rental.outstanding)},
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
                    "paid": float(rental.paid),
                    "outstanding": float(rental.outstanding),
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
        await self.session.refresh(rental)
        return rental

    async def cancel_rental(self, rental_id: str, reason: str | None) -> Rental:
        rental = await self.rentals.for_update(rental_id)
        if rental is None:
            raise NotFoundError("Rental not found")
        if rental.status not in ("Active", "Overdue"):
            raise ConflictError(f"Rental in status {rental.status} cannot be cancelled")

        result = await self.session.execute(select(Motorcycle).where(Motorcycle.id == rental.motorcycle_id).with_for_update())
        moto = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        rental.status = "Cancelled"
        rental.cancelled_at = now
        rental.cancel_reason = reason
        rental.outstanding = Decimal("0.00")
        if moto is not None:
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
        await self.session.refresh(rental)
        return rental

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
        payment = RentalPayment(
            id=payment_id,
            payment_no=payment_no,
            rental_id=rental.id,
            amount=money(request.amount),
            currency=rental.currency,
            payment_method=payment_method,
            paid_at=request.paid_at or now,
            reference=request.reference,
            note=request.note,
            created_by=_actor_label(self.actor),
            created_by_user_id=self.actor.id if self.actor else None,
        )
        self.session.add(payment)
        rental.paid = money(sum((p.amount for p in rental.payments), Decimal("0")) + payment.amount)
        rental.outstanding = money(max(rental.total_due - rental.paid, Decimal("0")))
        rental.payment_method = payment_method
        if rental.status == "Completed":
            rental.payment_status = "Paid" if rental.outstanding <= 0 else "Partial"
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
                    "paid": float(rental.paid),
                    "outstanding": float(rental.outstanding),
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
        await self.session.refresh(rental)
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
            rental.total_due = money(rental.rental_charge + rental.tax + rental.late_fee + rental.additional_charges)
            rental.outstanding = money(rental.total_due - rental.paid)
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

    async def _next_entity_id(self, prefix: str, model_cls) -> str:
        return await self.sequences.next_value(f"{prefix.upper()}_ID", prefix, 3, None)



