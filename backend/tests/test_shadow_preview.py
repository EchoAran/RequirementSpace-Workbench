"""
Integration tests for PreviewShadowConvergenceService.
Tests cover manual trigger, gate readiness check, incremental AI generation mocking,
and safe transactional commit (write-back) to sqlite database without duplicate entries.
"""

import os
import sys

os.environ["REQUIREMENTSPACE_GENERATION_BACKEND"] = "legacy"
for mod in ["backend.api.bootstrap", "backend.api.modules.preview_convergence.application.shadow_convergence"]:
    if mod in sys.modules:
        del sys.modules[mod]

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.model import (
    Base,
    ProjectModel,
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    FlowModel,
    FlowStepModel,
    ScopeModel,
    PreviewShadowDraftModel,
    feature_actor_table,
)
from backend.api.modules.preview_convergence.application.shadow_convergence import (
    PreviewShadowConvergenceService,
)
from backend.api.modules.preview_convergence.application.shadow_project_creator import (
    build_project_snapshot,
    calculate_stable_snapshot_hash,
)

# ---------------------------------------------------------------------------
# Fixtures - async in-memory SQLite database
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def seeded_project(db_session) -> int:
    """Create a seed project and return its ID."""
    project = ProjectModel(
        name="影子测试项目",
        description="用于测试影子收敛与写回的项目",
        user_requirements="需要有用户管理和权限审核功能流程。",
        kano_status="pending",
    )
    db_session.add(project)
    await db_session.flush()
    return project.id


