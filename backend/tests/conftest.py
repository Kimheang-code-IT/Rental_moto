import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://rental:rental@localhost:55432/rental_moto_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:56379/5")
os.environ.setdefault("CELERY_BROKER_URL", "amqp://rental:rental@localhost:55672/rental")
os.environ.setdefault("RABBITMQ_URL", "amqp://rental:rental@localhost:55672/rental")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "false")
os.environ.setdefault("RATE_LIMIT_LOGIN_PER_MINUTE", "1000")
os.environ.setdefault("RATE_LIMIT_REFRESH_PER_MINUTE", "1000")
os.environ.setdefault("RATE_LIMIT_RESET_PER_HOUR", "1000")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")

import asyncio
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_DB_URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
TEST_DB_NAME = TEST_DATABASE_URL.rsplit("/", 1)[1]

# Test-only account fixtures. The application and seed create no users and no
# roles; these fixtures exist so API tests can log in without shipping default
# credentials. The owner mirrors what POST /api/v2/auth/setup produces; the
# staff/viewer roles are inserted here exactly as the operator would create
# them through the roles API.
TEST_ADMIN_EMAIL = "owner@example.com"
TEST_ADMIN_PASSWORD = "test-admin-password"
TEST_ADMIN_NAME = "Owner"
TEST_STAFF_EMAIL = "staff@example.com"
TEST_STAFF_PASSWORD = "test-staff-password"
TEST_VIEWER_EMAIL = "viewer@example.com"
TEST_VIEWER_PASSWORD = "test-viewer-password"

STAFF_PERMISSIONS = [
    "dashboard.view",
    "rental.motorcycles.view", "rental.motorcycles.create", "rental.motorcycles.edit",
    "rental.customers.view", "rental.customers.create", "rental.customers.edit",
    "rental.rentals.view", "rental.rentals.create", "rental.rentals.edit",
    "rental.rentals.return", "rental.rentals.print",
    "rental.finance.view", "rental.finance.create",
    "reports.view", "reports.print",
]

VIEWER_PERMISSIONS = [
    "dashboard.view",
    "rental.motorcycles.view",
    "rental.customers.view",
    "rental.rentals.view", "rental.rentals.print",
    "rental.finance.view",
    "reports.view", "reports.print",
]


async def create_bootstrap_users() -> None:
    """Create the test owner plus staff/viewer fixture roles (test only)."""
    from app.core.security import hash_password
    from app.models import Role, User
    from app.repositories.admin import UserRepository

    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            from sqlalchemy import select

            existing_roles = (await session.execute(select(Role))).scalars().all()
            by_name = {role.name: role for role in existing_roles}
            staff_role = by_name.get("Rental Staff")
            if staff_role is None:
                staff_role = Role(
                    name="Rental Staff",
                    description="Rental operations staff (test fixture)",
                    permissions=STAFF_PERMISSIONS,
                    page_access=STAFF_PERMISSIONS,
                )
                session.add(staff_role)
            viewer_role = by_name.get("Report Viewer")
            if viewer_role is None:
                viewer_role = Role(
                    name="Report Viewer",
                    description="Read-only reporting access (test fixture)",
                    permissions=VIEWER_PERMISSIONS,
                    page_access=VIEWER_PERMISSIONS,
                )
                session.add(viewer_role)
            await session.flush()

            users = UserRepository(session)
            owner = User(
                username="owner",
                display_name=TEST_ADMIN_NAME,
                email=TEST_ADMIN_EMAIL,
                password_hash=hash_password(TEST_ADMIN_PASSWORD),
                role=None,
                role_id=None,
                is_owner=True,
                status="Active",
                permissions=None,
                page_access=None,
            )
            staffer = User(
                username="staffer",
                display_name="Staffer",
                email=TEST_STAFF_EMAIL,
                password_hash=hash_password(TEST_STAFF_PASSWORD),
                role=staff_role.name,
                role_id=staff_role.id,
                is_owner=False,
                status="Active",
                permissions=None,
                page_access=None,
            )
            viewer = User(
                username="viewer",
                display_name="Viewer",
                email=TEST_VIEWER_EMAIL,
                password_hash=hash_password(TEST_VIEWER_PASSWORD),
                role=viewer_role.name,
                role_id=viewer_role.id,
                is_owner=False,
                status="Active",
                permissions=None,
                page_access=None,
            )
            for user in (owner, staffer, viewer):
                await users.create(user)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def _prepare_database() -> None:
    async def _run() -> None:
        admin_engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
        async with admin_engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
            )
            if exists.scalar() is None:
                await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
        await admin_engine.dispose()

        from app.core import database as db_module
        from app.models import Base

        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        temp_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        original_factory = db_module.SessionFactory
        db_module.SessionFactory = temp_factory
        try:
            from app.seed import seed

            await seed()
            # Seed creates sequences/settings only — never users, never roles.
            await create_bootstrap_users()
        finally:
            db_module.SessionFactory = original_factory
        await engine.dispose()

    asyncio.run(_run())


@pytest_asyncio.fixture
async def db_session(_prepare_database) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(_prepare_database) -> AsyncIterator[httpx.AsyncClient]:
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def admin_headers(client: httpx.AsyncClient) -> dict:
    response = await client.post(
        "/api/v2/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}
