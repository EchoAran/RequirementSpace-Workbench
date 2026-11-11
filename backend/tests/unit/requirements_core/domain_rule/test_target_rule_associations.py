from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_project_member
from backend.api.modules.project_lifecycle.application.project_detail.builder import build_project_detail_response
from backend.api.modules.project_lifecycle.application.project_detail.loader import load_project_detail_model
from backend.api.modules.requirements_core.domain_rule.routes import router
from backend.database.database import get_session
from backend.database.model import (
    Base, BranchWorkspaceModel, DomainRuleModel, FlowModel, FlowStepModel,
    FlowTransitionModel, ProjectModel, RequirementBranchModel, RuleLinkModel,
)


@pytest_asyncio.fixture
async def association_space():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        project = ProjectModel(name="Rules", owner_user_id=1)
        branch = RequirementBranchModel(project=project, name="codex/rules", created_by_user_id=1)
        workspace = BranchWorkspaceModel(project=project, branch=branch)
        other_branch = RequirementBranchModel(project=project, name="codex/other", created_by_user_id=1)
        other_workspace = BranchWorkspaceModel(project=project, branch=other_branch)
        session.add_all([project, branch, workspace, other_branch, other_workspace])
        await session.flush()
        scope = dict(project_id=project.id, workspace_id=workspace.id)
        flow = FlowModel(**scope, name="Order")
        rules = [DomainRuleModel(**scope, title=f"Rule {i}", statement=f"Constraint {i}") for i in range(3)]
        foreign_rule = DomainRuleModel(project_id=project.id, workspace_id=other_workspace.id,
                                       title="Other branch", statement="Other scope")
        session.add_all([flow, *rules, foreign_rule])
        await session.flush()
        steps = [FlowStepModel(workspace_id=workspace.id, flow_id=flow.id, name=f"Step {i}",
                               position=i + 1, step_type="actorAction") for i in range(2)]
        session.add_all(steps)
        await session.flush()
        transition = FlowTransitionModel(**scope, flow_id=flow.id, source_step_id=steps[0].id,
                                         target_step_id=steps[1].id, label="Continue")
        session.add(transition)
        await session.commit()
        app = FastAPI()
        app.include_router(router)

        async def test_session():
            async with factory() as request_session:
                async with request_session.begin():
                    yield request_session

        app.dependency_overrides[get_session] = test_session
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        app.dependency_overrides[require_project_member] = lambda: project
        yield SimpleNamespace(app=app, factory=factory, project=project, workspace=workspace,
                              rules=rules, foreign_rule=foreign_rule, flow=flow,
                              flow_step=steps[0], flow_transition=transition)
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["flow", "flow_step", "flow_transition"])
async def test_atomic_association_edit_and_hydration(association_space, kind):
    space = association_space
    target = getattr(space, kind)
    scope = dict(project_id=space.project.id, workspace_id=space.workspace.id)
    async with space.factory() as session:
        retained = RuleLinkModel(**scope, rule_id=space.rules[0].id, target_kind=kind,
                                 target_logical_uuid=target.logical_uuid, context_text="Keep explanation")
        removed = RuleLinkModel(**scope, rule_id=space.rules[1].id, target_kind=kind,
                                target_logical_uuid=target.logical_uuid)
        source = RuleLinkModel(**scope, rule_id=space.rules[1].id, target_kind=kind,
                               target_logical_uuid=target.logical_uuid, link_purpose="source")
        unrelated = RuleLinkModel(**scope, rule_id=space.rules[0].id, target_kind="feature",
                                  target_logical_uuid="other-target")
        session.add_all([retained, removed, source, unrelated])
        await session.commit()
        retained_id, source_id, unrelated_id = retained.id, source.id, unrelated.id
    url = f"/api/projects/{space.project.public_id}/rules/associations?branch=codex/rules"
    payload = dict(targetKind=kind, targetLogicalUuid=target.logical_uuid,
                   ruleIds=[space.rules[0].id, space.rules[2].id, space.rules[2].id])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=space.app), base_url="http://test") as client:
        invalid = await client.put(url, json={**payload, "ruleIds": [space.foreign_rule.id]})
        assert invalid.status_code == 400
        async with space.factory() as session:
            assert len(list((await session.execute(select(RuleLinkModel))).scalars())) == 4
        response = await client.put(url, json=payload)
        assert response.status_code == 204, response.text
        assert (await client.put(url, json=payload)).status_code == 204
        async with space.factory() as session:
            links = list((await session.execute(select(RuleLinkModel))).scalars())
            assert len(links) == 4
            assert {link.rule_id for link in links if link.target_kind == kind and link.link_purpose == "applies_to"} == {
                space.rules[0].id, space.rules[2].id,
            }
            assert (await session.get(RuleLinkModel, retained_id)).context_text == "Keep explanation"
            assert await session.get(RuleLinkModel, source_id)
            assert await session.get(RuleLinkModel, unrelated_id)
            model = await load_project_detail_model(space.project.id, session, space.workspace.id)
            detail = build_project_detail_response(model, space.workspace, None, 0, "ok", "ok", [])
            hydrated = detail.model_dump(by_alias=True)
            assert len(hydrated["domainRules"]) == 3
            if kind == "flow_transition":
                assert set(hydrated["flows"][0]["transitions"][0]["ruleIds"]) == {space.rules[0].id, space.rules[2].id}
        assert (await client.put(url + "&commit_id=history", json=payload)).status_code == 403
        assert (await client.put(url, json={**payload, "ruleIds": []})).status_code == 204
    async with space.factory() as session:
        links = list((await session.execute(select(RuleLinkModel))).scalars())
        assert {link.id for link in links} == {source_id, unrelated_id}


@pytest.mark.asyncio
async def test_association_target_branch_boundary(association_space):
    space = association_space
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=space.app), base_url="http://test") as client:
        response = await client.put(
            f"/api/projects/{space.project.public_id}/rules/associations?branch=codex/other",
            json=dict(targetKind="flow", targetLogicalUuid=space.flow.logical_uuid, ruleIds=[]),
        )
        assert response.status_code == 400
