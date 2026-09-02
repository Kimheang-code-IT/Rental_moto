from __future__ import annotations

from collections.abc import Iterable

from argon2 import PasswordHasher

SUPER_ADMIN_ROLE = "SuperAdmin"
SUPER_ADMIN_PERMISSION = "ALL_PAGES"

# The single catalog for permissions assignable to interactive user roles.
PERMISSION_CATALOG: dict[str, tuple[str, ...]] = {
    "dashboard": ("view",),
    "rental.motorcycles": ("view", "create", "edit", "delete", "export"),
    "rental.customers": ("view", "create", "edit", "delete", "export"),
    "rental.rentals": ("view", "create", "edit", "delete", "return", "print", "export"),
    "rental.finance": ("view", "create", "edit", "delete", "export"),
    "reports": ("view", "print", "export"),
    "admin.users": ("view", "create", "edit", "delete"),
    "admin.roles": ("view", "create", "edit", "delete"),
    "configuration": ("view", "create", "edit", "delete"),
    "settings.app_config": ("view", "edit", "configure"),
    "admin.audit_logs": ("view", "export"),
}

SERVICE_PERMISSIONS = frozenset({"telegram.reports.read"})
ASSIGNABLE_PERMISSIONS = frozenset(
    f"{module}.{action}"
    for module, actions in PERMISSION_CATALOG.items()
    for action in actions
)


def permission_catalog() -> list[dict[str, object]]:
    return [
        {
            "module": module,
            "actions": list(actions),
            "permissions": [f"{module}.{action}" for action in actions],
        }
        for module, actions in PERMISSION_CATALOG.items()
    ]


def build_all_permissions() -> list[str]:
    return [key for group in permission_catalog() for key in group["permissions"]] + sorted(SERVICE_PERMISSIONS)


def normalize_role_permissions(values: Iterable[str] | None, *, allow_wildcard: bool = False) -> list[str]:
    normalized = list(dict.fromkeys(str(value).strip() for value in (values or []) if str(value).strip()))
    allowed = set(ASSIGNABLE_PERMISSIONS)
    if allow_wildcard:
        allowed.add(SUPER_ADMIN_PERMISSION)
    unknown = sorted(set(normalized) - allowed)
    if unknown:
        raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
    granted = set(normalized)
    for permission in normalized:
        module, action = permission.rsplit(".", 1)
        view_permission = f"{module}.view"
        if action != "view" and view_permission in ASSIGNABLE_PERMISSIONS:
            granted.add(view_permission)
    ordered = [permission for permission in build_all_permissions() if permission in granted]
    if SUPER_ADMIN_PERMISSION in granted:
        ordered.append(SUPER_ADMIN_PERMISSION)
    return ordered


def rental_staff_permissions() -> list[str]:
    return [
        "dashboard.view",
        "rental.motorcycles.view", "rental.motorcycles.create", "rental.motorcycles.edit",
        "rental.customers.view", "rental.customers.create", "rental.customers.edit",
        "rental.rentals.view", "rental.rentals.create", "rental.rentals.edit",
        "rental.rentals.return", "rental.rentals.print",
        "rental.finance.view", "rental.finance.create",
        "reports.view", "reports.print",
    ]


def viewer_permissions() -> list[str]:
    return [
        "dashboard.view",
        "rental.motorcycles.view",
        "rental.customers.view",
        "rental.rentals.view", "rental.rentals.print",
        "rental.finance.view",
        "reports.view", "reports.print",
    ]


def permissions_hasher() -> PasswordHasher:
    return PasswordHasher()


def effective_permissions(user: object) -> list[str]:
    """Resolve access exclusively from the authoritative related role."""
    role = getattr(user, "role_ref", None)
    if role is None:
        return []
    values = list(getattr(role, "permissions", None) or [])
    if getattr(role, "name", None) == SUPER_ADMIN_ROLE and SUPER_ADMIN_PERMISSION in values:
        return [SUPER_ADMIN_PERMISSION]
    return [value for value in values if value in ASSIGNABLE_PERMISSIONS]


def is_super_admin_user(user: object) -> bool:
    role = getattr(user, "role_ref", None)
    return bool(
        role
        and getattr(role, "name", None) == SUPER_ADMIN_ROLE
        and SUPER_ADMIN_PERMISSION in (getattr(role, "permissions", None) or [])
    )


def user_has_permission(user: object, required: str) -> bool:
    values = effective_permissions(user)
    return SUPER_ADMIN_PERMISSION in values or required in values


# Compatibility helpers for isolated code/tests. HTTP request authorization uses
# user_has_permission and therefore cannot trust a denormalized user role name.
def is_super_admin(role: str | None, permissions: list[str] | None) -> bool:
    return role == SUPER_ADMIN_ROLE or bool(permissions and SUPER_ADMIN_PERMISSION in permissions)


def has_permission(role: str | None, permissions: list[str] | None, required: str) -> bool:
    return is_super_admin(role, permissions) or bool(permissions and required in permissions)
