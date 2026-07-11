import pytest
import json
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from backend.database.model import (
    Base, ProjectModel, ActorModel, FeatureModel, ScenarioModel,
    FlowModel, FlowStepModel, BusinessObjectModel, BusinessObjectAttributeModel,
    feature_actor_table, flow_feature_table
)
from backend.api.modules.diagnosis_quality.public import IssueRepairService

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
async def seeded_project(db_session) -> ProjectModel:
    """Create a seed project and return it."""
    project = ProjectModel(
        name="Issue Repair 测试项目",
        description="用于测试 Issue 修复和 AI Solver 的项目",
        user_requirements="孤立角色应绑定 to 功能；同名场景应重命名",
        kano_status="pending",
        unlocked_stages="what,how,scope",
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_actor_without_feature_solver(db_session, seeded_project):
    # Setup: Isolated actor (no features) and a leaf feature
    actor = ActorModel(project_id=seeded_project.id, name="买家", description="购买商品的买家")
    feature = FeatureModel(project_id=seeded_project.id, name="商品下单", description="下单购买商品")
    db_session.add_all([actor, feature])
    await db_session.flush()

    service = IssueRepairService()
    
    mock_llm_response = {
        "candidates": [
            {
                "repair_type": "bind_existing_actor",
                "title": f"绑定到功能「{feature.name}」",
                "rationale": "买家是下单的主体",
                "confidence": 0.9,
                "patch": {
                    "addLinks": [
                        {
                            "type": "feature_actor_relation",
                            "source_id": feature.id,
                            "target_id": actor.id
                        }
                    ]
                },
                "requires_user_decision": False
            }
        ]
    }

    with patch("backend.services.llm_handler_service.LLMHandler.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = json.dumps(mock_llm_response)

        res = await service.resolve(
            project_id=seeded_project.id,
            issue_code="ACTOR_WITHOUT_FEATURE",
            stage="what",
            target={"target_type": "actor", "target_id": actor.id},
            metadata={},
            session=db_session
        )
        
        assert res["resolution_type"] == "repair_draft"
        assert res["patch"]["addLinks"][0]["source_id"] == feature.id
        assert res["patch"]["addLinks"][0]["target_id"] == actor.id


@pytest.mark.asyncio
async def test_scenario_actor_consistency_solver(db_session, seeded_project):
    # Setup: scenario, feature, actor (not in feature actors)
    actor = ActorModel(project_id=seeded_project.id, name="卖家", description="售卖商品的卖家")
    feature = FeatureModel(project_id=seeded_project.id, name="商品上架", description="上架商品")
    db_session.add_all([actor, feature])
    await db_session.flush()

    scenario = ScenarioModel(project_id=seeded_project.id, feature_id=feature.id, actor_id=actor.id, name="正常上架", content="卖家上架商品")
    db_session.add(scenario)
    await db_session.flush()

    service = IssueRepairService()

    mock_llm_response = {
        "candidates": [
            {
                "repair_type": "bind_actor_to_feature",
                "title": f"将角色「{actor.name}」加入功能「{feature.name}」的参与者中",
                "rationale": "卖家应该参与上架功能",
                "confidence": 0.95,
                "patch": {
                    "addLinks": [
                        {
                            "type": "feature_actor_relation",
                            "source_id": feature.id,
                            "target_id": actor.id
                        }
                    ]
                },
                "requires_user_decision": True
            },
            {
                "repair_type": "change_scenario_actor",
                "title": "将场景角色修改为其他角色",
                "rationale": "改绑为其他已有角色",
                "confidence": 0.5,
                "patch": {
                    "updateNodes": [
                        {
                            "kind": "scenario",
                            "id": scenario.id,
                            "actor_id": 999
                        }
                    ]
                },
                "requires_user_decision": True
            }
        ]
    }

    with patch("backend.services.llm_handler_service.LLMHandler.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = json.dumps(mock_llm_response)

        res = await service.resolve(
            project_id=seeded_project.id,
            issue_code="SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS",
            stage="what",
            target={"target_type": "scenario", "target_id": scenario.id},
            metadata={},
            session=db_session
        )

        assert res["resolution_type"] == "choice_group"
        assert len(res["action"]["payload"]["choice_group"]["choices"]) == 2


@pytest.mark.asyncio
async def test_duplicate_scenario_name_solver(db_session, seeded_project):
    # Setup: duplicate scenario names under same feature
    feature = FeatureModel(project_id=seeded_project.id, name="商品检索", description="检索商品")
    actor = ActorModel(project_id=seeded_project.id, name="检索用户", description="系统用户")
    db_session.add_all([feature, actor])
    await db_session.flush()

    s1 = ScenarioModel(project_id=seeded_project.id, feature_id=feature.id, actor_id=actor.id, name="检索成功", content="检索成功1")
    s2 = ScenarioModel(project_id=seeded_project.id, feature_id=feature.id, actor_id=actor.id, name="检索成功", content="检索成功2")
    db_session.add_all([s1, s2])
    await db_session.flush()

    service = IssueRepairService()

    mock_llm_response = {
        "candidates": [
            {
                "repair_type": "rename_scenario",
                "title": "重命名场景为「通过商品分类检索成功」",
                "rationale": "按分类检索",
                "confidence": 0.9,
                "patch": {
                    "updateNodes": [
                        {
                            "kind": "scenario",
                            "id": s2.id,
                            "name": "通过商品分类检索成功"
                        }
                    ]
                },
                "requires_user_decision": False
            }
        ]
    }

    with patch("backend.services.llm_handler_service.LLMHandler.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = json.dumps(mock_llm_response)

        res = await service.resolve(
            project_id=seeded_project.id,
            issue_code="DUPLICATE_SCENARIO_NAME",
            stage="what",
            target={"target_type": "scenario", "target_id": s2.id},
            metadata={},
            session=db_session
        )

        assert res["resolution_type"] == "repair_draft"
        assert res["patch"]["updateNodes"][0]["name"] == "通过商品分类检索成功"


@pytest.mark.asyncio
async def test_flow_without_steps_solver(db_session, seeded_project):
    # Setup: Two flows: one without steps (target), and one with steps (to avoid the equilibrium check)
    feature = FeatureModel(project_id=seeded_project.id, name="支付订单", description="支付订单流程")
    flow1 = FlowModel(project_id=seeded_project.id, name="微信支付", description="微信支付流程详情")
    flow2 = FlowModel(project_id=seeded_project.id, name="支付宝支付", description="支付宝支付流程详情")
    db_session.add_all([feature, flow1, flow2])
    await db_session.flush()

    # Link both flows to feature
    await db_session.execute(
        flow_feature_table.insert().values([
            {"flow_id": flow1.id, "feature_id": feature.id},
            {"flow_id": flow2.id, "feature_id": feature.id}
        ])
    )
    await db_session.flush()

    # Add a step to flow2 so at least one flow in the project has steps
    step = FlowStepModel(flow_id=flow2.id, position=0, name="步骤1", step_type="action")
    db_session.add(step)
    await db_session.flush()

    service = IssueRepairService()

    mock_llm_response = {
        "fallback": {
            "kind": "manual_action",
            "reason": "建议为此流程添加以下典型步骤：\n1. [扫码] ...\n2. [密码确认] ..."
        }
    }

    with patch("backend.services.llm_handler_service.LLMHandler.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = json.dumps(mock_llm_response)

        res = await service.resolve(
            project_id=seeded_project.id,
            issue_code="FLOW_WITHOUT_STEPS",
            stage="how",
            target={"target_type": "flow", "target_id": flow1.id},
            metadata={},
            session=db_session
        )

        assert res["resolution_type"] == "manual_action"
        assert "建议为此流程添加以下典型步骤" in res["description"]


@pytest.mark.asyncio
async def test_business_object_without_usage_solver(db_session, seeded_project):
    # Setup: business object without usage
    bo = BusinessObjectModel(project_id=seeded_project.id, name="交易订单", description="包含支付状态的订单")
    db_session.add(bo)
    await db_session.flush()

    service = IssueRepairService()

    mock_llm_response = {
        "fallback": {
            "kind": "manual_action",
            "reason": "建议在支付流程步骤中作为输出关联。"
        }
    }

    with patch("backend.services.llm_handler_service.LLMHandler.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = json.dumps(mock_llm_response)

        res = await service.resolve(
            project_id=seeded_project.id,
            issue_code="BUSINESS_OBJECT_WITHOUT_USAGE",
            stage="how",
            target={"target_type": "business_object", "target_id": bo.id},
            metadata={},
            session=db_session
        )

        assert res["resolution_type"] == "manual_action"
        assert "建议在支付流程步骤中作为输出关联" in res["description"]


@pytest.mark.asyncio
async def test_scenario_without_acceptance_criteria_choice_group_metadata(db_session, seeded_project):
    # Setup: scenario without AC, and another scenario with AC to satisfy non-equilibrium checks
    feature = FeatureModel(project_id=seeded_project.id, name="商品搜索", description="检索商品")
    actor = ActorModel(project_id=seeded_project.id, name="检索用户", description="系统用户")
    db_session.add_all([feature, actor])
    await db_session.flush()

    s1 = ScenarioModel(project_id=seeded_project.id, feature_id=feature.id, actor_id=actor.id, name="检索成功", content="检索成功1")
    s2 = ScenarioModel(project_id=seeded_project.id, feature_id=feature.id, actor_id=actor.id, name="检索失败", content="检索失败1")
    db_session.add_all([s1, s2])
    await db_session.flush()

    from backend.database.model import ScenarioAcceptanceCriterionModel
    ac = ScenarioAcceptanceCriterionModel(scenario_id=s2.id, position=0, content="如果检索不到商品则显示空白提示")
    db_session.add(ac)
    await db_session.flush()

    service = IssueRepairService()

    # Mock GenerationChoiceService.create_choice_group to return a mocked choice group
    # but verify the arguments passed to it!
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import GenerationChoiceService, GenerationChoiceSettings
    with patch.object(GenerationChoiceService, "create_choice_group", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "id": 123,
            "choices": []
        }
        # Ensure is_generation_type_enabled returns True
        with patch.object(GenerationChoiceSettings, "is_generation_type_enabled", return_value=True):
            res = await service.resolve(
                project_id=seeded_project.id,
                issue_code="SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA",
                stage="what",
                target={"target_type": "scenario", "target_id": s1.id},
                metadata={},
                session=db_session
            )
            
            # Assertions on mock_create call arguments
            mock_create.assert_called_once()
            kwargs = mock_create.call_args[1]
            assert kwargs["issue_code"] == "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA"
            assert kwargs["issue_id"] == f"what:SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA:scenario:{s1.id}"
            assert kwargs["stage"] == "what"
            assert kwargs["source_type"] == "issue_repair"
            assert kwargs["source_id"] is not None  # fingerprint
            assert kwargs["context_hash"] is not None
