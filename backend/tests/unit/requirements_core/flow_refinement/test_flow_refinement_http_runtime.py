import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_project_member
from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService
from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import GenerationChoiceService
from backend.api.modules.project_configuration.application.generation_strategy_config_service import DEFAULT_STRATEGIES
from backend.api.modules.requirements_core.flow_refinement.application.choice_adapter import FlowRefinementChoiceAdapter
from backend.api.modules.requirements_core.flow_refinement.routes import router
from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.core.generators.flow_refinement_generator import FlowRefinementGenerator
from backend.database.database import get_session
from backend.database.model import (
    ActorModel, Base, BranchWorkspaceModel, BusinessObjectAttributeModel, BusinessObjectModel,
    ChoiceGroupModel, ChoiceModel, DomainRuleModel, FeatureModel, FlowModel, FlowStepModel,
    FlowTransitionModel, ProjectGenerationStrategyConfigModel, ProjectModel, RequirementBranchModel,
    RuleLinkModel, ScenarioModel, UserModel, flow_step_input_business_object_table,
)
from backend.schemas import Finding, FindingType, IssueSeverity, IssueStage
from backend.services.llm_handler_service import LLMCallFailedError, LLMHandler


@pytest_asyncio.fixture
async def runtime_space():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            project = ProjectModel(name="Checkout", owner_user_id=1)
            branch = RequirementBranchModel(project=project, name="codex/runtime", created_by_user_id=1)
            workspace = BranchWorkspaceModel(project=project, branch=branch)
            session.add_all([project, branch, workspace])
            await session.flush()
            scope = {"project_id": project.id, "workspace_id": workspace.id}
            actor = ActorModel(**scope, name="Customer")
            feature = FeatureModel(**scope, name="Order", actors=[actor])
            bo = BusinessObjectModel(**scope, name="Order")
            flow = FlowModel(**scope, name="Checkout", description="Order processing", features=[feature])
            session.add_all([actor, feature, bo, flow])
            await session.flush()
            first = FlowStepModel(
                workspace_id=workspace.id, flow_id=flow.id, name="Submit", position=1,
                step_type="actorAction", actors=[actor], input_business_objects=[bo],
            )
            last = FlowStepModel(
                workspace_id=workspace.id, flow_id=flow.id, name="Complete", position=2,
                step_type="systemAction",
            )
            scenario = ScenarioModel(**scope, feature_id=feature.id, actor_id=actor.id, name="Success", content="Order completes")
            rule = DomainRuleModel(**scope, title="Order check", statement="Check order before completion")
            session.add_all([first, last, scenario, rule])
            await session.flush()
            transition = FlowTransitionModel(
                **scope, flow_id=flow.id, source_step_id=first.id, target_step_id=last.id, label="Complete",
            )
            session.add_all([
                transition,
                RuleLinkModel(**scope, rule_id=rule.id, target_kind="flow", target_logical_uuid=flow.logical_uuid, link_purpose="applies_to"),
                ProjectGenerationStrategyConfigModel(project_id=project.id, knowledge_enabled=False, strategies=DEFAULT_STRATEGIES),
            ])
            await session.commit()
            user = await session.get(UserModel, 1)
            app = FastAPI()
            app.include_router(router)

            async def test_session():
                yield session

            app.dependency_overrides[get_session] = test_session
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[require_project_member] = lambda: project
            yield SimpleNamespace(
                session=session, app=app, project=project, workspace=workspace, actor=actor,
                bo=bo, flow=flow, first=first, last=last, scenario=scenario, transition=transition,
            )
    finally:
        await engine.dispose()


