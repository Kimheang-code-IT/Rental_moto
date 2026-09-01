from decimal import Decimal

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Motorcycle(Base, TimestampMixin):
    __tablename__ = "motorcycles"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str | None] = mapped_column(String(60), nullable=True)
    plate: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    chassis_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    engine_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    three_day_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    weekly_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    monthly_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    asset_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Available", nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


