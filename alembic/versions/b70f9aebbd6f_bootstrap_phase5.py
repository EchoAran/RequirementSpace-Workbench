"""bootstrap_phase5

Revision ID: b70f9aebbd6f
Revises: 92880adaf486
Create Date: 2026-06-27 22:06:53.843714

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b70f9aebbd6f'
down_revision: Union[str, Sequence[str], None] = '92880adaf486'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create project_llm_configs table
    op.create_table(
        'project_llm_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('api_url', sa.String(length=255), nullable=False),
        sa.Column('encrypted_api_key', sa.Text(), nullable=False),
        sa.Column('api_key_last4', sa.String(length=4), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_project_llm_configs_project_id', 'project_llm_configs', ['project_id'], unique=False)

    # 2. Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recipient_user_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['collaboration_tasks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_notification_recipient', 'notifications', ['recipient_user_id'], unique=False)
    op.create_index('idx_notification_unread', 'notifications', ['recipient_user_id', 'read_at'], unique=False)

    # 3. Create task_comments table
    op.create_table(
        'task_comments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('author_user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['collaboration_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_task_comments_task_id', 'task_comments', ['task_id'], unique=False)

    # 4. Create task_assignees table
    op.create_table(
        'task_assignees',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('assignee_user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['assignee_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['collaboration_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_task_assignees_task_id', 'task_assignees', ['task_id'], unique=False)

    # 5. Add triggered_by_user_id to perception_jobs using batch operations for SQLite compatibility
    with op.batch_alter_table('perception_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('triggered_by_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_perception_jobs_triggered_user', 'users', ['triggered_by_user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('perception_jobs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_perception_jobs_triggered_user', type_='foreignkey')
        batch_op.drop_column('triggered_by_user_id')

    op.drop_table('task_assignees')
    op.drop_table('task_comments')
    op.drop_table('notifications')
    op.drop_table('project_llm_configs')
