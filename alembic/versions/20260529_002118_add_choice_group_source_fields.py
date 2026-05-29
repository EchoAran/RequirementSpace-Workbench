"""add choice_group source fields (issue_code, issue_id, stage, target, context_hash)

Revision ID: 20260529_002118
Revises: 20260528_233052
Create Date: 2026-05-29T00:21:18.666683
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '20260529_002118'
down_revision: Union[str, None] = '20260528_233052'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('choice_groups', sa.Column('source_type', sa.String(50), nullable=True))
    op.add_column('choice_groups', sa.Column('source_id', sa.String(200), nullable=True))
    op.add_column('choice_groups', sa.Column('issue_code', sa.String(100), nullable=True))
    op.add_column('choice_groups', sa.Column('issue_id', sa.String(200), nullable=True))
    op.add_column('choice_groups', sa.Column('stage', sa.String(20), nullable=True))
    op.add_column('choice_groups', sa.Column('target', sa.JSON(), nullable=True))
    op.add_column('choice_groups', sa.Column('context_hash', sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column('choice_groups', 'context_hash')
    op.drop_column('choice_groups', 'target')
    op.drop_column('choice_groups', 'stage')
    op.drop_column('choice_groups', 'issue_id')
    op.drop_column('choice_groups', 'issue_code')
    op.drop_column('choice_groups', 'source_id')
    op.drop_column('choice_groups', 'source_type')
