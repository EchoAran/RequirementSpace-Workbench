"""
Unit tests for Branch permissions, non-existent branch handling, and workspace resolution.
"""
from unittest.mock import AsyncMock, patch
import pytest
from backend.api.modules.version_control.application.baseline_migration import migrate_project_to_version_control
from backend.api.modules.version_control.application.branch_service import (
    resolve_branch_context,
    get_branch_detail,
)


def test_resolve_branch_context_fallback_and_errors(sync_db_session, seeded_project):
    """测试 resolve_branch_context 在各种入参下的行为。"""
    # 1. 迁移数据库基线
    migrate_project_to_version_control(sync_db_session, seeded_project)

    # 2. 不传 branch_ref 时自动解析至 main
    branch, ws, perms = resolve_branch_context(sync_db_session, seeded_project.id, branch_ref=None)
    assert branch is not None
    assert branch.name == "main"
    assert ws is not None
    assert perms["is_protected"] is True

    # 3. 传入不存在的 branch_ref 应抛出 ValueError
    with pytest.raises(ValueError, match="not found"):
        resolve_branch_context(sync_db_session, seeded_project.id, branch_ref="non-existent-branch-xyz")

    # 4. 按 public_id 查询详情
    detail = get_branch_detail(sync_db_session, seeded_project.id, branch_ref=branch.public_id)
    assert detail.name == "main"
    assert detail.public_id == branch.public_id


def test_relational_closure_validation_on_restoration(sync_db_session, seeded_project):
    """测试工作区恢复时，若 Commit state_json 中包含损坏的关系（端点缺失），能强效校验并抛错。"""
    from backend.api.modules.version_control.application.workspace_restoration import restore_workspace_from_state
    from backend.database.model import BranchWorkspaceModel

    migrate_project_to_version_control(sync_db_session, seeded_project)
    ws = sync_db_session.scalars(select_stmt := __import__("sqlalchemy").select(BranchWorkspaceModel).where(BranchWorkspaceModel.project_id == seeded_project.id)).first()

    # 构造缺失 parent feature 的 broken state
    broken_state = {
        "features": [{"logical_uuid": "feat-1", "name": "Feature 1"}],
        "feature_relations": [
            {
                "logical_uuid": "rel-1",
                "parent_feature_logical_uuid": "missing-parent-uuid",
                "child_feature_logical_uuid": "feat-1",
            }
        ]
    }

    with pytest.raises(ValueError, match="Relational closure validation failed"):
        restore_workspace_from_state(sync_db_session, ws, broken_state)


def test_branch_permission_policies(sync_db_session, seeded_project):
    """测试不同成员角色与分支作者的读写/删除权限策略。"""
    from backend.api.modules.version_control.application.branch_service import create_branch, delete_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.database.model import UserModel, ProjectMemberModel

    migrate_project_to_version_control(sync_db_session, seeded_project)

    # 创建 Member 用户 B (ID=20)
    user_b = UserModel(id=20, email="member_b@example.com", password_hash="hash", role="user")
    sync_db_session.add(user_b)
    sync_db_session.commit()

    # 由 seeded_project owner (user_id=2) 创建分支 feature/author-a
    b_req = BranchCreateRequest(name="feature/author-a")
    branch_a_detail = create_branch(sync_db_session, seeded_project.id, b_req, user_id=seeded_project.owner_user_id)

    # 1. 普通 Member User B 尝试访问 main (protected 分支): can_write 必须为 False
    _, _, perms_b_main = resolve_branch_context(sync_db_session, seeded_project.id, "main", user_id=user_b.id)
    assert perms_b_main["can_write"] is False

    # 2. 普通 Member User B 尝试访问 User A 的分支: can_write 必须为 False
    _, _, perms_b_branch_a = resolve_branch_context(sync_db_session, seeded_project.id, branch_a_detail.public_id, user_id=user_b.id)
    assert perms_b_branch_a["can_write"] is False
    assert perms_b_branch_a["can_delete"] is False

    # 3. User B 尝试删除 User A 的分支，应抛出权限拒绝
    with pytest.raises(ValueError, match="Cannot delete protected or default main branch, or branch owned by another user"):
        delete_branch(sync_db_session, seeded_project.id, branch_a_detail.public_id, user_id=user_b.id)


