from __future__ import annotations
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AccessDeniedError, ConflictError, NotFoundError
from app.core.redis import cache
from app.core.security import hash_password, utcnow
from app.models import AuditLog, Role, Rental, User
from app.repositories.admin import (
    AuditRepository,
    RoleRepository,
    SettingRepository,
    UserRepository,
)
from app.repositories.rental import CustomerRepository, ExpenseRepository, MotorcycleRepository, PaymentRepository, RentalRepository

DASHBOARD_CACHE_PREFIX = "dashboard:v1:"
SETTINGS_CACHE_PREFIX = "settings:v1:"


class UserService:
    def __init__(self, session: AsyncSession, actor: User | None = None) -> None:
        self.session = session
        self.repo = UserRepository(session)
        self.roles = RoleRepository(session)
        self.audit = AuditRepository(session)
        self.actor = actor

    def _require(self, permission: str) -> None:
        from app.core.permissions import user_has_permission

        if self.actor is None or not user_has_permission(self.actor, permission):
            raise AccessDeniedError(f"Missing permission: {permission}")

    async def _resolve_role(self, role_id: int | None, role_name: str | None) -> Role:
        by_id = await self.roles.get(role_id) if role_id is not None else None
        by_name = await self.roles.get_by_name(role_name) if role_name else None
        if role_id is not None and by_id is None:
            raise NotFoundError("Role not found")
        if role_name and by_name is None:
            raise NotFoundError(f"Role {role_name} not found")
        if by_id is not None and by_name is not None and by_id.id != by_name.id:
            raise ConflictError("roleId and legacy role refer to different roles")
        role = by_id or by_name
        if role is None:
            raise ConflictError("roleId is required")
        self._assert_assignable(role)
        return role

    def _assert_assignable(self, role: Role) -> None:
        from app.core.permissions import effective_permissions, is_super_admin_user

        if self.actor is None:
            raise AccessDeniedError()
        if is_super_admin_user(self.actor):
            return
        missing = set(role.permissions or []) - set(effective_permissions(self.actor))
        if missing:
            raise AccessDeniedError("You cannot assign a role with permissions you do not have")

    async def list(self, q, page, limit):
        self._require("admin.users.view")
        return await self.repo.list(q, page, limit)

    async def get(self, user_id: int) -> User:
        self._require("admin.users.view")
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def create(self, data) -> User:
        self._require("admin.users.create")
        if await self.repo.get_by_email(data.email):
            raise ConflictError(f"Email {data.email} is already registered")
        if await self.repo.get_by_username(data.username):
            raise ConflictError(f"Username {data.username} is already taken")
        role = await self._resolve_role(data.role_id, data.role)
        user = User(
            username=data.username,
            display_name=data.display_name,
            email=data.email.lower(),
            password_hash=hash_password(data.password),
            role=role.name,
            role_id=role.id,
            is_owner=False,
            status=data.status,
            permissions=None,
            page_access=None,
            avatar_url=data.avatar,
        )
        user.role_ref = role
        await self.repo.create(user)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="user_created",
                entity_type="user",
                entity_id=str(user.id),
                entity_label=user.email,
                details={"after": {"roleId": role.id, "role": role.name}},
            )
        )
        await self.session.commit()
        refreshed = await self.repo.get(user.id)
        return refreshed or user

    async def update(self, user_id: int, data) -> User:
        self._require("admin.users.edit")
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if user.is_owner and self.actor and user.id != self.actor.id:
            from app.core.permissions import is_super_admin_user

            if not is_super_admin_user(self.actor):
                raise AccessDeniedError("Only the owner or another owner-level user can modify the owner account")
        role_ref = user.role_ref
        before = {
            "roleId": user.role_id,
            "role": role_ref.name if role_ref is not None else None,
            "status": user.status,
        }
        updates = data.model_dump(exclude_unset=True, by_alias=False)
        if updates.get("email") and updates["email"].lower() != user.email.lower():
            other = await self.repo.get_by_email(updates["email"])
            if other is not None and other.id != user.id:
                raise ConflictError(f"Email {updates['email']} is already registered")
        if updates.get("username") and updates["username"].lower() != user.username.lower():
            other = await self.repo.get_by_username(updates["username"])
            if other is not None and other.id != user.id:
                raise ConflictError(f"Username {updates['username']} is already taken")
        password = updates.pop("password", None)
        if password:
            user.password_hash = hash_password(password)
            user.password_changed_at = utcnow()
        avatar = updates.pop("avatar", None)
        if avatar is not None:
            user.avatar_url = avatar or None
        role_id = updates.pop("role_id", None)
        role_name = updates.pop("role", None)
        target_role = user.role_ref
        if role_id is not None or role_name:
            target_role = await self._resolve_role(role_id, role_name)
        target_status = updates.get("status", user.status)
        if target_role is not None:
            user.role = target_role.name
            user.role_id = target_role.id
            user.role_ref = target_role
        for field, value in updates.items():
            setattr(user, field, value)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="user_updated",
                entity_type="user",
                entity_id=str(user.id),
                entity_label=user.email,
                details={
                    "before": before,
                    "after": {
                        "roleId": target_role.id if target_role is not None else None,
                        "role": target_role.name if target_role is not None else None,
                        "status": target_status,
                    },
                },
            )
        )
        await self.session.commit()
        refreshed = await self.repo.get(user.id)
        return refreshed or user

    async def delete(self, user_id: int) -> None:
        self._require("admin.users.delete")
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if self.actor and user.id == self.actor.id:
            raise ConflictError("You cannot delete your own account")
        if user.is_owner:
            # The system owner cannot be deleted; there is no transfer-owner
            # flow, so removing the owner would make administration impossible.
            raise ConflictError("The system owner account cannot be deleted")
        role_ref = user.role_ref
        await self.repo.delete(user)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="user_deleted",
                entity_type="user",
                entity_id=str(user_id),
                entity_label=user.email,
                details={"before": {
                    "roleId": user.role_id,
                    "role": role_ref.name if role_ref is not None else None,
                    "status": user.status,
                }},
            )
        )
        await self.session.commit()


