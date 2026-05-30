"""add_confirmation_status_to_models

Add confirmation_status column to all source-tracked models.

This migration handles two scenarios:
1. Fresh installs → creates confirmation_status with server_default='confirmed'
2. Existing DBs that ran e91dee28418b (object_status) → migrates data from
   object_status to confirmation_status, then drops object_status.

Revision ID: 20260529_220000
Revises: e91dee28418b
Create Date: 2026-05-29 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260529_220000'
down_revision: Union[str, Sequence[str], None] = 'e91dee28418b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that need confirmation_status (excluding flow_steps per design decision)
TARGET_TABLES = [
    'actors',
    'features',
    'feature_scopes',
    'scenarios',
    'scenario_acceptance_criteria',
    'business_objects',
    'flows',
]


def upgrade() -> None:
    """Upgrade schema."""
    for table in TARGET_TABLES:
        # Check if the table already has confirmation_status (from a partial run)
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        existing_columns = [c['name'] for c in inspector.get_columns(table)]

        if 'confirmation_status' not in existing_columns:
            op.add_column(
                table,
                sa.Column(
                    'confirmation_status',
                    sa.String(20),
                    server_default='confirmed',
                    nullable=False,
                ),
            )

        # Migrate data from legacy object_status if it exists
        if 'object_status' in existing_columns:
            op.execute(
                f"UPDATE {table} SET confirmation_status = object_status "
                f"WHERE object_status IS NOT NULL"
            )

    # Drop legacy object_status columns if they exist
    for table in TARGET_TABLES + ['flow_steps']:
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        existing_columns = [c['name'] for c in inspector.get_columns(table)]
        if 'object_status' in existing_columns:
            op.drop_column(table, 'object_status')


def downgrade() -> None:
    """Downgrade schema."""
    for table in TARGET_TABLES:
        op.drop_column(table, 'confirmation_status')