def model_output(space, locale, index):
    text = "检查库存" if locale == "zh-CN" else "Check inventory"
    return {
        "rationale": text,
        "steps_added": [{
            "temp_id": "s-new", "name": f"{text} {index}", "description": text,
            "step_type": "systemAction", "actor_ids": [space.actor.id],
            "input_business_object_numbers": [f"BO-{space.bo.id}"],
            "output_business_object_numbers": ["BO-NEW-1"],
        }],
        "transitions_added": [
            {"temp_id": "t-new-1", "source_step_ref": 1, "target_step_ref": "s-new", "label": text, "rule_refs": ["r-new"]},
            {"temp_id": "t-new-2", "source_step_ref": "s-new", "target_step_ref": 2, "label": text, "rule_refs": ["r-new"]},
        ],
        "transitions_updated": [{"logical_uuid": space.transition.logical_uuid, "label": text, "rule_refs": ["r-new"]}],
        "rules_added": [{
            "temp_id": "r-new", "title": text, "statement": text,
            "source_links": [
                {"target_kind": "scenario", "target_ref": space.scenario.logical_uuid, "context_text": text},
                {"target_kind": "scenario", "target_logical_uuid": space.scenario.logical_uuid, "context_text": f"{text} {text}"},
            ],
        }],
        "rule_links_added": [{"rule_ref": "r-new", "target_kind": "flow_transition", "target_ref": "t-new-1"}],
        "business_objects_added": [{
            "business_object_number": "BO-NEW-1", "business_object_name": text,
            "business_object_description": text,
            "business_object_attributes": [{"name": text, "description": text}],
        }],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
@pytest.mark.parametrize("target_kind", ["flow", "flow_step"])
async def test_http_generation_through_real_generator_then_choice_acceptance(runtime_space, locale, target_kind):
    space = runtime_space
    token = current_llm_context.set(LLMRequestContext("https://example.invalid", "test", "test", locale))
    finding = Finding(
        findingId="finding-1", type=FindingType.ISSUE, stage=IssueStage.HOW,
        code="TEST_FINDING", title="Context", description="Context", target="flow:1", severity=IssueSeverity.INFO,
    )
    requests = []

    async def fake_api(self, **kwargs):
        requests.append(kwargs["request_data"])
        prompt = "\n".join(message["content"] for message in kwargs["request_data"]["messages"])
        assert f'"target_kind": "{target_kind}"' in prompt
        assert '"target_flow_logical_uuid": "existing_flow_1"' in prompt
        output = model_output(space, locale, len(requests))
        output["rule_links_added"].append({
            "rule_ref": "r-new", "target_kind": "flow_step", "target_ref": "s-new",
        })
        if target_kind == "flow":
            output["rule_links_added"].extend([
                {"rule_ref": "r-new", "target_kind": "flow", "target_ref": space.flow.logical_uuid},
                {"rule_ref": (await space.session.get(DomainRuleModel, 1)).logical_uuid,
                 "target_kind": "flow", "target_ref": space.flow.logical_uuid},
            ])
        output = FlowRefinementGenerator._resolve_references(output, {
            space.flow.logical_uuid: "existing_flow_1",
            space.scenario.logical_uuid: "existing_scenario_1",
            space.transition.logical_uuid: "existing_flow_transition_1",
            (await space.session.get(DomainRuleModel, 1)).logical_uuid: "existing_rule_1",
        })
        return json.dumps(output, ensure_ascii=False)

    try:
        with patch.object(LLMHandler, "_call_api", new=fake_api), patch(
            "backend.core.findings.how_finding_policy.HowFindingPolicy.get_findings",
            new=AsyncMock(return_value=[finding]),
        ):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=space.app), base_url="http://test") as client:
                response = await client.post(
                    f"/api/projects/{space.project.public_id}/flows/refine?branch=codex/runtime",
                    json={"target_kind": target_kind, "target_id": space.flow.id if target_kind == "flow" else space.first.id, "candidate_count": 2, "source_finding_id": "finding-1"},
                )
            assert response.status_code == 200, response.text
            group_data = response.json()
            assert group_data["success_count"] == 2, json.dumps(group_data, ensure_ascii=False)
            assert group_data["failure_count"] == 0
            assert len(requests) == 2
            for request in requests:
                prompt = request["messages"][0]["content"]
                assert "{{" not in prompt
                assert f'"number": "BO-{space.bo.id}"' in prompt
                assert "allowed_step_positions" in prompt
                assert "Order completes" in prompt

            assert (await space.session.execute(select(func.count()).select_from(FlowStepModel))).scalar_one() == 2
            choices = (await space.session.execute(select(ChoiceModel).order_by(ChoiceModel.id))).scalars().all()
            assert {choice.strategy_id for choice in choices} == {"balanced", "comprehensive"}
            assert choices[0].payload["source_finding_id"] == "finding-1"
            assert await FlowRefinementChoiceAdapter().is_context_stale(choices[0], space.session) == (False, None)
            accepted = await ChoiceService().accept_choice(space.project.id, choices[0].id, space.session, workspace_id=space.workspace.id)
            assert accepted.status == "accepted"
            assert (await space.session.get(ChoiceGroupModel, choices[0].choice_group_id)).status == "resolved"
            assert choices[1].status == "rejected"
            assert (await space.session.execute(select(func.count()).select_from(FlowStepModel))).scalar_one() == 3
            assert (await space.session.execute(select(func.count()).select_from(FlowTransitionModel))).scalar_one() == 3
            assert (await space.session.execute(select(func.count()).select_from(BusinessObjectAttributeModel))).scalar_one() == 1
            new_rule = (await space.session.execute(select(DomainRuleModel).where(DomainRuleModel.id != 1))).scalar_one()
            links = (await space.session.execute(select(RuleLinkModel).where(RuleLinkModel.rule_id == new_rule.id))).scalars().all()
            assert len([link for link in links if link.link_purpose == "source"]) == 1
            assert len([link for link in links if link.link_purpose == "applies_to"]) == (5 if target_kind == "flow" else 4)
            assert len([link for link in links if link.target_kind == "flow_step"]) == 1
            assert len([link for link in links if link.target_kind == "flow"]) == (1 if target_kind == "flow" else 0)
            existing_flow_links = (await space.session.execute(select(RuleLinkModel).where(
                RuleLinkModel.rule_id == 1, RuleLinkModel.target_kind == "flow",
            ))).scalars().all()
            assert len(existing_flow_links) == 1
            assert (await space.session.execute(select(func.count()).select_from(flow_step_input_business_object_table))).scalar_one() == 2
    finally:
        current_llm_context.reset(token)


