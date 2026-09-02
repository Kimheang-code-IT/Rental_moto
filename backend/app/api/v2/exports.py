from __future__ import annotations
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_owned_resource, envelope, get_current_user, get_db_session
from app.core.errors import AccessDeniedError, NotFoundError, ValidationError
from app.core.permissions import user_has_permission
from app.models import ExportJob, TaskProgress
from app.repositories.admin import ExportRepository, TaskProgressRepository
from app.schemas.settings import ExportCreateRequest
from app.services.export_service import EXPORT_RESOURCES, export_permission
from app.tasks.celery_app import celery_app

router = APIRouter(tags=["exports"])


def _require_export_permission(user, resource: str) -> None:
    permission = export_permission(resource)
    if permission is None or not user_has_permission(user, permission):
        raise AccessDeniedError(f"Missing export permission for resource: {resource}")


def _require_owner(user, job: ExportJob) -> None:
    if not can_access_owned_resource(user, job.user_id):
        raise NotFoundError("Export job not found")


def _to_dict(job: ExportJob, include_download: bool = False) -> dict:
    download_url = None
    if include_download and job.status == "completed" and job.file_path:
        download_url = f"/api/v2/exports/{job.id}/download"
    return {
        "id": job.id,
        "status": job.status,
        "resource": job.resource,
        "format": job.format,
        "progress": job.progress,
        "createdAt": job.created_at.isoformat(),
        "downloadUrl": download_url,
        "expiresAt": job.expires_at.isoformat() if job.expires_at else None,
        "error": job.error,
    }


@router.post("/exports", status_code=202)
async def create_export(
    body: ExportCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(get_current_user),
) -> dict:
    if body.resource not in EXPORT_RESOURCES:
        raise ValidationError(f"Unknown export resource: {body.resource}")
    _require_export_permission(user, body.resource)
    if body.format not in ("csv", "xlsx"):
        raise ValidationError("Only csv and xlsx formats are supported")

    job = ExportJob(
        user_id=user.id,
        resource=body.resource,
        format=body.format,
        filters=body.model_dump(by_alias=True),
        status="queued",
        progress=0,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    repo = ExportRepository(session)
    await repo.add(job)
    task = TaskProgress(
        id=uuid.uuid4().hex,
        task_type=f"export:{body.resource}",
        status="queued",
        progress=0,
        user_id=user.id,
        related_id=job.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    await TaskProgressRepository(session).upsert(task)
    await session.commit()

    try:
        result = celery_app.send_task(
            "app.tasks.exports.export_resource",
            kwargs={"export_id": job.id, "task_id": task.id},
            queue="exports",
        )
        job.task_id = result.id
        task.status = "queued"
        await session.commit()
    except Exception:
        job.status = "failed"
        job.error = "Task broker unavailable"
        task.status = "failed"
        task.message = "Task broker unavailable"
        await session.commit()

    return envelope(_to_dict(job), {"taskId": task.id})


@router.get("/exports")
async def list_exports(
    page: int = 1,
    limit: int = 20,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(get_current_user),
) -> dict:
    repo = ExportRepository(session)
    items, total = await repo.list_for_user(user.id, page, limit)
    return envelope([_to_dict(j) for j in items], {"page": page, "limit": limit, "total": total})


@router.get("/exports/{export_id}")
async def get_export(
    export_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(get_current_user),
) -> dict:
    job = await ExportRepository(session).get(export_id)
    if job is None:
        raise NotFoundError("Export job not found")
    _require_owner(user, job)
    _require_export_permission(user, job.resource)
    return envelope(_to_dict(job, include_download=True))


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(get_current_user),
) -> FileResponse:
    job = await ExportRepository(session).get(export_id)
    if job is None:
        raise NotFoundError("Export job not found")
    _require_owner(user, job)
    _require_export_permission(user, job.resource)
    if job.status != "completed" or not job.file_path:
        raise ValidationError("Export is not ready for download")
    if job.expires_at:
        expires = job.expires_at if job.expires_at.tzinfo else job.expires_at.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            raise ValidationError("Export download has expired")
    if not os.path.exists(job.file_path):
        raise NotFoundError("Export file is no longer available")
    return FileResponse(job.file_path, filename=job.file_name or f"{export_id}.{job.format}")


@router.delete("/exports/{export_id}")
async def delete_export(
    export_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(get_current_user),
) -> dict:
    repo = ExportRepository(session)
    job = await repo.get(export_id)
    if job is None:
        raise NotFoundError("Export job not found")
    _require_owner(user, job)
    _require_export_permission(user, job.resource)
    if job.file_path and os.path.exists(job.file_path):
        try:
            os.remove(job.file_path)
        except OSError:
            pass
    await repo.delete(job)
    await session.commit()
    return envelope({"deleted": True})

