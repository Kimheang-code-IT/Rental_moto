from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, require_any_permission, require_permission
from app.schemas.admin import RoleCreate, RoleUpdate
from app.services.admin_service import RoleService

router = APIRouter(prefix="/roles", tags=["roles"])


def _to_dict(role, user_count: int = 0) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissions": list(role.permissions) if role.permissions else [],
        "pageAccess": list(role.page_access) if role.page_access else [],
        "isSystem": role.is_system,
        "permissionCount": len(role.permissions or []),
        "userCount": user_count,
        "createdAt": role.created_at.isoformat(),
        "updatedAt": role.updated_at.isoformat(),
    }


@router.get("")
async def list_roles(
    params: ListParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.roles.view")),
) -> dict:
    service = RoleService(session, user)
    items, total = await service.list(params.q, params.page, params.limit)
    counts = await service.repo.counts_by_role()
    return envelope([_to_dict(r, counts.get(r.id, 0)) for r in items], {"page": params.page, "limit": params.limit, "total": total})


@router.get("/options")
async def role_options(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_any_permission("admin.users.create", "admin.users.edit", "admin.roles.view")),
) -> dict:
    from app.core.permissions import effective_permissions, is_super_admin_user

    items, _ = await RoleService(session, user).repo.list(None, 1, 1000)
    actor_permissions = set(effective_permissions(user))
    options = []
    for role in items:
        if not is_super_admin_user(user):
            if not set(role.permissions or []).issubset(actor_permissions):
                continue
        options.append({
            "id": role.id,
            "name": role.name,
            "isSystem": role.is_system,
            "permissions": list(role.permissions or []),
        })
    return envelope(options, {"page": 1, "limit": len(options), "total": len(options)})


@router.get("/{role_id}")
async def get_role(
    role_id: int,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.roles.view")),
) -> dict:
    service = RoleService(session, user)
    found = await service.repo.get_by_id_checked(role_id)
    return envelope(_to_dict(found, await service.repo.users_with_role(found.id)))


@router.post("", status_code=201)
async def create_role(
    body: RoleCreate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.roles.create")),
) -> dict:
    service = RoleService(session, user)
    role = await service.create(body)
    return envelope(_to_dict(role))


@router.put("/{role_id}")
async def update_role(
    role_id: int,
    body: RoleUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.roles.edit")),
) -> dict:
    service = RoleService(session, user)
    role = await service.update(role_id, body)
    return envelope(_to_dict(role))


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.roles.delete")),
) -> dict:
    service = RoleService(session, user)
    await service.delete(role_id)
    return envelope({"deleted": True})