# ---------------------------------------------------------------------------
# Integration and Merge (Commit) Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_empty_project_shadow_workflow(db_session, seeded_project):
    """
    Test starting with a blank project (What, How, Scope all unconverged).
    We trigger manual shadow preview preparation, check generating state,
    mock the AI generators to return complete sandbox assets, run convergence,
    apply patch, and transactionally commit.
    """
    service = PreviewShadowConvergenceService()

    # Step 1: Verify all gates are False initially
    gates = await service.gate_evaluator.evaluate_gates(seeded_project, db_session)
    assert gates["what"] is False
    assert gates["how"] is False
    assert gates["scope"] is False

    # Step 2: Build base snapshot
    base_snap = await build_project_snapshot(seeded_project, db_session)
    assert len(base_snap["actors"]) == 0
    assert len(base_snap["features"]) == 0

    # Step 3: Run _generate_shadow_patch with mocked generators
    mock_actors_ret = {"actors": [{"actor_name": "管理员", "actor_description": "系统管理员"}]}
    mock_features_ret = {
        "features": [
            {
                "feature_number": "F1",
                "feature_name": "用户管理",
                "feature_description": "管理用户列表与角色配置",
                "actor_ids": ["1"],
            }
        ]
    }
    mock_scenarios_ret = {
        "scenarios": [
            {
                "scenario_name": "查询用户",
                "scenario_content": "Given 管理员已登录, When 查询用户列表, Then 展现所有注册用户",
            }
        ]
    }
    mock_ac_ret = {
        "acceptance_criteria": [{"criterion_content": "列表加载不超过500ms", "position": 1}]
    }
    mock_flows_ret = {
        "flows": [
            {
                "flow_name": "新建用户流程",
                "flow_description": "创建新用户的业务主流程",
                "feature_ids": ["tmp_feature_F1"],
                "flow_steps": [
                    {
                        "step_number": "S-001",
                        "step_name": "填写信息",
                        "step_description": "输入用户名和密码",
                        "step_type": "USER_ACTION",
                        "actor_ids": ["tmp_actor_1"],
                        "input_business_object_numbers": [],
                        "output_business_object_numbers": ["B-001"],
                        "next_steps": ["S-002"],
                    },
                    {
                        "step_number": "S-002",
                        "step_name": "提交保存",
                        "step_description": "系统保存账号",
                        "step_type": "SYSTEM_ACTION",
                        "actor_ids": [],
                        "input_business_object_numbers": ["B-001"],
                        "output_business_object_numbers": [],
                        "next_steps": [],
                    },
                ],
            }
        ],
        "business_objects": [
            {
                "business_object_number": "B-001",
                "business_object_name": "用户信息载体",
                "business_object_description": "用户信息表单数据",
                "business_object_attributes": [
                    {
                        "business_object_attribute_name": "用户名",
                        "business_object_attribute_description": "注册的用户名",
                        "business_object_attribute_type": "string",
                        "business_object_attribute_example": "alice",
                    }
                ],
            }
        ],
    }
    mock_scopes_ret = {
        "scopes": [
            {
                "feature_id": "tmp_feature_F1",
                "scope_status": "current",
                "reason": "核心基线需求",
                "kano_category": "M",
                "kano_category_name": "Must-be",
                "positive_summary": "已支持",
                "negative_summary": "不满足",
                "positive_picture_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "negative_picture_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            }
        ]
    }

    # Patch the AI generators called by _generate_shadow_patch
    with patch("backend.core.generators.actors_generator.ActorsGenerator.generate", new_callable=AsyncMock) as m_actors, \
         patch("backend.core.generators.features_generator.FeaturesGenerator.generate", new_callable=AsyncMock) as m_features, \
         patch("backend.core.generators.scenarios_generator.ScenariosGenerator.generate", new_callable=AsyncMock) as m_scenarios, \
         patch("backend.core.generators.acceptance_criteria_generator.AcceptanceCriteriaGenerator.generate", new_callable=AsyncMock) as m_ac, \
         patch("backend.core.generators.flows_generator.FlowsGenerator.generate", new_callable=AsyncMock) as m_flows, \
         patch("backend.core.generators.scopes_generator.ScopesGenerator.generate", new_callable=AsyncMock) as m_scopes:

        m_actors.return_value = mock_actors_ret
        m_features.return_value = mock_features_ret
        m_scenarios.return_value = mock_scenarios_ret
        m_ac.return_value = mock_ac_ret
        m_flows.return_value = mock_flows_ret
        m_scopes.return_value = mock_scopes_ret

        # Perform generator orchestration
        patch_json = await service._generate_shadow_patch(seeded_project, base_snap, db_session)

        # Check generated patch contains all components
        assert len(patch_json["actors_added"]) == 1
        assert len(patch_json["features_added"]) == 1
        assert len(patch_json["scenarios_added"]) == 1
        assert len(patch_json["acceptance_criteria_added"]) == 1
        assert len(patch_json["flows_added"]) == 1
        assert len(patch_json["business_objects_added"]) == 1
        assert len(patch_json["scopes_added"]) == 1

        # Check that picture base64 data is correctly present in the patch
        assert patch_json["scopes_added"][0]["positive_picture_base64"] == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        assert patch_json["scopes_added"][0]["negative_picture_base64"] == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # Check temporary mapping details
        assert patch_json["actors_added"][0]["temp_id"] == "tmp_actor_1"
        assert patch_json["features_added"][0]["temp_id"] == "tmp_feature_F1"

        # Apply patch to build sandboxed snapshot
        shadow_snap, temp_id_map = service._apply_patch_to_snapshot(base_snap, patch_json)

        # Verify negative IDs mapped successfully to differentiate from existing DB IDs
        assert temp_id_map["tmp_actor_1"] < 0
        assert temp_id_map["tmp_feature_F1"] < 0

        # Check that picture base64 data is correctly preserved in the sandbox shadow snapshot
        feat_scope = shadow_snap["features"][0]["scope"]
        assert feat_scope["positive_picture_base64"] == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        assert feat_scope["negative_picture_base64"] == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # Verify Kano status forced to generated in shadow snapshot
        assert shadow_snap["kano_status"] == "generated"

        # Save this to PreviewShadowDraftModel to mock background task completion
        draft_id = "test_draft_123"
        base_hash = calculate_stable_snapshot_hash(base_snap)
        draft = PreviewShadowDraftModel(
            project_id=seeded_project,
            draft_id=draft_id,
            status="ready",
            source="shadow_project",
            base_snapshot_hash=base_hash,
            base_snapshot_json=base_snap,
            patch_json=patch_json,
            shadow_snapshot_json=shadow_snap,
            prototype_preview_json={"prototypeId": 1, "html": "test", "pages": []},
        )
        db_session.add(draft)
        await db_session.flush()

        # Step 4: Verify transaction merge/write-back (Commit)
        # Mock prototype_generation_service preview generator called post-commit
        from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
        prototype_gen_service = get_prototype_generation_service()
        import asyncio
        with patch.object(prototype_gen_service, "generate_preview", new_callable=AsyncMock) as m_gen_prev:
            await service.commit_shadow_draft(seeded_project, draft_id, db_session)
            await asyncio.sleep(0.05)
            m_gen_prev.assert_called_once()

        # Step 5: Verify records successfully materialized in sqlite with positive DB auto-increment IDs
        db_actors = (await db_session.execute(select(ActorModel).where(ActorModel.project_id == seeded_project))).scalars().all()
        assert len(db_actors) == 1
        assert db_actors[0].name == "管理员"
        assert db_actors[0].id > 0

        db_features = (await db_session.execute(select(FeatureModel).where(FeatureModel.project_id == seeded_project))).scalars().all()
        assert len(db_features) == 1
        assert db_features[0].name == "用户管理"
        assert db_features[0].id > 0

        db_flows = (await db_session.execute(select(FlowModel).where(FlowModel.project_id == seeded_project))).scalars().all()
        assert len(db_flows) == 1
        assert db_flows[0].name == "新建用户流程"
        assert db_flows[0].id > 0

        db_scopes = (await db_session.execute(select(ScopeModel).join(FeatureModel).where(FeatureModel.project_id == seeded_project))).scalars().all()
        assert len(db_scopes) == 1
        assert db_scopes[0].status == "CURRENT"
        # Check that database records hold binary (bytes) representation of the picture
        assert db_scopes[0].positive_picture is not None
        assert db_scopes[0].negative_picture is not None

        # Verify build_project_snapshot serializes binary pictures back to base64
        new_base_snap = await build_project_snapshot(seeded_project, db_session)
        new_feat_scope = new_base_snap["features"][0]["scope"]
        assert new_feat_scope["positive_picture_base64"] == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        assert new_feat_scope["negative_picture_base64"] == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # Verify project kano_status updated to generated
        project = await db_session.get(ProjectModel, seeded_project)
        assert project.kano_status == "generated"


