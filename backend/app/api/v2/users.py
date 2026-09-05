from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, require_permission
from app.core.permissions import effective_permissions
from app.schemas.admin import UserCreate, UserUpdate
from app.services.admin_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _to_dict(user) -> dict:
    permissions = effective_permissions(user)
    role_ref = getattr(user, "role_ref", None)
    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.display_name,
        "email": user.email,
        "roleId": user.role_id,
        "role": role_ref.name if role_ref is not None else None,
        "isOwner": bool(getattr(user, "is_owner", False)),
        "status": user.status,
        "avatar": user.avatar_url,
        "effectivePermissions": permissions,
        "permissions": permissions,
        "pageAccess": permissions,
        "telegramLinked": bool(user.telegram_chat_id),
        "telegramChatId": user.telegram_chat_id or "",
        "lastLoginAt": user.last_login_at.isoformat() if user.last_login_at else None,
        "createdAt": user.created_at.isoformat(),
        "updatedAt": user.updated_at.isoformat(),
    }


@router.get("")
async def list_users(
    params: ListParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.users.view")),
) -> dict:
    service = UserService(session, user)
    items, total = await service.list(params.q, params.page, params.limit)
    return envelope([_to_dict(u) for u in items], {"page": params.page, "limit": params.limit, "total": total})


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.users.view")),
) -> dict:
    service = UserService(session, user)
    found = await service.get(user_id)
    return envelope(_to_dict(found))


@router.post("", status_code=201)
async def create_user(
    body: UserCreate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.users.create")),
) -> dict:
    service = UserService(session, user)
    created = await service.create(body)
    return envelope(_to_dict(created))


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.users.edit")),
) -> dict:
    service = UserService(session, user)
    updated = await service.update(user_id, body)
    return envelope(_to_dict(updated))


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.users.delete")),
) -> dict:
    service = UserService(session, user)
    await service.delete(user_id)
    return envelope({"deleted": True})


@router.post("/{user_id}/unlink-telegram")
async def unlink_telegram(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("admin.users.edit")),
) -> dict:
    from app.services.auth_service import AuthService

    service = UserService(session, user)
    target = await service.get(user_id)
    auth = AuthService(session)
    await auth.unlink_telegram(target)
    return envelope({"unlinked": True})
