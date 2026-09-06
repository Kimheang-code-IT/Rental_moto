import logging
from datetime import timedelta
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionFactory
from app.core.security import utcnow

logger = logging.getLogger("hollywing.tasks.maintenance")


async def cleanup_expired_data() -> dict:
    removed_exports = 0
    async with SessionFactory() as session:
        from sqlalchemy import delete

        from app.models import ExportJob, OutboxEvent, TaskProgress

        now = utcnow()
        await session.execute(
            delete(ExportJob).where(ExportJob.expires_at.is_not(None), ExportJob.expires_at < now)
        )
        await session.execute(
            delete(TaskProgress).where(TaskProgress.expires_at.is_not(None), TaskProgress.expires_at < now)
        )
        cutoff = now - timedelta(days=7)
        await session.execute(
            delete(OutboxEvent).where(OutboxEvent.status == "published", OutboxEvent.published_at < cutoff)
        )
        await session.commit()

    export_root = Path(settings.export_dir)
    if export_root.exists():
        for path in export_root.glob("**/*"):
            if path.is_file():
                try:
                    if path.stat().st_mtime < (utcnow() - timedelta(days=7)).timestamp():
                        path.unlink()
                        removed_exports += 1
                except OSError:
                    pass
    return {"removedExports": removed_exports}