@pytest.mark.asyncio
async def test_semi_converged_project_preservation_workflow(db_session, seeded_project):
    """
    Test starting with a semi-converged project where What stage is already converged.
    We seed the project database with 1 actor and 1 leaf feature.
    Verify that AI shadow generator evaluates gates, respects preservation rule
    (does not generate actors or features), but incrementally pushes How & Scope.
    Finally, commit transaction and check no duplicate actors/features are created.
    """
    service = PreviewShadowConvergenceService()

    # Seed Database with converged What stage (1 Actor, 1 Feature)
    actor = ActorModel(project_id=seeded_project, name="已收敛用户", description="老系统固有角色")
    feature = FeatureModel(project_id=seeded_project, name="系统设置功能", description="主干稳定特性")
    db_session.add_all([actor, feature])
    await db_session.flush()

    # Crucial link to satisfy the What gate blocker checking (leaf feature must have associated actor)
    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=feature.id,
            actor_id=actor.id
        )
    )
    await db_session.flush()

    # Evaluate gates: What should pass, How & Scope should fail
    gates = await service.gate_evaluator.evaluate_gates(seeded_project, db_session)
    assert gates["what"] is True
    assert gates["how"] is False
    assert gates["scope"] is False

    # Snapshot check
    base_snap = await build_project_snapshot(seeded_project, db_session)
    assert len(base_snap["actors"]) == 1
    assert len(base_snap["features"]) == 1

    # Mock Flows and Scopes generation returns
    mock_flows_ret = {
        "flows": [
            {
                "flow_name": "修改设置流程",
                "flow_description": "修改系统参数",
                "feature_ids": [feature.id],
                "flow_steps": [
                    {
                        "step_number": "S-101",
                        "step_name": "提交表单",
                        "step_description": "点击保存设置",
                        "step_type": "USER_ACTION",
                        "actor_ids": [actor.id],
                        "input_business_object_numbers": [],
                        "output_business_object_numbers": [],
                        "next_steps": [],
                    }
                ],
            }
        ],
        "business_objects": [],
    }
    mock_scopes_ret = {
        "scopes": [
            {
                "feature_id": feature.id,
                "scope_status": "current",
                "reason": "用户管理固有功能",
                "kano_category": "M",
                "kano_category_name": "Must-be",
                "positive_summary": "已支持",
                "negative_summary": "不满足",
            }
        ]
    }

    # Patch generators, especially ensuring ActorsGenerator and FeaturesGenerator ARE NOT CALLED AT ALL!
    with patch("backend.core.generators.actors_generator.ActorsGenerator.generate", new_callable=AsyncMock) as m_actors, \
         patch("backend.core.generators.features_generator.FeaturesGenerator.generate", new_callable=AsyncMock) as m_features, \
         patch("backend.core.generators.flows_generator.FlowsGenerator.generate", new_callable=AsyncMock) as m_flows, \
         patch("backend.core.generators.scopes_generator.ScopesGenerator.generate", new_callable=AsyncMock) as m_scopes:

        # Stub flow and scope previews to return raw structure
        m_flows.return_value = mock_flows_ret
        m_scopes.return_value = mock_scopes_ret

        patch_json = await service._generate_shadow_patch(seeded_project, base_snap, db_session)

        # Assert PRESERVATION RULE: what generator not called, patch lists for actors/features are empty
        m_actors.assert_not_called()
        m_features.assert_not_called()
        assert len(patch_json["actors_added"]) == 0
        assert len(patch_json["features_added"]) == 0

        # Assert incremental How & Scope are generated
        assert len(patch_json["flows_added"]) == 1
        assert len(patch_json["scopes_added"]) == 1

        # Apply patch
        shadow_snap, temp_id_map = service._apply_patch_to_snapshot(base_snap, patch_json)

        # Verify draft saving
        draft_id = "test_draft_456"
        base_hash = calculate_stable_snapshot_hash(base_snap)
        draft = PreviewShadowDraftModel(
            project_id=seeded_project,
            draft_id=draft_id,
            status="ready",
            source="shadow_project",
            base_snapshot_hash=base_hash,
            base_snapshot_json=base_snap,
            patch_json=patch_json,
            shadow_snapshot_json=shadow_snap,
            prototype_preview_json={"prototypeId": 2, "html": "test2", "pages": []},
        )
        db_session.add(draft)
        await db_session.flush()

        # Step 4: Verify transaction merge/write-back (Commit)
        from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
        prototype_gen_service = get_prototype_generation_service()
        import asyncio
        with patch.object(prototype_gen_service, "generate_preview", new_callable=AsyncMock) as m_gen_prev:
            await service.commit_shadow_draft(seeded_project, draft_id, db_session)
            await asyncio.sleep(0.05)
            m_gen_prev.assert_called_once()

        # Check DB State: Original Actor and Feature must exist exactly once (no duplicates created!)
        db_actors = (await db_session.execute(select(ActorModel).where(ActorModel.project_id == seeded_project))).scalars().all()
        assert len(db_actors) == 1
        assert db_actors[0].name == "已收敛用户"
        assert db_actors[0].id == actor.id  # Same exact database entity!

        db_features = (await db_session.execute(select(FeatureModel).where(FeatureModel.project_id == seeded_project))).scalars().all()
        assert len(db_features) == 1
        assert db_features[0].name == "系统设置功能"
        assert db_features[0].id == feature.id  # Same exact database entity!

        # Check new Flow has been appended
        db_flows = (await db_session.execute(select(FlowModel).where(FlowModel.project_id == seeded_project))).scalars().all()
        assert len(db_flows) == 1
        assert db_flows[0].name == "修改设置流程"
        assert db_flows[0].id > 0

        # Check Scope Kano status appended
        db_scopes = (await db_session.execute(select(ScopeModel).join(FeatureModel).where(FeatureModel.project_id == seeded_project))).scalars().all()
        assert len(db_scopes) == 1
        assert db_scopes[0].feature_id == feature.id
        assert db_scopes[0].status == "CURRENT"


