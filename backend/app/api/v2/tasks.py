from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import envelope, get_db_session, require_permission
from app.core.errors import NotFoundError
from app.repositories.admin import TaskProgressRepository

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("dashboard.view")),
) -> dict:
    repo = TaskProgressRepository(session)
    task = await repo.get(task_id)
    if task is None:
        raise NotFoundError("Task not found")
    if task.user_id is not None and task.user_id != user.id:
        from app.core.permissions import is_super_admin

        if not is_super_admin(user.role, user.permissions):
            raise NotFoundError("Task not found")
    return envelope(
        {
            "id": task.id,
            "taskType": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "message": task.message,
            "result": task.result,
            "createdAt": task.created_at.isoformat(),
            "updatedAt": task.updated_at.isoformat(),
        }
    )

