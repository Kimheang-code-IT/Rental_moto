from fastapi import APIRouter, Depends

from app.api.deps import envelope, require_any_permission
from app.core.permissions import permission_catalog

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("")
async def list_permissions(
    user=Depends(require_any_permission("admin.roles.view", "admin.users.create", "admin.users.edit")),
) -> dict:
    catalog = permission_catalog()
    return envelope(catalog, {"page": 1, "limit": len(catalog), "total": len(catalog)})
