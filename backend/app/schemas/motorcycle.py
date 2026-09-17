from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import CamelModel


class MotorcycleCreate(CamelModel):
    id: str | None = None
    code: str | None = None
    model: str = Field(min_length=1)
    brand: str | None = None
    year: int | None = Field(default=None, ge=1950, le=2100)
    color: str | None = None
    plate: str | None = None
    chassis_no: str | None = None
    engine_no: str | None = None
    daily_rate: Decimal = Field(default=Decimal("0"), ge=0)
    three_day_rate: Decimal = Field(default=Decimal("0"), ge=0)
    weekly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    asset_value: Decimal | None = Field(default=None, ge=0)
    currency: str = "USD"
    status: str = "Available"
    note: str | None = None


class MotorcycleUpdate(CamelModel):
    model: str | None = None
    brand: str | None = None
    year: int | None = None
    color: str | None = None
    plate: str | None = None
    chassis_no: str | None = None
    engine_no: str | None = None
    daily_rate: Decimal | None = None
    three_day_rate: Decimal | None = None
    weekly_rate: Decimal | None = None
    monthly_rate: Decimal | None = None
    asset_value: Decimal | None = None
    currency: str | None = None
    status: str | None = None
    note: str | None = None


class MotorcycleStatusUpdate(CamelModel):
    status: str


class MotorcycleResponse(CamelModel):
    id: str
    code: str
    model: str
    brand: str | None = None
    year: int | None = None
    color: str | None = None
    plate: str | None = None
    chassis_no: str | None = None
    engine_no: str | None = None
    daily_rate: Decimal
    three_day_rate: Decimal
    weekly_rate: Decimal
    monthly_rate: Decimal
    asset_value: Decimal | None = None
    currency: str
    status: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime
