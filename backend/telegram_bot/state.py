"""Redis-backed per-user navigation state."""

import json

from redis import asyncio as aioredis

NAV_PREFIX = "bot:nav:"
PAGE_PREFIX = "bot:page:"
RESET_PREFIX = "bot:reset:"
STATE_TTL = 900


class BotState:
    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis

    def _nav_key(self, chat_id: str, user_id: str) -> str:
        return f"{NAV_PREFIX}{chat_id}:{user_id}"

    def _page_key(self, chat_id: str, user_id: str) -> str:
        return f"{PAGE_PREFIX}{chat_id}:{user_id}"

    def _reset_key(self, chat_id: str, user_id: str) -> str:
        return f"{RESET_PREFIX}{chat_id}:{user_id}"

    async def get_nav(self, chat_id: str, user_id: str) -> dict:
        raw = await self.redis.get(self._nav_key(chat_id, user_id))
        return json.loads(raw) if raw else {"stack": ["root"], "data": {}}

    async def set_nav(self, chat_id: str, user_id: str, nav: dict) -> None:
        await self.redis.set(self._nav_key(chat_id, user_id), json.dumps(nav), ex=STATE_TTL)

    async def push(self, chat_id: str, user_id: str, level: str, data: dict | None = None) -> dict:
        nav = await self.get_nav(chat_id, user_id)
        nav["stack"].append(level)
        nav.setdefault("data", {}).update(data or {})
        await self.set_nav(chat_id, user_id, nav)
        return nav

    async def pop(self, chat_id: str, user_id: str) -> dict:
        nav = await self.get_nav(chat_id, user_id)
        if len(nav["stack"]) > 1:
            nav["stack"].pop()
        await self.set_nav(chat_id, user_id, nav)
        return nav

    async def reset(self, chat_id: str, user_id: str) -> None:
        await self.set_nav(chat_id, user_id, {"stack": ["root"], "data": {}})

    async def set_page(self, chat_id: str, user_id: str, page: int, meta: dict | None = None) -> None:
        payload = {"page": page, "meta": meta or {}}
        await self.redis.set(self._page_key(chat_id, user_id), json.dumps(payload), ex=STATE_TTL)

    async def get_page(self, chat_id: str, user_id: str) -> dict:
        raw = await self.redis.get(self._page_key(chat_id, user_id))
        return json.loads(raw) if raw else {"page": 1, "meta": {}}

    async def set_reset_flow(self, chat_id: str, user_id: str, step: str | None) -> None:
        key = self._reset_key(chat_id, user_id)
        if step is None:
            await self.redis.delete(key)
        else:
            await self.redis.set(key, step, ex=STATE_TTL)

    async def get_reset_flow(self, chat_id: str, user_id: str) -> str | None:
        return await self.redis.get(self._reset_key(chat_id, user_id))
