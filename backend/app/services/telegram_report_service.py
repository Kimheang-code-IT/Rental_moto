"""Context-aware Telegram report queries with sensitive-field redaction."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rental, RentalCustomer
from app.repositories.rental import CustomerRepository, ExpenseRepository, MotorcycleRepository, PaymentRepository, RentalRepository
from app.services.admin_service import DashboardService
from app.services.telegram_context import TelegramRequestContext, apply_sensitive_row

MOTORCYCLE_STATUS_MAP = {
    "available": "Available",
    "rented": "Progressing",
    "maintenance": "Maintenance",
    "all": None,
}

RENTAL_VIEW_STATUS = {
    "all": None,
    "active": "Active",
    "completed": "Completed",
    "overdue": "Overdue",
}


class TelegramReportService:
    def __init__(self, session: AsyncSession, ctx: TelegramRequestContext) -> None:
        self.session = session
        self.ctx = ctx
        self.motorcycle_repo = MotorcycleRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.rental_repo = RentalRepository(session)
        self.payment_repo = PaymentRepository(session)
        self.expense_repo = ExpenseRepository(session)
        self.dashboard = DashboardService(session)

    def access_payload(self) -> dict:
        modules = {key: self.ctx.can_module(key) for key in ("finance", "motorcycles", "customers", "rentals")}
        return {
            "mode": self.ctx.mode,
            "linked": self.ctx.user is not None,
            "modules": modules,
            "accountHelp": self.ctx.mode == "private",
        }

    async def income(self, start: datetime, end: datetime, page: int, limit: int) -> dict:
        self.ctx.require_module("finance")
        result = await self.payment_repo.list(None, page, limit, "paidAt:desc", start_date=start, end_date=end)
        rows, meta = result.items, result.meta
        items = []
        for row in rows:
            item = apply_sensitive_row(
                self.ctx,
                {
                    "paymentNo": row.payment_no,
                    "rentalId": row.rental_id,
                    "amount": float(row.amount),
                    "currency": row.currency,
                    "paymentMethod": row.payment_method,
                    "paidAt": row.paid_at.isoformat() if row.paid_at else None,
                    "reference": row.reference,
                },
            )
            items.append(item)
        total_amount = await self.payment_repo.sum_between(start, end)
        return {
            "items": items,
            "totalAmount": float(total_amount) if self.ctx.sensitive.financial_totals else None,
            "page": meta["page"],
            "limit": meta["limit"],
            "total": meta["total"],
        }

    async def expenses(self, start: datetime, end: datetime, page: int, limit: int) -> dict:
        self.ctx.require_module("finance")
        result = await self.expense_repo.list(None, page, limit, "date:desc", start_date=start, end_date=end)
        rows, meta = result.items, result.meta
        items = []
        for row in rows:
            items.append(
                apply_sensitive_row(
                    self.ctx,
                    {
                        "expenseNo": row.expense_no,
                        "expenseType": row.expense_type,
                        "description": row.description,
                        "amount": float(row.amount),
                        "currency": row.currency,
                        "date": row.date.isoformat() if row.date else None,
                    },
                )
            )
        total_amount = await self.expense_repo.sum_between(start, end)
        return {
            "items": items,
            "totalAmount": float(total_amount) if self.ctx.sensitive.financial_totals else None,
            "page": meta["page"],
            "limit": meta["limit"],
            "total": meta["total"],
        }

    async def finance_summary(self, start: datetime, end: datetime) -> dict:
        self.ctx.require_module("finance")
        summary = await self.dashboard.summary(start, end)
        if not self.ctx.sensitive.financial_totals:
            for key in ("income", "expense", "netIncome", "outstanding"):
                if key in summary:
                    summary[key] = None
            summary["incomeByDay"] = []
            summary["expenseByDay"] = []
        if not self.ctx.sensitive.rental_balances and "outstanding" in summary:
            summary["outstanding"] = None
        return summary

    async def motorcycles(self, view: str, page: int, limit: int) -> dict:
        self.ctx.require_module("motorcycles")
        status = MOTORCYCLE_STATUS_MAP.get((view or "all").lower(), view)
        result = await self.motorcycle_repo.list(None, page, limit, "code", status=status)
        rows, meta = result.items, result.meta
        items = [
            {
                "id": row.id,
                "code": row.code,
                "model": row.model,
                "brand": row.brand,
                "plate": row.plate,
                "status": row.status,
                "dailyRate": float(row.daily_rate) if self.ctx.sensitive.financial_totals else None,
            }
            for row in rows
        ]
        counts = await self.motorcycle_repo.status_counts()
        return {"items": items, "counts": counts, "page": meta["page"], "limit": meta["limit"], "total": meta["total"]}

    async def customers(self, view: str, start: datetime, end: datetime, page: int, limit: int) -> dict:
        self.ctx.require_module("customers")
        view_key = (view or "all").lower().replace(" ", "_")
        if view_key in ("active_rental", "active"):
            return await self._customers_by_rental_status("Active", page, limit)
        if view_key in ("completed_rental", "completed"):
            return await self._customers_by_rental_status("Completed", page, limit)
        result = await self.customer_repo.list(
            None, page, limit, "createdAt:desc", None, start_date=start, end_date=end
        )
        rows, meta = result.items, result.meta
        items = [self._customer_row(row) for row in rows]
        return {"items": items, "page": meta["page"], "limit": meta["limit"], "total": meta["total"]}

    async def _customers_by_rental_status(self, rental_status: str, page: int, limit: int) -> dict:
        ids_result = await self.session.execute(
            select(Rental.customer_id).where(Rental.status == rental_status).distinct()
        )
        ids = [row[0] for row in ids_result.all()]
        if not ids:
            return {"items": [], "page": page, "limit": limit, "total": 0}
        total = len(ids)
        offset = max(page - 1, 0) * limit
        page_ids = ids[offset : offset + limit]
        result = await self.session.execute(select(RentalCustomer).where(RentalCustomer.id.in_(page_ids)))
        rows = list(result.scalars().all())
        items = [self._customer_row(row) for row in rows]
        return {"items": items, "page": page, "limit": limit, "total": int(total)}

    def _customer_row(self, row: RentalCustomer) -> dict:
        return apply_sensitive_row(
            self.ctx,
            {
                "id": row.id,
                "code": row.code,
                "fullName": row.full_name,
                "phone": row.phone,
                "email": row.email,
                "status": row.status,
                "company": row.company,
            },
        )

    async def rentals(
        self,
        view: str,
        start: datetime,
        end: datetime,
        page: int,
        limit: int,
    ) -> dict:
        self.ctx.require_module("rentals")
        view_key = (view or "all").lower().replace(" ", "_")
        if view_key in ("upcoming_returns", "upcoming"):
            return await self._upcoming_returns(page, limit)
        status = RENTAL_VIEW_STATUS.get(view_key)
        result = await self.rental_repo.list(
            None, page, limit, "startDate:desc", status=status, start_date=start, end_date=end
        )
        rows, meta = result.items, result.meta
        items = [self._rental_row(row) for row in rows]
        return {"items": items, "page": meta["page"], "limit": meta["limit"], "total": meta["total"]}

    async def _upcoming_returns(self, page: int, limit: int) -> dict:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=24)
        stmt = (
            select(Rental)
            .where(Rental.status == "Active", Rental.due_date >= now, Rental.due_date <= window_end)
            .order_by(Rental.due_date)
        )
        total = (
            await self.session.execute(
                select(func.count()).select_from(stmt.subquery())
            )
        ).scalar() or 0
        offset = max(page - 1, 0) * limit
        result = await self.session.execute(stmt.offset(offset).limit(limit))
        items = [self._rental_row(row) for row in result.scalars().all()]
        return {"items": items, "page": page, "limit": limit, "total": int(total)}

    def _rental_row(self, row: Rental) -> dict:
        return apply_sensitive_row(
            self.ctx,
            {
                "id": row.id,
                "rentalNo": row.rental_no,
                "customer": row.customer,
                "phone": row.phone,
                "motorcycle": row.motorcycle,
                "plate": row.plate,
                "status": row.status,
                "startDate": row.start_date.isoformat() if row.start_date else None,
                "dueDate": row.due_date.isoformat() if row.due_date else None,
                "totalDue": float(row.total_due),
                "paid": float(row.paid),
                "outstanding": float(row.outstanding),
                "currency": row.currency,
            },
        )
