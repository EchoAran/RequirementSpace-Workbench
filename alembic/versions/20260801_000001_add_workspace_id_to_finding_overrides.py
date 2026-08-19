"""add workspace_id to finding_overrides

Revision ID: 20260801_000001
Revises: 20260730_200000
Create Date: 2026-08-01 00:00:01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260801_000001'
down_revision: Union[str, Sequence[str], None] = '20260730_200000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'finding_overrides'


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABLE):
        return
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns(TABLE)]
    constraints = [c['name'] for c in inspector.get_unique_constraints(TABLE)]

    with op.batch_alter_table(TABLE) as batch_op:
        if 'workspace_id' not in columns:
            batch_op.add_column(sa.Column('workspace_id', sa.Integer(), nullable=True))
            batch_op.create_index('ix_finding_overrides_workspace_id', ['workspace_id'], unique=False)
            batch_op.create_foreign_key(
                'fk_finding_overrides_workspace_id_branch_workspaces',
                'branch_workspaces',
                ['workspace_id'],
                ['id'],
                ondelete='CASCADE',
            )

        if 'uq_finding_override_project_finding' in constraints:
            batch_op.drop_constraint('uq_finding_override_project_finding', type_='unique')
        if 'uq_finding_override_project_workspace_finding' not in constraints:
            batch_op.create_unique_constraint(
                'uq_finding_override_project_workspace_finding',
                ['project_id', 'workspace_id', 'finding_id'],
            )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABLE):
        return
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns(TABLE)]
    constraints = [c['name'] for c in inspector.get_unique_constraints(TABLE)]

    with op.batch_alter_table(TABLE) as batch_op:
        if 'uq_finding_override_project_workspace_finding' in constraints:
            batch_op.drop_constraint('uq_finding_override_project_workspace_finding', type_='unique')
        if 'uq_finding_override_project_finding' not in constraints:
            batch_op.create_unique_constraint(
                'uq_finding_override_project_finding',
                ['project_id', 'finding_id'],
            )

        if 'workspace_id' in columns:
            batch_op.drop_index('ix_finding_overrides_workspace_id', table_name=TABLE)
            batch_op.drop_constraint('fk_finding_overrides_workspace_id_branch_workspaces', type_='foreignkey')
            batch_op.drop_column('workspace_id')
