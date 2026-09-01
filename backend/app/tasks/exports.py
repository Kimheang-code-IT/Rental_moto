import logging

from app.services.export_service import process_export
from app.tasks.base import BaseTask, run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger("hollywing.tasks.exports")


@celery_app.task(base=BaseTask, bind=True, name="app.tasks.exports.export_resource", max_retries=3)
def export_resource(self, export_id: str, task_id: str) -> dict:
    async def _run() -> dict:
        from app.core.database import SessionFactory as Factory

        async with Factory() as session:
            await process_export(session, export_id, task_id)
            return {"exportId": export_id, "taskId": task_id}

    return run_async(_run())
