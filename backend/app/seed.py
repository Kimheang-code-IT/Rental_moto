import asyncio
import logging

from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import SessionFactory, engine
from app.core.security import utcnow
from app.models import (
    AppSetting,
    DocumentSequence,
    StorageProvider,
)
from app.services.admin_service import default_document_sequences

logger = logging.getLogger("hollywing.seed")


async def seed_bootstrap() -> None:
    """Seed only non-auth bootstrap data: sequences, app info, storage provider.

    Roles are NEVER created here: the operator defines every role through
    Administration → Roles after the first administrator completes setup.
    Users are NEVER created here: the first administrator registers through
    POST /api/v2/auth/setup while the users table is empty (the setup page is
    the only public bootstrap path); later staff are created by the owner or
    another admin at /administration/users.
    """
    async with SessionFactory() as session:
        for spec in default_document_sequences():
            existing = (await session.execute(select(DocumentSequence).where(DocumentSequence.document_type == spec["document_type"]))).scalar_one_or_none()
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

        if settings.minio_enabled:
            minio_provider = await session.get(StorageProvider, "sp-minio")
            if minio_provider is None:
                existing_default = (
                    await session.execute(select(StorageProvider).where(StorageProvider.is_default.is_(True)))
                ).scalar_one_or_none()
                endpoint = settings.minio_endpoint
                if "://" not in endpoint:
                    endpoint = f"{'https' if settings.minio_secure else 'http'}://{endpoint}"
                session.add(
                    StorageProvider(
                        id="sp-minio",
                        name="HollyWing MinIO",
                        type="minio",
                        active=True,
                        is_default=existing_default is None,
                        max_file_size_mb=25,
                        allowed_file_types=["pdf", "csv", "xlsx"],
                        access_mode="private",
                        upload_path_pattern="{entity}/{yyyy}/{mm}/{id}",
                        connection_status="not_tested",
                        endpoint=endpoint,
                        region="us-east-1",
                        bucket=settings.minio_bucket,
                        access_key=settings.minio_access_key,
                        secret_key=settings.minio_secret_key,
                        path_style=True,
                    )
                )

        await session.commit()
        logger.info("Bootstrap seed completed")


async def seed() -> None:
    await seed_bootstrap()


async def reset_all_data() -> None:
    """Delete all business and auth data, then re-seed bootstrap only."""
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
        "storage_providers",
        "password_reset_challenges",
        "refresh_token_sessions",
        "telegram_link_codes",
        "users",
        "roles",
        "document_sequences",
        "app_settings",
    ]
    async with engine.begin() as conn:
        for table in tables:
            await conn.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))
    logger.info("All tables truncated")
    await seed_bootstrap()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
