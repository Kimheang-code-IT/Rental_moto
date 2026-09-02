"""add customer company column

Revision ID: d5e9f2a3b4c6
Revises: c4f8a1b2d3e5
Create Date: 2026-09-02 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e9f2a3b4c6'
down_revision: Union[str, None] = 'c4f8a1b2d3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rental_customers', sa.Column('company', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('rental_customers', 'company')
