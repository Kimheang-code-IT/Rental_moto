from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, parse_date_range, require_permission
from app.core.errors import NotFoundError
from app.repositories.rental import RentalRepository
from app.schemas.rental import RentalCancelRequest, RentalCloseRequest, RentalCreateRequest, RentalResponse, RentalUpdateRequest
from app.services.admin_service import DashboardService
from app.services.rental_service import RentalService

router = APIRouter(prefix="/rentals", tags=["rentals"])


def _to_dict(rental) -> dict:
    loaded_lines = rental.__dict__.get("lines")
    values = {name: getattr(rental, name) for name in RentalResponse.model_fields if name != "lines"}
    values["lines"] = list(loaded_lines or [])
    return RentalResponse.model_validate(values).model_dump(by_alias=True)


@router.get("")
async def list_rentals(
    params: ListParams = Depends(),
    customer_id: str | None = None,
    motorcycle_id: str | None = None,
    user=Depends(require_permission("rental.rentals.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(params.start_date, params.end_date)
    service = RentalService(session, user)
    await service.detect_overdue(notify=False)
    result = await RentalRepository(session).list(
        params.q,
        params.page,
        params.limit,
        params.sort,
        params.status or "Active,Overdue",
        customer_id=customer_id,
        motorcycle_id=motorcycle_id,
        start_date=start,
        end_date=end,
    )
    return envelope([_to_dict(r) for r in result.items], result.meta)


@router.get("/reports")
async def rental_reports(
    params: ListParams = Depends(),
    user=Depends(require_permission("reports.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(params.start_date, params.end_date)
    result = await RentalRepository(session).list(
        params.q,
        params.page,
        params.limit,
        params.sort,
        params.status or "Completed",
        start_date=start,
        end_date=end,
        date_field="return_date",
    )
    return envelope([_to_dict(r) for r in result.items], result.meta)


@router.get("/{rental_id}")
async def get_rental(
    rental_id: str,
    user=Depends(require_permission("rental.rentals.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rental = await RentalRepository(session).get(rental_id)
    if rental is None:
        raise NotFoundError("Rental not found")
    return envelope(_to_dict(rental))


@router.post("", status_code=201)
async def create_rental(
    body: RentalCreateRequest,
    user=Depends(require_permission("rental.rentals.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = RentalService(session, user)
    rentals = await service.create_rentals(body)
    await DashboardService(session).invalidate()
    return envelope([_to_dict(r) for r in rentals], {"page": 1, "limit": len(rentals), "total": len(rentals)})


@router.put("/{rental_id}")
async def update_rental(
    rental_id: str,
    body: RentalUpdateRequest,
    user=Depends(require_permission("rental.rentals.edit")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = RentalService(session, user)
    rental = await service.update_rental(rental_id, body)
    await DashboardService(session).invalidate()
    return envelope(_to_dict(rental))


@router.post("/{rental_id}/close")
async def close_rental(
    rental_id: str,
    body: RentalCloseRequest,
    user=Depends(require_permission("rental.rentals.return")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = RentalService(session, user)
    rental = await service.close_rental(rental_id, body)
    await DashboardService(session).invalidate()
    return envelope(_to_dict(rental))


@router.post("/{rental_id}/cancel")
async def cancel_rental(
    rental_id: str,
    body: RentalCancelRequest,
    user=Depends(require_permission("rental.rentals.edit")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = RentalService(session, user)
    rental = await service.cancel_rental(rental_id, body.reason)
    await DashboardService(session).invalidate()
    return envelope(_to_dict(rental))


@router.delete("/{rental_id}")
async def delete_rental(
    rental_id: str,
    user=Depends(require_permission("rental.rentals.delete")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = RentalRepository(session)
    rental = await repo.get(rental_id)
    if rental is None:
        raise NotFoundError("Rental not found")
    if rental.status != "Cancelled":
        from app.core.errors import ConflictError

        raise ConflictError("Only cancelled rentals can be deleted")
    await repo.delete(rental)
    await session.commit()
    await DashboardService(session).invalidate()
    return envelope({"deleted": True})
