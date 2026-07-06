"""make_project_llm_config_project_unique

Revision ID: 8d2f4c9a1b7e
Revises: 5f9983ca9bb2
Create Date: 2026-07-06 15:18:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d2f4c9a1b7e"
down_revision: Union[str, Sequence[str], None] = "5f9983ca9bb2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM project_llm_configs
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM project_llm_configs
            GROUP BY project_id
        )
    """))
    op.drop_index("ix_project_llm_configs_project_id", table_name="project_llm_configs")
    op.create_index(
        "ix_project_llm_configs_project_id",
        "project_llm_configs",
        ["project_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_project_llm_configs_project_id", table_name="project_llm_configs")
    op.create_index(
        "ix_project_llm_configs_project_id",
        "project_llm_configs",
        ["project_id"],
        unique=False,
    )
