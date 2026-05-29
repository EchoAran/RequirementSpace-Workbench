"""add issue overrides for persistent ignored issues

Revision ID: 20260529_021500
Revises: 20260529_002118
Create Date: 2026-05-29T02:15:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260529_021500"
down_revision: Union[str, None] = "20260529_002118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "issue_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "issue_id", name="uq_issue_override_project_issue"),
    )
    op.create_index(
        "ix_issue_overrides_project_status",
        "issue_overrides",
        ["project_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_issue_overrides_project_status", table_name="issue_overrides")
    op.drop_table("issue_overrides")
