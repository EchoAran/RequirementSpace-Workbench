"""add workspace_id to preview_shadow_drafts

Revision ID: 20260912_000001
Revises: 20260821_000003
Create Date: 2026-09-12

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260912_000001"
down_revision = "20260821_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch mode is required for SQLite (ALTER of constraints is unsupported).
    with op.batch_alter_table("preview_shadow_drafts") as batch_op:
        batch_op.add_column(
            sa.Column("workspace_id", sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_preview_shadow_drafts_workspace_id_branch_workspaces",
            "branch_workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_preview_shadow_drafts_workspace_id",
            ["workspace_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("preview_shadow_drafts") as batch_op:
        batch_op.drop_index(
            "ix_preview_shadow_drafts_workspace_id",
        )
        batch_op.drop_constraint(
            "fk_preview_shadow_drafts_workspace_id_branch_workspaces",
            type_="foreignkey",
        )
        batch_op.drop_column("preview_shadow_drafts", "workspace_id")
