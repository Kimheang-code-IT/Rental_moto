"""`AuthUserResponse` must match the live `_auth_user_payload` contract.

The login and /auth/me routes return `_auth_user_payload` directly, so the
schema is the documented contract. This test fails if the payload gains or
loses fields (roleId, effectivePermissions, telegramLinked, ...) without the
schema being updated.
"""

from types import SimpleNamespace

from app.api.v2.auth import _auth_user_payload
from app.schemas.auth import AuthUserResponse

from tests.conftest import STAFF_PERMISSIONS


def _staff_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        display_name="Staff User",
        email="staff@example.com",
        role_id=2,
        is_owner=False,
        role_ref=SimpleNamespace(name="Rental Staff", permissions=STAFF_PERMISSIONS),
        avatar_url=None,
        telegram_linked_at=None,
        telegram_chat_id=None,
    )


def test_payload_matches_schema():
    user = _staff_user()
    payload = _auth_user_payload(user)
    # The payload uses snake_case field names; populate_by_name on CamelModel
    # lets model_validate accept them before FastAPI serializes camelCase.
    validated = AuthUserResponse.model_validate(payload)
    assert validated.role_id == 2
    assert validated.role == "Rental Staff"
    assert validated.telegram_linked is False
    assert validated.effective_permissions  # role-derived, non-empty


def test_payload_mirrors_are_role_derived_and_equal():
    payload = _auth_user_payload(_staff_user())
    expected = STAFF_PERMISSIONS
    assert payload["effectivePermissions"] == expected
    assert payload["permissions"] == expected
    assert payload["pageAccess"] == expected
    assert payload["sourcePermissions"] == expected
    # No denormalized user-level grants leak into the contract.
    assert "ALL_PAGES" not in payload["effectivePermissions"]
