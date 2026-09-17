"""Drop stored rental tax/payment aggregate columns.

Paid, outstanding, payment_status and tax are now derived from rental_payments
and the rental charge, so the stored columns are no longer needed.

Revision ID: i0d1e2f3g4h5
Revises: h9c0d1e2f3g4
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa


revision = "i0d1e2f3g4h5"
down_revision = "h9c0d1e2f3g4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("rentals", "payment_status")
    op.drop_column("rentals", "outstanding")
    op.drop_column("rentals", "paid")
    op.drop_column("rentals", "tax")
    op.drop_column("rentals", "tax_percent")


def downgrade() -> None:
    op.add_column(
        "rentals",
        sa.Column("tax_percent", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"),
    )
    op.add_column(
        "rentals",
        sa.Column("tax", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
    )
    op.add_column(
        "rentals",
        sa.Column("paid", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
    )
    op.add_column(
        "rentals",
        sa.Column("outstanding", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
    )
    op.add_column(
        "rentals",
        sa.Column("payment_status", sa.String(length=20), nullable=True),
    )