@pytest.mark.asyncio
async def test_empty_project_shadow_numeric_mapping(db_session, seeded_project):
    """
    Test empty project shadow preview generation where AI generators return raw numeric IDs
    or integer references (like 7878 or 1) rather than string references (like 'tmp_feature_F1').
    Ensures our robust mapping translates these to proper temporary references (like 'tmp_feature_7878')
    to prevent validator membership failures.
    Additionally tests hierarchical parent relation resolution (parent_ref & parentId) for generated features.
    """
    service = PreviewShadowConvergenceService()

    # Step 1: Verify all gates are False initially
    gates = await service.gate_evaluator.evaluate_gates(seeded_project, db_session)
    assert gates["what"] is False

    # Step 2: Build base snapshot
    base_snap = await build_project_snapshot(seeded_project, db_session)

    # Step 3: Mock LLM output returning integer/numeric references and hierarchical feature numbers
    mock_actors_ret = {"actors": [{"actor_name": "管理员", "actor_description": "系统管理员"}]}
    mock_features_ret = {
        "features": [
            {
                "feature_number": "7878",  # Numeric string (root)
                "feature_name": "用户管理",
                "feature_description": "管理用户列表与角色配置",
                "actor_ids": [1],
            },
            {
                "feature_number": "7878-001",  # Hierarchical child feature
                "feature_name": "添加用户",
                "feature_description": "添加新系统用户",
                "actor_ids": [1],
            }
        ]
    }
    mock_scenarios_ret = {
        "scenarios": [
            {
                "scenario_name": "查询用户",
                "scenario_content": "Given 管理员已登录, When 查询用户列表, Then 展现所有注册用户",
            }
        ]
    }
    mock_ac_ret = {
        "acceptance_criteria": [{"criterion_content": "列表加载不超过500ms", "position": 1}]
    }
    mock_flows_ret = {
        "flows": [
            {
                "flow_name": "新建用户流程",
                "flow_description": "创建新用户的业务主流程",
                "feature_ids": ["7878-001"],  # Reference child feature
                "flow_steps": [
                    {
                        "step_number": "1",
                        "step_name": "填写信息",
                        "step_description": "输入用户名和密码",
                        "step_type": "USER_ACTION",
                        "actor_ids": [1],  # Integer ID instead of string 'tmp_actor_1'
                        "input_business_object_numbers": [],
                        "output_business_object_numbers": [1],  # Integer ID
                        "next_steps": ["2"],
                    },
                    {
                        "step_number": "2",
                        "step_name": "提交保存",
                        "step_description": "系统保存账号",
                        "step_type": "SYSTEM_ACTION",
                        "actor_ids": [],
                        "input_business_object_numbers": [1],  # Integer ID
                        "output_business_object_numbers": [],
                        "next_steps": [],
                    },
                ],
            }
        ],
        "business_objects": [
            {
                "business_object_number": 1,  # Integer ID
                "business_object_name": "用户信息载体",
                "business_object_description": "用户信息表单 data",
                "business_object_attributes": [
                    {
                        "business_object_attribute_name": "用户名",
                        "business_object_attribute_description": "注册的用户名",
                        "business_object_attribute_type": "string",
                        "business_object_attribute_example": "alice",
                    }
                ],
            }
        ],
    }

    # Mock to_current_scopes to simulate Kano analyzer output mapping to child feature
    mock_scopes_ret = [
        {
            "feature_id": "7878-001",  # Scope only for leaf feature
            "scope_status": "current",
            "reason": "核心基线需求",
            "kano_category": "M",
            "kano_category_name": "Must-be",
            "positive_summary": "已支持",
            "negative_summary": "不满足",
            "positive_picture_base64": "img1",
            "negative_picture_base64": "img2",
        }
    ]

    with patch("backend.core.generators.actors_generator.ActorsGenerator.generate", new_callable=AsyncMock) as m_actors, \
         patch("backend.core.generators.features_generator.FeaturesGenerator.generate", new_callable=AsyncMock) as m_features, \
         patch("backend.core.generators.scenarios_generator.ScenariosGenerator.generate", new_callable=AsyncMock) as m_scenarios, \
         patch("backend.core.generators.acceptance_criteria_generator.AcceptanceCriteriaGenerator.generate", new_callable=AsyncMock) as m_ac, \
         patch("backend.core.generators.flows_generator.FlowsGenerator.generate", new_callable=AsyncMock) as m_flows, \
         patch.object(service, "_generate_scopes_for_features", new_callable=AsyncMock) as m_scopes:

        m_actors.return_value = mock_actors_ret
        m_features.return_value = mock_features_ret
        m_scenarios.return_value = mock_scenarios_ret
        m_ac.return_value = mock_ac_ret
        m_flows.return_value = mock_flows_ret
        m_scopes.return_value = mock_scopes_ret

        # Perform generator orchestration
        patch_json = await service._generate_shadow_patch(seeded_project, base_snap, db_session)

        # 1. Check features added and their hierarchical relations
        assert len(patch_json["features_added"]) == 2
        assert patch_json["features_added"][0]["temp_id"] == "tmp_feature_7878"
        assert patch_json["features_added"][0]["parent_ref"] is None
        assert patch_json["features_added"][1]["temp_id"] == "tmp_feature_7878-001"
        assert patch_json["features_added"][1]["parent_ref"] == "tmp_feature_7878"

        # 2. Check all references mapped back to temporary references successfully
        assert patch_json["feature_actor_links_added"][0]["actor_ref"] == "tmp_actor_1"
        assert patch_json["flows_added"][0]["feature_refs"][0] == "tmp_feature_7878-001"
        assert patch_json["flow_steps_added"][0]["actor_refs"][0] == "tmp_actor_1"
        assert patch_json["flow_steps_added"][0]["output_bo_refs"][0] == "tmp_bo_gen_1"
        assert patch_json["flow_steps_added"][1]["input_bo_refs"][0] == "tmp_bo_gen_1"
        assert patch_json["scopes_added"][0]["feature_ref"] == "tmp_feature_7878-001"

        # 3. Verify that ShadowPatchValidator successfully validates this patch
        from backend.core.shadow_preview.shadow_patch_validator import ShadowPatchValidator
        ShadowPatchValidator.validate_patch(patch_json, base_snap, base_snap["project_id"])

        # 4. Save and commit draft to verify Database write-back creates FeatureRelationModel
        shadow_snap, temp_id_map = service._apply_patch_to_snapshot(base_snap, patch_json)
        draft_id = "test_draft_numeric"
        base_hash = calculate_stable_snapshot_hash(base_snap)
        draft = PreviewShadowDraftModel(
            project_id=seeded_project,
            draft_id=draft_id,
            status="ready",
            source="shadow_project",
            base_snapshot_hash=base_hash,
            base_snapshot_json=base_snap,
            patch_json=patch_json,
            shadow_snapshot_json=shadow_snap,
            prototype_preview_json={"prototypeId": 3, "html": "test3", "pages": []},
        )
        db_session.add(draft)
        await db_session.flush()

        from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
        prototype_gen_service = get_prototype_generation_service()
        with patch.object(prototype_gen_service, "generate_preview", new_callable=AsyncMock) as m_gen_prev:
            await service.commit_shadow_draft(seeded_project, draft_id, db_session)
            m_gen_prev.assert_called_once()

        # 5. Verify database relation table holds parent-child relation
        db_relations = (await db_session.execute(select(FeatureRelationModel))).scalars().all()
        assert len(db_relations) == 1

        # Verify the IDs link correctly
        db_features = (await db_session.execute(select(FeatureModel).where(FeatureModel.project_id == seeded_project))).scalars().all()
        assert len(db_features) == 2
        feat_by_name = {f.name: f for f in db_features}

        parent_feat = feat_by_name["用户管理"]
        child_feat = feat_by_name["添加用户"]
        assert db_relations[0].parent_feature_id == parent_feat.id
        assert db_relations[0].child_feature_id == child_feat.id


