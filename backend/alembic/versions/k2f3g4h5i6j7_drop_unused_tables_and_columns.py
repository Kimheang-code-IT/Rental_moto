"""Drop unused tables and columns.

Production cleanup. These objects are dead weight:

- ``storage_providers``: no routes, services, repositories, or frontend usage.
- ``password_reset_challenges``: password recovery state lives in Redis.
- ``telegram_link_codes``: Telegram linking state lives in Redis.
- ``refresh_token_sessions.replaced_by_jti``: never populated; family_id +
  revoked_at already cover rotation/reuse revocation.
- ``task_progress.amount``: never written or read.

Revision ID: k2f3g4h5i6j7
Revises: j1e2f3g4h5i6
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa


revision = "k2f3g4h5i6j7"
down_revision = "j1e2f3g4h5i6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("refresh_token_sessions", "replaced_by_jti")
    op.drop_column("task_progress", "amount")
    op.drop_table("telegram_link_codes")
    op.drop_table("password_reset_challenges")
    op.drop_table("storage_providers")


def downgrade() -> None:
    op.add_column(
        "task_progress",
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        "refresh_token_sessions",
        sa.Column("replaced_by_jti", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "storage_providers",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("max_file_size_mb", sa.Integer(), nullable=False),
        sa.Column("allowed_file_types", sa.JSON(), nullable=True),
        sa.Column("access_mode", sa.String(length=20), nullable=False),
        sa.Column("upload_path_pattern", sa.String(length=200), nullable=False),
        sa.Column("connection_status", sa.String(length=20), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("endpoint", sa.String(length=300), nullable=True),
        sa.Column("region", sa.String(length=60), nullable=True),
        sa.Column("bucket", sa.String(length=120), nullable=True),
        sa.Column("access_key", sa.String(length=200), nullable=True),
        sa.Column("secret_key", sa.String(length=300), nullable=True),
        sa.Column("public_url", sa.String(length=300), nullable=True),
        sa.Column("path_style", sa.Boolean(), nullable=True),
        sa.Column("folder_id", sa.String(length=120), nullable=True),
        sa.Column("client_id", sa.String(length=200), nullable=True),
        sa.Column("client_secret", sa.String(length=300), nullable=True),
        sa.Column("credential_status", sa.String(length=20), nullable=True),
        sa.Column("sync_status", sa.String(length=20), nullable=True),
        sa.Column("sync_schedule", sa.String(length=60), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "password_reset_challenges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_password_reset_challenges_code_hash"),
        "password_reset_challenges",
        ["code_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_password_reset_challenges_user_id"),
        "password_reset_challenges",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_prc_user_active",
        "password_reset_challenges",
        ["user_id", "consumed_at"],
        unique=False,
    )

    op.create_table(
        "telegram_link_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        op.f("ix_telegram_link_codes_user_id"),
        "telegram_link_codes",
        ["user_id"],
        unique=False,
    )
