from app.core.permissions import (
    build_all_permissions,
    has_permission,
    is_super_admin,
    rental_staff_permissions,
    viewer_permissions,
)


def test_super_admin_bypasses():
    assert is_super_admin("SuperAdmin", None)
    assert is_super_admin("Staff", ["ALL_PAGES"])
    assert has_permission("SuperAdmin", None, "rental.rentals.delete")


def test_has_permission_positive_and_negative():
    staff = rental_staff_permissions()
    assert has_permission("Rental Staff", staff, "rental.motorcycles.view")
    assert has_permission("Rental Staff", staff, "rental.rentals.create")
    assert not has_permission("Rental Staff", staff, "user.manage")
    assert not has_permission("Rental Staff", staff, "role.manage")


def test_viewer_cannot_create():
    viewer = viewer_permissions()
    assert has_permission("Report Viewer", viewer, "reports.view")
    assert not has_permission("Report Viewer", viewer, "rental.rentals.create")


def test_all_permissions_unique():
    keys = build_all_permissions()
    assert len(keys) == len(set(keys))
    assert "rental.rentals.return" in keys
    assert "telegram.reports.read" in keys


def test_empty_permissions_denied():
    assert not has_permission("Rental Staff", [], "dashboard.view")
    assert not has_permission(None, None, "dashboard.view")
