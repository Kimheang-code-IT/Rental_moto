from __future__ import annotations
import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Motorcycle, Rental, RentalCharge, RentalCustomer, RentalExpense, RentalPayment
from app.repositories.admin import ExportRepository, TaskProgressRepository

EXPORT_RESOURCES = {
    "motorcycles": "Motorcycles",
    "customers": "Customers",
    "rentals": "Rentals",
    "payments": "Payments",
    "charges": "Charges",
    "expenses": "Expenses",
}


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _columns(resource: str) -> list[tuple[str, str]]:
    mapping = {
        "motorcycles": [("code", "Code"), ("model", "Model"), ("brand", "Brand"), ("year", "Year"), ("plate", "Plate"), ("dailyRate", "daily_rate"), ("threeDayRate", "three_day_rate"), ("weeklyRate", "weekly_rate"), ("monthlyRate", "monthly_rate"), ("status", "Status")],
        "customers": [("code", "Code"), ("fullName", "full_name"), ("phone", "Phone"), ("email", "Email"), ("identityType", "identity_type"), ("identityNumber", "identity_number"), ("company", "Company"), ("status", "Status")],
        "rentals": [("rentalNo", "rental_no"), ("customer", "Customer"), ("motorcycle", "Motorcycle"), ("startDate", "start_date"), ("dueDate", "due_date"), ("rentalCharge", "rental_charge"), ("totalDue", "total_due"), ("paid", "Paid"), ("outstanding", "Outstanding"), ("status", "Status")],
        "payments": [("paymentNo", "payment_no"), ("rentalId", "rental_id"), ("amount", "Amount"), ("currency", "Currency"), ("paymentMethod", "payment_method"), ("paidAt", "paid_at"), ("reference", "Reference")],
        "charges": [("chargeNo", "charge_no"), ("rentalId", "rental_id"), ("chargeType", "charge_type"), ("amount", "Amount"), ("currency", "Currency"), ("createdAt", "created_at")],
        "expenses": [("expenseNo", "expense_no"), ("date", "Date"), ("expenseType", "expense_type"), ("description", "Description"), ("amount", "Amount"), ("currency", "Currency")],
    }
    return mapping.get(resource, [])


async def _rows_for_resource(session: AsyncSession, resource: str) -> list[dict]:
    if resource == "motorcycles":
        rows = (await session.execute(select(Motorcycle).order_by(Motorcycle.code))).scalars().all()
        return [dict(r.__dict__) for r in rows]
    if resource == "customers":
        rows = (await session.execute(select(RentalCustomer).order_by(RentalCustomer.code))).scalars().all()
        return [dict(r.__dict__) for r in rows]
    if resource == "rentals":
        rows = (await session.execute(select(Rental).order_by(Rental.rental_no))).scalars().all()
        return [dict(r.__dict__) for r in rows]
    if resource == "payments":
        rows = (await session.execute(select(RentalPayment).order_by(RentalPayment.paid_at))).scalars().all()
        return [dict(r.__dict__) for r in rows]
    if resource == "charges":
        rows = (await session.execute(select(RentalCharge).order_by(RentalCharge.created_at))).scalars().all()
        return [dict(r.__dict__) for r in rows]
    if resource == "expenses":
        rows = (await session.execute(select(RentalExpense).order_by(RentalExpense.date))).scalars().all()
        return [dict(r.__dict__) for r in rows]
    return []


async def generate_export_file(session: AsyncSession, resource: str, fmt: str, out_dir: Path, file_stem: str) -> tuple[Path, int]:
    columns = _columns(resource)
    rows = await _rows_for_resource(session, resource)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{file_stem}.{fmt}"

    if fmt == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append([label for _, label in columns])
        for row in rows:
            sheet.append([_fmt(row.get(attr)) for attr, _ in columns])
        workbook.save(path)
    else:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow([label for _, label in columns])
            for row in rows:
                writer.writerow([_fmt(row.get(attr)) for attr, _ in columns])
    return path, len(rows)


async def process_export(session: AsyncSession, export_id: str, task_id: str) -> None:

    repo = ExportRepository(session)
    task_repo = TaskProgressRepository(session)
    job = await repo.get(export_id)
    task = await task_repo.get(task_id)
    if job is None:
        return
    if job.status == "completed":
        return

    job.status = "processing"
    job.progress = 10
    if task:
        task.status = "running"
        task.progress = 10
    await session.commit()

    try:
        out_dir = Path(settings.export_dir) / export_id[:2]
        stem = f"{job.resource}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{export_id[:8]}"
        path, row_count = await generate_export_file(session, job.resource, job.format, out_dir, stem)
        job.file_path = str(path)
        job.file_name = path.name
        job.row_count = row_count
        job.status = "completed"
        job.progress = 100
        if task:
            task.status = "completed"
            task.progress = 100
            task.result = {"exportId": export_id, "rows": row_count, "fileName": path.name}
        await session.commit()
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)[:500]
        if task:
            task.status = "failed"
            task.message = str(exc)[:500]
        await session.commit()
        raise