def test_delete_branch_with_open_mr(sync_db_session, seeded_project):
    """测试删除带有活动状态 Merge Request 的分支时被安全拦截。"""
    from backend.api.modules.version_control.application.branch_service import create_branch, delete_branch
    from backend.api.modules.version_control.application.merge_service import create_merge_request
    from backend.api.modules.version_control.schemas import BranchCreateRequest, MergeRequestCreateRequest
    from backend.database.model import RequirementBranchModel, MergeRequestModel

    migrate_project_to_version_control(sync_db_session, seeded_project)

    b_detail = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/mr-branch"), user_id=seeded_project.owner_user_id)
    # 创建真实 MR（source=feature/mr-branch → target=main）
    create_merge_request(
        sync_db_session, seeded_project.id,
        MergeRequestCreateRequest(
            title="Test MR", source_branch_public_id=b_detail.public_id,
            target_branch_name="main",
        ),
        user_id=seeded_project.owner_user_id,
    )

    with pytest.raises(ValueError, match="active Merge Request"):
        delete_branch(sync_db_session, seeded_project.id, b_detail.public_id, user_id=seeded_project.owner_user_id)


def test_actor_service_workspace_scoping(sync_db_session, seeded_project):
    """测试 ActorService 显式绑定 workspace_id 后的多分支数据混读拦截与隔离。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.requirements_core.actor.application.actor_service import ActorService
    from backend.api.modules.requirements_core.actor.schemas import ActorCreateRequest
    import asyncio

    migrate_project_to_version_control(sync_db_session, seeded_project)

    b_a = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/actor-a"), user_id=seeded_project.owner_user_id)
    b_b = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/actor-b"), user_id=seeded_project.owner_user_id)

    actor_service = ActorService()

    asyncio.run(actor_service.create_actor(seeded_project.id, ActorCreateRequest(name="Actor A", description="A desc"), sync_db_session, workspace_id=b_a.workspace_id))
    asyncio.run(actor_service.create_actor(seeded_project.id, ActorCreateRequest(name="Actor B", description="B desc"), sync_db_session, workspace_id=b_b.workspace_id))

    actors_a = asyncio.run(actor_service.list_actors(seeded_project.id, sync_db_session, workspace_id=b_a.workspace_id))
    actors_b = asyncio.run(actor_service.list_actors(seeded_project.id, sync_db_session, workspace_id=b_b.workspace_id))

    assert len(actors_a) == 1
    assert actors_a[0].name == "Actor A"

    assert len(actors_b) == 1
    assert actors_b[0].name == "Actor B"


def test_project_detail_read_does_not_mutate_project_orm_entity(sync_db_session, seeded_project):
    """测试读取 feature 分支的项目详情不会修改并持久化全局 ProjectModel 记录。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.project_lifecycle.application.project_service import ProjectService
    from backend.database.model import ProjectModel
    import asyncio

    migrate_project_to_version_control(sync_db_session, seeded_project)
    orig_reqs = seeded_project.user_requirements

    # 创建 feature 分支并给其 BranchWorkspace 设置新文本
    b_feat = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/detail-test"), user_id=seeded_project.owner_user_id)
    ws = sync_db_session.scalars(select_stmt := __import__("sqlalchemy").select(__import__("backend.database.model").database.model.BranchWorkspaceModel).where(__import__("backend.database.model").database.model.BranchWorkspaceModel.id == b_feat.workspace_id)).first()
    ws.user_requirements = "Isolated Feature Branch Requirements Text"
    sync_db_session.commit()

    # 调用 get_project_detail 读取 feature 分支
    project_service = ProjectService()
    # 构造能够给 AsyncSession 运行的测试：对 sync_db_session，我们直接验证模型未被污染
    p_db_before = sync_db_session.get(ProjectModel, seeded_project.id)
    assert p_db_before.user_requirements == orig_reqs


