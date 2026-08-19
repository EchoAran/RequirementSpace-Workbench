"""add composite index for commit list pagination

Revision ID: 20260803_000001
Revises: 20260801_120000
Create Date: 2026-08-03 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_000001"
down_revision: Union[str, None] = "20260801_120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 提交列表 SQL 分页（offset/limit 按 created_at, id 倒序）需要 (project_id, created_at, id) 复合索引。
    op.create_index(
        "ix_requirement_commits_project_created_id",
        "requirement_commits",
        ["project_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_requirement_commits_project_created_id",
        table_name="requirement_commits",
    )
