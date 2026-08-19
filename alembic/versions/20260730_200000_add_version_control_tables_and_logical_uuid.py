"""add_version_control_tables_and_logical_uuid

Revision ID: 20260730_200000
Revises: 57a2677fc6b9
Create Date: 2026-07-30 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision: str = '20260730_200000'
down_revision: Union[str, Sequence[str], None] = '57a2677fc6b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TARGET_TABLES = [
    "actors",
    "features",
    "feature_relations",
    "feature_scopes",
    "scenarios",
    "scenario_acceptance_criteria",
    "business_objects",
    "business_object_attributes",
    "flows",
    "flow_steps",
    "choice_groups",
    "choices",
]


def upgrade() -> None:
    """Upgrade schema to support version control with SQLite batch alter support."""
    bind = op.get_bind()
    import sys

    # Print Backup Warning
    print("\n" + "="*80)
    print("WARNING: Please ensure you have backed up your database before proceeding with this migration!")
    print("This migration introduces version control tables and logical UUID backfills.")
    print("="*80)

    # Compute and print Dry-run stats
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    
    projects_count = 0
    if "projects" in existing_tables:
        projects_count = bind.execute(sa.text("SELECT COUNT(*) FROM projects")).scalar() or 0
        
    print(f"DRY-RUN STATISTICS:")
    print(f"- Total projects to initialize main branch: {projects_count}")
    print(f"- Total legacy entities to backfill logical UUIDs and workspace IDs:")
    
    for tbl in TARGET_TABLES:
        if tbl in existing_tables:
            columns = [c['name'] for c in inspector.get_columns(tbl)]
            if 'logical_uuid' not in columns:
                row_count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {tbl}")).scalar() or 0
            else:
                row_count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {tbl} WHERE logical_uuid IS NULL")).scalar() or 0
            print(f"  * {tbl}: {row_count} rows")
            
    print("="*80 + "\n")
    sys.stdout.flush()

    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    # 1. requirement_commits
    op.create_table(
        'requirement_commits',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('state_json', sa.Text(), nullable=False),
        sa.Column('state_hash', sa.String(length=64), nullable=False),
        sa.Column('schema_version', sa.String(length=32), nullable=False, server_default='1.0'),
        sa.Column('author_user_id', sa.Integer(), nullable=True),
        sa.Column('summary_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_requirement_commits_author_user_id', 'requirement_commits', ['author_user_id'], unique=False)
    op.create_index('ix_requirement_commits_project_id', 'requirement_commits', ['project_id'], unique=False)
    op.create_index('ix_requirement_commits_public_id', 'requirement_commits', ['public_id'], unique=True)
    op.create_index('ix_requirement_commits_state_hash', 'requirement_commits', ['state_hash'], unique=False)
    op.create_index('ix_requirement_commits_created_at', 'requirement_commits', ['created_at'], unique=False)

    # 2. requirement_branches
    op.create_table(
        'requirement_branches',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('head_commit_id', sa.Integer(), nullable=True),
        sa.Column('source_commit_id', sa.Integer(), nullable=True),
        sa.Column('is_protected', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['head_commit_id'], ['requirement_commits.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_commit_id'], ['requirement_commits.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_requirement_branch_project_name')
    )
    op.create_index('ix_requirement_branches_created_by_user_id', 'requirement_branches', ['created_by_user_id'], unique=False)
    op.create_index('ix_requirement_branches_head_commit_id', 'requirement_branches', ['head_commit_id'], unique=False)
    op.create_index('ix_requirement_branches_name', 'requirement_branches', ['name'], unique=False)
    op.create_index('ix_requirement_branches_project_id', 'requirement_branches', ['project_id'], unique=False)
    op.create_index('ix_requirement_branches_public_id', 'requirement_branches', ['public_id'], unique=True)
    op.create_index('ix_requirement_branches_source_commit_id', 'requirement_branches', ['source_commit_id'], unique=False)
    op.create_index('ix_requirement_branches_created_at', 'requirement_branches', ['created_at'], unique=False)

    # 3. requirement_commit_parents
    op.create_table(
        'requirement_commit_parents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('commit_id', sa.Integer(), nullable=False),
        sa.Column('parent_commit_id', sa.Integer(), nullable=False),
        sa.Column('parent_order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['commit_id'], ['requirement_commits.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_commit_id'], ['requirement_commits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('commit_id', 'parent_commit_id', name='uq_commit_parent')
    )
    op.create_index('ix_requirement_commit_parents_commit_id', 'requirement_commit_parents', ['commit_id'], unique=False)
    op.create_index('ix_requirement_commit_parents_parent_commit_id', 'requirement_commit_parents', ['parent_commit_id'], unique=False)

    # 4. branch_workspaces
    op.create_table(
        'branch_workspaces',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('user_requirements', sa.Text(), nullable=False, server_default=''),
        sa.Column('kano_status', sa.String(length=50), nullable=False, server_default='missing'),
        sa.Column('unlocked_stages', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['requirement_branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_branch_workspaces_branch_id', 'branch_workspaces', ['branch_id'], unique=True)
    op.create_index('ix_branch_workspaces_project_id', 'branch_workspaces', ['project_id'], unique=False)
    op.create_index('ix_branch_workspaces_created_at', 'branch_workspaces', ['created_at'], unique=False)

    # 5. Add logical_uuid, workspace_id, FKs and UQ constraints in a single batch_alter_table pass
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table_name in TARGET_TABLES:
        if table_name in existing_tables:
            columns = [c['name'] for c in inspector.get_columns(table_name)]
            constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
            uq_name = f'uq_{table_name}_workspace_logical_uuid'

            with op.batch_alter_table(table_name) as batch_op:
                if 'logical_uuid' not in columns:
                    batch_op.add_column(sa.Column('logical_uuid', sa.String(length=36), nullable=True))
                    batch_op.create_index(f'ix_{table_name}_logical_uuid', ['logical_uuid'], unique=False)

                if 'workspace_id' not in columns:
                    batch_op.add_column(sa.Column('workspace_id', sa.Integer(), nullable=True))
                    batch_op.create_index(f'ix_{table_name}_workspace_id', ['workspace_id'], unique=False)
                    batch_op.create_foreign_key(
                        f'fk_{table_name}_workspace_id_branch_workspaces',
                        'branch_workspaces',
                        ['workspace_id'],
                        ['id'],
                        ondelete='CASCADE'
                    )

                if uq_name not in constraints:
                    batch_op.create_unique_constraint(
                        uq_name,
                        ['workspace_id', 'logical_uuid']
                    )

    # 6. Execute baseline migration and orphan UUID backfill within Alembic's transaction
    db_session = Session(bind=bind)
    try:
        from backend.api.modules.version_control.application.baseline_migration import (
            migrate_all_projects_to_version_control,
        )
        migrate_all_projects_to_version_control(db_session)

        # 7. Backfill any orphan entity rows with generated UUIDs if logical_uuid is still NULL
        import uuid
        for table_name in TARGET_TABLES:
            if table_name in existing_tables:
                rows = db_session.execute(sa.text(f"SELECT id FROM {table_name} WHERE logical_uuid IS NULL")).fetchall()
                for row in rows:
                    db_session.execute(
                        sa.text(f"UPDATE {table_name} SET logical_uuid = :uuid WHERE id = :id"),
                        {"uuid": str(uuid.uuid4()), "id": row[0]}
                    )
        db_session.commit()

        # 8. Tighten logical_uuid to nullable=False across all versioned entity tables
        for table_name in TARGET_TABLES:
            if table_name in existing_tables:
                with op.batch_alter_table(table_name) as batch_op:
                    batch_op.alter_column('logical_uuid', existing_type=sa.String(length=36), nullable=False)
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()

    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=ON"))


def downgrade() -> None:
    """Downgrade schema safely using batch_alter_table."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=OFF"))

    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table_name in reversed(TARGET_TABLES):
        if table_name in existing_tables:
            columns = [c['name'] for c in inspector.get_columns(table_name)]
            constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
            uq_name = f'uq_{table_name}_workspace_logical_uuid'

            with op.batch_alter_table(table_name) as batch_op:
                if uq_name in constraints:
                    try:
                        batch_op.drop_constraint(uq_name, type_='unique')
                    except Exception:
                        pass

                if 'workspace_id' in columns:
                    try:
                        batch_op.drop_constraint(
                            f'fk_{table_name}_workspace_id_branch_workspaces',
                            type_='foreignkey'
                        )
                    except Exception:
                        pass
                    try:
                        batch_op.drop_index(f'ix_{table_name}_workspace_id')
                    except Exception:
                        pass
                    batch_op.drop_column('workspace_id')

                if 'logical_uuid' in columns:
                    try:
                        batch_index_names = [i['name'] for i in inspector.get_indexes(table_name)]
                        if f'ix_{table_name}_logical_uuid' in batch_index_names:
                            batch_op.drop_index(f'ix_{table_name}_logical_uuid')
                    except Exception:
                        pass
                    batch_op.drop_column('logical_uuid')

    if 'branch_workspaces' in existing_tables:
        op.drop_index('ix_branch_workspaces_project_id', table_name='branch_workspaces')
        op.drop_index('ix_branch_workspaces_branch_id', table_name='branch_workspaces')
        op.drop_index('ix_branch_workspaces_created_at', table_name='branch_workspaces')
        op.drop_table('branch_workspaces')

    if 'requirement_commit_parents' in existing_tables:
        op.drop_index('ix_requirement_commit_parents_parent_commit_id', table_name='requirement_commit_parents')
        op.drop_index('ix_requirement_commit_parents_commit_id', table_name='requirement_commit_parents')
        op.drop_table('requirement_commit_parents')

    if 'requirement_branches' in existing_tables:
        op.drop_index('ix_requirement_branches_source_commit_id', table_name='requirement_branches')
        op.drop_index('ix_requirement_branches_public_id', table_name='requirement_branches')
        op.drop_index('ix_requirement_branches_project_id', table_name='requirement_branches')
        op.drop_index('ix_requirement_branches_name', table_name='requirement_branches')
        op.drop_index('ix_requirement_branches_head_commit_id', table_name='requirement_branches')
        op.drop_index('ix_requirement_branches_created_by_user_id', table_name='requirement_branches')
        op.drop_index('ix_requirement_branches_created_at', table_name='requirement_branches')
        op.drop_table('requirement_branches')

    if 'requirement_commits' in existing_tables:
        op.drop_index('ix_requirement_commits_state_hash', table_name='requirement_commits')
        op.drop_index('ix_requirement_commits_public_id', table_name='requirement_commits')
        op.drop_index('ix_requirement_commits_project_id', table_name='requirement_commits')
        op.drop_index('ix_requirement_commits_author_user_id', table_name='requirement_commits')
        op.drop_index('ix_requirement_commits_created_at', table_name='requirement_commits')
        op.drop_table('requirement_commits')

    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("PRAGMA foreign_keys=ON"))
