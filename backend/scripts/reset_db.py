"""Wipe operational business data; keep users, roles, sequences, and settings."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed import reset_all_data

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await reset_all_data()
    print("Database reset complete. Users, roles, document sequences, and settings were kept.")
    print("Rentals, customers, motorcycles, payments, charges, expenses, and related operational data were removed.")


if __name__ == "__main__":
    asyncio.run(main())