@pytest.mark.asyncio
async def test_empty_project_prefixed_reference_mapping(db_session, seeded_project):
    """
    Test empty project shadow preview generation where AI generators return prefixed references
    like 'feature:7878', 'actor:1', and 'business_object:1' rather than raw integers or temporary names.
    Ensures our local mapping helpers successfully parse and map these to proper temporary references.
    """
    service = PreviewShadowConvergenceService()

    base_snap = await build_project_snapshot(seeded_project, db_session)

    mock_actors_ret = {"actors": [{"actor_name": "管理员", "actor_description": "系统管理员"}]}
    mock_features_ret = {
        "features": [
            {
                "feature_number": "7878",
                "feature_name": "用户管理",
                "feature_description": "管理用户列表与角色配置",
                "actor_ids": [1],
            }
        ]
    }
    mock_scenarios_ret = {
        "scenarios": [
            {
                "scenario_name": "查询用户",
                "scenario_content": "Given 管理员已登录, When 查询用户列表, Then 展现所有注册用户",
            }
        ]
    }
    mock_ac_ret = {
        "acceptance_criteria": [{"criterion_content": "列表加载不超过500ms", "position": 1}]
    }
    mock_flows_ret = {
        "flows": [
            {
                "flow_name": "新建用户流程",
                "flow_description": "创建新用户的业务主流程",
                "feature_ids": ["feature:7878"],  # prefixed string
                "flow_steps": [
                    {
                        "step_number": "1",
                        "step_name": "填写信息",
                        "step_description": "输入用户名",
                        "step_type": "USER_ACTION",
                        "actor_ids": ["actor:1"],  # prefixed string
                        "input_business_object_numbers": [],
                        "output_business_object_numbers": ["business_object:1"],  # prefixed string
                        "next_steps": [],
                    }
                ],
            }
        ],
        "business_objects": [
            {
                "business_object_number": 1,
                "business_object_name": "用户信息载体",
                "business_object_description": "用户信息表单 data",
                "business_object_attributes": [],
            }
        ],
    }

    mock_scopes_ret = [
        {
            "feature_id": "feature:7878",  # prefixed feature_id
            "scope_status": "current",
            "reason": "核心需求",
            "kano_category": "M",
            "kano_category_name": "Must-be",
        }
    ]

    with patch("backend.core.generators.actors_generator.ActorsGenerator.generate", new_callable=AsyncMock) as m_actors, \
         patch("backend.core.generators.features_generator.FeaturesGenerator.generate", new_callable=AsyncMock) as m_features, \
         patch("backend.core.generators.scenarios_generator.ScenariosGenerator.generate", new_callable=AsyncMock) as m_scenarios, \
         patch("backend.core.generators.acceptance_criteria_generator.AcceptanceCriteriaGenerator.generate", new_callable=AsyncMock) as m_ac, \
         patch("backend.core.generators.flows_generator.FlowsGenerator.generate", new_callable=AsyncMock) as m_flows, \
         patch.object(service, "_generate_scopes_for_features", new_callable=AsyncMock) as m_scopes:

        m_actors.return_value = mock_actors_ret
        m_features.return_value = mock_features_ret
        m_scenarios.return_value = mock_scenarios_ret
        m_ac.return_value = mock_ac_ret
        m_flows.return_value = mock_flows_ret
        m_scopes.return_value = mock_scopes_ret

        patch_json = await service._generate_shadow_patch(seeded_project, base_snap, db_session)

        # Assert robust parsing successfully mapped them back to temp IDs
        assert patch_json["flows_added"][0]["feature_refs"][0] == "tmp_feature_7878"
        assert patch_json["flow_steps_added"][0]["actor_refs"][0] == "tmp_actor_1"
        assert patch_json["flow_steps_added"][0]["output_bo_refs"][0] == "tmp_bo_gen_1"
        assert patch_json["scopes_added"][0]["feature_ref"] == "tmp_feature_7878"

        # Verify validation passes successfully
        from backend.core.shadow_preview.shadow_patch_validator import ShadowPatchValidator
        ShadowPatchValidator.validate_patch(patch_json, base_snap, base_snap["project_id"])