class RoleService:
    def __init__(self, session: AsyncSession, actor: User | None = None) -> None:
        self.session = session
        self.repo = RoleRepository(session)
        self.audit = AuditRepository(session)
        self.actor = actor

    def _require(self, permission: str) -> None:
        from app.core.permissions import user_has_permission

        if self.actor is None or not user_has_permission(self.actor, permission):
            raise AccessDeniedError(f"Missing permission: {permission}")

    def _validated_permissions(self, values: list[str] | None) -> list[str]:
        from app.core.permissions import effective_permissions, is_super_admin_user, normalize_role_permissions

        allow_wildcard = bool(self.actor is not None and is_super_admin_user(self.actor))
        try:
            permissions = normalize_role_permissions(values, allow_wildcard=allow_wildcard)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        if self.actor is not None and not is_super_admin_user(self.actor):
            missing = set(permissions) - set(effective_permissions(self.actor))
            if missing:
                raise AccessDeniedError("You cannot grant permissions you do not have")
        return permissions

    async def list(self, q, page, limit):
        self._require("admin.roles.view")
        return await self.repo.list(q, page, limit)

    async def create(self, data) -> Role:
        self._require("admin.roles.create")
        if await self.repo.get_by_name(data.name):
            raise ConflictError(f"Role {data.name} already exists")
        # No reserved role names: the operator may name a role anything,
        # including "SuperAdmin". Only the permission keys matter.
        permissions = self._validated_permissions(data.permissions)
        role = Role(
            name=data.name,
            description=data.description,
            permissions=permissions,
            page_access=permissions,
        )
        await self.repo.create(role)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="role_created",
                entity_type="role",
                entity_id=str(role.id),
                entity_label=role.name,
                details={"after": {"name": role.name, "permissions": permissions}},
            )
        )
        await self.session.commit()
        return role

    async def update(self, role_id: int, data) -> Role:
        self._require("admin.roles.edit")
        role = await self.repo.get(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        before = {"name": role.name, "permissions": list(role.permissions or [])}
        updates = data.model_dump(exclude_unset=True, by_alias=False)
        if updates.get("name") and updates["name"].lower() != role.name.lower():
            other = await self.repo.get_by_name(updates["name"])
            if other is not None and other.id != role.id:
                raise ConflictError(f"Role {updates['name']} already exists")
        if "permissions" in updates:
            updates["permissions"] = self._validated_permissions(updates["permissions"])
            role.page_access = updates["permissions"]
        old_name = role.name
        for field, value in updates.items():
            setattr(role, field, value)
        if role.name != old_name:
            await self.session.execute(update(User).where(User.role_id == role.id).values(role=role.name))
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="role_updated",
                entity_type="role",
                entity_id=str(role.id),
                entity_label=role.name,
                details={
                    "before": before,
                    "after": {"name": role.name, "permissions": list(role.permissions or [])},
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(role)
        return role

    async def delete(self, role_id: int) -> None:
        self._require("admin.roles.delete")
        role = await self.repo.get(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        # Roles are operator-owned; is_system is never set by code anymore and
        # is not treated as a delete blocker. Only user assignments block.
        if (await self.repo.users_with_role(role.id)) > 0:
            raise ConflictError("Role is assigned to users and cannot be deleted")
        await self.repo.delete(role)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="role_deleted",
                entity_type="role",
                entity_id=str(role.id),
                entity_label=role.name,
                details={"before": {"name": role.name, "permissions": list(role.permissions or [])}},
            )
        )
        await self.session.commit()


class SettingService:
    def __init__(self, session: AsyncSession, actor: User | None = None) -> None:
        self.session = session
        self.repo = SettingRepository(session)
        self.audit = AuditRepository(session)
        self.actor = actor

    async def get_app_info(self) -> dict:
        cached = await cache.get_json(f"{SETTINGS_CACHE_PREFIX}app-info")
        if cached is not None:
            return cached
        value = await self.repo.get_value("app_info")
        result = value or _default_app_info()
        await cache.set_json(f"{SETTINGS_CACHE_PREFIX}app-info", result, settings.settings_cache_ttl_seconds)
        return result

    async def update_app_info(self, patch: dict) -> dict:
        current = await self.repo.get_value("app_info") or _default_app_info()
        merged = _deep_merge(current, patch)
        merged["updatedAt"] = utcnow().isoformat()
        await self.repo.put_value("app_info", merged, self.actor.id if self.actor else None)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="settings_updated",
                entity_type="setting",
                entity_id="app_info",
            )
        )
        await self.session.commit()
        await cache.delete_keys(f"{SETTINGS_CACHE_PREFIX}app-info")
        return merged

    async def reset_app_info(self) -> dict:
        default = _default_app_info()
        default["updatedAt"] = utcnow().isoformat()
        await self.repo.put_value("app_info", default, self.actor.id if self.actor else None)
        await self.session.commit()
        await cache.delete_keys(f"{SETTINGS_CACHE_PREFIX}app-info")
        return default

    async def reset_all_data(self) -> dict:
        from app.seed import reset_all_data as run_reset_all_data

        # Release locks from this request session (loaded rows / open transaction)
        # so TRUNCATE on operational tables is not blocked.
        await self.session.rollback()
        self.session.expire_all()

        result = await run_reset_all_data()
        await cache.delete_prefix(DASHBOARD_CACHE_PREFIX)
        await cache.delete_prefix("task:telegram:event:")
        return {
            "message": (
                "Business data reset. Users, roles, document sequences, and "
                "settings were kept."
            ),
            "requiresReauth": False,
            "requiresSetup": False,
            "removedExports": result.get("removedExports", 0),
        }

    async def get_app_config(self, mask: bool = True) -> dict:
        from app.services.telegram_context import normalize_telegram_config

        cached = await cache.get_json(f"{SETTINGS_CACHE_PREFIX}app-config")
        if cached is not None:
            result = _deep_merge(_default_app_config(), cached)
            result["telegram"] = normalize_telegram_config(result.get("telegram") or {})
            return _mask_config(result) if mask else result
        value = await self.repo.get_value("app_config")
        result = _deep_merge(_default_app_config(), value or {})
        result["telegram"] = normalize_telegram_config(result.get("telegram") or {})
        await cache.set_json(f"{SETTINGS_CACHE_PREFIX}app-config", result, settings.settings_cache_ttl_seconds)
        return _mask_config(result) if mask else result

    async def update_app_config(self, patch: dict) -> dict:
        current = await self.repo.get_value("app_config") or _default_app_config()
        merged = _deep_merge(current, _mask_config(patch, write=True))
        from app.services.telegram_context import (
            normalize_telegram_config,
            sync_user_telegram_ids_from_access,
            validate_telegram_config,
        )

        if "telegram" in merged:
            merged["telegram"] = normalize_telegram_config(merged["telegram"])
            validate_telegram_config(merged["telegram"])
            await sync_user_telegram_ids_from_access(self.session, merged["telegram"])
        merged["updatedAt"] = utcnow().isoformat()
        await self.repo.put_value("app_config", merged, self.actor.id if self.actor else None)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="settings_updated",
                entity_type="setting",
                entity_id="app_config",
            )
        )
        await self.session.commit()
        await cache.delete_keys(f"{SETTINGS_CACHE_PREFIX}app-config", f"{DASHBOARD_CACHE_PREFIX}*")
        return _mask_config(merged)

    async def telegram_config(self) -> dict:
        config = await self.get_app_config(mask=False)
        return config.get("telegram", {})

    async def localization_config(self) -> dict:
        config = await self.get_app_config(mask=False)
        return config.get("localization", {})


