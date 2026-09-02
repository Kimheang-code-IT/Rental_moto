from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import envelope, get_current_user, get_db_session
from app.core.permissions import user_has_permission
from app.models import Motorcycle, Rental, RentalCustomer
from app.schemas.settings import SearchHit

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def global_search(
    q: str = Query(min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
    user=Depends(get_current_user),
) -> dict:
    term = f"%{q.strip().lower()}%"
    hits: list[dict] = []

    motos = (
        await session.execute(
            select(Motorcycle)
            .where(or_(func.lower(Motorcycle.code).like(term), func.lower(Motorcycle.model).like(term), func.lower(func.coalesce(Motorcycle.plate, "")).like(term)))
            .limit(limit)
        )
    ).scalars().all() if user_has_permission(user, "rental.motorcycles.view") else []
    for m in motos:
        hits.append(
            SearchHit(
                id=m.id,
                type="motorcycle",
                title=m.model,
                subtitle=m.code,
                url=f"/motorcycles/{m.id}",
            ).model_dump(by_alias=True)
        )

    customers = (
        await session.execute(
            select(RentalCustomer)
            .where(
                or_(
                    func.lower(RentalCustomer.code).like(term),
                    func.lower(RentalCustomer.full_name).like(term),
                    func.lower(func.coalesce(RentalCustomer.company, "")).like(term),
                    func.lower(func.coalesce(RentalCustomer.phone, "")).like(term),
                )
            )
            .limit(limit)
        )
    ).scalars().all() if user_has_permission(user, "rental.customers.view") else []
    for c in customers:
        hits.append(
            SearchHit(
                id=c.id,
                type="customer",
                title=c.full_name,
                subtitle=c.code,
                url=f"/customers/{c.id}",
            ).model_dump(by_alias=True)
        )

    rentals = (
        await session.execute(
            select(Rental)
            .where(or_(func.lower(Rental.rental_no).like(term), func.lower(Rental.customer).like(term)))
            .limit(limit)
        )
    ).scalars().all() if user_has_permission(user, "rental.rentals.view") else []
    for r in rentals:
        hits.append(
            SearchHit(
                id=r.id,
                type="rental",
                title=r.rental_no,
                subtitle=r.customer,
                url=f"/rentals/{r.id}",
            ).model_dump(by_alias=True)
        )

    return envelope({"hits": hits, "total": len(hits)})