@pytest.mark.asyncio
async def test_what_converged_missing_scenarios_workflow(db_session, seeded_project):
    """
    Test starting with a semi-converged project where What stage is converged (1 actor, 1 feature)
    but NO scenarios exist.
    We verify that shadow generator detects this gap, generates a template-based scenario and AC,
    and commits them to database.
    """
    service = PreviewShadowConvergenceService()

    # Seed database: 1 Actor, 1 Feature, link them
    actor = ActorModel(project_id=seeded_project, name="系统管理员", description="老系统固有角色")
    feature = FeatureModel(project_id=seeded_project, name="系统参数配置", description="主干特性")
    db_session.add_all([actor, feature])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=feature.id,
            actor_id=actor.id
        )
    )
    await db_session.flush()

    # Evaluate gates: What should pass (since missing scenarios is warning), How & Scope fail
    gates = await service.gate_evaluator.evaluate_gates(seeded_project, db_session)
    assert gates["what"] is True
    assert gates["how"] is False
    assert gates["scope"] is False

    base_snap = await build_project_snapshot(seeded_project, db_session)
    assert len(base_snap["actors"]) == 1
    assert len(base_snap["features"]) == 1
    assert len(base_snap["features"][0]["scenarios"]) == 0

    # Mock Flows and Scopes generation returns
    mock_flows_ret = {
        "flows": [
            {
                "flow_name": "修改设置流程",
                "flow_description": "修改系统参数",
                "feature_ids": [feature.id],
                "flow_steps": [
                    {
                        "step_number": "S-101",
                        "step_name": "提交表单",
                        "step_description": "点击保存设置",
                        "step_type": "USER_ACTION",
                        "actor_ids": [actor.id],
                        "input_business_object_numbers": [],
                        "output_business_object_numbers": [],
                        "next_steps": [],
                    }
                ],
            }
        ],
        "business_objects": [],
    }
    mock_scopes_ret = {
        "scopes": [
            {
                "feature_id": feature.id,
                "scope_status": "current",
                "reason": "用户管理固有功能",
                "kano_category": "M",
                "kano_category_name": "Must-be",
                "positive_summary": "已支持",
                "negative_summary": "不满足",
            }
        ]
    }

    # Patch generators, ensuring ActorsGenerator and FeaturesGenerator are not called
    with patch("backend.core.generators.actors_generator.ActorsGenerator.generate", new_callable=AsyncMock) as m_actors, \
         patch("backend.core.generators.features_generator.FeaturesGenerator.generate", new_callable=AsyncMock) as m_features, \
         patch("backend.core.generators.flows_generator.FlowsGenerator.generate", new_callable=AsyncMock) as m_flows, \
         patch("backend.core.generators.scopes_generator.ScopesGenerator.generate", new_callable=AsyncMock) as m_scopes:

        m_flows.return_value = mock_flows_ret
        m_scopes.return_value = mock_scopes_ret

        patch_json = await service._generate_shadow_patch(seeded_project, base_snap, db_session)

        # Assert no actors/features added (preservation rule)
        m_actors.assert_not_called()
        m_features.assert_not_called()
        assert len(patch_json["actors_added"]) == 0
        assert len(patch_json["features_added"]) == 0

        # Assert scenarios and AC are generated to fill the gap!
        assert len(patch_json["scenarios_added"]) == 1
        assert len(patch_json["acceptance_criteria_added"]) == 1

        sc = patch_json["scenarios_added"][0]
        assert sc["feature_ref"] == f"feature:{feature.id}"
        assert sc["actor_ref"] == f"actor:{actor.id}"
        assert "系统参数配置" in sc["name"]

        # Validate patch
        from backend.core.shadow_preview.shadow_patch_validator import ShadowPatchValidator
        ShadowPatchValidator.validate_patch(patch_json, base_snap, base_snap["project_id"])

        # Apply patch and save draft
        shadow_snap, temp_id_map = service._apply_patch_to_snapshot(base_snap, patch_json)
        
        # Verify the generated scenario exists in the sandboxed snapshot
        assert len(shadow_snap["features"][0]["scenarios"]) == 1
        assert len(shadow_snap["features"][0]["scenarios"][0]["acceptance_criteria"]) == 1

        draft_id = "test_draft_gap_fill"
        base_hash = calculate_stable_snapshot_hash(base_snap)
        draft = PreviewShadowDraftModel(
            project_id=seeded_project,
            draft_id=draft_id,
            status="ready",
            source="shadow_project",
            base_snapshot_hash=base_hash,
            base_snapshot_json=base_snap,
            patch_json=patch_json,
            shadow_snapshot_json=shadow_snap,
            prototype_preview_json={"prototypeId": 9, "html": "test", "pages": []},
        )
        db_session.add(draft)
        await db_session.flush()

        # Commit to verify database write-back
        from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
        prototype_gen_service = get_prototype_generation_service()
        with patch.object(prototype_gen_service, "generate_preview", new_callable=AsyncMock) as m_gen_prev:
            await service.commit_shadow_draft(seeded_project, draft_id, db_session)
            m_gen_prev.assert_called_once()

        # Check DB State: Scenario and AC should now exist in the database!
        db_scenarios = (await db_session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == seeded_project)
        )).scalars().all()
        assert len(db_scenarios) == 1
        assert db_scenarios[0].feature_id == feature.id
        assert db_scenarios[0].actor_id == actor.id

        from backend.database.model import ScenarioAcceptanceCriterionModel
        db_ac = (await db_session.execute(
            select(ScenarioAcceptanceCriterionModel).where(ScenarioAcceptanceCriterionModel.scenario_id == db_scenarios[0].id)
        )).scalars().all()
        assert len(db_ac) == 1
        assert "系统参数配置" in db_ac[0].content

