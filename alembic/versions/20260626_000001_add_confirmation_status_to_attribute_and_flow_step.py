"""add confirmation_status to attribute and flow step

Revision ID: 20260626_000001
Revises: 45e92af4340f
Create Date: 2026-06-26 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260626_000001"
down_revision: Union[str, Sequence[str], None] = "45e92af4340f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TARGET_TABLES = [
    "business_object_attributes",
    "flow_steps",
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for table in TARGET_TABLES:
        existing_columns = [column["name"] for column in inspector.get_columns(table)]
        if "confirmation_status" not in existing_columns:
            op.add_column(
                table,
                sa.Column(
                    "confirmation_status",
                    sa.String(20),
                    server_default="ai_assumption",
                    nullable=False,
                ),
            )


def downgrade() -> None:
    for table in TARGET_TABLES:
        op.drop_column(table, "confirmation_status")
