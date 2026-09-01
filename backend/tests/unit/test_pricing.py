from datetime import datetime, timezone
from decimal import Decimal

from app.core.money import allocate_payment, clamp_non_negative, distribute_document_discount, money
from app.core.pricing import (
    document_totals,
    duration_days,
    line_amounts,
    line_charge,
    resolve_motorcycle_rates,
    suggested_deposit,
)


def test_money_rounds_half_up():
    assert money("10.005") == Decimal("10.01")
    assert money(10.004) == Decimal("10.00")
    assert money(None) == Decimal("0.00")
    assert clamp_non_negative("-5") == Decimal("0.00")


def test_resolve_rates_fallbacks():
    rates = resolve_motorcycle_rates(8, 0, 0, 0)
    assert rates.daily == Decimal("8.00")
    assert rates.three_day == Decimal("24.00")
    assert rates.weekly == Decimal("52.00")
    assert rates.monthly == Decimal("176.00")


def test_line_charge_tiers():
    rates = resolve_motorcycle_rates(10, 27, 60, 200)
    assert line_charge(rates, 1) == Decimal("10.00")
    assert line_charge(rates, 2) == Decimal("20.00")
    assert line_charge(rates, 3) == Decimal("27.00")
    assert line_charge(rates, 7) == Decimal("60.00")
    assert line_charge(rates, 10) == Decimal("100.00")
    assert line_charge(rates, 28) == Decimal("200.00")
    assert line_charge(rates, 31) == Decimal("200.00")
    assert line_charge(rates, 32) == Decimal("320.00")
    assert line_charge(rates, 0) == Decimal("0.00")


def test_line_amounts_clamps_discount():
    rates = resolve_motorcycle_rates(10)
    amounts = line_amounts(rates, 3, 99)
    assert amounts.charge == Decimal("30.00")
    assert amounts.discount == Decimal("30.00")
    assert amounts.line_total == Decimal("0.00")


def test_document_totals_tax():
    totals = document_totals([Decimal("100.00"), Decimal("50.00")], 10, 10)
    assert totals.subtotal == Decimal("150.00")
    assert totals.discount == Decimal("10.00")
    assert totals.tax == Decimal("14.00")
    assert totals.total == Decimal("154.00")


def test_allocate_payment_last_line_gets_remainder():
    shares = allocate_payment([Decimal("100.00"), Decimal("100.00")], 30)
    assert shares[0] == Decimal("15.00")
    assert shares[1] == Decimal("15.00")
    shares = allocate_payment([Decimal("100.00"), Decimal("30.00")], 13)
    assert sum(shares) == Decimal("13.00")


def test_distribute_discount_sum_matches():
    shares = distribute_document_discount([Decimal("33.33"), Decimal("33.33"), Decimal("33.34")], 10)
    assert sum(shares) == Decimal("10.00")


def test_suggested_deposit():
    rates = resolve_motorcycle_rates(8)
    assert suggested_deposit(rates) == Decimal("80.00")
    rates_low = resolve_motorcycle_rates(2)
    assert suggested_deposit(rates_low) == Decimal("50.00")


def test_duration_days():
    start = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
    due = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
    assert duration_days(start, due) == 4
    assert duration_days(start, start) == 0
    assert duration_days(due, start) == 0
