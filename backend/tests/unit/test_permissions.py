from app.core.permissions import (
    ASSIGNABLE_PERMISSIONS,
    build_all_permissions,
    effective_permissions,
    has_permission,
    is_super_admin,
    rental_staff_permissions,
    normalize_role_permissions,
    permission_catalog,
    user_has_permission,
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


def test_explicit_catalog_has_only_assignable_role_permissions():
    catalog_keys = {
        permission
        for group in permission_catalog()
        for permission in group["permissions"]
    }
    assert catalog_keys == set(ASSIGNABLE_PERMISSIONS)
    assert "user.manage" not in catalog_keys
    assert "telegram.reports.read" not in catalog_keys


def test_action_permissions_imply_view():
    assert normalize_role_permissions(["rental.rentals.return"]) == [
        "rental.rentals.view",
        "rental.rentals.return",
    ]


def test_effective_permissions_use_role_relation_only():
    from types import SimpleNamespace

    user = SimpleNamespace(
        role="SuperAdmin",
        permissions=["ALL_PAGES"],
        page_access=["ALL_PAGES"],
        role_ref=SimpleNamespace(name="Restricted", permissions=["reports.view"]),
    )
    assert effective_permissions(user) == ["reports.view"]
    assert user_has_permission(user, "reports.view")
    assert not user_has_permission(user, "admin.roles.edit")


def test_empty_role_denies_even_with_legacy_user_permissions():
    from types import SimpleNamespace

    user = SimpleNamespace(role="SuperAdmin", permissions=["ALL_PAGES"], role_ref=None)
    assert effective_permissions(user) == []
    assert not user_has_permission(user, "dashboard.view")
