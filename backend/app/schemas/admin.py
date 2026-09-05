from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from app.schemas.common import CamelModel


class UserCreate(CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid")

    username: str = Field(min_length=2)
    display_name: str = Field(min_length=1)
    email: str
    password: str = Field(min_length=6)
    role_id: int | None = None
    role: str | None = None
    status: str = "Active"
    avatar: str | None = None

    @model_validator(mode="after")
    def require_role(self):
        if self.role_id is None and not self.role:
            raise ValueError("roleId is required")
        return self


class UserUpdate(CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid")

    username: str | None = None
    display_name: str | None = None
    email: str | None = None
    password: str | None = None
    role_id: int | None = None
    role: str | None = None
    status: str | None = None
    avatar: str | None = None


class UserResponse(CamelModel):
    id: int
    username: str
    display_name: str
    email: str
    role: str | None = None
    role_id: int | None = None
    is_owner: bool = False
    status: str
    avatar: str | None = None
    effective_permissions: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    page_access: list[str] = Field(default_factory=list)
    telegram_linked: bool = False
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RoleCreate(CamelModel):
    name: str = Field(min_length=2)
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(CamelModel):
    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class RoleResponse(CamelModel):
    id: int
    name: str
    description: str
    permissions: list[str] = Field(default_factory=list)
    page_access: list[str] = Field(default_factory=list)
    is_system: bool = False
    user_count: int = 0
    created_at: datetime
    updated_at: datetime


class AuditLogResponse(CamelModel):
    id: str
    occurred_at: datetime
    user_id: int | None = None
    user_name: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    entity_label: str | None = None
    details: dict | None = None
    ip_address: str | None = None


class DocumentSequenceCreate(CamelModel):
    id: str | None = None
    document_type: str
    prefix: str = ""
    year: int | None = None
    padding_length: int = 6
    last_value: int = 0
    status: str = "ACTIVE"
    note: str | None = None


class DocumentSequenceUpdate(CamelModel):
    document_type: str | None = None
    prefix: str | None = None
    year: int | None = None
    padding_length: int | None = None
    last_value: int | None = None
    status: str | None = None
    note: str | None = None


class DocumentSequenceResponse(CamelModel):
    id: str
    document_type: str
    prefix: str
    year: int | None = None
    padding_length: int
    last_value: int
    status: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class DashboardResponse(CamelModel):
    motorcycle_status: dict[str, int] = {}
    rentals_active: int = 0
    rentals_overdue: int = 0
    rentals_completed: int = 0
    income: Decimal = Decimal("0")
    expense: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")
    outstanding: Decimal = Decimal("0")
    rentals_by_day: list[dict] = []
    start_date: str | None = None
    end_date: str | None = None


class FinanceSummaryResponse(CamelModel):
    income: Decimal = Decimal("0")
    expense: Decimal = Decimal("0")
    net: Decimal = Decimal("0")
    outstanding: Decimal = Decimal("0")
    start_date: str | None = None
    end_date: str | None = None
