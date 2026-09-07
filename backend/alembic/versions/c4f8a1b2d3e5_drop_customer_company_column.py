"""drop customer company column

Revision ID: c4f8a1b2d3e5
Revises: ab57577973e4
Create Date: 2026-09-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f8a1b2d3e5'
down_revision: Union[str, None] = 'ab57577973e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('rental_customers', 'company')


def downgrade() -> None:
    op.add_column('rental_customers', sa.Column('company', sa.String(length=200), nullable=True))
