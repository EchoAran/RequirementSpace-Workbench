"""add workspace_id to perception_jobs and perception_slots, with partial unique indexes

Revision ID: 20260821_000001
Revises: 20260803_000001
Create Date: 2026-08-21 00:00:01
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20260821_000001'
down_revision: str | Sequence[str] | None = '20260803_000001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOBS_TABLE = 'perception_jobs'
SLOTS_TABLE = 'perception_slots'


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    # 1. Upgrade perception_jobs
    if sa.inspect(bind).has_table(JOBS_TABLE):
        inspector = sa.inspect(bind)
        job_columns = [c['name'] for c in inspector.get_columns(JOBS_TABLE)]
        job_constraints = [c['name'] for c in inspector.get_unique_constraints(JOBS_TABLE)]
        job_indexes = [i['name'] for i in inspector.get_indexes(JOBS_TABLE)]

        with op.batch_alter_table(JOBS_TABLE) as batch_op:
            if 'workspace_id' not in job_columns:
                batch_op.add_column(sa.Column('workspace_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_perception_jobs_workspace_id_branch_workspaces',
                    'branch_workspaces',
                    ['workspace_id'],
                    ['id'],
                    ondelete='CASCADE',
                )

            if 'ix_perception_jobs_workspace_id' not in job_indexes:
                batch_op.create_index('ix_perception_jobs_workspace_id', ['workspace_id'], unique=False)

            if 'uq_perception_job_context' in job_constraints:
                batch_op.drop_constraint('uq_perception_job_context', type_='unique')
            if 'uq_perception_job_workspace_context' in job_constraints:
                batch_op.drop_constraint('uq_perception_job_workspace_context', type_='unique')

            if 'uq_perception_jobs_workspace_context' not in job_indexes:
                batch_op.create_index(
                    'uq_perception_jobs_workspace_context',
                    ['project_id', 'workspace_id', 'stage', 'perception_kind', 'target_type', 'target_id', 'context_hash'],
                    unique=True,
                    sqlite_where=sa.text("workspace_id IS NOT NULL"),
                    postgresql_where=sa.text("workspace_id IS NOT NULL"),
                )
            if 'uq_perception_jobs_legacy_context' not in job_indexes:
                batch_op.create_index(
                    'uq_perception_jobs_legacy_context',
                    ['project_id', 'stage', 'perception_kind', 'target_type', 'target_id', 'context_hash'],
                    unique=True,
                    sqlite_where=sa.text("workspace_id IS NULL"),
                    postgresql_where=sa.text("workspace_id IS NULL"),
                )

        if sa.inspect(bind).has_table('branch_workspaces') and sa.inspect(bind).has_table('requirement_branches'):
            bind.execute(sa.text("""
                UPDATE perception_jobs
                SET workspace_id = (
                    SELECT bw.id
                    FROM branch_workspaces bw
                    JOIN requirement_branches rb ON rb.id = bw.branch_id
                    WHERE rb.project_id = perception_jobs.project_id
                      AND rb.name = 'main'
                    LIMIT 1
                )
                WHERE workspace_id IS NULL
            """))

    # 2. Upgrade perception_slots
    if sa.inspect(bind).has_table(SLOTS_TABLE):
        inspector = sa.inspect(bind)
        slot_columns = [c['name'] for c in inspector.get_columns(SLOTS_TABLE)]
        slot_constraints = [c['name'] for c in inspector.get_unique_constraints(SLOTS_TABLE)]
        slot_indexes = [i['name'] for i in inspector.get_indexes(SLOTS_TABLE)]

        with op.batch_alter_table(SLOTS_TABLE) as batch_op:
            if 'workspace_id' not in slot_columns:
                batch_op.add_column(sa.Column('workspace_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_perception_slots_workspace_id_branch_workspaces',
                    'branch_workspaces',
                    ['workspace_id'],
                    ['id'],
                    ondelete='CASCADE',
                )

            if 'ix_perception_slots_workspace_id' not in slot_indexes:
                batch_op.create_index('ix_perception_slots_workspace_id', ['workspace_id'], unique=False)

            # Drop old single project_id unique constraints if present
            for uc in slot_constraints:
                if 'project_id' in uc.lower():
                    batch_op.drop_constraint(uc, type_='unique')

            if 'uq_perception_slots_workspace' not in slot_indexes:
                batch_op.create_index(
                    'uq_perception_slots_workspace',
                    ['project_id', 'workspace_id'],
                    unique=True,
                    sqlite_where=sa.text("workspace_id IS NOT NULL"),
                    postgresql_where=sa.text("workspace_id IS NOT NULL"),
                )
            if 'uq_perception_slots_legacy' not in slot_indexes:
                batch_op.create_index(
                    'uq_perception_slots_legacy',
                    ['project_id'],
                    unique=True,
                    sqlite_where=sa.text("workspace_id IS NULL"),
                    postgresql_where=sa.text("workspace_id IS NULL"),
                )

        if sa.inspect(bind).has_table('branch_workspaces') and sa.inspect(bind).has_table('requirement_branches'):
            bind.execute(sa.text("""
                UPDATE perception_slots
                SET workspace_id = (
                    SELECT bw.id
                    FROM branch_workspaces bw
                    JOIN requirement_branches rb ON rb.id = bw.branch_id
                    WHERE rb.project_id = perception_slots.project_id
                      AND rb.name = 'main'
                    LIMIT 1
                )
                WHERE workspace_id IS NULL
            """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    # 1. Downgrade perception_slots
    if sa.inspect(bind).has_table(SLOTS_TABLE):
        dup_slots = bind.execute(sa.text("""
            SELECT project_id, COUNT(*) as cnt
            FROM perception_slots
            GROUP BY project_id
            HAVING COUNT(*) > 1
        """)).fetchall()
        if dup_slots:
            raise RuntimeError(
                f"Cannot downgrade migration 20260821_000001: Found {len(dup_slots)} project(s) "
                "with multiple branch workspace perception slots. "
                "Downgrading would cause irreversible data loss."
            )

        inspector = sa.inspect(bind)
        slot_columns = [c['name'] for c in inspector.get_columns(SLOTS_TABLE)]
        slot_indexes = [i['name'] for i in inspector.get_indexes(SLOTS_TABLE)]

        with op.batch_alter_table(SLOTS_TABLE) as batch_op:
            if 'uq_perception_slots_workspace' in slot_indexes:
                batch_op.drop_index('uq_perception_slots_workspace')
            if 'uq_perception_slots_legacy' in slot_indexes:
                batch_op.drop_index('uq_perception_slots_legacy')
            if 'ix_perception_slots_workspace_id' in slot_indexes:
                batch_op.drop_index('ix_perception_slots_workspace_id')

            if 'workspace_id' in slot_columns:
                batch_op.drop_constraint('fk_perception_slots_workspace_id_branch_workspaces', type_='foreignkey')
                batch_op.drop_column('workspace_id')

            batch_op.create_unique_constraint('uq_perception_slots_project_id', ['project_id'])

    # 2. Downgrade perception_jobs
    if sa.inspect(bind).has_table(JOBS_TABLE):
        dup_jobs = bind.execute(sa.text("""
            SELECT project_id, stage, perception_kind, target_type, target_id, context_hash, COUNT(*) as cnt
            FROM perception_jobs
            GROUP BY project_id, stage, perception_kind, target_type, target_id, context_hash
            HAVING COUNT(*) > 1
        """)).fetchall()
        if dup_jobs:
            raise RuntimeError(
                f"Cannot downgrade migration 20260821_000001: Found {len(dup_jobs)} duplicate job context(s) across workspaces. "
                "Downgrading would cause irreversible data loss."
            )

        inspector = sa.inspect(bind)
        job_columns = [c['name'] for c in inspector.get_columns(JOBS_TABLE)]
        job_constraints = [c['name'] for c in inspector.get_unique_constraints(JOBS_TABLE)]
        job_indexes = [i['name'] for i in inspector.get_indexes(JOBS_TABLE)]

        with op.batch_alter_table(JOBS_TABLE) as batch_op:
            if 'uq_perception_jobs_workspace_context' in job_indexes:
                batch_op.drop_index('uq_perception_jobs_workspace_context')
            if 'uq_perception_jobs_legacy_context' in job_indexes:
                batch_op.drop_index('uq_perception_jobs_legacy_context')
            if 'uq_perception_job_workspace_context' in job_constraints:
                batch_op.drop_constraint('uq_perception_job_workspace_context', type_='unique')

            if 'ix_perception_jobs_workspace_id' in job_indexes:
                batch_op.drop_index('ix_perception_jobs_workspace_id')

            if 'workspace_id' in job_columns:
                batch_op.drop_constraint('fk_perception_jobs_workspace_id_branch_workspaces', type_='foreignkey')
                batch_op.drop_column('workspace_id')

            if 'uq_perception_job_context' not in job_constraints:
                batch_op.create_unique_constraint(
                    'uq_perception_job_context',
                    ['project_id', 'stage', 'perception_kind', 'target_type', 'target_id', 'context_hash'],
                )
