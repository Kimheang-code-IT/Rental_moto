"""Recognize retained security deposits as income payments.

Revision ID: l3g4h5i6j7k8
Revises: k2f3g4h5i6j7
Create Date: 2026-09-17
"""

from alembic import op


revision = "l3g4h5i6j7k8"
down_revision = "k2f3g4h5i6j7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill completed rentals closed before retained deposits were recorded
    # in the income ledger. IDs and references are deterministic so the
    # migration is safe to inspect and cannot duplicate a rental's deposit.
    op.execute(
        """
        INSERT INTO rental_payments (
            id, payment_no, rental_id, amount, currency, tendered_amount,
            exchange_rate, payment_method, paid_at, reference, note,
            created_by, created_by_user_id, created_at, updated_at
        )
        SELECT
            'rp-dep-' || SUBSTRING(md5(r.id), 1, 32),
            SUBSTRING('DEP-' || r.rental_no, 1, 60),
            r.id,
            GREATEST(r.deposit - r.deposit_refund, 0),
            r.currency,
            GREATEST(r.deposit - r.deposit_refund, 0),
            1.0000,
            'Security Deposit',
            COALESCE(r.completed_at, r.updated_at),
            r.rental_no,
            'Security deposit applied to return charges',
            'System migration',
            NULL,
            COALESCE(r.completed_at, r.updated_at),
            COALESCE(r.completed_at, r.updated_at)
        FROM rentals r
        WHERE r.status = 'Completed'
          AND GREATEST(r.deposit - r.deposit_refund, 0) > 0
          AND NOT EXISTS (
              SELECT 1
              FROM rental_payments p
              WHERE p.rental_id = r.id
                AND p.note = 'Security deposit applied to return charges'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM rental_payments
        WHERE id LIKE 'rp-dep-%'
          AND note = 'Security deposit applied to return charges'
          AND created_by = 'System migration'
        """
    )
