"""Wipe all database data and re-seed non-auth bootstrap (sequences, settings)."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed import reset_all_data

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await reset_all_data()
    print("Database reset complete. Only non-auth bootstrap data remains (sequences, settings).")
    print("No users and no roles exist. Register the system owner through /auth/setup, then create roles in the UI.")


if __name__ == "__main__":
    asyncio.run(main())
