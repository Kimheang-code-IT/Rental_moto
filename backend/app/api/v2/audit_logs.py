from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, parse_date_range, require_permission
from app.repositories.admin import AuditRepository
from app.schemas.admin import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


def _to_dict(log) -> dict:
    return AuditLogResponse.model_validate(log).model_dump(by_alias=True)


@router.get("")
async def list_audit_logs(
    params: ListParams = Depends(),
    entity_type: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
    user=Depends(require_permission("admin.audit_logs.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(params.start_date, params.end_date)
    rows, total = await AuditRepository(session).list(
        params.q, params.page, params.limit, entity_type=entity_type, action=action, user_id=user_id, start_date=start, end_date=end
    )
    meta = {"page": params.page, "limit": params.limit, "total": total}
    return envelope([_to_dict(log) for log in rows], meta)
