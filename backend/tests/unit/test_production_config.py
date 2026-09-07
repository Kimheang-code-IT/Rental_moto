import pytest

from app.core.config import Settings
from app.main import create_app

_PROD_OK = {
    "environment": "production",
    "debug": False,
    "cors_allow_private_networks": False,
    "jwt_secret_key": "production-jwt-secret-key-that-is-long-enough-32+",
    "telegram_bot_client_secret": "production-telegram-client-secret-value",
}


def _settings(**overrides) -> Settings:
    return Settings(**{**_PROD_OK, **overrides})


def test_production_settings_accept_rotated_secrets():
    _settings().assert_safe_for_production()


@pytest.mark.parametrize(
    "field,value",
    [
        ("jwt_secret_key", "dev-only-secret-change-me-in-production-0123456789abcdef"),
        ("jwt_secret_key", "CHANGE_ME_LONG_RANDOM_JWT_SECRET"),
        ("jwt_secret_key", "short"),
        ("telegram_bot_client_secret", "dev-only-telegram-secret-change-me-0123456789abcdef"),
        ("debug", True),
        ("cors_allow_private_networks", True),
    ],
)
def test_production_settings_reject_unsafe_values(field, value):
    settings = _settings(**{field: value})
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        settings.assert_safe_for_production()


def test_development_settings_allow_defaults():
    Settings(environment="development").assert_safe_for_production()


def test_session_lifetime_defaults_to_seven_day_refresh():
    assert Settings.model_fields["access_token_expire_minutes"].default == 15
    assert Settings.model_fields["refresh_token_expire_days"].default == 7


def test_production_hides_openapi(monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(config_module, "settings", _settings())
    monkeypatch.setattr("app.main.settings", _settings())
    app = create_app()
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


def test_development_exposes_openapi(monkeypatch):
    from app.core.config import Settings as SettingsModel

    monkeypatch.setattr("app.main.settings", SettingsModel(environment="development", debug=True))
    app = create_app()
    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"
