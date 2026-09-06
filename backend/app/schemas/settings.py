from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import CamelModel


class AppInfoUpdate(CamelModel):
    application_name: str | None = None
    short_name: str | None = None
    business_name: str | None = None
    description: str | None = None
    support_email: str | None = None
    support_phone: str | None = None
    website: str | None = None
    address: str | None = None
    branding: dict[str, Any] | None = None
    footer: dict[str, Any] | None = None


class AppConfigUpdate(CamelModel):
    general: dict[str, Any] | None = None
    localization: dict[str, Any] | None = None
    email: dict[str, Any] | None = None
    telegram: dict[str, Any] | None = None
    notifications: dict[str, Any] | None = None
    security: dict[str, Any] | None = None
    system: dict[str, Any] | None = None


class ConnectionResult(CamelModel):
    status: str
    message: str = ""


class TestEmailRequest(CamelModel):
    to: str | None = None


class TestTelegramRequest(CamelModel):
    destination_id: str | None = None


class SearchHit(CamelModel):
    id: str
    type: str
    title: str
    subtitle: str | None = None
    url: str


class SearchResult(CamelModel):
    hits: list[SearchHit] = []
    total: int = 0


class ExportCreateRequest(CamelModel):
    resource: str
    format: str = "csv"
    scope: str = "all_matching"
    field_codes: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    query: dict[str, Any] | None = None
    selected_ids: list[str] | None = None


class ExportJobResponse(CamelModel):
    id: str
    status: str
    resource: str
    format: str
    progress: int = 0
    created_at: datetime
    download_url: str | None = None
    expires_at: datetime | None = None
    error: str | None = None


class TaskStatusResponse(CamelModel):
    id: str
    task_type: str
    status: str
    progress: int = 0
    message: str | None = None
    result: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TelegramPeriodParams(CamelModel):
    period: str = "today"
    start: str | None = None
    end: str | None = None
    page: int = 1
    limit: int = 10


class TelegramLinkRequest(CamelModel):
    code: str
    telegram_user_id: str
    telegram_chat_id: str


class SendTestRequest(CamelModel):
    chat_id: str | None = None
    message: str | None = None
