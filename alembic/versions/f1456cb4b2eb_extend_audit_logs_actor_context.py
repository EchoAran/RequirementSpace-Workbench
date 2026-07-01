"""extend_audit_logs_actor_context

Revision ID: f1456cb4b2eb
Revises: 2a3d8257d849
Create Date: 2026-06-27 11:38:47.092633

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1456cb4b2eb'
down_revision: Union[str, Sequence[str], None] = '2a3d8257d849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.add_column(sa.Column('actor_type', sa.String(length=50), server_default='system', nullable=False))
        batch_op.add_column(sa.Column('diff', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('request_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('task_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("actor_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_audit_logs_actor_user", "users", ["actor_user_id"], ["id"], ondelete="SET NULL")

    # 3. Create indexes
    op.create_index("idx_audit_actor_created", "audit_logs", ["actor_user_id", "created_at"], unique=False)
    op.create_index("idx_audit_project_created", "audit_logs", ["project_id", "created_at"], unique=False)
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"], unique=False)
    op.create_index("ix_audit_logs_task_id", "audit_logs", ["task_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_audit_logs_task_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("idx_audit_project_created", table_name="audit_logs")
    op.drop_index("idx_audit_actor_created", table_name="audit_logs")

    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_audit_logs_actor_user", type_="foreignkey")
        batch_op.drop_column("actor_user_id")
        batch_op.drop_column("task_id")
        batch_op.drop_column("request_id")
        batch_op.drop_column("diff")
        batch_op.drop_column("actor_type")
