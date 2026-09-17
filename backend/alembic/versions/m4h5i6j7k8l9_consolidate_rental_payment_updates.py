"""Consolidate system-generated rental payment updates.

Revision ID: m4h5i6j7k8l9
Revises: l3g4h5i6j7k8
Create Date: 2026-09-17
"""

from alembic import op


revision = "m4h5i6j7k8l9"
down_revision = "l3g4h5i6j7k8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the oldest system-generated base-rental payment, update it to the
    # current rental fee, and remove obsolete delta rows from earlier edits.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                p.id,
                p.rental_id,
                ROW_NUMBER() OVER (
                    PARTITION BY p.rental_id
                    ORDER BY p.paid_at, p.id
                ) AS row_number
            FROM rental_payments p
            WHERE p.note IN ('Full payment', 'Payment update', 'Initial payment')
        )
        UPDATE rental_payments p
        SET
            amount = r.rental_charge,
            tendered_amount = CASE
                WHEN p.currency = r.currency THEN r.rental_charge
                WHEN r.currency = 'USD' AND p.currency = 'KHR'
                    THEN ROUND(r.rental_charge * p.exchange_rate, 2)
                WHEN r.currency = 'KHR' AND p.currency = 'USD'
                    THEN ROUND(r.rental_charge / NULLIF(p.exchange_rate, 0), 2)
                ELSE r.rental_charge
            END,
            payment_method = COALESCE(NULLIF(r.payment_method, ''), p.payment_method),
            note = 'Full payment',
            updated_at = now()
        FROM ranked x
        JOIN rentals r ON r.id = x.rental_id
        WHERE p.id = x.id
          AND x.row_number = 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                p.id,
                ROW_NUMBER() OVER (
                    PARTITION BY p.rental_id
                    ORDER BY p.paid_at, p.id
                ) AS row_number
            FROM rental_payments p
            WHERE p.note IN ('Full payment', 'Payment update', 'Initial payment')
        )
        DELETE FROM rental_payments p
        USING ranked x
        WHERE p.id = x.id
          AND x.row_number > 1
        """
    )


def downgrade() -> None:
    # Consolidation is intentionally irreversible: deleted rows represented
    # obsolete deltas already included in the retained payment amount.
    pass
