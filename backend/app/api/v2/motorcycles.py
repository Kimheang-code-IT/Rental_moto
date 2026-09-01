from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, parse_date_range, require_permission
from app.core.errors import NotFoundError
from app.repositories.rental import MotorcycleRepository
from app.schemas.motorcycle import MotorcycleCreate, MotorcycleResponse, MotorcycleStatusUpdate, MotorcycleUpdate
from app.services.entity_service import MotorcycleService

router = APIRouter(prefix="/motorcycles", tags=["motorcycles"])


def _to_dict(moto) -> dict:
    return MotorcycleResponse.model_validate(moto).model_dump(by_alias=True)


@router.get("")
async def list_motorcycles(
    params: ListParams = Depends(),
    user=Depends(require_permission("rental.motorcycles.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(params.start_date, params.end_date)
    result = await MotorcycleRepository(session).list(
        params.q, params.page, params.limit, params.sort, params.status, start, end
    )
    return envelope([_to_dict(m) for m in result.items], result.meta)


@router.get("/{moto_id}")
async def get_motorcycle(
    moto_id: str,
    user=Depends(require_permission("rental.motorcycles.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    moto = await MotorcycleRepository(session).get(moto_id)
    if moto is None:
        raise NotFoundError("Motorcycle not found")
    return envelope(_to_dict(moto))


@router.post("", status_code=201)
async def create_motorcycle(
    body: MotorcycleCreate,
    user=Depends(require_permission("rental.motorcycles.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = MotorcycleService(session, user)
    moto = await service.create(body)
    return envelope(_to_dict(moto))


@router.put("/{moto_id}")
async def update_motorcycle(
    moto_id: str,
    body: MotorcycleUpdate,
    user=Depends(require_permission("rental.motorcycles.edit")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = MotorcycleService(session, user)
    moto = await service.update(moto_id, body)
    return envelope(_to_dict(moto))


@router.patch("/{moto_id}/status")
async def update_motorcycle_status(
    moto_id: str,
    body: MotorcycleStatusUpdate,
    user=Depends(require_permission("rental.motorcycles.edit")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = MotorcycleService(session, user)
    from app.schemas.motorcycle import MotorcycleUpdate

    moto = await service.update(moto_id, MotorcycleUpdate(status=body.status))
    return envelope(_to_dict(moto))


@router.delete("/{moto_id}")
async def delete_motorcycle(
    moto_id: str,
    user=Depends(require_permission("rental.motorcycles.delete")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = MotorcycleService(session, user)
    await service.delete(moto_id)
    return envelope({"deleted": True})
