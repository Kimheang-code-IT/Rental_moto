from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import (
    AppSetting,
    AuditLog,
    DocumentSequence,
    ExportJob,
    OutboxEvent,
    RefreshTokenSession,
    Role,
    TaskProgress,
    User,
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id, options=(joinedload(User.role_ref),))

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).options(joinedload(User.role_ref)).where(func.lower(User.email) == email.lower())
        )
        return result.unique().scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).options(joinedload(User.role_ref)).where(func.lower(User.username) == username.lower())
        )
        return result.unique().scalar_one_or_none()

    async def get_by_telegram_chat(self, chat_id: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .where(User.telegram_chat_id == str(chat_id))
            .order_by(User.telegram_linked_at.desc().nullslast(), User.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_ids(self, telegram_user_id: str, telegram_chat_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(
                User.telegram_user_id == str(telegram_user_id),
                User.telegram_chat_id == str(telegram_chat_id),
            ).order_by(User.telegram_linked_at.desc().nullslast(), User.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_user_id(self, telegram_user_id: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .where(User.telegram_user_id == str(telegram_user_id))
            .order_by(User.telegram_linked_at.desc().nullslast(), User.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def clear_conflicting_telegram_link(
        self, user_id: int, telegram_user_id: str, telegram_chat_id: str
    ) -> None:
        """A Telegram account/private chat may belong to only one application user."""
        await self.session.execute(
            update(User)
            .where(
                User.id != user_id,
                (User.telegram_user_id == str(telegram_user_id))
                | (User.telegram_chat_id == str(telegram_chat_id)),
            )
            .values(telegram_user_id=None, telegram_chat_id=None, telegram_linked_at=None)
        )

    async def list(self, q: str | None, page: int, limit: int) -> tuple[list[User], int]:
        filters = []
        if q:
            term = f"%{q.lower()}%"
            filters.append(
                (func.lower(User.email).like(term))
                | (func.lower(User.username).like(term))
                | (func.lower(User.display_name).like(term))
            )
        count_stmt = select(func.count()).select_from(User)
        stmt = select(User).options(joinedload(User.role_ref)).order_by(User.id)
        if filters:
            count_stmt = count_stmt.where(*filters)
            stmt = stmt.where(*filters)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        rows = (await self.session.execute(stmt.offset((page - 1) * limit).limit(limit))).unique().scalars().all()
        return list(rows), int(total)

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)

    async def count(self) -> int:
        return int((await self.session.execute(select(func.count()).select_from(User))).scalar() or 0)

    async def revoke_all_refresh_sessions(self, user_id: int) -> None:
        await self.session.execute(
            update(RefreshTokenSession)
            .where(RefreshTokenSession.user_id == user_id, RefreshTokenSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )


class RoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, role_id: int) -> Role | None:
        return await self.session.get(Role, role_id)

    async def get_by_id_checked(self, role_id: int) -> Role:
        from app.core.errors import NotFoundError

        role = await self.session.get(Role, role_id)
        if role is None:
            raise NotFoundError("Role not found")
        return role

    async def get_by_name(self, name: str) -> Role | None:
        result = await self.session.execute(select(Role).where(func.lower(Role.name) == name.lower()))
        return result.scalar_one_or_none()

    async def list(self, q: str | None, page: int, limit: int) -> tuple[list[Role], int]:
        stmt = select(Role).order_by(Role.id)
        if q:
            stmt = stmt.where(func.lower(Role.name).like(f"%{q.lower()}%"))
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
        rows = (await self.session.execute(stmt.offset((page - 1) * limit).limit(limit))).scalars().all()
        return list(rows), int(total)

    async def create(self, role: Role) -> Role:
        self.session.add(role)
        await self.session.flush()
        return role

    async def delete(self, role: Role) -> None:
        await self.session.delete(role)

    async def users_with_role(self, role_id: int) -> int:
        return int(
            (await self.session.execute(select(func.count()).select_from(User).where(User.role_id == role_id))).scalar() or 0
        )

    async def counts_by_role(self) -> dict[int, int]:
        rows = await self.session.execute(select(User.role_id, func.count()).group_by(User.role_id))
        return {int(role_id): int(count) for role_id, count in rows if role_id is not None}


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def list(
        self,
        q: str | None,
        page: int,
        limit: int,
        entity_type: str | None = None,
        action: str | None = None,
        user_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc())
        if q:
            term = f"%{q.lower()}%"
            stmt = stmt.where(
                (func.lower(AuditLog.action).like(term))
                | (func.lower(AuditLog.entity_type).like(term))
                | (func.lower(func.coalesce(AuditLog.entity_label, "")).like(term))
                | (func.lower(func.coalesce(AuditLog.user_name, "")).like(term))
            )
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if action:
            stmt = stmt.where(func.lower(AuditLog.action) == action.lower())
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if start_date:
            stmt = stmt.where(AuditLog.occurred_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.occurred_at <= end_date)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
        rows = (await self.session.execute(stmt.offset((page - 1) * limit).limit(limit))).scalars().all()
        return list(rows), int(total)


class DocumentSequenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, seq_id: str) -> DocumentSequence | None:
        return await self.session.get(DocumentSequence, seq_id)

    async def get_by_type_for_update(self, document_type: str) -> DocumentSequence | None:
        """Lock the sequence row so concurrent requests cannot draw the same number."""
        result = await self.session.execute(
            select(DocumentSequence).where(DocumentSequence.document_type == document_type).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_type(self, document_type: str) -> DocumentSequence | None:
        result = await self.session.execute(select(DocumentSequence).where(DocumentSequence.document_type == document_type))
        return result.scalar_one_or_none()

    async def list(self, q: str | None, page: int, limit: int) -> tuple[list[DocumentSequence], int]:
        stmt = select(DocumentSequence).order_by(DocumentSequence.document_type)
        if q:
            stmt = stmt.where(func.lower(DocumentSequence.document_type).like(f"%{q.lower()}%"))
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
        rows = (await self.session.execute(stmt.offset((page - 1) * limit).limit(limit))).scalars().all()
        return list(rows), int(total)

    async def add(self, seq: DocumentSequence) -> DocumentSequence:
        self.session.add(seq)
        await self.session.flush()
        return seq

    async def delete(self, seq: DocumentSequence) -> None:
        await self.session.delete(seq)

    async def next_value(self, document_type: str, prefix: str, padding: int, year: int | None) -> str:
        # Row lock serializes number allocation; the unique *_no columns are the
        # last line of defense if two transactions race on a brand-new sequence.
        seq = await self.get_by_type_for_update(document_type)
        if seq is None:
            seq = DocumentSequence(
                id=f"ds-{document_type.lower().replace('_', '-')}",
                document_type=document_type,
                prefix=prefix,
                year=year,
                padding_length=padding,
                last_value=0,
            )
            self.session.add(seq)
            await self.session.flush()
        seq.last_value = int(seq.last_value or 0) + 1
        effective_year = year if year is not None else (seq.year if seq.year is not None else None)
        parts = [p for p in [seq.prefix, str(effective_year) if effective_year else None, str(seq.last_value).zfill(seq.padding_length)] if p]
        return "-".join(parts)


class SettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_value(self, key: str) -> dict | None:
        row = await self.session.get(AppSetting, key)
        return dict(row.value) if row else None

    async def put_value(self, key: str, value: dict, updated_by: int | None = None) -> None:
        row = await self.session.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value, updated_by_user_id=updated_by)
            self.session.add(row)
        else:
            row.value = value
            row.updated_by_user_id = updated_by
        await self.session.flush()


class ExportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, job_id: str) -> ExportJob | None:
        return await self.session.get(ExportJob, job_id)

    async def add(self, job: ExportJob) -> ExportJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def list_for_user(self, user_id: int, page: int, limit: int) -> tuple[list[ExportJob], int]:
        stmt = select(ExportJob).where(ExportJob.user_id == user_id).order_by(ExportJob.created_at.desc())
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
        rows = (await self.session.execute(stmt.offset((page - 1) * limit).limit(limit))).scalars().all()
        return list(rows), int(total)


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, event: OutboxEvent) -> OutboxEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def pending(self, limit: int = 50) -> list[OutboxEvent]:
        result = await self.session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending", OutboxEvent.attempts < OutboxEvent.max_attempts)
            .order_by(OutboxEvent.available_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_published(self, event_id: str) -> None:
        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(status="published", published_at=datetime.now(timezone.utc))
        )

    async def mark_failed(self, event_id: str, error: str, backoff_seconds: int) -> None:
        from datetime import timedelta

        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(
                attempts=OutboxEvent.attempts + 1,
                last_error=error,
                available_at=datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds),
            )
        )

    async def stale_published_cleanup(self, older_than: datetime) -> None:
        await self.session.execute(delete(OutboxEvent).where(OutboxEvent.status == "published", OutboxEvent.published_at < older_than))


class TaskProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, task_id: str) -> TaskProgress | None:
        return await self.session.get(TaskProgress, task_id)

    async def upsert(self, task: TaskProgress) -> TaskProgress:
        existing = await self.session.get(TaskProgress, task.id)
        if existing:
            existing.status = task.status
            existing.progress = task.progress
            existing.message = task.message
            existing.result = task.result
            existing.expires_at = task.expires_at
            await self.session.flush()
            return existing
        self.session.add(task)
        await self.session.flush()
        return task

    async def cleanup_expired(self, now: datetime) -> None:
        await self.session.execute(delete(TaskProgress).where(TaskProgress.expires_at.is_not(None), TaskProgress.expires_at < now))

    async def get_any(self, task_id: str) -> dict[str, Any] | None:
        task = await self.get(task_id)
        if task:
            return {
                "id": task.id,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "message": task.message,
                "result": task.result,
            }
        return None

