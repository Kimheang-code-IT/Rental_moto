import asyncio
import logging

from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import SessionFactory, engine
from app.core.security import hash_password, utcnow
from app.core.permissions import rental_staff_permissions, viewer_permissions
from app.models import (
    AppSetting,
    DocumentSequence,
    Role,
    StorageProvider,
    User,
)
from app.services.admin_service import default_document_sequences

logger = logging.getLogger("hollywing.seed")


async def seed_bootstrap() -> None:
    """Seed only system bootstrap data: roles, admin user, sequences, app info."""
    async with SessionFactory() as session:
        super_admin_role = (await session.execute(select(Role).where(Role.name == "SuperAdmin"))).scalar_one_or_none()
        if super_admin_role is None:
            super_admin_role = Role(
                name="SuperAdmin",
                description="Full system access",
                permissions=["ALL_PAGES"],
                page_access=["ALL_PAGES"],
                is_system=True,
            )
            session.add(super_admin_role)
        else:
            super_admin_role.permissions = ["ALL_PAGES"]
            super_admin_role.page_access = ["ALL_PAGES"]
            super_admin_role.is_system = True

        staff_role = (await session.execute(select(Role).where(Role.name == "Rental Staff"))).scalar_one_or_none()
        if staff_role is None:
            staff_role = Role(
                name="Rental Staff",
                description="Rental operations staff",
                permissions=rental_staff_permissions(),
                page_access=rental_staff_permissions(),
                is_system=True,
            )
            session.add(staff_role)
        else:
            staff_role.permissions = rental_staff_permissions()
            staff_role.page_access = rental_staff_permissions()
            staff_role.is_system = True

        viewer_role = (await session.execute(select(Role).where(Role.name == "Report Viewer"))).scalar_one_or_none()
        if viewer_role is None:
            viewer_role = Role(
                name="Report Viewer",
                description="Read-only reporting access",
                permissions=viewer_permissions(),
                page_access=viewer_permissions(),
                is_system=True,
            )
            session.add(viewer_role)
        else:
            viewer_role.permissions = viewer_permissions()
            viewer_role.page_access = viewer_permissions()
            viewer_role.is_system = True
        await session.flush()

        admin = (await session.execute(select(User).where(User.email == settings.seed_admin_email))).scalar_one_or_none()
        if admin is None:
            admin = User(
                username="admin",
                display_name=settings.seed_admin_name,
                email=settings.seed_admin_email,
                password_hash=hash_password(settings.seed_admin_password),
                role="SuperAdmin",
                role_id=super_admin_role.id,
                status="Active",
                permissions=None,
                page_access=None,
            )
            session.add(admin)
            logger.info("Created admin user %s", settings.seed_admin_email)
        else:
            admin.role = super_admin_role.name
            admin.role_id = super_admin_role.id
            admin.permissions = None
            admin.page_access = None

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
