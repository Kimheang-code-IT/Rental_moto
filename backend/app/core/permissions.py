from argon2 import PasswordHasher

ALL_SOURCE_PERMISSIONS = [
    "settings.read",
    "settings.update",
    "user.read",
    "user.manage",
    "role.read",
    "role.manage",
    "attachment.read",
    "attachment.upload",
    "attachment.delete",
    "audit_log.read",
    "report.read",
    "telegram.reports.read",
]

PERMISSION_ACTIONS = ["view", "create", "edit", "delete", "return", "print"]

PERMISSION_MODULES = [
    "dashboard",
    "rental.motorcycles",
    "rental.customers",
    "rental.rentals",
    "rental.finance",
    "reports",
    "admin.users",
    "admin.roles",
    "admin.audit_logs",
    "admin.document_sequences",
    "settings.app_config",
    "configuration",
]

EXTRA_PERMISSIONS = [
    "dashboard.view",
    "reports.view",
    "reports.print",
    "configuration.view",
    "configuration.edit",
    "configuration.manage",
    "settings.app_config.view",
    "settings.app_config.edit",
]

SERVICE_PERMISSIONS = ["telegram.reports.read"]


def build_all_permissions() -> list[str]:
    keys: list[str] = []
    for module in PERMISSION_MODULES:
        for action in PERMISSION_ACTIONS:
            keys.append(f"{module}.{action}")
    keys.extend(EXTRA_PERMISSIONS)
    keys.extend(ALL_SOURCE_PERMISSIONS)
    keys.extend(SERVICE_PERMISSIONS)
    seen: set[str] = set()
    unique = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def rental_staff_permissions() -> list[str]:
    staff_pages = [
        "dashboard.view",
        "rental.motorcycles.view",
        "rental.motorcycles.create",
        "rental.motorcycles.edit",
        "rental.customers.view",
        "rental.customers.create",
        "rental.customers.edit",
        "rental.rentals.view",
        "rental.rentals.create",
        "rental.rentals.edit",
        "rental.rentals.print",
        "rental.rentals.return",
        "rental.finance.view",
        "rental.finance.create",
        "reports.view",
        "reports.print",
    ]
    source = ["settings.read", "attachment.read", "attachment.upload", "report.read"]
    return sorted(set(staff_pages + source))


def viewer_permissions() -> list[str]:
    pages = [
        "dashboard.view",
        "rental.motorcycles.view",
        "rental.customers.view",
        "rental.rentals.view",
        "rental.rentals.print",
        "rental.finance.view",
        "reports.view",
        "reports.print",
    ]
    source = ["settings.read", "attachment.read", "audit_log.read", "report.read"]
    return sorted(set(pages + source))


def permissions_hasher() -> PasswordHasher:
    return PasswordHasher()


def is_super_admin(role: str | None, permissions: list[str] | None) -> bool:
    if role == "SuperAdmin":
        return True
    return bool(permissions and "ALL_PAGES" in permissions)


def has_permission(role: str | None, permissions: list[str] | None, required: str) -> bool:
    if is_super_admin(role, permissions):
        return True
    if not permissions:
        return False
    if required in permissions:
        return True
    if required.endswith(".view") and required.replace(".view", ".manage") in permissions:
        return True
    if required.startswith("configuration.") and "configuration.manage" in permissions:
        return True
    return False
