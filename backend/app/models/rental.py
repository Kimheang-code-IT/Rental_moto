from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


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
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    rental_charge: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    late_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    additional_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    outstanding: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    payment_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

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

    payments: Mapped[list["RentalPayment"]] = relationship(back_populates="rental", lazy="selectin")
    charges: Mapped[list["RentalCharge"]] = relationship(back_populates="rental", lazy="selectin")
    lines: Mapped[list["RentalLine"]] = relationship(
        back_populates="rental",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="RentalLine.sort_order",
    )


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


