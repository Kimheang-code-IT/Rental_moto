from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    envelope,
    get_actor_or_service,
    get_db_session,
    get_redis_dep,
    get_service_principal,
    get_telegram_headers,
    parse_date_range,
    require_permission,
)
from app.core.errors import AccessDeniedError, ValidationError
from app.core.permissions import user_has_permission
from app.services.admin_service import SettingService
from app.services.auth_service import AuthService
from app.services.reports_service import TransactionsReportService
from app.services.telegram_context import build_telegram_context
from app.services.telegram_report_service import TelegramReportService
from app.services.telegram_service import TelegramNotificationService
from app.utils.dates import parse_period

router = APIRouter(prefix="/telegram", tags=["telegram"])

TELEGRAM_LOCALIZATION_KEYS = (
    "defaultLanguage",
    "timezone",
    "dateFormat",
    "timeFormat",
    "numberFormat",
    "currency",
    "locale",
)


def _require_user_actor_permission(actor, permission: str) -> None:
    if isinstance(actor, dict):
        return
    if not user_has_permission(actor, permission):
        raise AccessDeniedError(f"Missing permission: {permission}")


async def _period_range(period: str, start: str | None, end: str | None) -> tuple[datetime, datetime]:
    if start or end:
        parsed_start, parsed_end = parse_date_range(start, end)
        if parsed_start is None or parsed_end is None:
            raise ValidationError("Both start and end dates are required for custom ranges")
        return parsed_start, parsed_end
    try:
        return parse_period(period)
    except ValueError as exc:
        raise ValidationError(str(exc))


