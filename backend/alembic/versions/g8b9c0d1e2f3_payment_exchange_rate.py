"""Add tendered amount and exchange rate on rental payments.

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa


revision = "g8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rental_payments",
        sa.Column("tendered_amount", sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        "rental_payments",
        sa.Column("exchange_rate", sa.Numeric(precision=14, scale=4), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("rental_payments", "exchange_rate")
    op.drop_column("rental_payments", "tendered_amount")
