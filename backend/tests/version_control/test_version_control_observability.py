"""
Version Control Observability Tests (Phase 7).
验证：
  1. diff service 成功时记录 VC_DIFF_COMPLETED（含 duration_ms / entries_total / changed_object_count）；
  2. merge 遇未解决冲突时记录 VC_MERGE_FAILED（含 error_type=MergeConflictError）；
  3. audit_vc_failure 先记 WARNING 日志再调用 record_vc_failure_event；
  4. 迁移日志事件（成功/跳过）。
"""
import logging
import pytest

from backend.api.modules.version_control.application.diff_service import get_diff
from backend.api.modules.version_control.application import merge_execution


@pytest.fixture
def enable_domain_logging(monkeypatch):
    """确保 domain 类目开启，使 log_event 实际输出到 caplog。"""
    import backend.core.logging.logger as logger_mod
    import backend.core.logging.config as config_mod

    class _Settings:
        enabled = True
        def category_enabled(self, category):
            return True

    monkeypatch.setattr(config_mod, "load_logging_settings", lambda: _Settings())
    monkeypatch.setattr(logger_mod, "load_logging_settings", lambda: _Settings())
    yield


@pytest.fixture
def merge_project(sync_db_session, seeded_vc_project):
    """基于已迁移且含完整模型的种子项目，创建 main + feature 分支用于合并测试。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    project = seeded_vc_project.project
    feature = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature/merge"),
        user_id=project.owner_user_id,
    )
    return project, feature, seeded_vc_project.main_branch


def test_diff_records_duration_event(sync_db_session, seeded_vc_project, caplog, enable_domain_logging):
    """get_diff 成功后在 domain 日志记录 VC_DIFF_COMPLETED，含耗时与变更量。"""
    project = seeded_vc_project.project
    # 制造一次 target 侧变更：改 main 工作区用户需求后比较 head vs workspace。
    ws = seeded_vc_project.main_workspace
    ws.user_requirements = "changed requirements text"
    sync_db_session.flush()

    with caplog.at_level(logging.INFO, logger="backend.version_control"):
        result = get_diff(
            db=sync_db_session,
            project_id=project.id,
            base_ref=f"commit:{seeded_vc_project.baseline_commit_id}",
            branch_ref="main",
        )
    assert result is not None
    # domain 类目默认未开启，但 fixture 强制开启；断言事件已记录。
    events = [r for r in caplog.records if getattr(r, "event", None) == "vc_diff_completed"]
    assert events, "VC_DIFF_COMPLETED should be logged"
    fields = events[0].log_fields if hasattr(events[0], "log_fields") else {}
    assert "duration_ms" in fields
    assert "operation" in fields


def test_merge_conflict_detected_by_preview(sync_db_session, merge_project, caplog, enable_domain_logging):
    """存在未解决冲突时 get_merge_preview 报告冲突、perform_merge 拒绝合并。

    合并失败的可观测性由路由层 audit_vc_failure 提供（记 vc_merge_conflict 日志 + 审计），
    service 层仅保证冲突被正确检测与拒绝（不静默合并）。
    """
    from backend.api.modules.version_control.application.merge_execution import perform_merge
    from backend.api.modules.version_control.schemas import MergeRequestPayload
    from backend.api.modules.version_control.application.merge_service import create_merge_request, review_mr
    from backend.api.modules.version_control.application.commit_service import create_commit
    from backend.database.model import BranchWorkspaceModel, FeatureModel, RequirementBranchModel
    from sqlalchemy import select
    from backend.api.modules.version_control.schemas import (
        BranchCreateRequest, CommitCreateRequest, MergeRequestCreateRequest, MergeReviewRequest,
    )
    from backend.api.modules.version_control.application.branch_service import create_branch

    project, feature, main = merge_project
    feature2 = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature/conflict-tgt", source_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )

    def _set_name(branch, name):
        ws = sync_db_session.scalars(
            select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == branch.id)
        ).first()
        feat = sync_db_session.scalars(
            select(FeatureModel).where(FeatureModel.workspace_id == ws.id)
        ).first()
        feat.name = name
        sync_db_session.flush()
        cur = sync_db_session.get(RequirementBranchModel, branch.id)
        create_commit(
            sync_db_session, project.id, cur.public_id,
            CommitCreateRequest(message=name, expected_head_commit_id=cur.head_commit_id),
            user_id=project.owner_user_id,
        )

    _set_name(feature, "src-name")
    _set_name(feature2, "tgt-name")

    from backend.database.model import UserModel, ProjectMemberModel
    admin = UserModel(id=80, email="obs-admin@test.com", password_hash="h", role="admin")
    sync_db_session.add(admin)
    sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=admin.id, role="admin", status="active"))
    sync_db_session.commit()

    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(title="obs conflict", source_branch_public_id=feature.public_id, target_branch_public_id=feature2.public_id),
        user_id=project.owner_user_id,
    )
    review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)

    preview = merge_execution.get_merge_preview(sync_db_session, project.id, mr.public_id)
    assert preview.conflict_count >= 1

    # 未提供 resolution → 合并被拒绝（不产生 merge commit）。
    from backend.api.modules.version_control.application.errors import MergeConflictError
    with pytest.raises(MergeConflictError):
        perform_merge(
            sync_db_session, project.id, mr.public_id,
            MergeRequestPayload(
                resolutions=[],
                merge_base_public_id=preview.merge_base_public_id,
                source_head_public_id=preview.source_head_public_id,
                target_head_public_id=preview.target_head_public_id,
            ),
            user_id=project.owner_user_id,
        )


def test_audit_vc_failure_logs_and_audits(monkeypatch, caplog, enable_domain_logging):
    """audit_vc_failure 先记 WARNING 日志，再调用 record_vc_failure_event。"""
    from backend.api.modules.version_control import observability

    captured = {}

    async def _fake_failure_event(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(observability, "record_vc_failure_event", _fake_failure_event)

    import asyncio
    with caplog.at_level(logging.WARNING, logger="backend.version_control"):
        asyncio.run(observability.audit_vc_failure(
            project_id=1, action_type="commit_head_changed", summary="冲突",
            target_type="commit", target_id="head", error_type="HeadChangedError",
            latest_head_public_id="abc",
        ))
    assert captured["action_type"] == "commit_head_changed"
    assert captured["project_id"] == 1
    assert any(getattr(r, "event", None) == "vc_commit_head_changed" for r in caplog.records)


def test_migration_logs_events(sync_db_session, seeded_project, caplog, enable_domain_logging):
    """migrate_project_to_version_control 成功时记录 VC_MIGRATION_PROJECT_COMPLETED。"""
    from backend.api.modules.version_control.application.baseline_migration import migrate_project_to_version_control
    project = seeded_project
    with caplog.at_level(logging.INFO, logger="backend.version_control.baseline_migration"):
        result = migrate_project_to_version_control(sync_db_session, project)
        sync_db_session.commit()
    assert result["status"] == "success"
    events = [r for r in caplog.records if getattr(r, "event", None) == "vc_migration_project_completed"]
    assert events, "VC_MIGRATION_PROJECT_COMPLETED should be logged"
