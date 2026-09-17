"""Revision ID: e6f1a2b3c4d5
Revises: d5e9f2a3b4c6
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "e6f1a2b3c4d5"
down_revision = "e6f0a3b4c5d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rentals", sa.Column("deadline_alerted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_rentals_status_due_date", "rentals", ["status", "due_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rentals_status_due_date", table_name="rentals")
    op.drop_column("rentals", "deadline_alerted_at")