@pytest.mark.asyncio
async def test_http_model_failure_remains_failed_not_empty_success(runtime_space):
    space = runtime_space
    token = current_llm_context.set(LLMRequestContext("https://example.invalid", "test", "test"))
    try:
        with patch.object(LLMHandler, "_call_api", new=AsyncMock(side_effect=LLMCallFailedError("upstream unavailable"))):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=space.app), base_url="http://test") as client:
                response = await client.post(
                    f"/api/projects/{space.project.public_id}/flows/refine?branch=codex/runtime",
                    json={"target_kind": "flow", "target_id": space.flow.id, "candidate_count": 2},
                )
            assert response.status_code == 200, response.text
            group = response.json()
            assert group["status"] == "failed"
            assert group["success_count"] == 0
            assert group["failure_count"] == 2
            assert all(choice["status"] == "failed" and not choice["payload"] for choice in group["choices"])
        with patch.object(LLMHandler, "_call_api", new=AsyncMock(return_value='{"rationale": "当前路径已完整"}')), patch(
            "backend.core.findings.how_finding_policy.HowFindingPolicy.get_findings",
            new=AsyncMock(return_value=[]),
        ):
            regenerated = await GenerationChoiceService().regenerate_choice_group(space.project.id, group["id"], session=space.session)
            assert regenerated["status"] == "open"
            assert regenerated["failure_count"] == 0
            assert regenerated["choices"][0]["payload"]["done_empty"] is True
            accepted = await ChoiceService().accept_choice(space.project.id, regenerated["choices"][0]["id"], space.session, workspace_id=space.workspace.id)
            assert accepted.status == "accepted"
            assert (await space.session.execute(select(func.count()).select_from(FlowStepModel))).scalar_one() == 2
    finally:
        current_llm_context.reset(token)
