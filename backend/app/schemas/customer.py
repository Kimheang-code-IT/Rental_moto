from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class CustomerCreate(CamelModel):
    id: str | None = None
    code: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    identity_type: str | None = None
    identity_number: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    address: str | None = None
    status: str = "Active"
    note: str | None = None


class CustomerUpdate(CamelModel):
    code: str | None = None
    full_name: str | None = None
    identity_type: str | None = None
    identity_number: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    address: str | None = None
    status: str | None = None
    note: str | None = None


class CustomerResponse(CamelModel):
    id: str
    code: str
    full_name: str
    identity_type: str | None = None
    identity_number: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    address: str | None = None
    status: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime
