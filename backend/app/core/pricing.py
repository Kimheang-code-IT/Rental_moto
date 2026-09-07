from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.core.money import money


@dataclass
class MotorcycleRates:
    daily: Decimal
    three_day: Decimal
    weekly: Decimal
    monthly: Decimal


@dataclass
class LineAmounts:
    charge: Decimal
    discount: Decimal
    line_total: Decimal


@dataclass
class DocumentTotals:
    subtotal: Decimal
    discount: Decimal
    tax_percent: Decimal
    tax: Decimal
    total: Decimal


def resolve_motorcycle_rates(
    daily_rate=None, three_day_rate=None, weekly_rate=None, monthly_rate=None
) -> MotorcycleRates:
    daily = money(daily_rate) if daily_rate and daily_rate > 0 else Decimal("0.00")

    def positive(value) -> Decimal:
        try:
            v = money(value)
            return v if v > 0 else Decimal("0.00")
        except Exception:
            return Decimal("0.00")

    three_day = positive(three_day_rate) or money(daily * 3)
    weekly = positive(weekly_rate) or money(daily * Decimal("6.5"))
    monthly = positive(monthly_rate) or money(daily * 22)
    return MotorcycleRates(daily=daily, three_day=three_day, weekly=weekly, monthly=monthly)


def duration_days(start: datetime, due: datetime) -> int:
    if not start or not due:
        return 0
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    seconds = (due - start).total_seconds()
    if seconds <= 0:
        return 0
    return max(int(seconds / 86400 + 0.999999), 1) if seconds % 86400 else int(seconds // 86400)


def _at_minute(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.replace(second=0, microsecond=0)


def add_months(start: datetime, months: int) -> datetime:
    """Add calendar months, clamping to the last day of the target month."""
    month_index = start.month - 1 + max(0, int(months or 0))
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def calendar_months_between(start: datetime | None, due: datetime | None) -> int:
    """Return n when due is exactly start plus n calendar months (minute precision)."""
    if not start or not due:
        return 0
    start_m = _at_minute(start)
    due_m = _at_minute(due)
    if due_m <= start_m:
        return 0
    for n in range(1, 37):
        if _at_minute(add_months(start_m, n)) == due_m:
            return n
    return 0


def rate_type_for(days: int, start: datetime | None = None, due: datetime | None = None) -> str:
    months = calendar_months_between(start, due)
    if months >= 1:
        return "Monthly"
    d = max(0, int(days or 0))
    if d == 3:
        return "ThreeDay"
    if d == 7:
        return "Weekly"
    if 28 <= d <= 31:
        return "Monthly"
    return "Daily"


def line_charge(
    rates: MotorcycleRates,
    days: int,
    start: datetime | None = None,
    due: datetime | None = None,
) -> Decimal:
    d = max(0, int(days or 0))
    if d <= 0:
        return Decimal("0.00")
    months = calendar_months_between(start, due)
    if months >= 1:
        return money(rates.monthly * months)
    if d == 1:
        return rates.daily
    if d == 3:
        return rates.three_day
    if d == 7:
        return rates.weekly
    if 28 <= d <= 31:
        return rates.monthly
    return money(rates.daily * d)


def line_amounts(
    rates: MotorcycleRates, days: int, discount=0, start: datetime | None = None, due: datetime | None = None
) -> LineAmounts:
    charge = line_charge(rates, days, start, due)
    disc = min(max(money(discount), Decimal("0.00")), charge)
    return LineAmounts(charge=charge, discount=money(disc), line_total=money(max(charge - disc, Decimal("0"))))


def document_totals(line_totals: list[Decimal], discount=0, tax_percent=0) -> DocumentTotals:
    subtotal = money(sum(line_totals, Decimal("0")))
    disc = min(max(money(discount), Decimal("0.00")), subtotal)
    taxable = max(subtotal - disc, Decimal("0"))
    pct = max(money(tax_percent), Decimal("0"))
    tax = money(taxable * pct / Decimal("100"))
    return DocumentTotals(subtotal=subtotal, discount=money(disc), tax_percent=pct, tax=tax, total=money(taxable + tax))


def suggested_deposit(rates: MotorcycleRates) -> Decimal:
    return money(max(rates.daily * 10, 50))
