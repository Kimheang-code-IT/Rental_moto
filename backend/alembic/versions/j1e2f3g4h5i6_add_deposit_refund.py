"""Track deposit refunds paid to the customer on rental return.

Revision ID: j1e2f3g4h5i6
Revises: i0d1e2f3g4h5
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa


revision = "j1e2f3g4h5i6"
down_revision = "i0d1e2f3g4h5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rentals",
        sa.Column("deposit_refund", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("rentals", "deposit_refund")