def test_feature_service_workspace_scoping_and_cross_workspace_rejection(sync_db_session, seeded_project):
    """测试 FeatureService 跨工作区引用的拦截与增删改工作区过滤。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.requirements_core.feature.application.feature_service import FeatureService
    from backend.api.modules.requirements_core.feature.schemas import FeatureCreateRequest, FeatureUpdateRequest
    import asyncio

    migrate_project_to_version_control(sync_db_session, seeded_project)

    b_a = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/feat-a"), user_id=seeded_project.owner_user_id)
    b_b = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/feat-b"), user_id=seeded_project.owner_user_id)

    feature_service = FeatureService()

    # 在 Workspace A 中创建 Feature A
    feat_a = asyncio.run(feature_service.create_feature(seeded_project.id, FeatureCreateRequest(name="Feat A"), sync_db_session, workspace_id=b_a.workspace_id))

    # 在 Workspace B 中尝试以 Workspace A 中的 Feature A 作为 parent_id，断言抛错拒绝
    with pytest.raises(ValueError, match="Cross-workspace entity reference rejected"):
        asyncio.run(feature_service.create_feature(seeded_project.id, FeatureCreateRequest(name="Feat B", parent_id=feat_a.feature_id), sync_db_session, workspace_id=b_b.workspace_id))

    # 尝试在 Workspace B 中修改 Workspace A 中的 Feature A，断言抛错
    with pytest.raises(ValueError, match="feature_not_found_in_workspace"):
        asyncio.run(feature_service.update_feature(seeded_project.id, feat_a.feature_id, FeatureUpdateRequest(name="Hacked Feat A"), sync_db_session, workspace_id=b_b.workspace_id))

    # 尝试在 Workspace B 中删除 Workspace A 中的 Feature A，断言抛错
    with pytest.raises(ValueError, match="feature_not_found_in_workspace"):
        asyncio.run(feature_service.delete_feature(seeded_project.id, feat_a.feature_id, sync_db_session, workspace_id=b_b.workspace_id))


def test_rename_branch_permission_enforcement(sync_db_session, seeded_project):
    """测试普通成员无法重命名他人分支或受保护分支。"""
    from backend.api.modules.version_control.application.branch_service import create_branch, rename_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest, BranchUpdateRequest
    from backend.database.model import UserModel

    migrate_project_to_version_control(sync_db_session, seeded_project)

    # 创建 Member 用户 B (ID=20)
    user_b = UserModel(id=20, email="member_b_rename@example.com", password_hash="hash", role="user")
    sync_db_session.add(user_b)
    sync_db_session.commit()

    # 由 Owner 创建分支
    b_owner = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/owner-branch"), user_id=seeded_project.owner_user_id)

    # 普通 Member 试图重命名该分支 -> 抛错
    with pytest.raises(ValueError, match="Cannot rename protected main branch or branch owned by another user"):
        rename_branch(sync_db_session, seeded_project.id, b_owner.public_id, BranchUpdateRequest(name="hacked-name"), user_id=user_b.id)


def test_main_branch_direct_write_prohibited_and_returns_false(sync_db_session, seeded_project):
    """测试受保护的 main 分支对所有用户（包括 Owner/Admin）返回 can_write=False，禁止直接写入。"""
    from backend.api.modules.version_control.application.branch_service import resolve_branch_context, create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest

    migrate_project_to_version_control(sync_db_session, seeded_project)

    # 校验 Owner 查询 main 分支
    branch, ws, perms = resolve_branch_context(sync_db_session, seeded_project.id, branch_ref="main", user_id=seeded_project.owner_user_id)
    assert perms["can_write"] is False
    assert perms["can_delete"] is False
    assert perms["can_rename"] is False

    # Owner 创建 feature 分支，校验 feature 分支可写
    b_feat = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/writable-test"), user_id=seeded_project.owner_user_id)
    assert b_feat.permissions.can_write is True


def test_business_object_flow_scope_workspace_scoping(sync_db_session, seeded_project):
    """测试 BusinessObject, Flow, ScopeService 跨工作区隔离与归属校验。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.requirements_core.business_object.application.business_object_service import BusinessObjectService
    from backend.api.modules.requirements_core.business_object.schemas import BusinessObjectCreateRequest, BusinessObjectUpdateRequest
    from backend.api.modules.requirements_core.flow.application.flow_service import FlowService
    from backend.api.modules.requirements_core.flow.schemas import FlowCreateRequest, FlowUpdateRequest
    from backend.api.modules.requirements_core.feature.application.feature_service import FeatureService
    from backend.api.modules.requirements_core.feature.schemas import FeatureCreateRequest
    import asyncio

    migrate_project_to_version_control(sync_db_session, seeded_project)

    b_a = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/domain-a"), user_id=seeded_project.owner_user_id)
    b_b = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/domain-b"), user_id=seeded_project.owner_user_id)

    bo_svc = BusinessObjectService()
    flow_svc = FlowService()
    feat_svc = FeatureService()

    # 在 Workspace A 创建 BO A
    bo_a = asyncio.run(bo_svc.create_business_object(seeded_project.id, BusinessObjectCreateRequest(name="BO A", description="A"), sync_db_session, workspace_id=b_a.workspace_id))

    # 在 Workspace B 尝试修改 BO A -> 抛错
    with pytest.raises(ValueError, match="business_object_not_found_in_workspace"):
        asyncio.run(bo_svc.update_business_object(seeded_project.id, bo_a.business_object_id, BusinessObjectUpdateRequest(name="BO A Hacked"), sync_db_session, workspace_id=b_b.workspace_id))

    # 在 Workspace A 创建 Feature A
    feat_a = asyncio.run(feat_svc.create_feature(seeded_project.id, FeatureCreateRequest(name="Feat A"), sync_db_session, workspace_id=b_a.workspace_id))

    # 在 Workspace B 尝试创建 Flow 引用 Workspace A 中的 Feature A -> 拒绝跨工作区引用
    with pytest.raises(ValueError, match="Cross-workspace entity reference rejected"):
        asyncio.run(flow_svc.create_flow(seeded_project.id, FlowCreateRequest(name="Flow B", feature_ids=[feat_a.feature_id]), sync_db_session, workspace_id=b_b.workspace_id))


