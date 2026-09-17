"""enforce role-only RBAC

Revision ID: e6f0a3b4c5d7
Revises: d5e9f2a3b4c6
Create Date: 2026-09-02 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e6f0a3b4c5d7"
down_revision: Union[str, None] = "d5e9f2a3b4c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users AS u
        SET role_id = r.id
        FROM roles AS r
        WHERE lower(trim(u.role)) = lower(trim(r.name))
        """
    )
    op.execute(
        """
        DO $$
        DECLARE unmatched text;
        BEGIN
          SELECT string_agg(format('id=%s email=%s role=%s', id, email, role), '; ' ORDER BY id)
          INTO unmatched
          FROM users
          WHERE role_id IS NULL;
          IF unmatched IS NOT NULL THEN
            RAISE EXCEPTION 'RBAC migration aborted; unmatched user roles: %', unmatched;
          END IF;
        END $$;
        """
    )
    op.execute(
        "UPDATE roles SET is_system = TRUE WHERE name IN ('SuperAdmin', 'Rental Staff', 'Report Viewer')"
    )
    op.execute("UPDATE users SET permissions = NULL, page_access = NULL")
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


def downgrade() -> None:
    op.drop_constraint("users_role_id_fkey", "users", type_="foreignkey")
    op.alter_column("users", "role_id", nullable=True)
    op.create_foreign_key(
        "users_role_id_fkey",
        "users",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="SET NULL",
    )
