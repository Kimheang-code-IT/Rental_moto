"""Telegram bot request context, settings, and authorization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AccessDeniedError, ValidationError
from app.core.permissions import effective_permissions, user_has_permission
from app.models import User
from app.repositories.admin import UserRepository

DEADLINE_REMINDER_UNITS = {"minutes", "hours", "days"}

DEFAULT_DESTINATION_EVENTS = [
    "rental_created",
    "rental_overdue",
    "rental_completed",
    "payment_recorded",
    "charge_recorded",
    "expense_recorded",
    "deadline_approaching",
]

MODULE_PERMISSIONS = {
    "finance": "rental.finance.view",
    "motorcycles": "rental.motorcycles.view",
    "customers": "rental.customers.view",
    "rentals": "rental.rentals.view",
}

DEFAULT_ALLOWED_MODULES = {
    "finance": False,
    "motorcycles": True,
    "customers": False,
    "rentals": True,
}

DEFAULT_SENSITIVE_FIELDS = {
    "customerName": False,
    "customerPhone": False,
    "financialTotals": False,
    "rentalBalances": False,
}

NOTIFICATION_EVENTS_EXCLUDE_RESET = {
    "password_reset_requested",
}


@dataclass
class TelegramSensitivePolicy:
    customer_name: bool = False
    customer_phone: bool = False
    financial_totals: bool = False
    rental_balances: bool = False

    @classmethod
    def from_config(cls, raw: dict | None) -> TelegramSensitivePolicy:
        data = raw or {}
        return cls(
            customer_name=bool(data.get("customerName", False)),
            customer_phone=bool(data.get("customerPhone", False)),
            financial_totals=bool(data.get("financialTotals", False)),
            rental_balances=bool(data.get("rentalBalances", False)),
        )


@dataclass
class TelegramRequestContext:
    telegram_user_id: str
    telegram_chat_id: str
    chat_type: Literal["private", "group", "supergroup", "channel"]
    mode: Literal["private", "group"]
    user: User | None = None
    permissions: list[str] = field(default_factory=list)
    allowed_modules: dict[str, bool] = field(default_factory=dict)
    sensitive: TelegramSensitivePolicy = field(default_factory=TelegramSensitivePolicy)
    localization: dict = field(default_factory=dict)
    denied_reason: str | None = None

    def can_module(self, module: str) -> bool:
        return bool(self.allowed_modules.get(module, False))

    def require_module(self, module: str) -> None:
        if not self.can_module(module):
            raise AccessDeniedError(f"Module not allowed: {module}")


def normalize_telegram_config(config: dict | None) -> dict:
    cfg = dict(config or {})
    allowed = {**DEFAULT_ALLOWED_MODULES, **(cfg.get("allowedModules") or {})}
    sensitive = {**DEFAULT_SENSITIVE_FIELDS, **(cfg.get("sensitiveFields") or {})}
    cfg["allowedModules"] = allowed
    cfg["sensitiveFields"] = sensitive
    cfg.setdefault("interactiveGroupEnabled", False)
    cfg.setdefault("interactiveGroupId", "")
    cfg.setdefault("destinations", [])
    cfg.setdefault("userAccess", [])
    cfg.setdefault("deadlineReminderEnabled", True)
    cfg.setdefault("deadlineReminderValue", 1)
    cfg.setdefault("deadlineReminderUnit", "hours")
    chat_id = str(cfg.get("chatId") or "").strip()
    if chat_id:
        cfg["interactiveGroupId"] = chat_id
        cfg["interactiveGroupEnabled"] = True
        _sync_main_destination(cfg, chat_id)
    return cfg


def telegram_ids_equal(left: str | int | None, right: str | int | None) -> bool:
    """Match Telegram/user IDs across int/string and optional -100 supergroup prefix."""
    if left is None or right is None:
        return False
    left_raw = str(left).strip()
    right_raw = str(right).strip()
    if not left_raw or not right_raw:
        return False
    return bool(_id_variants(left_raw) & _id_variants(right_raw))


def _id_variants(value: str) -> set[str]:
    variants = {value}
    try:
        variants.add(str(int(value)))
    except (TypeError, ValueError):
        pass
    if value.startswith("-100") and value[4:].isdigit():
        variants.add("-" + value[4:])
    elif value.startswith("-") and value[1:].isdigit() and not value.startswith("-100"):
        variants.add("-100" + value[1:])
    return variants


def _denied_message(exc: AccessDeniedError) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("message") or "Access denied")
    return str(detail or "Access denied")


def _sync_main_destination(cfg: dict, chat_id: str) -> None:
    """Keep a default notification destination aligned with the configured group ID."""
    destinations = list(cfg.get("destinations") or [])
    main = next((item for item in destinations if telegram_ids_equal(item.get("chatId"), chat_id)), None)
    if main is None:
        destinations.insert(
            0,
            {
                "id": "main-group",
                "name": "Main Group",
                "type": "group",
                "chatId": chat_id,
                "enabled": True,
                "enabledEvents": list(DEFAULT_DESTINATION_EVENTS),
                "status": "not_tested",
                "isInteractiveGroup": True,
            },
        )
    else:
        main["enabled"] = True
        main["isInteractiveGroup"] = True
        existing = [str(event) for event in (main.get("enabledEvents") or []) if event]
        for event in DEFAULT_DESTINATION_EVENTS:
            if event not in existing:
                existing.append(event)
        main["enabledEvents"] = existing
    for dest in destinations:
        if not telegram_ids_equal(dest.get("chatId"), chat_id):
            dest["isInteractiveGroup"] = False
    cfg["destinations"] = destinations


def _interactive_group_chat_ids(config: dict) -> set[str]:
    ids: set[str] = set()
    root_id = str(config.get("interactiveGroupId") or "").strip()
    if config.get("interactiveGroupEnabled") and root_id:
        ids.add(root_id)
    for dest in config.get("destinations") or []:
        if dest.get("isInteractiveGroup") and dest.get("enabled", True):
            chat_id = str(dest.get("chatId") or "").strip()
            if chat_id:
                ids.add(chat_id)
    return ids


def _find_user_access(cfg: dict, *, user_id: int | None = None, chat_id: str | None = None) -> dict | None | bool:
    rows = cfg.get("userAccess") or []
    if not rows:
        return None
    for row in rows:
        if user_id is not None and telegram_ids_equal(row.get("userId"), user_id):
            return row
        if chat_id and telegram_ids_equal(row.get("chatId"), chat_id):
            return row
    return False


def _require_private_user_access(cfg: dict, user: User, telegram_chat_id: str) -> None:
    match = _find_user_access(cfg, user_id=user.id, chat_id=telegram_chat_id)
    if match is None:
        return
    if match is False or not match.get("chatbotEnabled", True):
        raise AccessDeniedError("Private chatbot access is disabled for this user")


async def _require_group_user_access(session: AsyncSession, cfg: dict, telegram_user_id: str) -> None:
    rows = cfg.get("userAccess") or []
    if not rows:
        return
    users = UserRepository(session)
    user = await users.get_by_telegram_user_id(telegram_user_id)
    if user is None:
        raise AccessDeniedError("This Telegram user is not authorized for group access")
    match = _find_user_access(cfg, user_id=user.id, chat_id=user.telegram_chat_id)
    if match is False or not match.get("groupEnabled", True):
        raise AccessDeniedError("Group chatbot access is disabled for this user")


def validate_telegram_config(config: dict) -> None:
    """Reject more than one enabled interactive group destination."""
    if len(_interactive_group_chat_ids(config)) > 1:
        raise ValidationError("Only one interactive Telegram group may be enabled")
    try:
        reminder_value = int(config.get("deadlineReminderValue", 1))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Deadline reminder duration must be a whole number") from exc
    if not 1 <= reminder_value <= 10_080:
        raise ValidationError("Deadline reminder duration must be between 1 and 10080")
    if config.get("deadlineReminderUnit", "hours") not in DEADLINE_REMINDER_UNITS:
        raise ValidationError("Deadline reminder unit must be minutes, hours, or days")


def resolve_interactive_group_id(config: dict) -> str | None:
    cfg = normalize_telegram_config(config)
    if cfg.get("interactiveGroupEnabled") and cfg.get("interactiveGroupId"):
        return str(cfg["interactiveGroupId"]).strip() or None
    for dest in cfg.get("destinations") or []:
        if dest.get("isInteractiveGroup") and dest.get("enabled", True) and dest.get("chatId"):
            return str(dest["chatId"]).strip()
    return None


async def build_telegram_context(
    session: AsyncSession,
    telegram_user_id: str,
    telegram_chat_id: str,
    chat_type: str,
    telegram_config: dict,
    localization: dict | None = None,
    require_linked: bool = True,
) -> TelegramRequestContext:
    cfg = normalize_telegram_config(telegram_config)
    chat_type_norm = (chat_type or "private").lower()
    if chat_type_norm not in ("private", "group", "supergroup", "channel"):
        raise ValidationError("Invalid Telegram chat type")

    loc = localization or {}
    sensitive = TelegramSensitivePolicy.from_config(cfg.get("sensitiveFields"))

    def denied(
        mode: Literal["private", "group"],
        reason: str | None = None,
        user: User | None = None,
    ) -> TelegramRequestContext:
        return TelegramRequestContext(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            chat_type=chat_type_norm,  # type: ignore[arg-type]
            mode=mode,
            user=user,
            permissions=[],
            allowed_modules={key: False for key in MODULE_PERMISSIONS},
            sensitive=sensitive,
            localization=loc,
            denied_reason=reason,
        )

    if chat_type_norm == "private":
        users = UserRepository(session)
        user = await users.get_by_telegram_ids(telegram_user_id, telegram_chat_id)
        if user is None or user.status != "Active":
            if require_linked:
                raise AccessDeniedError("Telegram account is not linked to an active user")
            return denied("private")
        try:
            _require_private_user_access(cfg, user, telegram_chat_id)
        except AccessDeniedError as exc:
            if require_linked:
                raise
            return denied("private", _denied_message(exc), user=user)
        perms = effective_permissions(user)
        allowed = {
            key: user_has_permission(user, perm)
            for key, perm in MODULE_PERMISSIONS.items()
        }
        return TelegramRequestContext(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            chat_type=chat_type_norm,  # type: ignore[arg-type]
            mode="private",
            user=user,
            permissions=perms,
            allowed_modules=allowed,
            sensitive=sensitive,
            localization=loc,
        )

    if chat_type_norm not in ("group", "supergroup"):
        reason = "Reports are only available in private or configured group chats"
        if require_linked:
            raise AccessDeniedError(reason)
        return denied("private", reason)

    authorized_ids = _interactive_group_chat_ids(cfg)
    if not any(telegram_ids_equal(telegram_chat_id, group_id) for group_id in authorized_ids):
        reason = "This Telegram group is not authorized"
        if require_linked:
            raise AccessDeniedError(reason)
        return denied("group", reason)

    try:
        await _require_group_user_access(session, cfg, telegram_user_id)
    except AccessDeniedError as exc:
        if require_linked:
            raise
        return denied("group", _denied_message(exc))

    allowed = dict(cfg.get("allowedModules") or DEFAULT_ALLOWED_MODULES)
    sensitive = TelegramSensitivePolicy.from_config(cfg.get("sensitiveFields"))
    return TelegramRequestContext(
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        chat_type=chat_type_norm,  # type: ignore[arg-type]
        mode="group",
        user=None,
        permissions=[],
        allowed_modules=allowed,
        sensitive=sensitive,
        localization=loc,
    )


def mask_phone(value: str | None) -> str:
    raw = str(value or "").strip()
    if len(raw) <= 4:
        return "***"
    return f"{raw[:3]} XXX XXX"


def apply_sensitive_row(ctx: TelegramRequestContext, row: dict) -> dict:
    """Redact configured fields before formatting bot responses."""
    out = dict(row)
    s = ctx.sensitive
    if not s.customer_name and "customer" in out:
        out["customer"] = "***"
    if not s.customer_phone and "phone" in out:
        out["phone"] = mask_phone(str(out.get("phone") or ""))
    money_keys = ("amount", "total", "totalDue", "paid", "outstanding", "balance", "income", "expense", "net")
    if not s.financial_totals:
        for key in money_keys:
            if key in out:
                out[key] = None
    if not s.rental_balances:
        for key in ("outstanding", "balance", "paid"):
            if key in out:
                out[key] = None
    return out
