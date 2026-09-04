from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.services.invoice_pdf_service import LABELS, InvoicePdfService


def test_discount_uses_correct_khmer_invoice_label():
    assert LABELS["discount"] == ("បញ្ចុះតម្លៃ", "Discount")


async def test_rental_invoice_pdf_contains_invoice_details():
    rental = SimpleNamespace(
        rental_no="RNT-2026-001",
        customer="Sok Dara",
        phone="012345678",
        motorcycle="Honda Dream",
        plate="1A-1234",
        start_date=datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
        due_date=datetime(2026, 9, 9, 8, 0, tzinfo=UTC),
        return_date=None,
        created_at=datetime(2026, 9, 2, 7, 30, tzinfo=UTC),
        duration_days=7,
        rate_amount=Decimal("20.00"),
        deposit=Decimal("10.00"),
        discount=Decimal("0.00"),
        status="Active",
        rental_charge=Decimal("20.00"),
        late_fee=Decimal("0.00"),
        additional_charges=Decimal("2.50"),
        tax=Decimal("0.00"),
        total_due=Decimal("22.50"),
        paid=Decimal("10.00"),
        outstanding=Decimal("12.50"),
        currency="USD",
        payment_method="Cash",
        payments=[],
        charges=[],
    )
    service = InvoicePdfService(SimpleNamespace())

    async def get_by_no(_rental_no):
        return rental

    class FakeSettings:
        async def get_app_info(self):
            return {"applicationName": "HollyWing Motor", "address": "Phnom Penh, Cambodia"}

        async def get_app_config(self, mask=False):
            return {
                "localization": {
                    "timezone": "Asia/Phnom_Penh",
                    "dateFormat": "DD-MM-YYYY",
                    "timeFormat": "HH:mm",
                    "currency": "USD",
                }
            }

    service.rentals.get_by_no = get_by_no
    from app.services import admin_service

    original = admin_service.SettingService
    admin_service.SettingService = lambda _session: FakeSettings()
    try:
        content, filename = await service.render_rental_invoice(rental.rental_no)
    finally:
        admin_service.SettingService = original

    assert content is not None and content.startswith(b"%PDF")
    assert len(content) > 5_000
    assert filename == "Invoice-RNT-2026-001.pdf"
    # A4 is 595.27 x 841.89 points; A5 is 419.53 x 595.28.
    assert b"841.88" in content or b"841.89" in content
    assert b"419.52" not in content and b"419.53" not in content


def test_invoice_datetime_uses_ui_localization_config():
    from app.services.invoice_pdf_service import _format_datetime

    assert _format_datetime(
        datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
        {"timezone": "Asia/Phnom_Penh", "dateFormat": "DD-MM-YYYY", "timeFormat": "HH:mm"},
    ) == "02-09-2026 15:00"
