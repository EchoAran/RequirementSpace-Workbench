"""Drop legacy unique index on perception_slots.project_id and ensure workspace partial indexes

Revision ID: 20260821_000002
Revises: 20260821_000001
Create Date: 2026-08-21 17:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260821_000002"
down_revision: str | Sequence[str] | None = "20260821_000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLOTS_TABLE = "perception_slots"
JOBS_TABLE = "perception_jobs"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    if sa.inspect(bind).has_table(SLOTS_TABLE):
        inspector = sa.inspect(bind)
        slot_columns = [c["name"] for c in inspector.get_columns(SLOTS_TABLE)]
        slot_constraints = inspector.get_unique_constraints(SLOTS_TABLE)
        slot_indexes = inspector.get_indexes(SLOTS_TABLE)

        with op.batch_alter_table(SLOTS_TABLE) as batch_op:
            # 1. Ensure workspace_id column & fk exist
            if "workspace_id" not in slot_columns:
                batch_op.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_perception_slots_workspace_id_branch_workspaces",
                    "branch_workspaces",
                    ["workspace_id"],
                    ["id"],
                    ondelete="CASCADE",
                )

            # 2. Drop any unique constraint or unique index on single project_id column
            for uc in slot_constraints:
                if uc.get("column_names") == ["project_id"] or "project_id" in uc.get("name", "").lower():
                    batch_op.drop_constraint(uc["name"], type_="unique")

            for idx in slot_indexes:
                idx_name = idx.get("name", "")
                is_single_project = idx.get("column_names") == ["project_id"]
                if is_single_project and (idx.get("unique") or idx_name == "ix_perception_slots_project_id"):
                    batch_op.drop_index(idx_name)

            # 3. Create regular non-unique project_id index
            batch_op.create_index("ix_perception_slots_project_id", ["project_id"], unique=False)

            # 4. Ensure workspace_id index exists
            existing_idx_names = [i["name"] for i in inspector.get_indexes(SLOTS_TABLE)]
            if "ix_perception_slots_workspace_id" not in existing_idx_names:
                batch_op.create_index("ix_perception_slots_workspace_id", ["workspace_id"], unique=False)

            # 5. Ensure workspace-aware partial unique indexes exist
            if "uq_perception_slots_workspace" not in existing_idx_names:
                batch_op.create_index(
                    "uq_perception_slots_workspace",
                    ["project_id", "workspace_id"],
                    unique=True,
                    sqlite_where=sa.text("workspace_id IS NOT NULL"),
                    postgresql_where=sa.text("workspace_id IS NOT NULL"),
                )
            if "uq_perception_slots_legacy" not in existing_idx_names:
                batch_op.create_index(
                    "uq_perception_slots_legacy",
                    ["project_id"],
                    unique=True,
                    sqlite_where=sa.text("workspace_id IS NULL"),
                    postgresql_where=sa.text("workspace_id IS NULL"),
                )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    if sa.inspect(bind).has_table(SLOTS_TABLE):
        # Fail-safe check: detect whether multiple slots exist under the same project
        dup_rows = bind.execute(sa.text("""
            SELECT project_id, COUNT(*) as cnt
            FROM perception_slots
            GROUP BY project_id
            HAVING COUNT(*) > 1
        """)).fetchall()
        if dup_rows:
            raise RuntimeError(
                f"Cannot downgrade migration 20260821_000002: Found {len(dup_rows)} project(s) "
                "with multiple branch workspace perception slots. "
                "Downgrading would cause irreversible data loss. "
                "Please manually clean up duplicate branch slots before downgrading."
            )

        inspector = sa.inspect(bind)
        slot_indexes = [i["name"] for i in inspector.get_indexes(SLOTS_TABLE)]

        with op.batch_alter_table(SLOTS_TABLE) as batch_op:
            if "uq_perception_slots_workspace" in slot_indexes:
                batch_op.drop_index("uq_perception_slots_workspace")
            if "uq_perception_slots_legacy" in slot_indexes:
                batch_op.drop_index("uq_perception_slots_legacy")
            if "ix_perception_slots_project_id" in slot_indexes:
                batch_op.drop_index("ix_perception_slots_project_id")

            # Restore old unique index on project_id
            batch_op.create_index("ix_perception_slots_project_id", ["project_id"], unique=True)
