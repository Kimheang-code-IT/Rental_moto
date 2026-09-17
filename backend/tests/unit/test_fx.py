from decimal import Decimal

from app.core.fx import resolve_payment_money, to_rental_currency_amount


def test_same_currency_keeps_amount():
    credited, tendered, rate, currency = resolve_payment_money(
        rental_currency="USD",
        payment_currency="USD",
        tendered_amount=Decimal("12.50"),
        exchange_rate=Decimal("4100"),
    )
    assert credited == Decimal("12.50")
    assert tendered == Decimal("12.50")
    assert currency == "USD"
    assert rate == Decimal("1.0000")


def test_khr_tender_converts_to_usd_rental():
    assert to_rental_currency_amount(Decimal("8200"), "KHR", "USD", Decimal("4100")) == Decimal("2.00")
    credited, tendered, rate, currency = resolve_payment_money(
        rental_currency="USD",
        payment_currency="KHR",
        tendered_amount=Decimal("8200"),
        exchange_rate=Decimal("4100"),
    )
    assert credited == Decimal("2.00")
    assert tendered == Decimal("8200.00")
    assert currency == "KHR"
    assert rate == Decimal("4100.0000")


def test_cross_currency_placeholder_rate_one_uses_market_fallback():
    credited, tendered, rate, currency = resolve_payment_money(
        rental_currency="USD",
        payment_currency="KHR",
        tendered_amount=Decimal("8200"),
        exchange_rate=Decimal("1"),
    )
    assert credited == Decimal("2.00")
    assert tendered == Decimal("8200.00")
    assert currency == "KHR"
    assert rate == Decimal("4100")