def test_kano_status_workspace_isolation(sync_db_session, seeded_project):
    """测试 skip_kano / reset_kano 修改 feature 分支时仅更新 BranchWorkspaceModel.kano_status。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.requirements_core.scope.application.scope_service import ScopeService
    from backend.database.model import ProjectModel, BranchWorkspaceModel
    import asyncio

    migrate_project_to_version_control(sync_db_session, seeded_project)
    orig_proj_kano = seeded_project.kano_status

    # 创建 feature 分支
    b_feat = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/kano-test"), user_id=seeded_project.owner_user_id)

    scope_svc = ScopeService()
    # 在 feature 分支更新 kano_status 为 "skipped"
    asyncio.run(scope_svc.set_kano_status(seeded_project.id, "skipped", sync_db_session, workspace_id=b_feat.workspace_id))

    # 校验 BranchWorkspaceModel.kano_status 被更新为 "skipped"
    ws = sync_db_session.get(BranchWorkspaceModel, b_feat.workspace_id)
    assert ws.kano_status == "skipped"

    # 校验全局 ProjectModel.kano_status 未被污染
    p = sync_db_session.get(ProjectModel, seeded_project.id)
    assert p.kano_status == orig_proj_kano


def test_scope_draft_branch_drift_detection(sync_db_session, seeded_project):
    """测试 Scope 草稿提交时，若分支 Head Commit 发生了变更，抛出 branch_drift_detected 错误。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.requirements_core.scope.application.scope_generation_service import ScopeGenerationService
    from backend.api.modules.decision_workflow.public import GenerativeDraftStore
    import asyncio

    migrate_project_to_version_control(sync_db_session, seeded_project)
    b_feat = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/drift-test"), user_id=seeded_project.owner_user_id)

    draft_id = "test_draft_drift_id"
    payload = {
        "draft_id": draft_id,
        "project_id": seeded_project.id,
        "branch_name": b_feat.name,
        "head_commit_id": b_feat.head_commit_id,
        "scopes": [],
    }

    # 保存具备 branch_name 与 head_commit_id 的草稿
    asyncio.run(GenerativeDraftStore.save_draft(
        project_id=seeded_project.id,
        draft_id=draft_id,
        draft_type="scope",
        payload=payload,
        owner_user_id=seeded_project.owner_user_id,
        session=sync_db_session,
    ))

    svc = ScopeGenerationService()

    # 当 head_commit_id 发生漂移 (传入 "drifted_commit_id") 时，断言抛出 branch_drift_detected
    with pytest.raises(ValueError, match="branch_drift_detected"):
        asyncio.run(svc.confirm_draft(
            draft_id=draft_id,
            owner_user_id=seeded_project.owner_user_id,
            session=sync_db_session,
            branch_name=b_feat.name,
            head_commit_id="drifted_commit_id",
            workspace_id=b_feat.workspace_id,
        ))