def _deep_merge(base: dict, patch: dict) -> dict:
    result = dict(base)
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


SENSITIVE_FIELDS = {"password", "secretKey", "clientSecret", "botToken"}


def _mask_config(data, write: bool = False):
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in SENSITIVE_FIELDS and isinstance(value, str):
                if write:
                    if value and not value.startswith("***"):
                        result[key] = value
                    continue
                result[key] = "***" if value else ""
                continue
            result[key] = _mask_config(value, write)
        return result
    if isinstance(data, list):
        return [_mask_config(item, write) for item in data]
    return data


def _default_app_info() -> dict:
    return {
        "applicationName": "HollyWing Motor",
        "shortName": "HollyWing",
        "businessName": "HollyWing Motor Rental",
        "description": "Motorcycle rental management",
        "supportEmail": "",
        "supportPhone": "",
        "website": "",
        "address": "Phnom Penh, Cambodia",
        "branding": {"primaryColor": "#e8472a", "secondaryColor": "#3a539f"},
        "footer": {"copyrightText": "© HollyWing Motor"},
        "updatedAt": utcnow().isoformat(),
    }


def _default_app_config() -> dict:
    return {
        "general": {
            "defaultLandingPage": "/",
            "defaultPageSize": 20,
            "defaultRecordView": "table",
            "enableComments": False,
            "enableSharing": False,
            "enableExport": True,
            "maxUploadSizeMb": 10,
        },
        "localization": {
            "defaultLanguage": "en",
            "availableLanguages": ["en", "km"],
            "timezone": "Asia/Phnom_Penh",
            "dateFormat": "DD/MM/YYYY",
            "timeFormat": "HH:mm",
            "firstDayOfWeek": 1,
            "numberFormat": "1,234.56",
            "currency": "USD",
            "locale": "en-US",
        },
        "email": {
            "enabled": False,
            "smtpHost": "",
            "smtpPort": 587,
            "username": "",
            "password": "",
            "encryption": "tls",
            "fromName": "HollyWing Motor",
            "fromEmail": "",
            "timeoutSeconds": 15,
            "connectionStatus": "not_tested",
        },
        "telegram": {
            "enabled": True,
            "botDisplayName": "HollyWing Bot",
            "botToken": "",
            "connectionMode": "bot_api",
            "messageLanguage": "en",
            "interactiveGroupEnabled": False,
            "interactiveGroupId": "",
            "allowedModules": {
                "finance": False,
                "motorcycles": True,
                "customers": False,
                "rentals": True,
            },
            "sensitiveFields": {
                "customerName": False,
                "customerPhone": False,
                "financialTotals": False,
                "rentalBalances": False,
            },
            "notifyNewRental": True,
            "notifyOverdueRental": True,
            "notifyRentalCompleted": True,
            "notifyPayment": True,
            "notifyCharge": True,
            "notifyExpense": True,
            "deadlineReminderEnabled": True,
            "deadlineReminderValue": 1,
            "deadlineReminderUnit": "hours",
            "passwordResetEnabled": True,
            "connectionStatus": "not_tested",
            "destinations": [],
            "userAccess": [],
        },
        "notifications": {
            "inAppEnabled": True,
            "emailEnabled": False,
            "telegramEnabled": True,
            "deliveryRetries": 5,
            "language": "en",
            "rules": [],
        },
        "security": {
            "sessionTimeoutMinutes": 60,
            "maxLoginAttempts": 10,
            "accountLockMinutes": 15,
            "passwordResetChannel": "telegram",
            "passwordResetCodeExpiryMinutes": 10,
            "jwtAccessTokenMinutes": settings.access_token_expire_minutes,
            "jwtRefreshTokenDays": settings.refresh_token_expire_days,
        },
        "system": {
            "maintenanceMode": False,
            "readOnlyMode": False,
            "paginationDefault": 20,
            "configurationVersion": "1.0.0",
            "environment": settings.environment,
            "cacheStatus": "unknown",
            "backgroundJobStatus": "unknown",
        },
        "updatedAt": utcnow().isoformat(),
    }


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.motorcycles = MotorcycleRepository(session)
        self.rentals = RentalRepository(session)
        self.payments = PaymentRepository(session)
        self.expenses = ExpenseRepository(session)
        self.customers = CustomerRepository(session)

    async def summary(self, start: datetime | None, end: datetime | None) -> dict:
        range_key = f"{start.date().isoformat() if start else 'all'}:{end.date().isoformat() if end else 'all'}"
        cache_key = f"{DASHBOARD_CACHE_PREFIX}{hashlib.sha1(range_key.encode()).hexdigest()}"
        cached = await cache.get_json(cache_key)
        if cached is not None:
            return cached

        moto_counts = await self.motorcycles.status_counts()
        rental_counts = await self.rentals.status_counts()
        income = await self.payments.sum_between(start, end)
        expense = await self.expenses.sum_between(start, end)

        outstanding_result = await self.session.execute(
            select(func.coalesce(func.sum(Rental.outstanding), 0)).where(Rental.status.in_(["Active", "Overdue", "Completed"]))
        )
        outstanding = Decimal(str(outstanding_result.scalar() or 0))

        rentals_by_day: list[dict] = []
        income_by_day: list[dict] = []
        expense_by_day: list[dict] = []
        if start and end:
            series_start = start
            day_counts = {
                row[0]: int(row[1])
                for row in (
                    await self.session.execute(
                        select(func.date(Rental.start_date), func.count())
                        .where(Rental.start_date >= start, Rental.start_date <= end)
                        .group_by(func.date(Rental.start_date))
                    )
                ).all()
            }
            income_map = {day: float(amount) for day, amount in await self.payments.daily_series(start, end)}
            expense_map = {day: float(amount) for day, amount in await self.expenses.daily_series(start, end)}
            cursor = series_start.date()
            while cursor <= end.date():
                key = cursor.isoformat()
                rentals_by_day.append({"date": key, "count": day_counts.get(key, 0)})
                income_by_day.append({"date": key, "amount": income_map.get(key, 0.0)})
                expense_by_day.append({"date": key, "amount": expense_map.get(key, 0.0)})
                cursor += timedelta(days=1)

        result = {
            "motorcycleStatus": moto_counts,
            "rentalsActive": rental_counts.get("Active", 0),
            "rentalsOverdue": rental_counts.get("Overdue", 0),
            "rentalsCompleted": rental_counts.get("Completed", 0),
            "income": float(income),
            "expense": float(expense),
            "netIncome": float(income - expense),
            "outstanding": float(outstanding),
            "rentalsByDay": rentals_by_day,
            "incomeByDay": income_by_day,
            "expenseByDay": expense_by_day,
            "startDate": start.date().isoformat() if start else None,
            "endDate": end.date().isoformat() if end else None,
        }
        await cache.set_json(cache_key, result, settings.dashboard_cache_ttl_seconds)
        return result

    async def invalidate(self) -> None:
        await cache.delete_prefix(DASHBOARD_CACHE_PREFIX)


def default_document_sequences() -> list[dict]:
    return [
        {"document_type": "RENTAL", "prefix": "RNT", "padding_length": 6, "year": datetime.now(timezone.utc).year},
        {"document_type": "PAYMENT", "prefix": "RNP", "padding_length": 6},
        {"document_type": "CHARGE", "prefix": "RNC", "padding_length": 6},
        {"document_type": "EXPENSE", "prefix": "RNX", "padding_length": 6},
        {"document_type": "CUSTOMER", "prefix": "CUS", "padding_length": 3},
        {"document_type": "MOTORCYCLE", "prefix": "MC", "padding_length": 3},
    ]

