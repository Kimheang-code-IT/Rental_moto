"""Unit tests for export field maps and export row filtering (no DB required)."""
from app.services.export_service import (
    FIELD_SETS,
    _select_columns,
    apply_export_filters,
)


def codes(resource: str) -> list[str]:
    return [code for code, _ in FIELD_SETS[resource]]


def test_motorcycles_field_map_covers_table_and_full_data_fields():
    assert codes("motorcycles") == [
        "code", "model", "brand", "year", "color", "plate", "chassisNo", "engineNo",
        "dailyRate", "threeDayRate", "weeklyRate", "monthlyRate", "currency", "status",
    ]


def test_customers_field_map_covers_table_and_full_data_fields():
    assert codes("customers") == [
        "code", "fullName", "company", "identityNumber", "phone",
        "email", "identityType", "address", "status",
    ]


def test_rentals_field_map_covers_table_and_full_data_fields():
    expected = [
        "rentalNo", "customer", "phone", "motorcycle", "plate", "startDate", "dueDate",
        "durationDays", "rateType", "rateAmount", "deposit", "discount", "currency",
        "additionalCharges", "rentalCharge", "lateFee", "totalDue", "paid", "outstanding",
        "paymentMethod", "returnDate", "condition", "createdBy", "status",
    ]
    assert codes("rentals") == expected


def test_rental_reports_field_map_matches_report_table():
    assert codes("rental_reports") == [
        "rentalNo", "customer", "motorcycle", "plate", "startDate", "dueDate", "returnDate",
        "rentalCharge", "lateFee", "additionalCharges", "totalDue", "paid", "outstanding",
        "paymentStatus", "paymentMethod",
    ]


def test_expenses_field_map_is_the_combined_ledger():
    assert codes("expenses") == [
        "date", "reference", "description", "type", "amount",
        "currency", "rentalNo", "paymentMethod", "createdBy",
    ]


def test_every_field_has_a_human_label():
    for resource, columns in FIELD_SETS.items():
        assert columns, resource
        for code, label in columns:
            assert code
            assert label and label.strip() and "_" not in label, (resource, code, label)


def test_select_columns_defaults_to_all_and_keeps_stable_order():
    assert _select_columns("motorcycles", None) == FIELD_SETS["motorcycles"]
    assert _select_columns("motorcycles", []) == FIELD_SETS["motorcycles"]


def test_select_columns_follows_requested_order_and_drops_unknown():
    selected = _select_columns("motorcycles", ["plate", "code", "notAField", "status"])
    assert selected == [
        ("plate", "Plate Number"),
        ("code", "Motorcycle Code"),
        ("status", "Status"),
    ]


def _rental(status="Active", **overrides):
    row = {
        "id": "r1",
        "rentalNo": "R-001",
        "customer": "Dara",
        "status": status,
        "startDate": "2026-02-01 09:00",
        "dueDate": "2026-02-05 09:00",
        "totalDue": "120.00",
    }
    row.update(overrides)
    return row


def test_filters_status_and_search():
    rows = [_rental(), _rental("Overdue", id="r2", rentalNo="R-002", customer="Sok")]
    filtered = apply_export_filters(rows, "rentals", {"query": {"status": ["Overdue"]}})
    assert [row["id"] for row in filtered] == ["r2"]

    filtered = apply_export_filters(rows, "rentals", {"query": {"q": "sok"}})
    assert [row["id"] for row in filtered] == ["r2"]


def test_filters_date_range_on_resource_date_key():
    rows = [_rental(), _rental(id="r2", startDate="2026-03-10 09:00")]
    filtered = apply_export_filters(rows, "rentals", {"startDate": "2026-03-01", "endDate": "2026-03-31"})
    assert [row["id"] for row in filtered] == ["r2"]


def test_filters_selected_ids_and_page_ids():
    rows = [_rental(), _rental(id="r2"), _rental(id="r3")]
    by_selected = apply_export_filters(rows, "rentals", {"selectedIds": ["r3"]})
    assert [row["id"] for row in by_selected] == ["r3"]

    by_page = apply_export_filters(rows, "rentals", {"query": {"ids": ["r1", "r2"]}})
    assert [row["id"] for row in by_page] == ["r1", "r2"]


def test_ledger_type_filter_matches_income_case_insensitively():
    rows = [
        {"id": "p1", "type": "Income", "amount": "50.00"},
        {"id": "e1", "type": "Fuel", "amount": "-10.00"},
    ]
    filtered = apply_export_filters(rows, "expenses", {"query": {"types": ["income"]}})
    assert [row["id"] for row in filtered] == ["p1"]

    filtered = apply_export_filters(rows, "expenses", {"query": {"types": ["Fuel"]}})
    assert [row["id"] for row in filtered] == ["e1"]


def test_no_filters_returns_rows_unchanged():
    rows = [_rental(), _rental(id="r2")]
    assert apply_export_filters(rows, "rentals", None) == rows
    assert apply_export_filters(rows, "rentals", {}) == rows
