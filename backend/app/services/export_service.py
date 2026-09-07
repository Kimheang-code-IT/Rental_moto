from __future__ import annotations
import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import AuditLog, Motorcycle, Rental, RentalCharge, RentalCustomer, RentalExpense, RentalPayment
from app.repositories.admin import ExportRepository, TaskProgressRepository

EXPORT_RESOURCES = {
    "motorcycles": "Motorcycles",
    "customers": "Customers",
    "rentals": "Rentals",
    "rental_reports": "Rental reports",
    "payments": "Payments",
    "charges": "Charges",
    "expenses": "Expenses",
    "audit_logs": "Audit logs",
}

# Canonical export field maps per resource: (camelCase code, human label).
# The camelCase codes match the frontend export field codes; every code the
# frontend exposes must exist here so no requested column is silently dropped.
FIELD_SETS: dict[str, list[tuple[str, str]]] = {
    "motorcycles": [
        ("code", "Motorcycle Code"),
        ("model", "Model"),
        ("brand", "Brand"),
        ("year", "Year"),
        ("color", "Color"),
        ("plate", "Plate Number"),
        ("chassisNo", "Chassis Number"),
        ("engineNo", "Engine Number"),
        ("dailyRate", "1 Day Rate"),
        ("threeDayRate", "3 Day Rate"),
        ("weeklyRate", "1 Week Rate"),
        ("monthlyRate", "1 Month Rate"),
        ("currency", "Currency"),
        ("status", "Status"),
    ],
    "customers": [
        ("code", "Customer Code"),
        ("fullName", "Full Name"),
        ("company", "Company"),
        ("identityNumber", "Identity Number"),
        ("phone", "Phone"),
        ("email", "Email"),
        ("identityType", "Identity Type"),
        ("address", "Address"),
        ("status", "Status"),
    ],
    "rentals": [
        ("rentalNo", "Rental Number"),
        ("customer", "Customer"),
        ("phone", "Phone"),
        ("motorcycle", "Motorcycle"),
        ("plate", "Plate"),
        ("startDate", "Start Date"),
        ("dueDate", "Due Date"),
        ("durationDays", "Days"),
        ("rateType", "Rate Type"),
        ("rateAmount", "Rate Amount"),
        ("deposit", "Deposit"),
        ("discount", "Discount"),
        ("currency", "Currency"),
        ("additionalCharges", "Additional Charges"),
        ("rentalCharge", "Rental Charge"),
        ("lateFee", "Late Fee"),
        ("totalDue", "Total Due"),
        ("paid", "Paid"),
        ("outstanding", "Outstanding"),
        ("paymentMethod", "Payment Method"),
        ("returnDate", "Actual Return"),
        ("condition", "Motorcycle Condition"),
        ("createdBy", "Created By"),
        ("status", "Status"),
    ],
    # Completed rentals only; mirrors the rental reports table columns.
    "rental_reports": [
        ("rentalNo", "Rental Number"),
        ("customer", "Customer"),
        ("motorcycle", "Motorcycle"),
        ("plate", "Plate"),
        ("startDate", "Start Date"),
        ("dueDate", "Due Date"),
        ("returnDate", "Return Date"),
        ("rentalCharge", "Rental Charge"),
        ("lateFee", "Late Fee"),
        ("additionalCharges", "Additional Charges"),
        ("totalDue", "Total Due"),
        ("paid", "Paid"),
        ("outstanding", "Outstanding"),
        ("paymentStatus", "Payment Status"),
        ("paymentMethod", "Payment Method"),
    ],
    # Combined income & expense ledger: rental payments (income) + expenses.
    # Amounts keep the page convention: income positive, expenses negative,
    # with an explicit type column.
    "expenses": [
        ("date", "Date"),
        ("reference", "Reference"),
        ("description", "Description"),
        ("type", "Type"),
        ("amount", "Amount"),
        ("currency", "Currency"),
        ("rentalNo", "Rental Number"),
        ("paymentMethod", "Payment Method"),
        ("createdBy", "Created By"),
    ],
    "payments": [
        ("paymentNo", "Payment Number"),
        ("rentalId", "Rental"),
        ("amount", "Amount"),
        ("currency", "Currency"),
        ("paymentMethod", "Payment Method"),
        ("paidAt", "Paid At"),
        ("reference", "Reference"),
        ("createdBy", "Created By"),
    ],
    "charges": [
        ("chargeNo", "Charge Number"),
        ("rentalId", "Rental"),
        ("chargeType", "Charge Type"),
        ("description", "Description"),
        ("amount", "Amount"),
        ("currency", "Currency"),
        ("createdAt", "Created At"),
        ("createdBy", "Created By"),
    ],
    "audit_logs": [
        ("occurredAt", "Date / Time"),
        ("user", "User"),
        ("eventType", "Event Type"),
        ("action", "Action"),
        ("entityType", "Entity Type"),
        ("entity", "Entity"),
        ("result", "Result"),
        ("ipDevice", "IP Device"),
    ],
}

