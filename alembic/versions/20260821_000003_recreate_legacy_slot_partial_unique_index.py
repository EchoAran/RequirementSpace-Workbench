"""Recreate legacy partial unique index on perception_slots.project_id where workspace_id is null

Revision ID: 20260821_000003
Revises: 20260821_000002
Create Date: 2026-08-21 20:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260821_000003"
down_revision: str | Sequence[str] | None = "20260821_000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLOTS_TABLE = "perception_slots"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    if sa.inspect(bind).has_table(SLOTS_TABLE):
        # 1. Fail-safe check: detect whether multiple legacy NULL workspace slots exist for the same project
        dup_rows = bind.execute(sa.text("""
            SELECT project_id, COUNT(*) as cnt
            FROM perception_slots
            WHERE workspace_id IS NULL
            GROUP BY project_id
            HAVING COUNT(*) > 1
        """)).fetchall()
        if dup_rows:
            raise RuntimeError(
                f"Cannot upgrade migration 20260821_000003: Found {len(dup_rows)} project(s) "
                "with duplicate legacy NULL workspace perception slots. "
                "Manual data resolution is required before creating the legacy partial unique index."
            )

        inspector = sa.inspect(bind)
        existing_idx_names = [i["name"] for i in inspector.get_indexes(SLOTS_TABLE)]

        with op.batch_alter_table(SLOTS_TABLE) as batch_op:
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
        inspector = sa.inspect(bind)
        existing_idx_names = [i["name"] for i in inspector.get_indexes(SLOTS_TABLE)]

        with op.batch_alter_table(SLOTS_TABLE) as batch_op:
            if "uq_perception_slots_legacy" in existing_idx_names:
                batch_op.drop_index("uq_perception_slots_legacy")
