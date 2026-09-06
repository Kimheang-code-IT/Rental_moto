import asyncio
import logging

from fastapi import APIRouter

from app.api.deps import envelope
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import cache

logger = logging.getLogger("hollywing.health")
setup_logging()

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Process is alive — cheap, no dependency checks."""
    return envelope({"status": "ok", "environment": settings.environment})


@router.get("/health/live")
async def live() -> dict:
    return envelope({"status": "ok"})


@router.get("/health/ready")
async def ready() -> dict:
    """Required dependencies available. Never leaks internal error details."""
    checks: dict[str, str] = {}
    overall = True

    try:
        from sqlalchemy import text

        from app.core.database import SessionFactory

        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        logger.exception("Health readiness check failed for postgres")
        checks["postgres"] = "error"
        overall = False

    checks["redis"] = "ok" if await cache.ping() else "error"
    if checks["redis"] == "error":
        overall = False

    try:
        from redis import asyncio as aioredis

        client = aioredis.from_url(settings.celery_broker_url, decode_responses=True)
        try:
            await asyncio.wait_for(client.ping(), timeout=2)
            checks["celery_broker"] = "ok"
        finally:
            await client.aclose()
    except Exception:
        logger.exception("Health readiness check failed for celery broker")
        checks["celery_broker"] = "error"
        overall = False

    return envelope({"status": "ok" if overall else "degraded", "checks": checks})


@router.get("/health/workers")
async def workers() -> dict:
    from app.tasks.celery_app import celery_app

    try:
        inspector = celery_app.control.inspect(timeout=2)
        ping = inspector.ping() or {}
        stats = inspector.stats() or {}
        queues = []
        for name in stats:
            queues.append({"worker": name, "concurrency": stats[name].get("pool", {}).get("max-concurrency")})
        return envelope({"status": "ok" if ping else "no_workers", "workers": queues, "ping": list(ping.keys())})
    except Exception as exc:
        return envelope({"status": "error", "error": str(exc)})
