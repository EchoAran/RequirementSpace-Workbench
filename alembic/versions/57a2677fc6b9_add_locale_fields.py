"""add_locale_fields

Revision ID: 57a2677fc6b9
Revises: 8d2f4c9a1b7e
Create Date: 2026-07-13 11:34:55.508493

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57a2677fc6b9'
down_revision: Union[str, Sequence[str], None] = '8d2f4c9a1b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "preferred_locale",
            sa.String(length=16),
            sa.CheckConstraint("preferred_locale IN ('zh-CN', 'en-US')", name="check_user_preferred_locale"),
            nullable=False,
            server_default="zh-CN"
        )
    )
    op.add_column(
        "projects",
        sa.Column(
            "content_locale",
            sa.String(length=16),
            sa.CheckConstraint("content_locale IS NULL OR content_locale IN ('zh-CN', 'en-US')", name="check_project_content_locale"),
            nullable=True
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projects", "content_locale")
    op.drop_column("users", "preferred_locale")
