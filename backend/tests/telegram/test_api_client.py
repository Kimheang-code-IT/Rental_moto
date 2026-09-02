import httpx
import pytest


class _StubResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class _StubClient:
    calls = []
    get_count = 0

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self._gets = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        _StubClient.calls.append(("POST", url, json, headers))
        if url.endswith("/auth/service-token"):
            return _StubResponse(200, {"data": {"accessToken": "svc-token", "expiresIn": 600}})
        return _StubResponse(200, {"data": {}})

    async def get(self, url, params=None, headers=None):
        _StubClient.calls.append(("GET", url, params, headers))
        self._gets += 1
        token = (headers or {}).get("Authorization", "")
        if self._gets == 1 and token.endswith("svc-token"):
            return _StubResponse(401)
        return _StubResponse(200, {"data": {"modules": {"finance": True}}})


async def test_api_client_refreshes_service_token(monkeypatch):
    from telegram_bot.api_client import ApiClient

    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)
    _StubClient.calls = []

    api = ApiClient("http://api", "client", "secret")
    result = await api.get(
        "/api/v2/telegram/access",
        telegram_user_id="1",
        telegram_chat_id="1",
        telegram_chat_type="private",
    )

    assert result["data"]["modules"]["finance"] is True
    posts = [c for c in _StubClient.calls if c[0] == "POST"]
    assert any("auth/service-token" in c[1] for c in posts)
    gets = [c for c in _StubClient.calls if c[0] == "GET"]
    assert len(gets) == 2


class _NoRetryStubClient(_StubClient):
    async def get(self, url, params=None, headers=None):
        _StubClient.calls.append(("GET", url, params, headers))
        return _StubResponse(200, {"data": {"modules": {"finance": True}}})


async def test_api_client_sends_context_headers(monkeypatch):
    from telegram_bot.api_client import ApiClient

    monkeypatch.setattr(httpx, "AsyncClient", _NoRetryStubClient)
    _StubClient.calls = []

    api = ApiClient("http://api", "client", "secret")
    await api.get(
        "/api/v2/telegram/access",
        telegram_user_id="42",
        telegram_chat_id="-10099",
        telegram_chat_type="group",
    )

    gets = [c for c in _StubClient.calls if c[0] == "GET"]
    assert len(gets) == 1
    headers = gets[0][3]
    assert headers["X-Telegram-User-Id"] == "42"
    assert headers["X-Telegram-Chat-Id"] == "-10099"
    assert headers["X-Telegram-Chat-Type"] == "group"


def test_bot_module_imports():
    import telegram_bot.api_client
    import telegram_bot.formatter
    import telegram_bot.keyboards
    import telegram_bot.state

    keyboard = telegram_bot.keyboards.main_menu({"finance": True, "motorcycles": True, "customers": False, "rentals": True}, private=True)
    labels = [btn.text for row in keyboard.keyboard for btn in row]
    assert "💰 Finance" in labels
    period = telegram_bot.keyboards.period_menu()
    period_labels = [btn.text for row in period.keyboard for btn in row]
    assert "📅 Today" in period_labels
