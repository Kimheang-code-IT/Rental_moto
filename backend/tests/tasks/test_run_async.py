"""Celery async runner disposes the SQLAlchemy engine between task loops."""

import asyncio

from app.core.database import engine
from app.tasks.base import run_async


def test_run_async_disposes_engine_between_loops():
    seen = []

    async def sample():
        seen.append(asyncio.get_running_loop())
        return "ok"

    assert run_async(sample()) == "ok"
    assert run_async(sample()) == "ok"
    assert len({id(loop) for loop in seen}) == 2

    async def _pool_is_fresh():
        return engine.pool.status()

    status = run_async(_pool_is_fresh())
    assert isinstance(status, str)
