from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.services.rental_service import _price_line_rows


def _motorcycle():
    return SimpleNamespace(
        id="mc-001",
        code="MC-001",
        daily_rate=Decimal("10.00"),
        three_day_rate=Decimal("27.00"),
        weekly_rate=Decimal("60.00"),
        monthly_rate=Decimal("200.00"),
    )


def test_rental_line_update_accepts_operator_rate_amount():
    start = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
    line = SimpleNamespace(
        motorcycle_id="mc-001",
        start_date=start,
        due_date=start + timedelta(days=3),
        rate_amount=Decimal("24.50"),
        deposit=Decimal("0"),
        discount=Decimal("1.50"),
        note=None,
    )

    priced = _price_line_rows({"mc-001": _motorcycle()}, [line])

    assert priced[0]["charge"] == Decimal("24.50")
    assert priced[0]["line_discount"] == Decimal("1.50")


def test_rental_line_update_recalculates_when_rate_amount_is_omitted():
    start = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
    line = SimpleNamespace(
        motorcycle_id="mc-001",
        start_date=start,
        due_date=start + timedelta(days=3),
        rate_amount=None,
        deposit=Decimal("0"),
        discount=Decimal("0"),
        note=None,
    )

    priced = _price_line_rows({"mc-001": _motorcycle()}, [line])

    assert priced[0]["charge"] == Decimal("27.00")