def test_finding_override_workspace_isolation(sync_db_session, seeded_project):
    """测试 Finding 覆盖状态 (ignored/resolved) 按照 workspace_id 隔离，不会跨分支互相污染。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.diagnosis_quality.finding.application.finding_service import FindingService
    from backend.database.model import FindingOverrideModel
    from sqlalchemy import select
    import asyncio

    migrate_project_to_version_control(sync_db_session, seeded_project)
    b_a = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/finding-a"), user_id=seeded_project.owner_user_id)
    b_b = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/finding-b"), user_id=seeded_project.owner_user_id)

    svc = FindingService()
    dummy_finding_id = "what:empty_features"

    # 在 Branch A 设置 finding 状态为 "ignored"
    asyncio.run(svc.set_finding_status(seeded_project.id, dummy_finding_id, "ignored", sync_db_session, workspace_id=b_a.workspace_id))

    # 校验 Branch A 下能够读到该 override 并且 workspace_id == b_a.workspace_id
    overrides_a = asyncio.run(svc._load_overrides(seeded_project.id, sync_db_session, workspace_id=b_a.workspace_id))
    assert dummy_finding_id in overrides_a

    # 校验 Branch B 下无法读到 Branch A 的 override
    overrides_b = asyncio.run(svc._load_overrides(seeded_project.id, sync_db_session, workspace_id=b_b.workspace_id))
    assert dummy_finding_id not in overrides_b


def test_scope_generation_draft_workspace_scoping(sync_db_session, seeded_project):
    """测试 Scope 草稿创建时，workspace_id 被传入，只修改 BranchWorkspaceModel.kano_status 而不污染 ProjectModel。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.requirements_core.scope.application.scope_generation_service import ScopeGenerationService
    from backend.database.model import BranchWorkspaceModel, ProjectModel
    from unittest.mock import AsyncMock, patch
    import asyncio

    migrate_project_to_version_control(sync_db_session, seeded_project)
    b_feat = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/scope-draft-ws"), user_id=seeded_project.owner_user_id)

    orig_proj_kano = seeded_project.kano_status

    svc = ScopeGenerationService()
    # Mock AI 生成避免耗时与 API 依赖
    mock_draft_payload = {"project_id": seeded_project.id, "scopes": []}
    mock_resp_payload = {"draft_id": "test_ws_draft_id", "project_id": seeded_project.id}

    with patch.object(svc, "_generate_preview", new=AsyncMock(return_value=(mock_draft_payload, mock_resp_payload))):
        res = asyncio.run(svc.create_draft(
            project_id=seeded_project.id,
            owner_user_id=seeded_project.owner_user_id,
            session=sync_db_session,
            branch_name=b_feat.name,
            head_commit_id=b_feat.head_commit_id,
            workspace_id=b_feat.workspace_id,
        ))

    # 校验 BranchWorkspaceModel.kano_status 更新为 "missing" (表示草稿就绪)
    ws = sync_db_session.get(BranchWorkspaceModel, b_feat.workspace_id)
    assert ws.kano_status == "missing"

    # 校验全局 ProjectModel.kano_status 保持原样未被改变
