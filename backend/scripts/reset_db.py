"""Wipe all database data and re-seed bootstrap (roles, admin, sequences)."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed import reset_all_data

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await reset_all_data()
    print("Database reset complete. Only bootstrap data remains (admin user, roles, sequences).")


if __name__ == "__main__":
    asyncio.run(main())
