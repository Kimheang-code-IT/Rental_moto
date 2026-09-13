"""Store tendered deposit currency amounts on rentals for invoice display.

Revision ID: h9c0d1e2f3g4
Revises: g8b9c0d1e2f3
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa


revision = "h9c0d1e2f3g4"
down_revision = "g8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rentals",
        sa.Column("deposit_tendered_amount", sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        "rentals",
        sa.Column("deposit_currency", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "rentals",
        sa.Column("exchange_rate", sa.Numeric(precision=14, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rentals", "exchange_rate")
    op.drop_column("rentals", "deposit_currency")
    op.drop_column("rentals", "deposit_tendered_amount")
