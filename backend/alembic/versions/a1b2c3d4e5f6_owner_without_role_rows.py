"""owner flag and nullable role_id; no role rows are seeded

Revision ID: a1b2c3d4e5f6
Revises: e6f1a2b3c4d5
Create Date: 2026-09-10 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e6f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # System owner flag: the first-setup user (users.is_owner) gets ALL_PAGES
    # without any Role row. Roles are created by the operator in the UI only;
    # this migration must not insert role rows.
    op.add_column(
        "users",
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_constraint("users_role_id_fkey", "users", type_="foreignkey")
    op.alter_column("users", "role_id", nullable=True)
    op.create_foreign_key(
        "users_role_id_fkey",
        "users",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("users", "role", existing_type=sa.String(length=80), nullable=True)
    # Roles are operator-owned; nothing is system-owned anymore.
    op.execute("UPDATE roles SET is_system = FALSE")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE unmatched text;
        BEGIN
          SELECT string_agg(format('id=%s email=%s', id, email), '; ' ORDER BY id)
          INTO unmatched
          FROM users
          WHERE role_id IS NULL;
          IF unmatched IS NOT NULL THEN
            RAISE EXCEPTION 'Cannot restore NOT NULL role_id; users without a role: %', unmatched;
          END IF;
        END $$;
        """
    )
    op.drop_constraint("users_role_id_fkey", "users", type_="foreignkey")
    op.alter_column("users", "role_id", nullable=False)
    op.create_foreign_key(
        "users_role_id_fkey",
        "users",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("users", "role", existing_type=sa.String(length=80), nullable=False)
    op.drop_column("users", "is_owner")
