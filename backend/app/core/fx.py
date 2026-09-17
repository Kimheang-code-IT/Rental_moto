"""USD/KHR payment conversion helpers.

``exchange_rate`` always means how many KHR equal 1 USD (Cambodia market convention).
Payment ``amount`` credited to a rental is always stored in the rental currency.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import money

DEFAULT_USD_KHR_RATE = Decimal("4100")


def normalize_payment_currency(value: str | None) -> str:
    code = str(value or "USD").strip().upper()
    return "KHR" if code == "KHR" else "USD"


def normalize_exchange_rate(value) -> Decimal:
    try:
        rate = Decimal(str(value))
    except Exception:
        return DEFAULT_USD_KHR_RATE
    if rate <= 0:
        return DEFAULT_USD_KHR_RATE
    return rate.quantize(Decimal("0.0001"))


def exchange_rate_for_currencies(value, payment_currency: str | None, rental_currency: str | None) -> Decimal:
    """Reject the placeholder rate 1 when USD and KHR actually differ."""
    rate = normalize_exchange_rate(value)
    if normalize_payment_currency(payment_currency) != normalize_payment_currency(rental_currency) and rate <= 1:
        return DEFAULT_USD_KHR_RATE
    return rate


def to_rental_currency_amount(
    tendered_amount,
    payment_currency: str | None,
    rental_currency: str | None,
    exchange_rate=DEFAULT_USD_KHR_RATE,
) -> Decimal:
    tendered = money(tendered_amount)
    rental = normalize_payment_currency(rental_currency)
    payment = normalize_payment_currency(payment_currency)
    rate = exchange_rate_for_currencies(exchange_rate, payment, rental)
    if payment == rental:
        return tendered
    if rental == "USD" and payment == "KHR":
        return money(tendered / rate)
    if rental == "KHR" and payment == "USD":
        return money(tendered * rate)
    return tendered


def resolve_payment_money(
    *,
    rental_currency: str | None,
    payment_currency: str | None = None,
    amount=None,
    tendered_amount=None,
    exchange_rate=None,
) -> tuple[Decimal, Decimal, Decimal, str]:
    """Return ``(amount_in_rental_currency, tendered_amount, exchange_rate, payment_currency)``."""
    rental = normalize_payment_currency(rental_currency)
    payment = normalize_payment_currency(payment_currency or rental)
    rate = exchange_rate_for_currencies(
        exchange_rate if exchange_rate is not None else DEFAULT_USD_KHR_RATE,
        payment,
        rental,
    )
    if payment == rental:
        rate = Decimal("1.0000") if payment == "USD" else rate

    if tendered_amount is not None:
        tendered = money(tendered_amount)
        credited = to_rental_currency_amount(tendered, payment, rental, rate)
    elif amount is not None:
        credited = money(amount)
        if payment == rental:
            tendered = credited
        elif rental == "USD" and payment == "KHR":
            tendered = money(credited * rate)
        elif rental == "KHR" and payment == "USD":
            tendered = money(credited / rate)
        else:
            tendered = credited
    else:
        credited = Decimal("0.00")
        tendered = Decimal("0.00")

    if payment == rental and payment == "USD":
        rate = Decimal("1.0000")
    return credited, tendered, rate, payment
