from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.money import money
from app.models.base import TimestampMixin
from app.models.customer import RentalCustomer


class Rental(Base, TimestampMixin):
    __tablename__ = "rentals"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    rental_no: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("rental_customers.id"), nullable=False, index=True)
    motorcycle_id: Mapped[str] = mapped_column(ForeignKey("motorcycles.id"), nullable=False, index=True)

    customer: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    motorcycle: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    plate: Mapped[str | None] = mapped_column(String(200), nullable=True)

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    rate_type: Mapped[str] = mapped_column(String(20), default="Daily", nullable=False)
    rate_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    deposit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    deposit_tendered_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    deposit_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    rental_charge: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    late_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    additional_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    payment_method: Mapped[str | None] = mapped_column(String(40), nullable=True)

    return_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(40), nullable=True)
    return_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="Active", nullable=False, index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overdue_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payments: Mapped[list["RentalPayment"]] = relationship(
        back_populates="rental", lazy="selectin", cascade="all, delete-orphan"
    )
    charges: Mapped[list["RentalCharge"]] = relationship(
        back_populates="rental", lazy="selectin", cascade="all, delete-orphan"
    )
    lines: Mapped[list["RentalLine"]] = relationship(
        back_populates="rental",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="RentalLine.sort_order",
    )
    customer_record: Mapped[RentalCustomer] = relationship(
        "RentalCustomer",
        lazy="selectin",
        viewonly=True,
    )

    @property
    def identity_number(self) -> str | None:
        """Customer identity number, denormalized into the API response for invoices."""
        customer = self.customer_record
        return customer.identity_number if customer is not None else None

    @property
    def paid(self) -> Decimal:
        """Total received, derived from recorded payments (not stored)."""
        return money(sum((payment.amount for payment in self.payments), Decimal("0")))

    @property
    def outstanding(self) -> Decimal:
        """Remaining after deposit and recorded payments (not stored)."""
        due = max(money(self.total_due), Decimal("0"))
        deposit = max(money(self.deposit), Decimal("0"))
        after_deposit = max(due - deposit, Decimal("0"))
        return money(max(after_deposit - self.paid, Decimal("0")))

    @property
    def payment_status(self) -> str | None:
        if not self.payments:
            return None
        return "Paid" if self.outstanding <= 0 else "Partial"

    @property
    def tax(self) -> Decimal:
        return Decimal("0.00")

    @property
    def tax_percent(self) -> Decimal:
        return Decimal("0.00")


class RentalLine(Base, TimestampMixin):
    __tablename__ = "rental_lines"
    __table_args__ = (UniqueConstraint("rental_id", "motorcycle_id", name="uq_rental_lines_rental_motorcycle"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    rental_id: Mapped[str] = mapped_column(ForeignKey("rentals.id", ondelete="CASCADE"), nullable=False, index=True)
    motorcycle_id: Mapped[str] = mapped_column(ForeignKey("motorcycles.id"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    motorcycle: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    plate: Mapped[str | None] = mapped_column(String(60), nullable=True)

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    rate_type: Mapped[str] = mapped_column(String(20), default="Daily", nullable=False)
    rate_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    deposit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    rental_charge: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    rental: Mapped[Rental] = relationship(back_populates="lines")


class RentalPayment(Base, TimestampMixin):
    __tablename__ = "rental_payments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    payment_no: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    rental_id: Mapped[str] = mapped_column(ForeignKey("rentals.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    tendered_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("1"), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(40), default="Cash", nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rental: Mapped[Rental] = relationship(back_populates="payments")


class RentalCharge(Base, TimestampMixin):
    __tablename__ = "rental_charges"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    charge_no: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    rental_id: Mapped[str] = mapped_column(ForeignKey("rentals.id"), nullable=False, index=True)
    charge_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    charge_to_customer: Mapped[str] = mapped_column(String(10), default="Yes", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rental: Mapped[Rental] = relationship(back_populates="charges")


class RentalExpense(Base, TimestampMixin):
    __tablename__ = "rental_expenses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    expense_no: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expense_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


