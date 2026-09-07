import logging
import time

import httpx

logger = logging.getLogger("hollywing.bot.api")


class ApiClient:
    """FastAPI client using short-lived service JWTs and Telegram context headers."""

    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_exp: float = 0

    async def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.base_url}/api/v2/auth/service-token",
                json={"clientId": self.client_id, "clientSecret": self.client_secret},
            )
            response.raise_for_status()
            data = response.json()["data"]
            self._token = data["accessToken"]
            self._token_exp = time.time() + data.get("expiresIn", 600)
            return self._token

    def _context_headers(
        self,
        telegram_user_id: str | None,
        telegram_chat_id: str | None,
        telegram_chat_type: str | None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {}
        if telegram_user_id:
            headers["X-Telegram-User-Id"] = str(telegram_user_id)
        if telegram_chat_id:
            headers["X-Telegram-Chat-Id"] = str(telegram_chat_id)
        if telegram_chat_type:
            headers["X-Telegram-Chat-Type"] = str(telegram_chat_type)
        return headers

    async def get(
        self,
        path: str,
        params: dict | None = None,
        *,
        telegram_user_id: str | None = None,
        telegram_chat_id: str | None = None,
        telegram_chat_type: str | None = None,
    ) -> dict:
        token = await self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}
        headers.update(self._context_headers(telegram_user_id, telegram_chat_id, telegram_chat_type))
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
            if response.status_code == 401:
                self._token = None
                token = await self._ensure_token()
                headers["Authorization"] = f"Bearer {token}"
                response = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    async def post(
        self,
        path: str,
        payload: dict | None = None,
        *,
        telegram_user_id: str | None = None,
        telegram_chat_id: str | None = None,
        telegram_chat_type: str | None = None,
    ) -> dict:
        token = await self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}
        headers.update(self._context_headers(telegram_user_id, telegram_chat_id, telegram_chat_type))
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload or {}, headers=headers)
            response.raise_for_status()
            return response.json()

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
