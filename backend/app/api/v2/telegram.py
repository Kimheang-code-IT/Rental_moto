from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    envelope,
    get_actor_or_service,
    get_current_user,
    get_db_session,
    get_redis_dep,
    get_service_principal,
    parse_date_range,
)
from app.core.errors import ValidationError
from app.services.admin_service import DashboardService
from app.services.reports_service import TransactionsReportService
from app.services.telegram_service import TelegramNotificationService
from app.utils.dates import parse_period

router = APIRouter(prefix="/telegram", tags=["telegram"])


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
    report = TransactionsReportService(session)
    return envelope(await report.motorcycle_status())


@router.get("/finance-summary")
async def finance_summary(
    period: str = "today",
    start: str | None = None,
    end: str | None = None,
    actor=Depends(get_actor_or_service),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    range_start, range_end = await _period_range(period, start, end)
    dashboard = DashboardService(session)
    summary = await dashboard.summary(range_start, range_end)
    return envelope(summary)


@router.post("/send-test")
async def send_test(
    body: dict | None = None,
    actor=Depends(get_current_user),
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
    from app.services.auth_service import AuthService

    code = str(body.get("code") or "")
    telegram_user_id = str(body.get("telegramUserId") or body.get("telegram_user_id") or "")
    telegram_chat_id = str(body.get("telegramChatId") or body.get("telegram_chat_id") or "")
    if not code or not telegram_user_id or not telegram_chat_id:
        raise ValidationError("code, telegramUserId and telegramChatId are required")
    service = AuthService(session, redis)
    user = await service.consume_link_code(code, telegram_user_id, telegram_chat_id)
    return envelope({"linked": True, "user": {"id": user.id, "email": user.email, "name": user.display_name}})