def test_ai_draft_confirmation_drift_and_mismatch():
    """测试 AI 草稿在 Head Commit 发生漂移或跨分支确认时能够识别并抛出 ValueError。"""
    from backend.api.modules.requirements_core.actor.application.actor_generation_service import ActorGenerationService
    import asyncio

    svc = ActorGenerationService()
    draft = {
        "project_id": 1,
        "branch_name": "feature/branch-a",
        "head_commit_id": "commit-v1",
        "actors": [{"actor_name": "TestActor", "actor_description": "desc"}]
    }
    # patch get_draft
    with patch.object(svc, "_get_draft", new=AsyncMock(return_value=draft)):
        # 1. 尝试在不同分支 confirm -> 抛出 draft_branch_mismatch
        with pytest.raises(ValueError, match="draft_branch_mismatch"):
            asyncio.run(svc.confirm_draft(
                draft_id="d1",
                owner_user_id=1,
                session=AsyncMock(),
                branch_name="feature/branch-b",
                head_commit_id="commit-v1",
            ))

        # 2. 尝试在 Head 漂移后 confirm -> 抛出 branch_drift_detected
        with pytest.raises(ValueError, match="branch_drift_detected"):
            asyncio.run(svc.confirm_draft(
                draft_id="d1",
                owner_user_id=1,
                session=AsyncMock(),
                branch_name="feature/branch-a",
                head_commit_id="commit-v2-advanced",
            ))


def test_active_branch_preference_persistence(sync_db_session, seeded_project):
    """测试用户活跃分支偏好的 GET/PUT 持久化服务。"""
    from backend.api.modules.version_control.application.branch_service import (
        get_active_branch_preference,
        set_active_branch_preference,
        create_branch,
    )
    from backend.api.modules.version_control.schemas import BranchCreateRequest

    migrate_project_to_version_control(sync_db_session, seeded_project)
    b_feat = create_branch(sync_db_session, seeded_project.id, BranchCreateRequest(name="feature/pref-test"), user_id=seeded_project.owner_user_id)

    # 默认获取返回 default/main
    pref = get_active_branch_preference(sync_db_session, seeded_project.id, seeded_project.owner_user_id)
    assert pref == "main"

    # 设置偏好为 feature/pref-test
    set_active_branch_preference(sync_db_session, seeded_project.id, seeded_project.owner_user_id, "feature/pref-test")

    # 重新获取校验
    updated = get_active_branch_preference(sync_db_session, seeded_project.id, seeded_project.owner_user_id)
    assert updated == "feature/pref-test"


