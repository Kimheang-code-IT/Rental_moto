import logging
import time

import httpx

logger = logging.getLogger("hollywing.bot.api")


class ApiClient:
    """FastAPI client using short-lived service JWTs."""

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

    async def get(self, path: str, params: dict | None = None, user_token: str | None = None) -> dict:
        token = user_token or await self._ensure_token()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 401 and user_token is None:
                self._token = None
                token = await self._ensure_token()
                response = await client.get(
                    f"{self.base_url}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, payload: dict | None = None, user_token: str | None = None) -> dict:
        token = user_token or await self._ensure_token()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}{path}",
                json=payload or {},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
