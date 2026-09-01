"""Redis-backed conversation state, pagination cursors, and callback idempotency."""

import json

from redis import asyncio as aioredis

STATE_PREFIX = "bot:state:"
PAGE_PREFIX = "bot:page:"
CALLBACK_PREFIX = "bot:cb:"
STATE_TTL = 900
PAGE_TTL = 300


class BotState:
    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis

    async def set_conversation(self, chat_id: str, state: dict) -> None:
        await self.redis.set(f"{STATE_PREFIX}{chat_id}", json.dumps(state), ex=STATE_TTL)

    async def get_conversation(self, chat_id: str) -> dict | None:
        raw = await self.redis.get(f"{STATE_PREFIX}{chat_id}")
        return json.loads(raw) if raw else None

    async def clear_conversation(self, chat_id: str) -> None:
        await self.redis.delete(f"{STATE_PREFIX}{chat_id}")

    async def set_page(self, chat_id: str, view: str, page: int, meta: dict | None = None) -> None:
        payload = {"view": view, "page": page, "meta": meta or {}}
        await self.redis.set(f"{PAGE_PREFIX}{chat_id}", json.dumps(payload), ex=PAGE_TTL)

    async def get_page(self, chat_id: str) -> dict | None:
        raw = await self.redis.get(f"{PAGE_PREFIX}{chat_id}")
        return json.loads(raw) if raw else None

    async def consume_callback(self, callback_id: str) -> bool:
        try:
            result = await self.redis.set(f"{CALLBACK_PREFIX}{callback_id}", "1", ex=60, nx=True)
            return bool(result)
        except Exception:
            return True
