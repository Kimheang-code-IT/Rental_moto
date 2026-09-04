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
    response = await client.post("/api/v2/auth/login", json={"email": "admin@gmail.com", "password": "123456"})
    assert response.status_code == 200, response.text
    token = response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}
