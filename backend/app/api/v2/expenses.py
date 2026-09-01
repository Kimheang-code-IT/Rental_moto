from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, parse_date_range, require_permission
from app.core.errors import NotFoundError
from app.repositories.rental import ExpenseRepository
from app.schemas.rental import ExpenseRecordRequest, ExpenseResponse, ExpenseUpdateRequest
from app.services.admin_service import DashboardService
from app.services.rental_service import RentalService

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _to_dict(expense) -> dict:
    return ExpenseResponse.model_validate(expense).model_dump(by_alias=True)


@router.get("")
async def list_expenses(
    params: ListParams = Depends(),
    expense_type: str | None = None,
    user=Depends(require_permission("rental.finance.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(params.start_date, params.end_date)
    result = await ExpenseRepository(session).list(params.q, params.page, params.limit, params.sort, expense_type, start, end)
    return envelope([_to_dict(e) for e in result.items], result.meta)


@router.get("/{expense_id}")
async def get_expense(
    expense_id: str,
    user=Depends(require_permission("rental.finance.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    expense = await ExpenseRepository(session).get(expense_id)
    if expense is None:
        raise NotFoundError("Expense not found")
    return envelope(_to_dict(expense))


@router.post("", status_code=201)
async def record_expense(
    body: ExpenseRecordRequest,
    user=Depends(require_permission("rental.finance.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = RentalService(session, user)
    expense = await service.record_expense(body)
    await DashboardService(session).invalidate()
    return envelope(_to_dict(expense))


@router.put("/{expense_id}")
async def update_expense(
    expense_id: str,
    body: ExpenseUpdateRequest,
    user=Depends(require_permission("rental.finance.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = ExpenseRepository(session)
    expense = await repo.get(expense_id)
    if expense is None:
        raise NotFoundError("Expense not found")
    updates = body.model_dump(exclude_unset=True, by_alias=False)
    for field, value in updates.items():
        setattr(expense, field, value)
    await session.commit()
    await DashboardService(session).invalidate()
    return envelope(_to_dict(expense))


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: str,
    user=Depends(require_permission("rental.finance.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = ExpenseRepository(session)
    expense = await repo.get(expense_id)
    if expense is None:
        raise NotFoundError("Expense not found")
    await repo.delete(expense)
    await session.commit()
    await DashboardService(session).invalidate()
    return envelope({"deleted": True})
