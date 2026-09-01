from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, require_permission
from app.schemas.admin import RoleCreate, RoleUpdate
from app.services.admin_service import RoleService

router = APIRouter(prefix="/roles", tags=["roles"])


def _to_dict(role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissions": list(role.permissions) if role.permissions else [],
        "pageAccess": list(role.page_access) if role.page_access else [],
        "isSystem": role.is_system,
        "createdAt": role.created_at.isoformat(),
        "updatedAt": role.updated_at.isoformat(),
    }


@router.get("")
async def list_roles(
    params: ListParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("role.read")),
) -> dict:
    service = RoleService(session, user)
    items, total = await service.list(params.q, params.page, params.limit)
    return envelope([_to_dict(r) for r in items], {"page": params.page, "limit": params.limit, "total": total})


@router.get("/{role_id}")
async def get_role(
    role_id: int,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("role.read")),
) -> dict:
    service = RoleService(session, user)
    found = await service.repo.get_by_id_checked(role_id)
    return envelope(_to_dict(found))


@router.post("", status_code=201)
async def create_role(
    body: RoleCreate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("role.manage")),
) -> dict:
    service = RoleService(session, user)
    role = await service.create(body)
    return envelope(_to_dict(role))


@router.put("/{role_id}")
async def update_role(
    role_id: int,
    body: RoleUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("role.manage")),
) -> dict:
    service = RoleService(session, user)
    role = await service.update(role_id, body)
    return envelope(_to_dict(role))


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("role.manage")),
) -> dict:
    service = RoleService(session, user)
    await service.delete(role_id)
    return envelope({"deleted": True})
