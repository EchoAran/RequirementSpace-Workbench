"""add MergeRequest, MergeReview, MergeComment tables (Phase 5)

Revision ID: 20260801_120000
Revises: 20260801_000001
Create Date: 2026-08-01 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_120000"
down_revision: Union[str, None] = "20260801_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "merge_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "public_id",
            sa.String(36),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_branch_id",
            sa.Integer(),
            sa.ForeignKey("requirement_branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_branch_id",
            sa.Integer(),
            sa.ForeignKey("requirement_branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "merge_base_commit_id",
            sa.Integer(),
            sa.ForeignKey("requirement_commits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_head_commit_id",
            sa.Integer(),
            sa.ForeignKey("requirement_commits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_head_commit_id",
            sa.Integer(),
            sa.ForeignKey("requirement_commits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "author_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "merged_commit_id",
            sa.Integer(),
            sa.ForeignKey("requirement_commits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "closed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "project_id", "title",
            name="uq_merge_request_project_title",
        ),
    )
    op.create_index("ix_merge_request_public_id", "merge_requests", ["public_id"], unique=True)
    op.create_index("ix_merge_requests_project", "merge_requests", ["project_id"])
    op.create_index("ix_merge_requests_status", "merge_requests", ["project_id", "status"])
    op.create_index("ix_merge_requests_source_target", "merge_requests", ["source_branch_id", "target_branch_id"])
    op.create_index("ix_merge_requests_author", "merge_requests", ["author_user_id"])
    op.create_index("ix_merge_requests_created_at", "merge_requests", ["created_at"])

    op.create_table(
        "merge_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "merge_request_id",
            sa.Integer(),
            sa.ForeignKey("merge_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decision",
            sa.String(30),
            nullable=False,
            server_default="approved",
        ),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("stale_reason", sa.String(100), nullable=True),
        sa.Column(
            "stale_source_head_id",
            sa.Integer(),
            sa.ForeignKey("requirement_commits.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "stale_target_head_id",
            sa.Integer(),
            sa.ForeignKey("requirement_commits.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "merge_request_id", "reviewer_user_id",
            name="uq_merge_review_reviewer",
        ),
    )
    op.create_index("ix_merge_reviews_mr", "merge_reviews", ["merge_request_id"])
    op.create_index("ix_merge_reviews_status", "merge_reviews", ["merge_request_id", "status"])

    op.create_table(
        "merge_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "merge_request_id",
            sa.Integer(),
            sa.ForeignKey("merge_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_uuid", sa.String(36), nullable=True),
        sa.Column("field_path", sa.String(200), nullable=True),
        sa.Column("relation_key", sa.String(100), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "effective_source_head_id",
            sa.Integer(),
            sa.ForeignKey("requirement_commits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "expired_by_source_head_id",
            sa.Integer(),
            sa.ForeignKey("requirement_commits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index("ix_merge_comments_mr", "merge_comments", ["merge_request_id"])
    op.create_index(
        "ix_merge_comments_entity",
        "merge_comments",
        ["merge_request_id", "entity_uuid"],
    )
    op.create_index("ix_merge_comments_author", "merge_comments", ["author_user_id"])


def downgrade() -> None:
    op.drop_table("merge_comments")
    op.drop_table("merge_reviews")
    op.drop_table("merge_requests")
