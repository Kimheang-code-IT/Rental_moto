from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import AuditLog, Motorcycle, RentalCustomer, User
from app.repositories.admin import AuditRepository
from app.repositories.rental import CustomerRepository, MotorcycleRepository, RentalRepository

VALID_MOTORCYCLE_STATUS = ["Available", "Progressing", "Maintenance"]
VALID_CUSTOMER_STATUS = ["Active", "Inactive"]


class MotorcycleService:
    def __init__(self, session: AsyncSession, actor: User | None = None) -> None:
        self.session = session
        self.repo = MotorcycleRepository(session)
        self.rentals = RentalRepository(session)
        self.audit = AuditRepository(session)
        self.actor = actor

    async def create(self, data) -> Motorcycle:
        if data.status not in VALID_MOTORCYCLE_STATUS:
            raise ValidationError(f"Invalid status: {data.status}")
        if await self.repo.get_by_code(data.code):
            raise ConflictError(f"Motorcycle code {data.code} already exists")
        moto_id = data.id or f"mc-{data.code.lower().replace('mc-', '')}"
        existing = await self.repo.get(moto_id)
        if existing is not None:
            raise ConflictError(f"Motorcycle id {moto_id} already exists")
        moto = Motorcycle(
            **data.model_dump(exclude={"id"}, by_alias=False),
            id=moto_id,
            created_by_user_id=self.actor.id if self.actor else None,
        )
        await self.repo.add(moto)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="motorcycle_created",
                entity_type="motorcycle",
                entity_id=moto.id,
                entity_label=moto.code,
            )
        )
        await self.session.commit()
        await self.session.refresh(moto)
        return moto

    async def update(self, moto_id: str, data) -> Motorcycle:
        moto = await self.repo.get(moto_id)
        if moto is None:
            raise NotFoundError("Motorcycle not found")
        updates = data.model_dump(exclude_unset=True, by_alias=False)
        new_status = updates.get("status")
        if new_status and new_status not in VALID_MOTORCYCLE_STATUS:
            raise ValidationError(f"Invalid status: {new_status}")
        if new_status == "Available" and moto.status == "Progressing":
            active = await self.rentals.list(
                q=None, page=1, limit=1, sort=None, status="Active,Overdue", motorcycle_id=moto_id
            )
            if active.total > 0:
                raise ConflictError("Motorcycle is currently rented and cannot be set Available")
        if "code" in updates and updates["code"] and updates["code"].lower() != moto.code.lower():
            other = await self.repo.get_by_code(updates["code"])
            if other is not None and other.id != moto.id:
                raise ConflictError(f"Motorcycle code {updates['code']} already exists")
        for field, value in updates.items():
            setattr(moto, field, value)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="motorcycle_updated",
                entity_type="motorcycle",
                entity_id=moto.id,
                entity_label=moto.code,
                details={k: str(v) for k, v in updates.items()},
            )
        )
        await self.session.commit()
        await self.session.refresh(moto)
        return moto

    async def delete(self, moto_id: str) -> None:
        moto = await self.repo.get(moto_id)
        if moto is None:
            raise NotFoundError("Motorcycle not found")
        if moto.status == "Progressing":
            raise ConflictError("Motorcycle is currently rented and cannot be deleted")
        await self.repo.delete(moto)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="motorcycle_deleted",
                entity_type="motorcycle",
                entity_id=moto_id,
                entity_label=moto.code,
            )
        )
        await self.session.commit()


class CustomerService:
    def __init__(self, session: AsyncSession, actor: User | None = None) -> None:
        self.session = session
        self.repo = CustomerRepository(session)
        self.audit = AuditRepository(session)
        self.actor = actor

    async def create(self, data) -> RentalCustomer:
        if data.status not in VALID_CUSTOMER_STATUS:
            raise ValidationError(f"Invalid status: {data.status}")
        if await self.repo.get_by_code(data.code):
            raise ConflictError(f"Customer code {data.code} already exists")
        customer_id = data.id or f"rc-{data.code.lower().replace('cus-', '')}"
        existing = await self.repo.get(customer_id)
        if existing is not None:
            raise ConflictError(f"Customer id {customer_id} already exists")
        customer = RentalCustomer(
            **data.model_dump(exclude={"id"}, by_alias=False),
            id=customer_id,
            created_by_user_id=self.actor.id if self.actor else None,
        )
        await self.repo.add(customer)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="customer_created",
                entity_type="customer",
                entity_id=customer.id,
                entity_label=customer.code,
            )
        )
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def update(self, customer_id: str, data) -> RentalCustomer:
        customer = await self.repo.get(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        updates = data.model_dump(exclude_unset=True, by_alias=False)
        if updates.get("status") and updates["status"] not in VALID_CUSTOMER_STATUS:
            raise ValidationError(f"Invalid status: {updates['status']}")
        if "code" in updates and updates["code"] and updates["code"].lower() != customer.code.lower():
            other = await self.repo.get_by_code(updates["code"])
            if other is not None and other.id != customer.id:
                raise ConflictError(f"Customer code {updates['code']} already exists")
        for field, value in updates.items():
            setattr(customer, field, value)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="customer_updated",
                entity_type="customer",
                entity_id=customer.id,
                entity_label=customer.code,
                details={k: str(v) for k, v in updates.items()},
            )
        )
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def delete(self, customer_id: str) -> None:
        customer = await self.repo.get(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        if customer.status != "Inactive":
            raise ConflictError("Only inactive customers can be deleted")
        if await self.repo.has_active_rentals(customer_id):
            raise ConflictError("Customer has active rentals and cannot be deleted")
        await self.repo.delete(customer)
        await self.audit.add(
            AuditLog(
                user_id=self.actor.id if self.actor else None,
                user_name=self.actor.display_name if self.actor else None,
                action="customer_deleted",
                entity_type="customer",
                entity_id=customer_id,
                entity_label=customer.code,
            )
        )
        await self.session.commit()

