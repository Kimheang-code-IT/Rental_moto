import asyncio
import logging
from pathlib import Path

from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import SessionFactory, engine
from app.core.security import utcnow
from app.models import (
    AppSetting,
    DocumentSequence,
)
from app.services.admin_service import default_document_sequences

logger = logging.getLogger("hollywing.seed")


async def seed_bootstrap() -> None:
    """Seed only non-auth bootstrap data: sequences and app info.

    Roles are NEVER created here: the operator defines every role through
    Administration → Roles after the first administrator completes setup.
    Users are NEVER created here: the first administrator registers through
    POST /api/v2/auth/setup while the users table is empty (the setup page is
    the only public bootstrap path); later staff are created by the owner or
    another admin at /administration/users.
    """
    async with SessionFactory() as session:
        for spec in default_document_sequences():
            existing = (
                await session.execute(
                    select(DocumentSequence).where(DocumentSequence.document_type == spec["document_type"])
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    DocumentSequence(
                        id=f"ds-{spec['document_type'].lower().replace('_', '-')}",
                        document_type=spec["document_type"],
                        prefix=spec.get("prefix", ""),
                        padding_length=spec.get("padding_length", 6),
                        year=spec.get("year"),
                    )
                )

        app_info = await session.get(AppSetting, "app_info")
        if app_info is None:
            session.add(
                AppSetting(
                    key="app_info",
                    value={
                        "applicationName": "HollyWing Motor",
                        "shortName": "HollyWing",
                        "businessName": "HollyWing Motor Rental",
                        "address": "Phnom Penh, Cambodia",
                        "branding": {"primaryColor": "#e8472a", "secondaryColor": "#3a539f"},
                        "footer": {"copyrightText": "© HollyWing Motor"},
                        "updatedAt": utcnow().isoformat(),
                    },
                )
            )

        await session.commit()
        logger.info("Bootstrap seed completed")


async def seed() -> None:
    await seed_bootstrap()


def _clear_export_files() -> int:
    export_root = Path(settings.export_dir)
    if not export_root.exists():
        return 0
    removed = 0
    for path in export_root.glob("**/*"):
        if path.is_file():
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    # Remove empty directories left behind.
    for path in sorted(export_root.glob("**/*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    return removed


async def reset_all_data() -> dict:
    """Delete operational business data and export files; keep auth and config.

    Preserved: users, roles, document sequences, app settings, storage providers,
    and refresh-token sessions. Missing sequences/app-info are re-seeded only if
    absent. Callers that hold an open request session must rollback/expire it
    first so TRUNCATE is not blocked by locks on truncated tables.
    """
    tables = [
        "rental_payments",
        "rental_charges",
        "rental_expenses",
        "rentals",
        "rental_customers",
        "motorcycles",
        "audit_logs",
        "export_jobs",
        "outbox_events",
        "task_progress",
        "password_reset_challenges",
        "telegram_link_codes",
    ]
    async with engine.begin() as conn:
        for table in tables:
            await conn.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))
    logger.info("Operational tables truncated; users, roles, sequences, and settings kept")

    removed_exports = await asyncio.to_thread(_clear_export_files)
    logger.info("Cleared %s export file(s) under %s", removed_exports, settings.export_dir)

    await seed_bootstrap()
    return {"removedExports": removed_exports}


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
