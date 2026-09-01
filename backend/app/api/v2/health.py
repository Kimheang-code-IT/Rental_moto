from fastapi import APIRouter

from app.api.deps import envelope
from app.core.config import settings
from app.core.redis import cache

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return envelope({"status": "ok", "environment": settings.environment})


@router.get("/health/live")
async def live() -> dict:
    return envelope({"status": "ok"})


@router.get("/health/ready")
async def ready() -> dict:
    checks: dict[str, str] = {}
    overall = True

    try:
        from sqlalchemy import text

        from app.core.database import SessionFactory

        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"
        overall = False

    checks["redis"] = "ok" if await cache.ping() else "error"
    if checks["redis"] == "error":
        overall = overall and False

    try:
        import kombu

        connection = kombu.Connection(settings.rabbitmq_url)
        try:
            connection.ensure_connection(max_retries=0, timeout=2)
            checks["rabbitmq"] = "ok"
        finally:
            connection.release()
    except Exception as exc:
        checks["rabbitmq"] = f"error: {exc}"
        overall = overall and False

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
