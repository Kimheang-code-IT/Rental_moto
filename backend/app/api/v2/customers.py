from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, parse_date_range, require_permission
from app.core.errors import NotFoundError
from app.repositories.rental import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.entity_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])


def _to_dict(customer) -> dict:
    return CustomerResponse.model_validate(customer).model_dump(by_alias=True)


@router.get("")
async def list_customers(
    params: ListParams = Depends(),
    user=Depends(require_permission("rental.customers.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    start, end = parse_date_range(params.start_date, params.end_date)
    result = await CustomerRepository(session).list(params.q, params.page, params.limit, params.sort, params.status, start, end)
    return envelope([_to_dict(c) for c in result.items], result.meta)


@router.get("/{customer_id}")
async def get_customer(
    customer_id: str,
    user=Depends(require_permission("rental.customers.view")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    customer = await CustomerRepository(session).get(customer_id)
    if customer is None:
        raise NotFoundError("Customer not found")
    return envelope(_to_dict(customer))


@router.post("", status_code=201)
async def create_customer(
    body: CustomerCreate,
    user=Depends(require_permission("rental.customers.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = CustomerService(session, user)
    customer = await service.create(body)
    return envelope(_to_dict(customer))


@router.put("/{customer_id}")
async def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    user=Depends(require_permission("rental.customers.edit")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = CustomerService(session, user)
    customer = await service.update(customer_id, body)
    return envelope(_to_dict(customer))


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: str,
    user=Depends(require_permission("rental.customers.delete")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = CustomerService(session, user)
    await service.delete(customer_id)
    return envelope({"deleted": True})
