from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, parse_date_range, require_permission
from app.core.errors import NotFoundError
from app.repositories.rental import ChargeRepository, RentalRepository
from app.schemas.rental import ChargeRecordRequest, ChargeResponse, ChargeUpdateRequest
from app.services.admin_service import DashboardService
from app.services.rental_service import RentalService

router = APIRouter(prefix="/charges", tags=["charges"])


def _to_dict(charge, rental_no: str | None = None, customer: str | None = None) -> dict:
    data = ChargeResponse.model_validate(charge).model_dump(by_alias=True)
    if rental_no:
        data["rentalNo"] = rental_no
    if customer:
        data["customer"] = customer
    return data


@router.get("")
async def list_charges(
    params: ListParams = Depends(),
    rental_id: str | None = None,
    charge_type: str | None = None,
    user=Depends(require_permission("rental.finance.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(params.start_date, params.end_date)
    result = await ChargeRepository(session).list(
        params.q, params.page, params.limit, params.sort, rental_id, charge_type, start, end
    )
    rental_repo = RentalRepository(session)
    items = []
    for c in result.items:
        rental = await rental_repo.get(c.rental_id)
        items.append(_to_dict(c, rental.rental_no if rental else None, rental.customer if rental else None))
    return envelope(items, result.meta)


@router.get("/{charge_id}")
async def get_charge(
    charge_id: str,
    user=Depends(require_permission("rental.finance.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    charge = await ChargeRepository(session).get(charge_id)
    if charge is None:
        raise NotFoundError("Charge not found")
    rental = await RentalRepository(session).get(charge.rental_id)
    return envelope(_to_dict(charge, rental.rental_no if rental else None, rental.customer if rental else None))


@router.post("", status_code=201)
async def record_charge(
    body: ChargeRecordRequest,
    user=Depends(require_permission("rental.finance.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = RentalService(session, user)
    charge, rental = await service.record_charge(body)
    await DashboardService(session).invalidate()
    return envelope(_to_dict(charge, rental.rental_no, rental.customer))


@router.put("/{charge_id}")
async def update_charge(
    charge_id: str,
    body: ChargeUpdateRequest,
    user=Depends(require_permission("rental.finance.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = ChargeRepository(session)
    charge = await repo.get(charge_id)
    if charge is None:
        raise NotFoundError("Charge not found")
    updates = body.model_dump(exclude_unset=True, by_alias=False)
    for field, value in updates.items():
        setattr(charge, field, value)
    await session.commit()
    await DashboardService(session).invalidate()
    rental = await RentalRepository(session).get(charge.rental_id)
    return envelope(_to_dict(charge, rental.rental_no if rental else None, rental.customer if rental else None))


@router.delete("/{charge_id}")
async def delete_charge(
    charge_id: str,
    user=Depends(require_permission("rental.finance.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = ChargeRepository(session)
    charge = await repo.get(charge_id)
    if charge is None:
        raise NotFoundError("Charge not found")
    await repo.delete(charge)
    await session.commit()
    await DashboardService(session).invalidate()
    return envelope({"deleted": True})
