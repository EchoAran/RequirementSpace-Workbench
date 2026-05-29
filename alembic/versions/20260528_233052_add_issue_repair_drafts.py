"""add issue_repair_drafts table

Revision ID: 20260528_233052
Revises: 57970a473607
Create Date: 2026-05-28T23:30:52.721876
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '20260528_233052'
down_revision: Union[str, None] = '57970a473607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'issue_repair_drafts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('draft_id', sa.String(length=50), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('issue_code', sa.String(length=100), nullable=False),
        sa.Column('issue_id', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('stage', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('target', sa.JSON(), nullable=False),
        sa.Column('issue_fingerprint', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('context_hash', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('repair_type', sa.String(length=50), nullable=False, server_default=''),
        sa.Column('title', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('rationale', sa.Text(), nullable=False, server_default=''),
        sa.Column('proposal', sa.JSON(), nullable=False),
        sa.Column('patch', sa.JSON(), nullable=True),
        sa.Column('validation_report', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_issue_repair_drafts_draft_id'), 'issue_repair_drafts', ['draft_id'], unique=True)
    op.create_index(op.f('ix_issue_repair_drafts_project_id'), 'issue_repair_drafts', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_issue_repair_drafts_project_id'), table_name='issue_repair_drafts')
    op.drop_index(op.f('ix_issue_repair_drafts_draft_id'), table_name='issue_repair_drafts')
    op.drop_table('issue_repair_drafts')