# Row keys used for date-range filtering, in fallback order.
DATE_KEYS: dict[str, tuple[str, ...]] = {
    "motorcycles": (),
    "customers": (),
    "rentals": ("startDate",),
    "rental_reports": ("returnDate", "dueDate"),
    "expenses": ("date",),
    "payments": ("paidAt",),
    "charges": ("createdAt",),
    "audit_logs": ("occurredAt",),
}

# Row keys searched when the list page sends a `q` search term.
SEARCH_KEYS: dict[str, tuple[str, ...]] = {
    "motorcycles": ("code", "model", "brand", "plate", "chassisNo", "engineNo"),
    "customers": ("code", "fullName", "company", "identityNumber", "phone", "email"),
    "rentals": ("rentalNo", "customer", "phone", "motorcycle", "plate"),
    "rental_reports": ("rentalNo", "customer", "motorcycle", "plate"),
    "expenses": ("reference", "description", "rentalNo"),
    "payments": ("paymentNo", "reference"),
    "charges": ("chargeNo", "description"),
    "audit_logs": ("user", "action", "entityType", "entity"),
}


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _day(value: Any) -> str:
    """Normalize a row value to a YYYY-MM-DD string for range comparisons."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value or "")[:10]


def _select_columns(resource: str, field_codes: list[str] | None) -> list[tuple[str, str]]:
    """Resolve the requested field codes to (code, label) pairs in stable order."""
    columns = FIELD_SETS.get(resource, [])
    if not field_codes:
        return columns
    known = {code: label for code, label in columns}
    return [(code, known[code]) for code in field_codes if code in known]


def _match_search(row: dict[str, Any], term: str, resource: str) -> bool:
    needle = term.strip().lower()
    if not needle:
        return True
    return any(needle in str(row.get(key) or "").lower() for key in SEARCH_KEYS.get(resource, ()))


def _match_date_range(row: dict[str, Any], resource: str, start: str | None, end: str | None) -> bool:
    keys = DATE_KEYS.get(resource, ())
    if not keys or not (start or end):
        return True
    day = ""
    for key in keys:
        candidate = _day(row.get(key))
        if candidate:
            day = candidate
            break
    if not day:
        return False
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True


def apply_export_filters(
    rows: list[dict[str, Any]],
    resource: str,
    filters: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Apply scope, query filters, and date range to normalized export rows.

    Supported filter payload (stored on the export job):
    - selectedIds: explicit row ids (scope=selected)
    - query.ids: explicit row ids (scope=current_page)
    - query.q / query.status / query.model / query.motorcycle /
      query.paymentStatus / query.paymentMethod / query.types: list filters
    - startDate / endDate: inclusive date range on the resource's date column
    """
    filters = filters or {}
    query = filters.get("query") or {}
    if not isinstance(query, dict):
        query = {}

    explicit_ids = [str(v) for v in (filters.get("selectedIds") or [])]
    if not explicit_ids:
        explicit_ids = [str(v) for v in (query.get("ids") or [])]
    if explicit_ids:
        wanted = set(explicit_ids)
        rows = [row for row in rows if str(row.get("id") or "") in wanted]

    for key in ("status", "model", "motorcycle", "paymentStatus", "paymentMethod"):
        values = [str(v) for v in (query.get(key) or []) if str(v)]
        if values:
            rows = [row for row in rows if str(row.get(key) or "") in values]

    types = [str(v) for v in (query.get("types") or []) if str(v)]
    if types and resource == "expenses":
        rows = [
            row for row in rows
            if (str(row.get("type") or "").lower() in {t.lower() for t in types})
            or (str(row.get("type") or "") in types)
        ]

    term = str(query.get("q") or "")
    if term:
        rows = [row for row in rows if _match_search(row, term, resource)]

    rows = [
        row for row in rows
        if _match_date_range(row, resource, filters.get("startDate"), filters.get("endDate"))
    ]
    return rows