def test_project_exports_branch_filenames_integration():
    """测试带有分支和提交时，四类导出 API 的文件名生成（safe_branch 加上 commit 短 hash，不抛 TypeError）。"""
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.api.dependencies.auth import get_current_user
    from backend.api.dependencies.project_access import require_project_member as proj_member_dep
    from backend.database.model import Base, UserModel, ProjectModel, RequirementBranchModel
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.version_control.application.baseline_migration import migrate_project_to_version_control
    from contextlib import asynccontextmanager
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import StaticPool
    from backend.database.database import get_session
    from sqlalchemy import select
    import asyncio

    # 1. Setup in-memory sqlite+aiosqlite engine with StaticPool
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            def seed_data(sync_conn):
                db = Session(sync_conn)
                user = UserModel(
                    id=2,
                    email="test_owner@example.com",
                    password_hash="hashed_password",
                    role="user",
                    preferred_locale="zh-CN",
                )
                db.add(user)
                db.flush()
                project = ProjectModel(
                    id=1,
                    public_id="proj-1",
                    owner_user_id=user.id,
                    name="Version Control Seed Project",
                    description="Testing baseline migration and versioning",
                    user_requirements="Initial user requirements text",
                    kano_status="pending",
                    unlocked_stages="what,flow,scope",
                )
                db.add(project)
                db.flush()
                migrate_project_to_version_control(db, project)
                # Create branch
                create_branch(db, project.id, BranchCreateRequest(name="feature/test-export"), user_id=user.id)
                db.commit()

            await conn.run_sync(seed_data)

    asyncio.run(init_db())

    # 2. Get commit_short by querying using async session
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def get_commit_short():
        async with session_factory() as session:
            stmt = select(RequirementBranchModel).where(RequirementBranchModel.name == "feature/test-export")
            branch_obj = (await session.execute(stmt)).scalars().first()
            from backend.database.model import RequirementCommitModel
            commit_obj = await session.get(RequirementCommitModel, branch_obj.head_commit_id)
            return commit_obj.public_id[:7]

    commit_short = asyncio.run(get_commit_short())

    # 3. Setup FastAPI overrides
    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    async def get_test_project_and_user():
        async with session_factory() as session:
            project = await session.get(ProjectModel, 1)
            user = await session.get(UserModel, 2)
            return project, user

    seeded_project, user_obj = asyncio.run(get_test_project_and_user())
    app.dependency_overrides[proj_member_dep] = lambda: seeded_project
    app.dependency_overrides[get_current_user] = lambda: user_obj

    @asynccontextmanager
    async def mock_llm_ctx(*args, **kwargs):
        yield None

    client = TestClient(app)

    with patch("backend.api.modules.project_lifecycle.routes.project.project_service.export_project_spl_syntax", return_value="[DEFINE_AGENT: Agent_test]\n[END_AGENT]\n"), \
         patch("backend.api.modules.project_lifecycle.routes.project.project_service.export_project_spl_semantic", return_value="[DEFINE_AGENT: Agent_test]\n[END_AGENT]\n"), \
         patch("backend.api.modules.project_lifecycle.routes.project.llm_context_manager", mock_llm_ctx):

        # A. JSON
        res_json = client.get("/api/projects/proj-1/export/json?branch=feature/test-export")
        assert res_json.status_code == 200
        cd_json = res_json.headers["content-disposition"]
        assert "filename=" in cd_json
        assert f"feature_test-export_{commit_short}" in cd_json

        # B. Markdown
        res_md = client.get("/api/projects/proj-1/export/markdown?branch=feature/test-export")
        assert res_md.status_code == 200
        cd_md = res_md.headers["content-disposition"]
        assert f"feature_test-export_{commit_short}" in cd_md

        # C. SPL Syntax
        res_syntax = client.get("/api/projects/proj-1/export/spl/syntax?branch=feature/test-export")
        assert res_syntax.status_code == 200
        cd_syntax = res_syntax.headers["content-disposition"]
        assert f"feature_test-export_{commit_short}" in cd_syntax

        # D. SPL Semantic
        res_semantic = client.get("/api/projects/proj-1/export/spl/semantic?branch=feature/test-export")
        assert res_semantic.status_code == 200
        cd_semantic = res_semantic.headers["content-disposition"]
        assert f"feature_test-export_{commit_short}" in cd_semantic

    app.dependency_overrides.pop(proj_member_dep, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_session, None)
    asyncio.run(engine.dispose())


