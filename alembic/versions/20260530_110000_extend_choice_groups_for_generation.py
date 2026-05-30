"""extend choice_groups and choices for generation choice groups (Phase 1)

Adds columns to support draft_payload style choices alongside existing patch style:
- ChoiceGroupModel: generation_type, origin_endpoint, candidate_count,
  success_count, failure_count, status_detail
- ChoiceModel: payload, draft_type, apply_mode, preview, score,
  validation_report, error

Revision ID: 20260530_110000
Revises: 20260529_220000
Create Date: 2026-05-30 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260530_110000"
down_revision: Union[str, None] = "20260529_220000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- choice_groups 扩展 ---
    op.add_column(
        "choice_groups",
        sa.Column("generation_type", sa.String(80), nullable=True,
                   comment="候选生成类型: actor, scenario, feature, project_creation 等"),
    )
    op.add_column(
        "choice_groups",
        sa.Column("origin_endpoint", sa.String(200), nullable=True,
                   comment="触发此 choice group 的 API endpoint"),
    )
    op.add_column(
        "choice_groups",
        sa.Column("candidate_count", sa.Integer(), nullable=True,
                   comment="请求的候选总数"),
    )
    op.add_column(
        "choice_groups",
        sa.Column("success_count", sa.Integer(), nullable=True,
                   comment="成功生成的候选数"),
    )
    op.add_column(
        "choice_groups",
        sa.Column("failure_count", sa.Integer(), nullable=True,
                   comment="失败的候选数"),
    )
    op.add_column(
        "choice_groups",
        sa.Column("status_detail", sa.JSON(), nullable=True,
                   comment="扩展状态信息: 错误汇总、候选失败详情、跨候选差异摘要等"),
    )

    # --- choices 扩展 ---
    op.add_column(
        "choices",
        sa.Column("payload", sa.JSON(), nullable=True,
                   comment="候选草稿的完整 payload（非 patch 型生成结果）"),
    )
    op.add_column(
        "choices",
        sa.Column("draft_type", sa.String(80), nullable=True,
                   comment="候选类型: actor, scenario, feature, project_creation 等"),
    )
    op.add_column(
        "choices",
        sa.Column("apply_mode", sa.String(50), nullable=False,
                   server_default="patch",
                   comment="采纳模式: patch 沿用 issue repair, draft_payload 用 payload 写入"),
    )
    op.add_column(
        "choices",
        sa.Column("preview", sa.JSON(), nullable=True,
                   comment="前端展示用摘要，避免 UI 直接理解所有 payload 细节"),
    )
    op.add_column(
        "choices",
        sa.Column("score", sa.JSON(), nullable=True,
                   comment="模型自评: completeness, risk, novelty, fit 等"),
    )
    op.add_column(
        "choices",
        sa.Column("validation_report", sa.JSON(), nullable=True,
                   comment="采纳前校验结果"),
    )
    op.add_column(
        "choices",
        sa.Column("error", sa.JSON(), nullable=True,
                   comment="候选生成失败时的错误信息"),
    )


def downgrade() -> None:
    # --- choices 回滚 ---
    op.drop_column("choices", "error")
    op.drop_column("choices", "validation_report")
    op.drop_column("choices", "score")
    op.drop_column("choices", "preview")
    op.drop_column("choices", "apply_mode")
    op.drop_column("choices", "draft_type")
    op.drop_column("choices", "payload")

    # --- choice_groups 回滚 ---
    op.drop_column("choice_groups", "status_detail")
    op.drop_column("choice_groups", "failure_count")
    op.drop_column("choice_groups", "success_count")
    op.drop_column("choice_groups", "candidate_count")
    op.drop_column("choice_groups", "origin_endpoint")
    op.drop_column("choice_groups", "generation_type")
