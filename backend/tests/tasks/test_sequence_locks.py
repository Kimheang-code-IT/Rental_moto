"""Sequence number allocation must be safe under concurrency.

rental_no/payment_no are drawn from a shared DocumentSequence row. Without a
row lock two concurrent requests can draw the same number and hit the unique
constraint (500) — this test pins the FOR UPDATE behavior against real
PostgreSQL.
"""
import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import TEST_DATABASE_URL


async def _allocate(factory, document_type: str) -> str:
    from app.repositories.admin import DocumentSequenceRepository

    async with factory() as session:
        value = await DocumentSequenceRepository(session).next_value(document_type, "RN-", 6, None)
        await session.commit()
        return value


@pytest.mark.asyncio
async def test_concurrent_sequence_allocation_yields_distinct_numbers():
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        values = await asyncio.gather(
            *[_allocate(factory, "RENTAL") for _ in range(5)],
            return_exceptions=False,
        )
        assert len(values) == len(set(values)), f"duplicate sequence numbers allocated: {values}"
        assert all(v for v in values)
    finally:
        await engine.dispose()