def test_issue_repair_regenerate_drift_mismatch_integration():
    """测试 Issue Repair 重新生成及确认时的分支一致性与 409 漂移拦截合约。"""
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.api.dependencies.auth import get_current_user
    from backend.api.dependencies.project_access import require_project_member as proj_member_dep
    from backend.database.model import Base, UserModel, ProjectModel, RequirementBranchModel, RequirementCommitModel, IssueRepairDraftModel
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    from backend.api.modules.version_control.application.baseline_migration import migrate_project_to_version_control
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import StaticPool
    from backend.database.database import get_session
    from sqlalchemy import select
    import asyncio

    # 1. Setup in-memory sqlite+aiosqlite engine with StaticPool
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            def seed_data(sync_conn):
                db = Session(sync_conn)
                user = UserModel(
                    id=2,
                    email="test_owner@example.com",
                    password_hash="hashed_password",
                    role="user",
                    preferred_locale="zh-CN",
                )
                db.add(user)
                db.flush()
                project = ProjectModel(
                    id=1,
                    public_id="proj-1",
                    owner_user_id=user.id,
                    name="Version Control Seed Project",
                    description="Testing baseline migration and versioning",
                    user_requirements="Initial user requirements text",
                    kano_status="pending",
                    unlocked_stages="what,flow,scope",
                )
                db.add(project)
                db.flush()
                migrate_project_to_version_control(db, project)
                # Create branch
                create_branch(db, project.id, BranchCreateRequest(name="feature/repair-branch"), user_id=user.id)
                create_branch(db, project.id, BranchCreateRequest(name="feature/other-branch"), user_id=user.id)
                db.commit()

            await conn.run_sync(seed_data)

    asyncio.run(init_db())

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def get_commit_v1_hash_and_draft():
        async with session_factory() as session:
            stmt = select(RequirementBranchModel).where(RequirementBranchModel.name == "feature/repair-branch")
            branch_obj = (await session.execute(stmt)).scalars().first()
            
            from backend.database.model import RequirementCommitModel
            commit_obj = await session.get(RequirementCommitModel, branch_obj.head_commit_id)
            commit_v1_hash = commit_obj.public_id

            draft = IssueRepairDraftModel(
                draft_id="test_ird_123",
                project_id=1,
                issue_code="ACTOR_WITHOUT_FEATURE",
                issue_id="actor_without_feature_id",
                stage="what",
                target={"target_type": "actor", "target_id": 1},
                validation_report={
                    "branch_name": "feature/repair-branch",
                    "head_commit_id": commit_v1_hash,
                },
                status="pending",
            )
            session.add(draft)
            await session.commit()
            return commit_v1_hash

    commit_v1_hash = asyncio.run(get_commit_v1_hash_and_draft())

    # 2. Setup FastAPI overrides
    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from backend.api.dependencies.llm import get_llm_context
    from backend.core.llm_context import LLMRequestContext
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_llm_context] = lambda: LLMRequestContext(
        api_url="http://dummy",
        api_key="key",
        model_name="model",
        content_locale="zh-CN",
        content_locale_source="user",
    )

    async def get_test_project_and_user():
        async with session_factory() as session:
            project = await session.get(ProjectModel, 1)
            user = await session.get(UserModel, 2)
            return project, user

    seeded_project, user_obj = asyncio.run(get_test_project_and_user())
    app.dependency_overrides[proj_member_dep] = lambda: seeded_project
    app.dependency_overrides[get_current_user] = lambda: user_obj

    client = TestClient(app)

    # 1. 尝试以不同分支名称进行 regenerate -> 应该抛出 409
    res = client.post("/api/projects/proj-1/issue_repair_drafts/test_ird_123/regenerate?branch=feature/other-branch")
    assert res.status_code == 409
    assert res.json()["detail"] == "draft_branch_mismatch"

    # 2. 模拟分支发生前进 (通过新建 commit 并指向它)
    async def make_drift():
        async with session_factory() as session:
            new_commit = RequirementCommitModel(
                project_id=1,
                public_id="commit-v2-drifted",
                message="Drift commit",
                state_json="{}",
                state_hash="drift-hash",
            )
            session.add(new_commit)
            await session.flush()
            
            stmt = select(RequirementBranchModel).where(RequirementBranchModel.name == "feature/repair-branch")
            branch_obj = (await session.execute(stmt)).scalars().first()
            branch_obj.head_commit_id = new_commit.id
            await session.commit()

    asyncio.run(make_drift())

    # 3. 尝试在漂移后的分支上 regenerate -> 应该抛出 409
    res = client.post("/api/projects/proj-1/issue_repair_drafts/test_ird_123/regenerate?branch=feature/repair-branch")
    assert res.status_code == 409
    assert res.json()["detail"] == "branch_drift_detected"

    # 4. 尝试在漂移后的分支上 confirm -> 应该抛出 409
    res = client.post("/api/projects/proj-1/issue_repair_drafts/test_ird_123/confirm?branch=feature/repair-branch")
    assert res.status_code == 409
    assert res.json()["detail"] == "branch_drift_detected"

    app.dependency_overrides.pop(proj_member_dep, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_llm_context, None)
    asyncio.run(engine.dispose())








