import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks")


def run_async(coro):
    """Run async task code on a fresh loop and dispose DB pool connections afterward.

    Celery prefork workers reuse processes; SQLAlchemy/asyncpg connections must not
    survive across per-task event loops.
    """
    from app.core.database import engine

    async def _runner():
        try:
            return await coro
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_runner())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(None)


class BaseTask(celery_app.Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 5

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        super().on_failure(exc, task_id, args, kwargs, einfo)
