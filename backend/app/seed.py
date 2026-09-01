import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionFactory
from app.core.security import hash_password, utcnow
from app.core.permissions import rental_staff_permissions, viewer_permissions
from app.models import (
    AppSetting,
    DocumentSequence,
    Motorcycle,
    RentalCustomer,
    Role,
    User,
)
from app.services.admin_service import default_document_sequences

logger = logging.getLogger("hollywing.seed")


async def seed() -> None:
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

        staff_role = (await session.execute(select(Role).where(Role.name == "Rental Staff"))).scalar_one_or_none()
        if staff_role is None:
            staff_role = Role(
                name="Rental Staff",
                description="Rental operations staff",
                permissions=rental_staff_permissions(),
                page_access=rental_staff_permissions(),
            )
            session.add(staff_role)

        viewer_role = (await session.execute(select(Role).where(Role.name == "Report Viewer"))).scalar_one_or_none()
        if viewer_role is None:
            viewer_role = Role(
                name="Report Viewer",
                description="Read-only reporting access",
                permissions=viewer_permissions(),
                page_access=viewer_permissions(),
            )
            session.add(viewer_role)
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
                permissions=["ALL_PAGES"],
                page_access=["ALL_PAGES"],
            )
            session.add(admin)
            logger.info("Created development admin %s", settings.seed_admin_email)

        demo_users = [
            ("staff@example.com", "staff", "Rental Staff", staff_role, rental_staff_permissions()),
            ("viewer@example.com", "viewer", "Report Viewer", viewer_role, viewer_permissions()),
        ]
        for email, username, role_name, role, permissions in demo_users:
            existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing is None:
                session.add(
                    User(
                        username=username,
                        display_name=role_name,
                        email=email,
                        password_hash=hash_password(settings.seed_admin_password),
                        role=role_name,
                        role_id=role.id,
                        status="Active",
                        permissions=permissions,
                        page_access=permissions,
                    )
                )
                logger.info("Created development demo user %s (development-only)", email)

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

        app_info = (await session.get(AppSetting, "app_info"))
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

        moto_count = (await session.execute(select(Motorcycle.id).limit(1))).scalar_one_or_none()
        if moto_count is None:
            for index in range(1, 13):
                moto_id = f"mc-{index:03d}"
                session.add(
                    Motorcycle(
                        id=moto_id,
                        code=f"MC-{index:03d}",
                        model=f"Demo Model {index}",
                        brand="Honda" if index % 2 else "Yamaha",
                        year=2023,
                        color="Black",
                        plate=f"PP-{index}K-0000",
                        chassis_no=f"CH-{index:06d}",
                        engine_no=f"EN-{index:06d}",
                        daily_rate=10,
                        three_day_rate=30,
                        weekly_rate=65,
                        monthly_rate=220,
                        asset_value=1500,
                        currency="USD",
                        status="Available",
                    )
                )
            logger.info("Seeded 12 demo motorcycles")

        customer_count = (await session.execute(select(RentalCustomer.id).limit(1))).scalar_one_or_none()
        if customer_count is None:
            session.add(
                RentalCustomer(
                    id="rc-001",
                    code="CUS-001",
                    full_name="Demo Customer",
                    identity_type="National ID",
                    identity_number="KH-000000000",
                    phone="+855 00 000 000",
                    status="Active",
                )
            )
            session.add(
                RentalCustomer(
                    id="rc-002",
                    code="CUS-002",
                    full_name="Inactive Customer",
                    identity_type="Passport",
                    identity_number="XX-000000000",
                    phone="+855 00 000 001",
                    status="Inactive",
                )
            )
            logger.info("Seeded demo customers")

        await session.commit()
        logger.info("Seed completed")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await seed()


if __name__ == "__main__":
    asyncio.run(main())