def _motorcycle_rows(records: list[Motorcycle]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "code": record.code,
            "model": record.model,
            "brand": record.brand,
            "year": record.year,
            "color": record.color,
            "plate": record.plate,
            "chassisNo": record.chassis_no,
            "engineNo": record.engine_no,
            "dailyRate": record.daily_rate,
            "threeDayRate": record.three_day_rate,
            "weeklyRate": record.weekly_rate,
            "monthlyRate": record.monthly_rate,
            "currency": record.currency,
            "status": record.status,
        }
        for record in records
    ]


def _customer_rows(records: list[RentalCustomer]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "code": record.code,
            "fullName": record.full_name,
            "company": record.company,
            "identityNumber": record.identity_number,
            "phone": record.phone,
            "email": record.email,
            "identityType": record.identity_type,
            "address": record.address,
            "status": record.status,
        }
        for record in records
    ]


def _rental_rows(records: list[Rental]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "rentalNo": record.rental_no,
            "customer": record.customer,
            "phone": record.phone,
            "motorcycle": record.motorcycle,
            "plate": record.plate,
            "startDate": record.start_date,
            "dueDate": record.due_date,
            "durationDays": record.duration_days,
            "rateType": record.rate_type,
            "rateAmount": record.rate_amount,
            "deposit": record.deposit,
            "discount": record.discount,
            "currency": record.currency,
            "rentalCharge": record.rental_charge,
            "lateFee": record.late_fee,
            "additionalCharges": record.additional_charges,
            "totalDue": record.total_due,
            "paid": record.paid,
            "outstanding": record.outstanding,
            "paymentMethod": record.payment_method,
            "paymentStatus": record.payment_status,
            "returnDate": record.return_date,
            "condition": record.condition,
            "createdBy": record.created_by,
            "status": record.status,
        }
        for record in records
    ]


def _ledger_rows(
    payments: list[RentalPayment],
    expenses: list[RentalExpense],
    rental_nos: dict[str, str],
) -> list[dict[str, Any]]:
    """Combined income & expense ledger matching the income/expense page."""
    rows: list[dict[str, Any]] = []
    for record in payments:
        rows.append({
            "id": record.id,
            "date": record.paid_at,
            "reference": record.payment_no,
            "description": record.reference or rental_nos.get(record.rental_id, ""),
            "type": "Income",
            "amount": record.amount,
            "currency": record.currency,
            "rentalNo": rental_nos.get(record.rental_id, record.rental_id),
            "paymentMethod": record.payment_method,
            "createdBy": record.created_by,
        })
    for record in expenses:
        rows.append({
            "id": record.id,
            "date": record.date,
            "reference": record.expense_no,
            "description": record.description,
            "type": record.expense_type,
            "amount": -record.amount,
            "currency": record.currency,
            "rentalNo": "",
            "paymentMethod": "",
            "createdBy": record.created_by,
        })
    rows.sort(key=lambda row: _day(row["date"]), reverse=True)
    return rows


def _payment_rows(records: list[RentalPayment]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "paymentNo": record.payment_no,
            "rentalId": record.rental_id,
            "amount": record.amount,
            "currency": record.currency,
            "paymentMethod": record.payment_method,
            "paidAt": record.paid_at,
            "reference": record.reference,
            "createdBy": record.created_by,
        }
        for record in records
    ]


def _charge_rows(records: list[RentalCharge]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "chargeNo": record.charge_no,
            "rentalId": record.rental_id,
            "chargeType": record.charge_type,
            "description": record.description,
            "amount": record.amount,
            "currency": record.currency,
            "createdAt": record.created_at,
            "createdBy": record.created_by,
        }
        for record in records
    ]


