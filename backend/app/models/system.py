import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


def uuid_str() -> str:
    return uuid.uuid4().hex


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    entity_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DocumentSequence(Base, TimestampMixin):
    __tablename__ = "document_sequences"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    padding_length: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class StorageProvider(Base, TimestampMixin):
    __tablename__ = "storage_providers"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    allowed_file_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    access_mode: Mapped[str] = mapped_column(String(20), default="private", nullable=False)
    upload_path_pattern: Mapped[str] = mapped_column(String(200), default="{entity}/{yyyy}/{mm}/{id}", nullable=False)
    connection_status: Mapped[str] = mapped_column(String(20), default="not_tested", nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(300), nullable=True)
    region: Mapped[str | None] = mapped_column(String(60), nullable=True)
    bucket: Mapped[str | None] = mapped_column(String(120), nullable=True)
    access_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    secret_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    public_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    path_style: Mapped[bool | None] = mapped_column(nullable=True)
    folder_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_secret: Mapped[str | None] = mapped_column(String(300), nullable=True)
    credential_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sync_schedule: Mapped[str | None] = mapped_column(String(60), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ExportJob(Base, TimestampMixin):
    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    resource: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(10), default="csv", nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OutboxEvent(Base, TimestampMixin):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    queue: Mapped[str] = mapped_column(String(40), default="telegram", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskProgress(Base, TimestampMixin):
    __tablename__ = "task_progress"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    related_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


