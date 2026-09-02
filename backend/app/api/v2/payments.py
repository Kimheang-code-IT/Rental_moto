from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, parse_date_range, require_permission
from app.core.errors import NotFoundError
from app.repositories.rental import PaymentRepository, RentalRepository
from app.schemas.rental import PaymentRecordRequest, PaymentResponse, PaymentUpdateRequest
from app.services.admin_service import DashboardService
from app.services.rental_service import RentalService, normalize_charge_type, normalize_payment_method

router = APIRouter(prefix="/payments", tags=["payments"])


def _to_dict(payment, rental_no: str | None = None, customer: str | None = None) -> dict:
    data = PaymentResponse.model_validate(payment).model_dump(by_alias=True)
    if rental_no:
        data["rentalNo"] = rental_no
    if customer:
        data["customer"] = customer
    return data


async def _payment_with_rental(session: AsyncSession, payment) -> dict:
    rental = await RentalRepository(session).get(payment.rental_id)
    return _to_dict(payment, rental.rental_no if rental else None, rental.customer if rental else None)


@router.get("")
async def list_payments(
    params: ListParams = Depends(),
    rental_id: str | None = None,
    payment_method: str | None = None,
    user=Depends(require_permission("rental.finance.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(params.start_date, params.end_date)
    result = await PaymentRepository(session).list(
        params.q, params.page, params.limit, params.sort, rental_id, start, end, payment_method
    )
    rental_repo = RentalRepository(session)
    items = []
    for p in result.items:
        rental = await rental_repo.get(p.rental_id)
        items.append(_to_dict(p, rental.rental_no if rental else None, rental.customer if rental else None))
    return envelope(items, result.meta)


@router.get("/{payment_id}")
async def get_payment(
    payment_id: str,
    user=Depends(require_permission("rental.finance.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payment = await PaymentRepository(session).get(payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    return envelope(await _payment_with_rental(session, payment))


@router.post("", status_code=201)
async def record_payment(
    body: PaymentRecordRequest,
    user=Depends(require_permission("rental.finance.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = RentalService(session, user)
    payment, rental = await service.record_payment(body)
    await DashboardService(session).invalidate()
    return envelope(_to_dict(payment, rental.rental_no, rental.customer))


@router.put("/{payment_id}")
async def update_payment(
    payment_id: str,
    body: PaymentUpdateRequest,
    user=Depends(require_permission("rental.finance.edit")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:

    repo = PaymentRepository(session)
    payment = await repo.get(payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    updates = body.model_dump(exclude_unset=True, by_alias=False)
    if "payment_method" in updates and updates["payment_method"] is not None:
        updates["payment_method"] = normalize_payment_method(updates["payment_method"])
    for field, value in updates.items():
        setattr(payment, field, value)
    await session.commit()
    await DashboardService(session).invalidate()
    return envelope(await _payment_with_rental(session, payment))


@router.delete("/{payment_id}")
async def delete_payment(
    payment_id: str,
    user=Depends(require_permission("rental.finance.delete")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = PaymentRepository(session)
    payment = await repo.get(payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    await repo.delete(payment)
    await session.commit()
    await DashboardService(session).invalidate()
    return envelope({"deleted": True})
