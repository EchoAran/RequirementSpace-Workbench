"""
Comprehensive Negative and Isolation Test Matrix for Branch Workspaces.
Covers:
1. Cross-workspace sub-entity (BO Attribute, FlowStep, Scenario AC) update & deletion rejection (404 Not Found)
2. Sub-entity creation workspace attribution assertions
3. Perception Job running-state and duplication cross-branch isolation
4. User Requirements API protected-main 403 guard and empty string non-fallback
5. Unified map_branch_error 404 on unknown branch across all endpoint categories
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.dependencies.llm import get_llm_context
from backend.api.modules.requirements_core.business_object.application.business_object_service import (
    BusinessObjectService,
)
from backend.api.modules.requirements_core.business_object.schemas import (
    BusinessObjectAttributeCreateRequest,
    BusinessObjectAttributeUpdateRequest,
    BusinessObjectCreateRequest,
)
from backend.api.modules.requirements_core.flow.application.flow_service import (
    FlowService,
)
from backend.api.modules.requirements_core.flow.schemas import (
    FlowCreateRequest,
    FlowStepCreateRequest,
    FlowStepUpdateRequest,
)
from backend.api.modules.requirements_core.scenario.application.scenario_service import (
    ScenarioService,
)
from backend.api.modules.requirements_core.scenario.schemas import (
    AcceptanceCriterionCreateRequest,
    AcceptanceCriterionUpdateRequest,
    ScenarioCreateRequest,
)
from backend.api.modules.version_control.application.clean_initialization import (
    create_initial_workspace,
    finalize_initial_commit,
    initialize_project_version_control,
)
from backend.api.modules.version_control.application.branch_service import (
    create_branch,
    resolve_branch_context,
)
from backend.api.modules.version_control.schemas import BranchCreateRequest
from backend.database.database import Base, get_session
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    PerceptionJobModel,
    PerceptionSlotModel,
    ProjectModel,
    RequirementBranchModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    UserLLMConfigModel,
    UserModel,
)
from backend.main import app


@pytest.fixture
async def matrix_test_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_llm_context():
        yield None

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_llm_context] = override_get_llm_context
    yield session_factory
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_llm_context, None)
    await engine.dispose()


@pytest.mark.asyncio
async def test_cross_workspace_subentity_rejection(matrix_test_db):
    """
    负向测试：跨分支工作区操作子实体（Attribute / FlowStep / AC）必须被严格拦截（Not Found）。
    """
    async with matrix_test_db() as session:
        user = UserModel(email="subentity_user@example.com", password_hash="pw")
        session.add(user)
        await session.flush()

        project = ProjectModel(
            name="Subentity Isolation Project",
            owner_user_id=user.id,
            user_requirements="Initial Requirements",
        )
        session.add(project)
        await session.flush()

        main_branch, main_workspace = await session.run_sync(
            lambda sync_session: create_initial_workspace(sync_session, project)
        )

        bo = BusinessObjectModel(project_id=project.id, workspace_id=main_workspace.id, name="Order", description="Order entity")
        session.add(bo)
        await session.flush()

        attr = BusinessObjectAttributeModel(
            workspace_id=main_workspace.id,
            business_object_id=bo.id,
            name="total_price",
            data_type="decimal",
        )
        session.add(attr)

        feat = FeatureModel(project_id=project.id, workspace_id=main_workspace.id, name="Checkout")
        session.add(feat)
        await session.flush()

        actor = ActorModel(project_id=project.id, workspace_id=main_workspace.id, name="Customer")
        session.add(actor)
        await session.flush()

        scen = ScenarioModel(
            project_id=project.id,
            workspace_id=main_workspace.id,
            feature_id=feat.id,
            actor_id=actor.id,
            name="Pay",
            content="Given items in cart",
        )
        session.add(scen)
        await session.flush()

        ac = ScenarioAcceptanceCriterionModel(workspace_id=main_workspace.id, scenario_id=scen.id, position=1, content="Paid successfully")
        session.add(ac)

        flow = FlowModel(project_id=project.id, workspace_id=main_workspace.id, name="Checkout Flow")
        session.add(flow)
        await session.flush()

        step = FlowStepModel(workspace_id=main_workspace.id, flow_id=flow.id, position=1, name="Submit", description="", step_type="systemAction")
        session.add(step)
        await session.flush()
        await session.run_sync(
            lambda sync_session: finalize_initial_commit(
                sync_session,
                project,
                main_branch,
                main_workspace,
            )
        )
        await session.commit()

        br_a = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/alpha", source_branch_public_id="main"))
        )
        br_b = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/beta", source_branch_public_id="main"))
        )

        _, ws_a, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_a.public_id))
        _, ws_b, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_b.public_id))

        # 获取 Branch B 工作区中的子实体 ID
        bo_b = (await session.execute(
            select(BusinessObjectModel).where(BusinessObjectModel.workspace_id == ws_b.id)
        )).scalars().first()
        attr_b = (await session.execute(
            select(BusinessObjectAttributeModel).where(BusinessObjectAttributeModel.workspace_id == ws_b.id)
        )).scalars().first()
        scen_b = (await session.execute(
            select(ScenarioModel).where(ScenarioModel.workspace_id == ws_b.id)
        )).scalars().first()
        ac_b = (await session.execute(
            select(ScenarioAcceptanceCriterionModel).where(ScenarioAcceptanceCriterionModel.workspace_id == ws_b.id)
        )).scalars().first()
        flow_b = (await session.execute(
            select(FlowModel).where(FlowModel.workspace_id == ws_b.id)
        )).scalars().first()
        step_b = (await session.execute(
            select(FlowStepModel).where(FlowStepModel.workspace_id == ws_b.id)
        )).scalars().first()

        assert bo_b is not None
        assert attr_b is not None
        assert scen_b is not None
        assert ac_b is not None
        assert flow_b is not None
        assert step_b is not None

        # 验证使用 Branch A 工作区上下文去更新/删除 Branch B 的子实体全部抛出 not found
        bo_service = BusinessObjectService()
        flow_service = FlowService()
        scenario_service = ScenarioService()

        # (a) BusinessObjectAttribute 跨工作区更新 & 删除拦截 (使用 ws_a 上下文)
        with pytest.raises(ValueError):
            await bo_service.update_business_object_attribute(
                project_id=project.id,
                bo_id=bo_b.id,
                attr_id=attr_b.id,
                req=BusinessObjectAttributeUpdateRequest(name="hacked_price"),
                session=session,
                workspace_id=ws_a.id,
            )

        with pytest.raises(ValueError):
            await bo_service.delete_business_object_attribute(
                project_id=project.id,
                bo_id=bo_b.id,
                attr_id=attr_b.id,
                session=session,
                workspace_id=ws_a.id,
            )

        # (b) FlowStep 跨工作区更新 & 删除拦截 (使用 ws_a 上下文)
        with pytest.raises(ValueError):
            await flow_service.update_flow_step(
                project_id=project.id,
                flow_id=flow_b.id,
                step_id=step_b.id,
                req=FlowStepUpdateRequest(name="hacked_action"),
                session=session,
                workspace_id=ws_a.id,
            )

        with pytest.raises(ValueError):
            await flow_service.delete_flow_step(
                project_id=project.id,
                flow_id=flow_b.id,
                step_id=step_b.id,
                session=session,
                workspace_id=ws_a.id,
            )

        # (c) Scenario Acceptance Criterion 跨工作区更新 & 删除拦截 (使用 ws_a 上下文)
        with pytest.raises(ValueError):
            await scenario_service.update_acceptance_criterion(
                project_id=project.id,
                scenario_id=scen_b.id,
                ac_id=ac_b.id,
                req=AcceptanceCriterionUpdateRequest(content="hacked_content"),
                session=session,
                workspace_id=ws_a.id,
            )

        with pytest.raises(ValueError):
            await scenario_service.delete_acceptance_criterion(
                project_id=project.id,
                scenario_id=scen_b.id,
                ac_id=ac_b.id,
                session=session,
                workspace_id=ws_a.id,
            )


@pytest.mark.asyncio
async def test_child_entity_creation_workspace_attribution(matrix_test_db):
    """
    验证在指定工作区中创建子实体后，其实体的 workspace_id 严格归属于该工作区。
    """
    async with matrix_test_db() as session:
        user = UserModel(email="child_user@example.com", password_hash="pw")
        session.add(user)
        await session.flush()

        project = ProjectModel(
            name="Child Attribution Project",
            owner_user_id=user.id,
            user_requirements="Initial Requirements",
        )
        session.add(project)
        await session.flush()

        await session.run_sync(lambda s: initialize_project_version_control(s, project))
        br_a = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/attr-test", source_branch_public_id="main"))
        )
        _, ws_a, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_a.public_id))

        bo_service = BusinessObjectService()
        flow_service = FlowService()
        scenario_service = ScenarioService()

        # 在 ws_a 中创建 BO、Flow 和 Scenario
        bo = await bo_service.create_business_object(
            project_id=project.id,
            req=BusinessObjectCreateRequest(name="Invoice", description="Invoice entity"),
            session=session,
            workspace_id=ws_a.id,
        )
        bo_model = await session.get(BusinessObjectModel, bo.business_object_id)
        assert bo_model.workspace_id == ws_a.id

        attr = await bo_service.create_business_object_attribute(
            project_id=project.id,
            bo_id=bo.business_object_id,
            req=BusinessObjectAttributeCreateRequest(name="invoice_no", data_type="string"),
            session=session,
            workspace_id=ws_a.id,
        )
        attr_model = await session.get(BusinessObjectAttributeModel, attr.attribute_id)
        assert attr_model.workspace_id == ws_a.id

        feat = FeatureModel(project_id=project.id, name="Billing", workspace_id=ws_a.id)
        session.add(feat)
        actor = ActorModel(project_id=project.id, name="Accountant", workspace_id=ws_a.id)
        session.add(actor)
        await session.flush()

        scen = await scenario_service.create_scenario(
            project_id=project.id,
            req=ScenarioCreateRequest(
                feature_id=feat.id,
                actor_id=actor.id,
                name="Generate Invoice",
                content="When order paid",
            ),
            session=session,
            workspace_id=ws_a.id,
        )
        scen_model = await session.get(ScenarioModel, scen.scenario_id)
        assert scen_model.workspace_id == ws_a.id

        ac = await scenario_service.create_acceptance_criterion(
            project_id=project.id,
            scenario_id=scen.scenario_id,
            req=AcceptanceCriterionCreateRequest(content="Invoice generated with PDF"),
            session=session,
            workspace_id=ws_a.id,
        )
        ac_model = await session.get(ScenarioAcceptanceCriterionModel, ac.criterion_id)
        assert ac_model.workspace_id == ws_a.id

        flow = await flow_service.create_flow(
            project_id=project.id,
            req=FlowCreateRequest(name="Invoice Flow"),
            session=session,
            workspace_id=ws_a.id,
        )
        flow_model = await session.get(FlowModel, flow.flow_id)
        assert flow_model.workspace_id == ws_a.id

        step = await flow_service.create_flow_step(
            project_id=project.id,
            flow_id=flow.flow_id,
            req=FlowStepCreateRequest(name="Trigger billing", step_type="systemAction"),
            session=session,
            workspace_id=ws_a.id,
        )
        step_model = await session.get(FlowStepModel, step.step_id)
        assert step_model.workspace_id == ws_a.id


@pytest.mark.asyncio
async def test_perception_job_cross_branch_running_isolation(matrix_test_db):
    """
    验证 Perception Job 运行状态（analysis_running）按 workspace_id 完全隔离，
    分支 A 上正在运行的 Job 不会导致分支 B 或 main 的 stage-progress 变为 analysis_running。
    """
    client = TestClient(app)
    reg_payload = {"email": "matrix_user@example.com", "password": "password123"}
    res = client.post("/api/auth/register", json=reg_payload)
    user_id = int(res.json()["id"])
    client.post("/api/auth/login", json=reg_payload)

    # 1. 种子项目与 VC 迁移
    async with matrix_test_db() as session:
        project = ProjectModel(
            name="Perception Isolation Project",
            description="Testing perception isolation",
            owner_user_id=user_id,
            user_requirements="Initial Requirements",
        )
        session.add(project)
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))
        await session.commit()
        pub_pid = project.public_id
        int_pid = project.id

    # 2. 创建分支 feature/work-a 与 feature/work-b
    br_a_res = client.post(f"/api/projects/{pub_pid}/branches", json={"name": "feature/work-a"})
    assert br_a_res.status_code == 201

    br_b_res = client.post(f"/api/projects/{pub_pid}/branches", json={"name": "feature/work-b"})
    assert br_b_res.status_code == 201

    async with matrix_test_db() as session:
        # 获取 branch-a 的 workspace_id
        ws_a = (
            await session.execute(
                select(BranchWorkspaceModel)
                .join(RequirementBranchModel, RequirementBranchModel.id == BranchWorkspaceModel.branch_id)
                .where(RequirementBranchModel.project_id == int_pid, RequirementBranchModel.name == "feature/work-a")
            )
        ).scalars().first()
        assert ws_a is not None

        # 在 ws_a 上插入一个 running perception job
        job_a = PerceptionJobModel(
            project_id=int_pid,
            workspace_id=ws_a.id,
            stage="what",
            perception_kind="ACTOR",
            status="running",
            target_type="project",
            target_id=str(int_pid),
            context_hash="hash_a",
        )
        session.add(job_a)
        await session.commit()

    # 3. 检查 branch=feature/work-a 的 stage-progress：应显示 analysis_running
    resp_a = client.get(f"/api/projects/{pub_pid}/stage-progress?branch=feature/work-a")
    assert resp_a.status_code == 200
    what_a = next(s for s in resp_a.json()["stages"] if s["stage"] == "what")
    assert what_a["statusCode"] == "analysis_running"

    # 4. 检查 branch=feature/work-b 的 stage-progress：必须不受污染（非 analysis_running）
    resp_b = client.get(f"/api/projects/{pub_pid}/stage-progress?branch=feature/work-b")
    assert resp_b.status_code == 200
    what_b = next(s for s in resp_b.json()["stages"] if s["stage"] == "what")
    assert what_b["statusCode"] != "analysis_running"

    # 5. 检查 main 分支：必须不受污染
    resp_main = client.get(f"/api/projects/{pub_pid}/stage-progress?branch=main")
    assert resp_main.status_code == 200
    what_main = next(s for s in resp_main.json()["stages"] if s["stage"] == "what")
    assert what_main["statusCode"] != "analysis_running"


@pytest.mark.asyncio
async def test_user_requirements_empty_string_reading_and_main_protection(matrix_test_db):
    """
    验证 User Requirements：
    1. 直接写入受保护 main 返回 403
    2. 分支写入空字符串后，读取详情保持为空字符串 ""，不回退到项目全局值
    """
    client = TestClient(app)
    reg_payload = {"email": "req_matrix_user@example.com", "password": "password123"}
    res = client.post("/api/auth/register", json=reg_payload)
    user_id = int(res.json()["id"])
    client.post("/api/auth/login", json=reg_payload)

    # 1. 种子项目并迁移 VC
    async with matrix_test_db() as session:
        project = ProjectModel(
            name="Requirements Test Project",
            description="Testing reqs empty string",
            owner_user_id=user_id,
            user_requirements="Initial Global Requirement Text",
            unlocked_stages="what,how,scope,preview",
        )
        session.add(project)
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))
        await session.commit()
        pub_pid = project.public_id

    # 2. 尝试直接修改 main 分支的 user-requirements -> 403 Forbidden
    main_put_res = client.put(
        f"/api/projects/{pub_pid}/user-requirements?branch=main",
        json={"user_requirements": "Direct main modification attempt"},
    )
    assert main_put_res.status_code == 403

    # 3. 创建分支 feature/clean-req
    br_res = client.post(f"/api/projects/{pub_pid}/branches", json={"name": "feature/clean-req"})
    assert br_res.status_code == 201

    # 4. 在分支上清空需求文本（设为空字符串 ""）
    branch_put_res = client.put(
        f"/api/projects/{pub_pid}/user-requirements?branch=feature/clean-req",
        json={"user_requirements": ""},
    )
    assert branch_put_res.status_code == 200
    assert branch_put_res.json()["userRequirements"] == ""

    # 5. 获取分支项目详情，验证 user_requirements 依然是 ""，没有回退到 Initial Global Requirement Text
    detail_res = client.get(f"/api/projects/{pub_pid}?branch=feature/clean-req")
    assert detail_res.status_code == 200
    assert detail_res.json()["userRequirements"] == ""


@pytest.mark.asyncio
async def test_invalid_branch_routes_unified_404(matrix_test_db):
    """
    验证在各个模块的 API 路由上传入非法/不存在的 branch，统一返回 404 Not Found。
    """
    client = TestClient(app)
    reg_payload = {"email": "branch_404_user@example.com", "password": "password123"}
    res = client.post("/api/auth/register", json=reg_payload)
    user_id = int(res.json()["id"])
    client.post("/api/auth/login", json=reg_payload)

    # 1. 种子项目并迁移 VC
    async with matrix_test_db() as session:
        project = ProjectModel(
            name="404 Branch Test Project",
            description="Testing 404 branches",
            owner_user_id=user_id,
        )
        session.add(project)
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))
        await session.commit()
        pub_pid = project.public_id

    non_existent_branch = "feature/non-existent-branch-xyz"

    # 1. Findings 路由
    res_findings = client.get(f"/api/projects/{pub_pid}/findings?branch={non_existent_branch}")
    assert res_findings.status_code == 404

    # 2. Issue Repair 路由 (confirm)
    res_repair = client.post(f"/api/projects/{pub_pid}/issue_repair_drafts/draft_123/confirm?branch={non_existent_branch}")
    assert res_repair.status_code == 404

    # 3. Issue Resolve 路由
    res_resolve = client.post(
        f"/api/projects/{pub_pid}/issue_repairs/resolve?branch={non_existent_branch}",
        json={"issue_id": "issue_1", "issue_code": "EMPTY_ACTORS", "stage": "what"},
    )
    assert res_resolve.status_code == 404

    # 4. Requirements 路由
    res_reqs = client.put(
        f"/api/projects/{pub_pid}/user-requirements?branch={non_existent_branch}",
        json={"user_requirements": "Test"},
    )
    assert res_reqs.status_code == 404

    # 5. Commits 路由
    res_commits = client.get(f"/api/projects/{pub_pid}/commits?branch={non_existent_branch}")
    assert res_commits.status_code == 404

    # 6. AI Add 路由
    res_ai_add = client.post(
        f"/api/ai_add/sessions/init?branch={non_existent_branch}",
        json={"project_id": pub_pid},
    )
    assert res_ai_add.status_code == 404

    # 7. Perception Slot Filling 路由
    res_perception = client.post(
        f"/api/perception_slot_filling_drafts/actor?branch={non_existent_branch}",
        json={"project_id": pub_pid, "perception_job_id": 999},
    )
    assert res_perception.status_code == 404

    # 8. Perception Slot Delete 路由
    res_slot_delete = client.delete(f"/api/projects/{pub_pid}/perception-slot?branch={non_existent_branch}")
    assert res_slot_delete.status_code == 404


@pytest.mark.asyncio
async def test_cross_branch_perception_draft_creation_rejected(matrix_test_db):
    """
    负向测试：禁止使用分支 B 的 perception_job_id 在分支 A 创建草稿或预览。
    """
    client = TestClient(app)
    reg_payload = {"email": "cross_draft_user@example.com", "password": "password123"}
    res = client.post("/api/auth/register", json=reg_payload)
    user_id = int(res.json()["id"])
    client.post("/api/auth/login", json=reg_payload)

    async with matrix_test_db() as session:
        project = ProjectModel(
            name="Cross Draft Test Project",
            description="Testing cross draft rejection",
            owner_user_id=user_id,
            user_requirements="Project Requirements",
        )
        from backend.core.security.encryption import encrypt_llm_api_key
        llm_cfg = UserLLMConfigModel(
            user_id=user_id,
            api_url="http://localhost:8000",
            encrypted_api_key=encrypt_llm_api_key("sk-testkey1234567890"),
            api_key_last4="7890",
            model_name="gpt-4o",
        )
        session.add_all([project, llm_cfg])
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))

        await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/alpha", source_branch_public_id="main"))
        )
        br_b = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/beta", source_branch_public_id="main"))
        )
        _, ws_b, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_b.public_id))

        # 在 Branch B 上创建一个 DONE_WITH_SLOT 的 Job
        job_b = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_b.id,
            stage="what",
            perception_kind="ACTOR",
            status="done_with_slot",
            target_type="project",
            target_id="",
            context_hash="ctx_hash_b",
            result_slot_payload={
                "perception_slot_id": 1,
                "perception_kind": "ACTOR",
                "perception_kind_code": "ACTOR",
                "perception_description": "Actor Slot on Branch B",
            },
        )
        session.add(job_b)
        await session.commit()
        job_b_id = job_b.id
        pub_pid = project.public_id

    # 尝试在 Branch A 上使用 job_b_id 创建草稿 -> 必须被 404 拒绝 (perception_job_not_found)
    create_res = client.post(
        "/api/perception_slot_filling_drafts/actor?branch=feature/alpha",
        json={"project_id": pub_pid, "perception_job_id": job_b_id},
    )
    assert create_res.status_code == 404
    assert create_res.json()["detail"] == "perception_job_not_found"


@pytest.mark.asyncio
async def test_cross_branch_draft_confirmation_invalidation_isolation(matrix_test_db):
    """
    验证分支 A 确认 Perception/Issue Repair 草稿时，仅失效分支 A 的 Job，分支 B 的 Job 状态完全不受影响。
    """
    from backend.api.modules.diagnosis_quality.perception.application.invalidation import (
        mark_perception_jobs_stale,
    )
    from backend.database.model import PerceptionSlotModel

    async with matrix_test_db() as session:
        user = UserModel(email="confirmer_iso_user@example.com", password_hash="pw")
        session.add(user)
        await session.flush()

        project = ProjectModel(
            name="Confirmer Isolation Project",
            owner_user_id=user.id,
            user_requirements="Initial Requirements",
        )
        session.add(project)
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))

        br_a = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/alpha", source_branch_public_id="main"))
        )
        br_b = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/beta", source_branch_public_id="main"))
        )
        _, ws_a, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_a.public_id))
        _, ws_b, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_b.public_id))

        # 在 ws_a 与 ws_b 上分别创建 DONE_WITH_SLOT 的 Job 和 PerceptionSlot
        job_a = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_a.id,
            stage="what",
            perception_kind="ACTOR",
            status="done_with_slot",
            target_type="project",
            target_id="",
            context_hash="hash_a",
        )
        job_b = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_b.id,
            stage="what",
            perception_kind="ACTOR",
            status="done_with_slot",
            target_type="project",
            target_id="",
            context_hash="hash_b",
        )
        session.add_all([job_a, job_b])
        await session.flush()

        slot_a = PerceptionSlotModel(
            id=job_a.id,
            project_id=project.id,
            workspace_id=ws_a.id,
            perception_kind="ACTOR",
            description="Slot A",
        )
        slot_b = PerceptionSlotModel(
            id=job_b.id,
            project_id=project.id,
            workspace_id=ws_b.id,
            perception_kind="ACTOR",
            description="Slot B",
        )
        session.add_all([slot_a, slot_b])
        await session.commit()

        # 在 ws_a 上触发失效
        await mark_perception_jobs_stale(
            project_id=project.id,
            stages={"what"},
            perception_kinds={"ACTOR"},
            session=session,
            workspace_id=ws_a.id,
        )
        await session.commit()

        # 验证: ws_a 上的 job_a 变为 stale，slot_a 被清除
        refreshed_job_a = await session.get(PerceptionJobModel, job_a.id)
        refreshed_job_b = await session.get(PerceptionJobModel, job_b.id)
        refreshed_slot_a = await session.get(PerceptionSlotModel, job_a.id)
        refreshed_slot_b = await session.get(PerceptionSlotModel, job_b.id)

        assert refreshed_job_a.status == "stale"
        assert refreshed_slot_a is None

        # 验证: ws_b 上的 job_b 和 slot_b 保持不变！
        assert refreshed_job_b.status == "done_with_slot"
        assert refreshed_slot_b is not None
        assert refreshed_slot_b.description == "Slot B"


@pytest.mark.asyncio
async def test_perception_slot_workspace_isolation(matrix_test_db):
    """
    验证 PerceptionSlotModel 完全工作区化：
    1. 分支 A 和 分支 B 可同时拥有各自的 Slot
    2. 删除分支 A 的 Slot 不影响分支 B
    3. Project Detail 接口按分支正确返回对应工作区的 Slot
    """
    client = TestClient(app)
    reg_payload = {"email": "slot_iso_user@example.com", "password": "password123"}
    res = client.post("/api/auth/register", json=reg_payload)
    user_id = int(res.json()["id"])
    client.post("/api/auth/login", json=reg_payload)

    async with matrix_test_db() as session:
        from backend.database.model import PerceptionSlotModel
        project = ProjectModel(
            name="Slot Isolation Project",
            owner_user_id=user_id,
            user_requirements="Initial Requirements",
            unlocked_stages="what,how,scope,preview",
        )
        session.add(project)
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))

        br_a = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/alpha", source_branch_public_id="main"))
        )
        br_b = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/beta", source_branch_public_id="main"))
        )
        _, ws_a, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_a.public_id))
        _, ws_b, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_b.public_id))

        job_a = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_a.id,
            stage="what",
            perception_kind="ACTOR",
            status="done_with_slot",
            target_type="project",
            target_id="",
            context_hash="hash_a",
        )
        job_b = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_b.id,
            stage="what",
            perception_kind="FEATURE",
            status="done_with_slot",
            target_type="project",
            target_id="",
            context_hash="hash_b",
        )
        session.add_all([job_a, job_b])
        await session.flush()

        slot_a = PerceptionSlotModel(
            id=job_a.id,
            project_id=project.id,
            workspace_id=ws_a.id,
            perception_kind="ACTOR",
            description="Missing Actor: Admin",
        )
        slot_b = PerceptionSlotModel(
            id=job_b.id,
            project_id=project.id,
            workspace_id=ws_b.id,
            perception_kind="FEATURE",
            description="Missing Feature: Export",
        )
        session.add_all([slot_a, slot_b])
        await session.commit()
        pub_pid = project.public_id

    # 1. 检查 Branch A 的 project detail：返回 Actor Slot
    det_a = client.get(f"/api/projects/{pub_pid}?branch=feature/alpha")
    assert det_a.status_code == 200
    assert det_a.json()["perceptionSlot"]["perceptionKind"] == "ACTOR"
    assert det_a.json()["perceptionSlot"]["perceptionDescription"] == "Missing Actor: Admin"

    # 2. 检查 Branch B 的 project detail：返回 Feature Slot
    det_b = client.get(f"/api/projects/{pub_pid}?branch=feature/beta")
    assert det_b.status_code == 200
    assert det_b.json()["perceptionSlot"]["perceptionKind"] == "FEATURE"
    assert det_b.json()["perceptionSlot"]["perceptionDescription"] == "Missing Feature: Export"

    # 3. 删除 Branch A 的 Slot
    del_res = client.delete(f"/api/projects/{pub_pid}/perception-slot?branch=feature/alpha")
    assert del_res.status_code == 200

    # 4. 再次获取 Branch A：perceptionSlot 为 None
    det_a_after = client.get(f"/api/projects/{pub_pid}?branch=feature/alpha")
    assert det_a_after.status_code == 200
    assert det_a_after.json()["perceptionSlot"] is None

    # 5. 再次获取 Branch B：perceptionSlot 依然完好！
    det_b_after = client.get(f"/api/projects/{pub_pid}?branch=feature/beta")
    assert det_b_after.status_code == 200
    assert det_b_after.json()["perceptionSlot"]["perceptionKind"] == "FEATURE"
    assert det_b_after.json()["perceptionSlot"]["perceptionDescription"] == "Missing Feature: Export"


@pytest.mark.asyncio
async def test_legacy_null_workspace_unique_constraint(matrix_test_db):
    """
    验证部分唯一索引对 legacy workspace_id=NULL 的数据依然严格排重。
    """
    from sqlalchemy.exc import IntegrityError

    async with matrix_test_db() as session:
        user = UserModel(email="null_uniq_user@example.com", password_hash="pw")
        session.add(user)
        await session.flush()

        project = ProjectModel(
            name="NULL Unique Project",
            owner_user_id=user.id,
            user_requirements="Requirements",
        )
        session.add(project)
        await session.flush()

        # 插入第一个 legacy NULL workspace_id job
        job_1 = PerceptionJobModel(
            project_id=project.id,
            workspace_id=None,
            stage="what",
            perception_kind="ACTOR",
            status="done_empty",
            target_type="project",
            target_id="",
            context_hash="same_context_hash",
        )
        session.add(job_1)
        await session.commit()

        # 插入第二个完全相同上下文的 legacy NULL workspace_id job -> 必须触发 IntegrityError
        job_2 = PerceptionJobModel(
            project_id=project.id,
            workspace_id=None,
            stage="what",
            perception_kind="ACTOR",
            status="done_empty",
            target_type="project",
            target_id="",
            context_hash="same_context_hash",
        )
        session.add(job_2)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_job_executor_loads_only_branch_context(matrix_test_db, monkeypatch):
    """
    验证后台 Perception Job 执行时仅加载所属分支工作区的实体数据，绝不跨分支聚合。
    """
    from backend.api.modules.diagnosis_quality.perception.application.job_executor import (
        PerceptionJobExecutor,
    )
    from backend.core.detectors.issue_context_loader import load_issue_project_context

    captured_contexts = []

    async with matrix_test_db() as session:
        user = UserModel(email="executor_iso@example.com", password_hash="pw")
        session.add(user)
        await session.flush()

        project = ProjectModel(
            name="Executor Isolation Proj",
            owner_user_id=user.id,
            user_requirements="Reqs",
            unlocked_stages="what,how,scope",
        )
        session.add(project)
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))

        br_a = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/exec-a", source_branch_public_id="main"))
        )
        br_b = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/exec-b", source_branch_public_id="main"))
        )
        _, ws_a, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_a.public_id))
        _, ws_b, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_b.public_id))

        # 为 Branch A 插入专用 Actor A
        actor_a = ActorModel(project_id=project.id, workspace_id=ws_a.id, name="Admin Alpha")
        session.add(actor_a)

        # 为 Branch B 插入专用 Actor B
        actor_b = ActorModel(project_id=project.id, workspace_id=ws_b.id, name="Customer Beta")
        session.add(actor_b)

        executor = PerceptionJobExecutor()
        ctx_a = await load_issue_project_context(project_id=project.id, session=session, workspace_id=ws_a.id)
        ctx_b = await load_issue_project_context(project_id=project.id, session=session, workspace_id=ws_b.id)
        hash_a = executor._build_context_hash("ACTOR", "", ctx_a)
        hash_b = executor._build_context_hash("ACTOR", "", ctx_b)

        job_a = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_a.id,
            stage="what",
            perception_kind="ACTOR",
            status="pending",
            target_type="project",
            target_id="",
            context_hash=hash_a,
        )
        job_b = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_b.id,
            stage="what",
            perception_kind="ACTOR",
            status="pending",
            target_type="project",
            target_id="",
            context_hash=hash_b,
        )
        session.add_all([job_a, job_b])
        await session.commit()
        job_a_id = job_a.id
        job_b_id = job_b.id

    executor = PerceptionJobExecutor()
    monkeypatch.setattr("backend.api.modules.diagnosis_quality.perception.application.job_executor.AsyncSessionLocal", matrix_test_db)

    # Intercept perceptron execution to capture the IssueProjectContext loaded
    async def mock_run_perceptron(perception_kind, target_id, context):
        captured_contexts.append(context)
        return {"perception_description": "Found gap"}

    monkeypatch.setattr(PerceptionJobExecutor, "_run_perceptron", staticmethod(mock_run_perceptron))

    # 1. 执行 Branch A 的 Job
    await executor.run_perception_job(job_a_id)
    assert len(captured_contexts) == 1
    ctx_a = captured_contexts[0]
    actor_names_a = [a.name for a in ctx_a.actors]
    assert "Admin Alpha" in actor_names_a
    assert "Customer Beta" not in actor_names_a, "Branch A job must NOT see Branch B actor!"

    # 2. 执行 Branch B 的 Job
    await executor.run_perception_job(job_b_id)
    assert len(captured_contexts) == 2
    ctx_b = captured_contexts[1]
    actor_names_b = [a.name for a in ctx_b.actors]
    assert "Customer Beta" in actor_names_b
    assert "Admin Alpha" not in actor_names_b, "Branch B job must NOT see Branch A actor!"


@pytest.mark.asyncio
async def test_requirements_write_service_invalidates_only_target_branch(matrix_test_db):
    """
    验证通用需求写入（如 ActorService.update_actor）仅失效当前分支的 Job/Slot，另一分支完全保持不变。
    """
    from backend.api.modules.requirements_core.actor.application.actor_service import (
        ActorService,
    )
    from backend.api.modules.requirements_core.actor.schemas import ActorUpdateRequest

    async with matrix_test_db() as session:
        user = UserModel(email="write_inval@example.com", password_hash="pw")
        session.add(user)
        await session.flush()

        project = ProjectModel(
            name="Write Invalidation Proj",
            owner_user_id=user.id,
            user_requirements="Reqs",
            unlocked_stages="what,how,scope",
        )
        session.add(project)
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))

        br_a = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/inval-a", source_branch_public_id="main"))
        )
        br_b = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/inval-b", source_branch_public_id="main"))
        )
        _, ws_a, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_a.public_id))
        _, ws_b, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_b.public_id))

        actor_a = ActorModel(project_id=project.id, workspace_id=ws_a.id, name="Buyer A", description="")
        actor_b = ActorModel(project_id=project.id, workspace_id=ws_b.id, name="Buyer B", description="")
        session.add_all([actor_a, actor_b])
        await session.flush()

        job_a = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_a.id,
            stage="what",
            perception_kind="ACTOR",
            status="done_with_slot",
            target_type="project",
            target_id="",
            context_hash="hash_a",
        )
        job_b = PerceptionJobModel(
            project_id=project.id,
            workspace_id=ws_b.id,
            stage="what",
            perception_kind="ACTOR",
            status="done_with_slot",
            target_type="project",
            target_id="",
            context_hash="hash_b",
        )
        session.add_all([job_a, job_b])
        await session.flush()

        slot_a = PerceptionSlotModel(
            id=job_a.id,
            project_id=project.id,
            workspace_id=ws_a.id,
            perception_kind="ACTOR",
            description="Slot A",
        )
        slot_b = PerceptionSlotModel(
            id=job_b.id,
            project_id=project.id,
            workspace_id=ws_b.id,
            perception_kind="ACTOR",
            description="Slot B",
        )
        session.add_all([slot_a, slot_b])
        await session.commit()

        actor_a_id = actor_a.id
        job_a_id = job_a.id
        job_b_id = job_b.id

    # 在 Branch A 上通过 ActorService 修改实体
    async with matrix_test_db() as session:
        actor_service = ActorService()
        await actor_service.update_actor(
            project_id=project.id,
            actor_id=actor_a_id,
            req=ActorUpdateRequest(name="Buyer A Renamed"),
            session=session,
            workspace_id=ws_a.id,
        )
        await session.commit()

    # 验证 Branch A 的 Job 变为 stale、Slot 被删除；Branch B 的 Job 与 Slot 100% 保持完好！
    async with matrix_test_db() as session:
        res_job_a = await session.get(PerceptionJobModel, job_a_id)
        res_slot_a = await session.execute(
            select(PerceptionSlotModel).where(PerceptionSlotModel.workspace_id == ws_a.id)
        )
        assert res_job_a.status == "stale", "Branch A job must be marked stale after actor update on Branch A"
        assert res_slot_a.scalar_one_or_none() is None, "Branch A slot must be cleared"

        res_job_b = await session.get(PerceptionJobModel, job_b_id)
        res_slot_b = await session.execute(
            select(PerceptionSlotModel).where(PerceptionSlotModel.workspace_id == ws_b.id)
        )
        assert res_job_b.status == "done_with_slot", "Branch B job must remain completely untouched"
        slot_b_obj = res_slot_b.scalar_one_or_none()
        assert slot_b_obj is not None and slot_b_obj.description == "Slot B", "Branch B slot must remain completely untouched"


@pytest.mark.asyncio
async def test_next_suggestion_branch_isolation_and_guards(matrix_test_db):
    """
    验证 NextSuggestion 端点的分支隔离、未知分支 404 及受保护分支写入拦截 403。
    """
    client = TestClient(app)

    async with matrix_test_db() as session:
        user = UserModel(email="ns_guard_user@example.com", password_hash="pw")
        session.add(user)
        await session.flush()

        from backend.core.security.encryption import encrypt_llm_api_key

        llm_cfg = UserLLMConfigModel(
            user_id=user.id,
            api_url="https://api.openai.com/v1",
            encrypted_api_key=encrypt_llm_api_key("sk-fake-1234"),
            api_key_last4="1234",
            model_name="gpt-4o",
        )
        session.add(llm_cfg)

        project = ProjectModel(
            name="NS Guard Proj",
            owner_user_id=user.id,
            user_requirements="Reqs",
            unlocked_stages="what",
        )
        session.add(project)
        await session.flush()
        await session.run_sync(lambda s: initialize_project_version_control(s, project))

        br_a = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/ns-a", source_branch_public_id="main"))
        )
        br_b = await session.run_sync(
            lambda s: create_branch(s, project.id, BranchCreateRequest(name="feature/ns-b", source_branch_public_id="main"))
        )
        _, ws_a, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_a.public_id))
        _, ws_b, _ = await session.run_sync(lambda s: resolve_branch_context(s, project.id, br_b.public_id))

        # Branch A 仅解锁 what（此时 scope 阶段处于锁定状态）；Branch B 解锁 what,how（此时 scope 阶段已解锁）
        ws_a.unlocked_stages = "what"
        ws_b.unlocked_stages = "what,how"
        await session.commit()
        pub_pid, user_id = project.public_id, user.id

    from backend.api.dependencies.auth import get_current_user
    async def override_user():
        async with matrix_test_db() as s:
            return await s.get(UserModel, user_id)
    app.dependency_overrides[get_current_user] = override_user

    try:
        # 1. 访问 Branch A 的 Scope 阶段建议 -> 阶段未解锁 STAGE_LOCKED
        res_a = client.get(f"/api/projects/{pub_pid}/next-suggestion?stage=scope&branch=feature/ns-a")
        assert res_a.status_code == 200, f"res_a failed: {res_a.status_code} {res_a.text}"
        assert res_a.json()["suggestion"]["code"] == "STAGE_LOCKED"

        # 2. 访问 Branch B 的 Scope 阶段建议 -> 阶段已解锁，正常返回生成用例范围建议
        res_b = client.get(f"/api/projects/{pub_pid}/next-suggestion?stage=scope&branch=feature/ns-b")
        assert res_b.status_code == 200
        assert res_b.json()["suggestion"]["code"] != "STAGE_LOCKED"

        # 3. 访问未知分支 -> 404 Not Found (branch_not_found)
        res_404 = client.get(f"/api/projects/{pub_pid}/next-suggestion?stage=what&branch=nonexistent-branch")
        assert res_404.status_code == 404
        assert "not found" in res_404.json()["detail"].lower()

        # 4. 在受保护的 main 分支执行 rediagnose -> 403 Forbidden (branch_readonly_or_protected)
        res_403 = client.post(f"/api/projects/{pub_pid}/next-suggestion/rediagnose?branch=main", json={"stage": "what"})
        assert res_403.status_code == 403
        assert res_403.json()["detail"] == "branch_readonly_or_protected"

        # 5. 在可写的 feature/ns-a 分支执行 rediagnose -> 200 Success
        res_redia = client.post(f"/api/projects/{pub_pid}/next-suggestion/rediagnose?branch=feature/ns-a", json={"stage": "what"})
        assert res_redia.status_code == 200

    finally:
        app.dependency_overrides.pop(get_current_user, None)
