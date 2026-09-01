from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import envelope, get_db_session, parse_date_range, require_permission
from app.services.admin_service import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(
    start_date: str | None = None,
    end_date: str | None = None,
    user=Depends(require_permission("dashboard.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(start_date, end_date)
    service = DashboardService(session)
    summary = await service.summary(start, end)
    return envelope(summary)


@router.get("/finance/summary")
async def finance_summary(
    start_date: str | None = None,
    end_date: str | None = None,
    user=Depends(require_permission("rental.finance.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(start_date, end_date)
    service = DashboardService(session)
    summary = await service.summary(start, end)
    return envelope(
        {
            "income": summary["income"],
            "expense": summary["expense"],
            "net": summary["netIncome"],
            "outstanding": summary["outstanding"],
            "startDate": summary["startDate"],
            "endDate": summary["endDate"],
        }
    )