def _audit_log_rows(records: list[AuditLog]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "occurredAt": record.occurred_at,
            "user": record.user_name or "",
            "eventType": str(record.action or "").upper().replace("_", " "),
            "action": record.action,
            "entityType": record.entity_type,
            "entity": record.entity_label or record.entity_id or "",
            "result": "SUCCESS",
            "ipDevice": record.ip_address or "",
        }
        for record in records
    ]


async def _rows_for_resource(session: AsyncSession, resource: str) -> list[dict[str, Any]]:
    """Load rows for a resource and normalize them to the export field codes."""
    if resource == "motorcycles":
        records = (await session.execute(select(Motorcycle).order_by(Motorcycle.code))).scalars().all()
        return _motorcycle_rows(list(records))
    if resource == "customers":
        records = (await session.execute(select(RentalCustomer).order_by(RentalCustomer.code))).scalars().all()
        return _customer_rows(list(records))
    if resource == "rentals":
        records = (await session.execute(select(Rental).order_by(Rental.rental_no))).scalars().all()
        return _rental_rows(list(records))
    if resource == "rental_reports":
        records = (await session.execute(select(Rental).order_by(Rental.rental_no))).scalars().all()
        return [row for row in _rental_rows(list(records)) if row["status"] == "Completed"]
    if resource == "expenses":
        payments = (await session.execute(select(RentalPayment).order_by(RentalPayment.paid_at))).scalars().all()
        expenses = (await session.execute(select(RentalExpense).order_by(RentalExpense.date))).scalars().all()
        rentals = (await session.execute(select(Rental.id, Rental.rental_no))).all()
        rental_nos = {rental_id: rental_no for rental_id, rental_no in rentals}
        return _ledger_rows(list(payments), list(expenses), rental_nos)
    if resource == "payments":
        records = (await session.execute(select(RentalPayment).order_by(RentalPayment.paid_at))).scalars().all()
        return _payment_rows(list(records))
    if resource == "charges":
        records = (await session.execute(select(RentalCharge).order_by(RentalCharge.created_at))).scalars().all()
        return _charge_rows(list(records))
    if resource == "audit_logs":
        records = (await session.execute(select(AuditLog).order_by(AuditLog.occurred_at.desc()))).scalars().all()
        return _audit_log_rows(list(records))
    return []


async def generate_export_file(
    session: AsyncSession,
    resource: str,
    fmt: str,
    out_dir: Path,
    file_stem: str,
    filters: dict[str, Any] | None = None,
) -> tuple[Path, int]:
    columns = _select_columns(resource, list(filters.get("fieldCodes") or []) if filters else [])
    rows = await _rows_for_resource(session, resource)
    rows = apply_export_filters(rows, resource, filters)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{file_stem}.{fmt}"

    if fmt == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append([label for _, label in columns])
        for row in rows:
            sheet.append([_fmt(row.get(code)) for code, _ in columns])
        workbook.save(path)
    else:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow([label for _, label in columns])
            for row in rows:
                writer.writerow([_fmt(row.get(code)) for code, _ in columns])
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

    from app.core.permissions import user_has_permission
    from app.repositories.admin import UserRepository

    owner = await UserRepository(session).get(job.user_id)
    permission = export_permission(job.resource)
    if owner is None or permission is None or not user_has_permission(owner, permission):
        job.status = "failed"
        job.error = "Export permission was revoked"
        if task:
            task.status = "failed"
            task.message = job.error
        await session.commit()
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
        path, row_count = await generate_export_file(
            session, job.resource, job.format, out_dir, stem, job.filters,
        )
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


def export_permission(resource: str) -> str | None:
    return {
        "motorcycles": "rental.motorcycles.export",
        "customers": "rental.customers.export",
        "rentals": "rental.rentals.export",
        "rental_reports": "reports.export",
        "payments": "rental.finance.export",
        "charges": "rental.finance.export",
        "expenses": "rental.finance.export",
        "audit_logs": "admin.audit_logs.export",
    }.get(resource)