async def _ctx_reports(
    headers=Depends(get_telegram_headers),
    _service=Depends(get_service_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings_svc = SettingService(session)
    config = await settings_svc.get_app_config(mask=False)
    return await build_telegram_context(
        session,
        headers.user_id,
        headers.chat_id,
        headers.chat_type,
        config.get("telegram") or {},
        config.get("localization") or {},
        require_linked=True,
    )


async def _ctx_access(
    headers=Depends(get_telegram_headers),
    _service=Depends(get_service_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings_svc = SettingService(session)
    config = await settings_svc.get_app_config(mask=False)
    return await build_telegram_context(
        session,
        headers.user_id,
        headers.chat_id,
        headers.chat_type,
        config.get("telegram") or {},
        config.get("localization") or {},
        require_linked=False,
    )


@router.get("/access")
async def access(
    ctx=Depends(_ctx_access),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = TelegramReportService(session, ctx)
    return envelope(service.access_payload())


@router.get("/localization")
async def telegram_localization(
    _service=Depends(get_service_principal),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Expose only safe display settings required by the standalone bot."""
    config = await SettingService(session).get_app_config(mask=False)
    localization = config.get("localization") or {}
    return envelope({key: localization.get(key) for key in TELEGRAM_LOCALIZATION_KEYS})


@router.get("/income")
async def income(
    period: str = "today",
    start: str | None = None,
    end: str | None = None,
    page: int = 1,
    limit: int = 10,
    ctx=Depends(_ctx_reports),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    range_start, range_end = await _period_range(period, start, end)
    service = TelegramReportService(session, ctx)
    data = await service.income(range_start, range_end, page, limit)
    return envelope(
        data["items"],
        {
            "page": data["page"],
            "limit": data["limit"],
            "total": data["total"],
            "totalAmount": data.get("totalAmount"),
            "startDate": range_start.isoformat(),
            "endDate": range_end.isoformat(),
        },
    )


@router.get("/expenses")
async def expenses(
    period: str = "today",
    start: str | None = None,
    end: str | None = None,
    page: int = 1,
    limit: int = 10,
    ctx=Depends(_ctx_reports),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    range_start, range_end = await _period_range(period, start, end)
    service = TelegramReportService(session, ctx)
    data = await service.expenses(range_start, range_end, page, limit)
    return envelope(
        data["items"],
        {
            "page": data["page"],
            "limit": data["limit"],
            "total": data["total"],
            "totalAmount": data.get("totalAmount"),
            "startDate": range_start.isoformat(),
            "endDate": range_end.isoformat(),
        },
    )


@router.get("/motorcycles")
async def motorcycles_report(
    view: str = "all",
    page: int = 1,
    limit: int = 10,
    ctx=Depends(_ctx_reports),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = TelegramReportService(session, ctx)
    data = await service.motorcycles(view, page, limit)
    return envelope(
        data["items"],
        {"page": data["page"], "limit": data["limit"], "total": data["total"], "counts": data.get("counts", {})},
    )


@router.get("/customers")
async def customers_report(
    view: str = "all",
    period: str = "all",
    start: str | None = None,
    end: str | None = None,
    page: int = 1,
    limit: int = 10,
    ctx=Depends(_ctx_reports),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    range_start, range_end = await _period_range(period, start, end)
    service = TelegramReportService(session, ctx)
    data = await service.customers(view, range_start, range_end, page, limit)
    return envelope(
        data["items"],
        {
            "page": data["page"],
            "limit": data["limit"],
            "total": data["total"],
            "startDate": range_start.isoformat(),
            "endDate": range_end.isoformat(),
        },
    )


@router.get("/rentals")
async def rentals_report(
    view: str = "all",
    period: str = "all",
    start: str | None = None,
    end: str | None = None,
    page: int = 1,
    limit: int = 10,
    ctx=Depends(_ctx_reports),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    range_start, range_end = await _period_range(period, start, end)
    service = TelegramReportService(session, ctx)
    data = await service.rentals(view, range_start, range_end, page, limit)
    return envelope(
        data["items"],
        {
            "page": data["page"],
            "limit": data["limit"],
            "total": data["total"],
            "startDate": range_start.isoformat(),
            "endDate": range_end.isoformat(),
        },
    )


@router.post("/password-reset/request")
async def password_reset_request(
    ctx=Depends(_ctx_access),
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    if ctx.mode != "private" or ctx.user is None:
        raise AccessDeniedError("Password reset is only available in a linked private chat")
    service = AuthService(session, redis)
    code = await service.telegram_request_password_reset(ctx.user)
    return envelope({"message": "If eligible, a reset code has been sent", "delivered": bool(code)})


@router.post("/password-reset/verify")
async def password_reset_verify(
    body: dict,
    ctx=Depends(_ctx_access),
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    if ctx.mode != "private" or ctx.user is None:
        raise AccessDeniedError("Password reset is only available in a linked private chat")
    code = str(body.get("code") or "")
    service = AuthService(session, redis)
    handoff = await service.telegram_verify_reset_code(ctx.user, code)
    return envelope({"handoffToken": handoff["token"], "expiresIn": handoff["expires_in"]})


# Legacy service-JWT routes (kept for backward compatibility)
@router.get("/transactions")
async def transactions(
    period: str = "today",
    start: str | None = None,
    end: str | None = None,
    page: int = 1,
    limit: int = 10,
    actor=Depends(get_actor_or_service),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_user_actor_permission(actor, "reports.view")
    range_start, range_end = await _period_range(period, start, end)
    report = TransactionsReportService(session)
    data = await report.transactions(range_start, range_end, page, limit)
    return envelope(
        data["items"],
        {
            "page": data["page"],
            "limit": data["limit"],
            "total": data["total"],
            "startDate": range_start.isoformat(),
            "endDate": range_end.isoformat(),
        },
    )


@router.get("/motorcycle-status")
async def motorcycle_status(
    actor=Depends(get_actor_or_service),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_user_actor_permission(actor, "rental.motorcycles.view")
    report = TransactionsReportService(session)
    return envelope(await report.motorcycle_status())


@router.get("/finance-summary")
async def finance_summary(
    period: str = "today",
    start: str | None = None,
    end: str | None = None,
    ctx=Depends(_ctx_reports),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    range_start, range_end = await _period_range(period, start, end)
    service = TelegramReportService(session, ctx)
    return envelope(await service.finance_summary(range_start, range_end))


@router.post("/send-test")
async def send_test(
    body: dict | None = None,
    actor=Depends(require_permission("settings.app_config.configure")),
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    body = body or {}
    service = TelegramNotificationService(session, redis)
    message = body.get("message") or "HollyWing Motor test message"
    chat_id = body.get("chatId")
    ok = await service.send_direct(chat_id=chat_id, message=message)
    return envelope(
        {
            "status": "connected" if ok else "failed",
            "message": "Test message sent" if ok else "Telegram delivery failed",
        }
    )


@router.post("/link")
async def link_chat(
    body: dict,
    actor=Depends(get_service_principal),
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    code = str(body.get("code") or "")
    telegram_user_id = str(body.get("telegramUserId") or body.get("telegram_user_id") or "")
    telegram_chat_id = str(body.get("telegramChatId") or body.get("telegram_chat_id") or "")
    if not code or not telegram_user_id or not telegram_chat_id:
        raise ValidationError("code, telegramUserId and telegramChatId are required")
    service = AuthService(session, redis)
    user = await service.consume_link_code(code, telegram_user_id, telegram_chat_id)
    return envelope({"linked": True, "user": {"id": user.id, "email": user.email, "name": user.display_name}})
