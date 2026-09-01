from __future__ import annotations
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
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

    def _require_admin(self) -> None:
        from app.core.permissions import has_permission, is_super_admin

        if self.actor is None:
            raise AccessDeniedError()
        if not is_super_admin(self.actor.role, self.actor.permissions):
            if not has_permission(self.actor.role, self.actor.permissions, "user.manage"):
                raise AccessDeniedError("You do not have permission to manage users")

    async def list(self, q, page, limit):
        self._require_admin()
        return await self.repo.list(q, page, limit)

    async def get(self, user_id: int) -> User:
        self._require_admin()
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def create(self, data) -> User:
        self._require_admin()
        if await self.repo.get_by_email(data.email):
            raise ConflictError(f"Email {data.email} is already registered")
        if await self.repo.get_by_username(data.username):
            raise ConflictError(f"Username {data.username} is already taken")
        role = await self.roles.get_by_name(data.role)
        user = User(
            username=data.username,
            display_name=data.display_name,
            email=data.email.lower(),
            password_hash=hash_password(data.password),
            role=data.role,
            role_id=role.id if role else None,
            status=data.status,
            permissions=data.permissions,
            page_access=data.page_access,
            avatar_url=data.avatar,
        )
        await self.repo.create(user)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="user_created",
                entity_type="user",
                entity_id=str(user.id),
                entity_label=user.email,
            )
        )
        await self.session.commit()
        return user

    async def update(self, user_id: int, data) -> User:
        self._require_admin()
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        updates = data.model_dump(exclude_unset=True, by_alias=False)
        if updates.get("email") and updates["email"].lower() != user.email.lower():
            other = await self.repo.get_by_email(updates["email"])
            if other is not None and other.id != user.id:
                raise ConflictError(f"Email {updates['email']} is already registered")
        if updates.get("username") and updates["username"].lower() != user.username.lower():
            other = await self.repo.get_by_username(updates["username"])
            if other is not None and other.id != user.id:
                raise ConflictError(f"Username {updates['username']} is already taken")
        if updates.get("password"):
            user.password_hash = hash_password(updates.pop("password"))
            user.password_changed_at = utcnow()
        role_name = updates.pop("role", None)
        if role_name:
            user.role = role_name
            role = await self.roles.get_by_name(role_name)
            user.role_id = role.id if role else None
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
            )
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: int) -> None:
        self._require_admin()
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if self.actor and user.id == self.actor.id:
            raise ConflictError("You cannot delete your own account")
        if user.role == "SuperAdmin" and (await self._super_admin_count()) <= 1:
            raise ConflictError("Cannot delete the last SuperAdmin account")
        await self.repo.delete(user)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="user_deleted",
                entity_type="user",
                entity_id=str(user_id),
                entity_label=user.email,
            )
        )
        await self.session.commit()

    async def _super_admin_count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User).where(User.role == "SuperAdmin"))
        return int(result.scalar() or 0)


class RoleService:
    def __init__(self, session: AsyncSession, actor: User | None = None) -> None:
        self.session = session
        self.repo = RoleRepository(session)
        self.audit = AuditRepository(session)
        self.actor = actor

    def _require_admin(self) -> None:
        from app.core.permissions import has_permission, is_super_admin

        if self.actor is None or not (
            is_super_admin(self.actor.role, self.actor.permissions) or has_permission(self.actor.role, self.actor.permissions, "role.manage")
        ):
            raise AccessDeniedError("You do not have permission to manage roles")

    async def list(self, q, page, limit):
        self._require_admin()
        return await self.repo.list(q, page, limit)

    async def create(self, data) -> Role:
        self._require_admin()
        if await self.repo.get_by_name(data.name):
            raise ConflictError(f"Role {data.name} already exists")
        role = Role(
            name=data.name,
            description=data.description,
            permissions=data.permissions,
            page_access=data.page_access,
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
            )
        )
        await self.session.commit()
        return role

    async def update(self, role_id: int, data) -> Role:
        self._require_admin()
        role = await self.repo.get(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        updates = data.model_dump(exclude_unset=True, by_alias=False)
        if updates.get("name") and updates["name"].lower() != role.name.lower():
            other = await self.repo.get_by_name(updates["name"])
            if other is not None and other.id != role.id:
                raise ConflictError(f"Role {updates['name']} already exists")
        for field, value in updates.items():
            setattr(role, field, value)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="role_updated",
                entity_type="role",
                entity_id=str(role.id),
                entity_label=role.name,
            )
        )
        await self.session.commit()
        await self.session.refresh(role)
        return role

    async def delete(self, role_id: int) -> None:
        self._require_admin()
        role = await self.repo.get(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        if role.is_system:
            raise ConflictError("System roles cannot be deleted")
        if (await self.repo.users_with_role(role.name)) > 0:
            raise ConflictError("Role is assigned to users and cannot be deleted")
        await self.repo.delete(role)
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

    async def get_app_config(self, mask: bool = True) -> dict:
        cached = await cache.get_json(f"{SETTINGS_CACHE_PREFIX}app-config")
        if cached is not None:
            return cached
        value = await self.repo.get_value("app_config")
        result = value or _default_app_config()
        await cache.set_json(f"{SETTINGS_CACHE_PREFIX}app-config", result, settings.settings_cache_ttl_seconds)
        return _mask_config(result) if mask else result

    async def update_app_config(self, patch: dict) -> dict:
        current = await self.repo.get_value("app_config") or _default_app_config()
        merged = _deep_merge(current, _mask_config(patch, write=True))
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
            "notifyNewRental": True,
            "notifyOverdueRental": True,
            "notifyRentalCompleted": True,
            "notifyPayment": True,
            "notifyCharge": True,
            "notifyExpense": True,
            "passwordResetEnabled": True,
            "connectionStatus": "not_tested",
            "destinations": [],
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
            cursor = series_start.date()
            while cursor <= end.date():
                key = cursor.isoformat()
                rentals_by_day.append({"date": key, "count": day_counts.get(key, 0)})
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

