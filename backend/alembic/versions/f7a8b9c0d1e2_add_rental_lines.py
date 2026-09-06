"""Store multiple motorcycles on one rental transaction.

Revision ID: f7a8b9c0d1e2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-06
"""

from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("rentals", "motorcycle", existing_type=sa.String(length=200), type_=sa.String(length=500), existing_nullable=False)
    op.alter_column("rentals", "plate", existing_type=sa.String(length=60), type_=sa.String(length=200), existing_nullable=True)

    op.create_table(
        "rental_lines",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("rental_id", sa.String(length=40), nullable=False),
        sa.Column("motorcycle_id", sa.String(length=40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("motorcycle", sa.String(length=160), nullable=False),
        sa.Column("plate", sa.String(length=60), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("rate_type", sa.String(length=20), nullable=False),
        sa.Column("rate_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("deposit", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("discount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("rental_charge", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["motorcycle_id"], ["motorcycles.id"]),
        sa.ForeignKeyConstraint(["rental_id"], ["rentals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rental_id", "motorcycle_id", name="uq_rental_lines_rental_motorcycle"),
    )
    op.create_index(op.f("ix_rental_lines_rental_id"), "rental_lines", ["rental_id"], unique=False)
    op.create_index(op.f("ix_rental_lines_motorcycle_id"), "rental_lines", ["motorcycle_id"], unique=False)

    op.execute(
        """
        INSERT INTO rental_lines (
            id, rental_id, motorcycle_id, sort_order, motorcycle, plate,
            start_date, due_date, duration_days, rate_type, rate_amount,
            deposit, discount, rental_charge, note, created_at, updated_at
        )
        SELECT
            CONCAT('rlh-', id),
            id,
            motorcycle_id,
            0,
            motorcycle,
            plate,
            start_date,
            due_date,
            duration_days,
            rate_type,
            rate_amount,
            deposit,
            discount,
            rental_charge,
            note,
            created_at,
            updated_at
        FROM rentals
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_rental_lines_motorcycle_id"), table_name="rental_lines")
    op.drop_index(op.f("ix_rental_lines_rental_id"), table_name="rental_lines")
    op.drop_table("rental_lines")
    op.alter_column("rentals", "plate", existing_type=sa.String(length=200), type_=sa.String(length=60), existing_nullable=True)
    op.alter_column("rentals", "motorcycle", existing_type=sa.String(length=500), type_=sa.String(length=200), existing_nullable=False)
