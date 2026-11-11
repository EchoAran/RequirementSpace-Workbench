"""Regression tests for workspace isolation through real API routes."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.project_access import require_project_member
from backend.api.modules.ai_interaction.ai_add import routes as ai_routes
from backend.api.modules.ai_interaction.ai_add.application.session import AIAddSessionService
from backend.api.modules.ai_interaction.ai_explain import routes as explain_routes
from backend.api.modules.ai_interaction.ai_explain.application.explain import AIExplainService
from backend.database.database import get_session
from backend.database.model import (
    ActorModel,
    AIAddSessionModel,
    Base,
    BranchWorkspaceModel,
    BusinessObjectModel,
    DomainRuleModel,
    FeatureModel,
    FlowModel,
    PerceptionSlotModel,
    ProjectModel,
    RequirementBranchModel,
    RuleLinkModel,
    UserModel,
)
from backend.main import app


@asynccontextmanager
async def no_llm_configuration(*args, **kwargs):
    yield None


@pytest.fixture
async def env(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await session.get(UserModel, 1)
        project = ProjectModel(owner_user_id=1, name="Audit project", user_requirements="PROJECT_ROOT_REQUIREMENTS")
        session.add(project)
        await session.flush()
        workspaces = {}
        for name in ["main", "work/a", "work/b"]:
            branch = RequirementBranchModel(project_id=project.id, name=name, created_by_user_id=1,
                                            is_protected=name == "main", is_default=name == "main")
            session.add(branch)
            await session.flush()
            workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                             user_requirements=f"REQUIREMENTS_{name}", unlocked_stages="what,how,scope")
            session.add(workspace)
            await session.flush()
            workspaces[name] = workspace
        await session.commit()

        async def session_dependency():
            yield session

        overrides = dict(app.dependency_overrides)
        app.dependency_overrides[get_session] = session_dependency
        app.dependency_overrides[get_current_user] = lambda: user
        monkeypatch.setattr(ai_routes, "llm_context_manager", no_llm_configuration)
        monkeypatch.setattr(explain_routes, "llm_context_manager", no_llm_configuration)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://audit.test") as client:
            yield SimpleNamespace(session=session, client=client, project=project, user=user, ws=workspaces)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [{"kind": "workspace"}, {"kind": "projection", "stage": "what"}])
async def test_explain_workspace_uses_selected_branch(env, monkeypatch, scope):
    actors = [ActorModel(project_id=env.project.id, workspace_id=env.ws[name].id,
                         name=f"ACTOR_ONLY_{name}") for name in ["work/a", "work/b"]]
    env.session.add_all(actors)
    await env.session.flush()
    llm = SimpleNamespace(call_chat=AsyncMock(return_value="mock answer"))
    service = AIExplainService()
    monkeypatch.setattr(service, "_get_llm_handler", lambda: llm)
    monkeypatch.setattr(explain_routes, "_get_service", lambda: service)
    response = await env.client.post("/api/ai/explain?branch=work/a", json={
        "project_id": env.project.public_id, "scope": scope, "question": "Explain actors"})
    assert response.status_code == 200, response.text
    prompt = llm.call_chat.await_args.args[0][0]["content"]
    assert "ACTOR_ONLY_work/a" in prompt
    assert "ACTOR_ONLY_work/b" not in prompt
    assert "REQUIREMENTS_work/a" in prompt
    assert "PROJECT_ROOT_REQUIREMENTS" not in prompt


async def seed_foreign_actor(env):
    private_owner = UserModel(email="private-owner@audit.test", password_hash="system_locked", role="user")
    env.session.add(private_owner)
    await env.session.flush()
    foreign = ProjectModel(owner_user_id=private_owner.id, name="Not a member", user_requirements="private")
    env.session.add(foreign)
    await env.session.flush()
    foreign_branch = RequirementBranchModel(project_id=foreign.id, name="main")
    env.session.add(foreign_branch)
    await env.session.flush()
    foreign_workspace = BranchWorkspaceModel(project_id=foreign.id, branch_id=foreign_branch.id)
    env.session.add(foreign_workspace)
    await env.session.flush()
    actor = ActorModel(project_id=foreign.id, workspace_id=foreign_workspace.id,
                       name="FOREIGN_PRIVATE_ACTOR", description="FOREIGN_PRIVATE_DESCRIPTION")
    env.session.add(actor)
    await env.session.flush()
    return foreign, actor


@pytest.mark.asyncio
async def test_explain_rejects_another_project_node(env, monkeypatch):
    foreign, actor = await seed_foreign_actor(env)
    # There is deliberately no membership for this user in the foreign project.
    with pytest.raises(Exception) as denied:
        await require_project_member(foreign.public_id, env.user, env.session, None)
    assert denied.value.status_code == 404
    llm = SimpleNamespace(call_chat=AsyncMock(return_value="mock answer"))
    service = AIExplainService()
    monkeypatch.setattr(service, "_get_llm_handler", lambda: llm)
    monkeypatch.setattr(explain_routes, "_get_service", lambda: service)
    response = await env.client.post("/api/ai/explain?branch=work/a", json={
        "project_id": env.project.public_id, "scope": {"kind": "node", "target_type": "actor", "target_id": actor.id},
        "question": "Explain this actor"})
    assert response.status_code == 404, response.text
    llm.call_chat.assert_not_awaited()


async def generate_actor_draft(env, monkeypatch):
    ai_session = AIAddSessionModel(project_id=env.project.id, target_type="actor", anchor_payload={},
                                   status="ready", ready_to_generate=True, summary_payload={"known_facts": []})
    env.session.add(ai_session)
    await env.session.flush()
    generator = SimpleNamespace(generate=AsyncMock(return_value={"actor": {"name": "Generated on A", "description": "audit"}}))
    service = AIAddSessionService()
    monkeypatch.setattr(service, "_get_generator", lambda *args: generator)
    monkeypatch.setattr(ai_routes, "_get_service", lambda: service)
    response = await env.client.post(f"/api/ai_add_sessions/{ai_session.id}/generate_draft?branch=work/a")
    assert response.status_code == 200, response.text
    return response.json()["draftId"], generator


@pytest.mark.asyncio
async def test_ai_draft_uses_workspace_requirements(env, monkeypatch):
    _draft_id, generator = await generate_actor_draft(env, monkeypatch)
    requirements = generator.generate.await_args.args[0].user_requirements
    assert requirements == env.ws["work/a"].user_requirements
    assert requirements != "PROJECT_ROOT_REQUIREMENTS"


@pytest.mark.asyncio
async def test_ai_draft_cannot_be_confirmed_in_another_branch(env, monkeypatch):
    draft_id, _ = await generate_actor_draft(env, monkeypatch)
    response = await env.client.post(f"/api/ai_object_generation_drafts/{draft_id}/confirm?branch=work/b")
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "draft_workspace_mismatch"
    assert (await env.session.execute(select(ActorModel))).scalars().all() == []
    accepted = await env.client.post(f"/api/ai_object_generation_drafts/{draft_id}/confirm?branch=work/a")
    assert accepted.status_code == 200, accepted.text
    actors = (await env.session.execute(select(ActorModel))).scalars().all()
    assert len(actors) == 1 and actors[0].workspace_id == env.ws["work/a"].id


@pytest.mark.asyncio
async def test_perception_slot_respects_read_only_branch(env):
    slot = PerceptionSlotModel(project_id=env.project.id, workspace_id=env.ws["main"].id,
                               perception_kind="ACTOR", description="main protected slot")
    env.session.add(slot)
    await env.session.commit()
    response = await env.client.delete(f"/api/projects/{env.project.public_id}/perception-slot?branch=main&commit_id=historical")
    assert response.status_code == 403, response.text
    response = await env.client.delete(f"/api/projects/{env.project.public_id}/perception-slot?branch=main")
    assert response.status_code == 403, response.text
    assert (await env.session.execute(select(PerceptionSlotModel))).scalars().all() == [slot]


@pytest.mark.asyncio
async def test_flow_update_rejects_foreign_workspace_feature(env):
    feature = FeatureModel(project_id=env.project.id, workspace_id=env.ws["work/a"].id, name="Feature only on A")
    flow = FlowModel(project_id=env.project.id, workspace_id=env.ws["work/b"].id, name="Flow only on B")
    env.session.add_all([feature, flow])
    await env.session.flush()
    response = await env.client.put(f"/api/projects/{env.project.public_id}/flows/{flow.id}?branch=work/b",
                                    json={"feature_ids": [feature.id]})
    assert response.status_code == 400, response.text
    await env.session.refresh(flow, ["features"])
    assert flow.features == []


@pytest.mark.asyncio
async def test_ai_edit_rejects_foreign_project_on_creation_and_generation(env, monkeypatch):
    _, actor = await seed_foreign_actor(env)
    created = await env.client.post("/api/ai_add_sessions?branch=work/a", json={
        "project_id": env.project.public_id, "target_type": "edit_actor", "anchor": {"target_id": actor.id},
    })
    assert created.status_code == 400, created.text
    assert created.json()["detail"] == "target_not_found"
    ai_session = AIAddSessionModel(project_id=env.project.id, target_type="edit_actor",
                                   anchor_payload={"target_id": actor.id}, status="ready",
                                   ready_to_generate=True, summary_payload={"known_facts": []})
    env.session.add(ai_session)
    await env.session.flush()
    generator = SimpleNamespace(generate=AsyncMock())
    service = AIAddSessionService()
    monkeypatch.setattr(service, "_get_generator", lambda *args: generator)
    monkeypatch.setattr(ai_routes, "_get_service", lambda: service)
    response = await env.client.post(f"/api/ai_add_sessions/{ai_session.id}/generate_draft?branch=work/a")
    assert response.status_code == 400, response.text
    generator.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_control_existing_workspace_and_main_guards_reject(env):
    feature = FeatureModel(project_id=env.project.id, workspace_id=env.ws["work/a"].id, name="A-only parent")
    env.session.add(feature)
    await env.session.flush()
    child = await env.client.post(f"/api/projects/{env.project.public_id}/features?branch=work/b",
                                  json={"name": "B child", "parent_id": feature.id})
    flow = await env.client.post(f"/api/projects/{env.project.public_id}/flows?branch=work/b",
                                 json={"name": "B flow", "feature_ids": [feature.id]})
    actor = await env.client.post(f"/api/projects/{env.project.public_id}/actors?branch=main",
                                  json={"name": "Forbidden main write"})
    assert child.status_code == 400, child.text
    assert flow.status_code == 400, flow.text
    assert actor.status_code == 403, actor.text


@pytest.mark.asyncio
async def test_explain_answer_and_label_hide_database_ids(env, monkeypatch):
    actor = ActorModel(project_id=env.project.id, workspace_id=env.ws["work/a"].id, name="Manager")
    env.session.add(actor)
    await env.session.flush()
    handler = SimpleNamespace(call_chat=AsyncMock(return_value=f"Manager (actor:{actor.id}) handles 500 orders."))
    service = AIExplainService()
    monkeypatch.setattr(service, "_get_llm_handler", lambda: handler)
    monkeypatch.setattr(explain_routes, "_get_service", lambda: service)
    response = await env.client.post("/api/ai/explain?branch=work/a", json={
        "project_id": env.project.public_id,
        "scope": {"kind": "node", "target_type": "actor", "target_id": actor.id}, "question": "Explain",
    })
    assert response.status_code == 200, response.text
    assert "actor:" not in response.json()["answer"]
    assert "500 orders" in response.json()["answer"]
    assert response.json()["context_summary"]["scope_label"] == "Manager"
    prompt = handler.call_chat.await_args.args[0][0]["content"]
    assert f"ID:{actor.id}" not in prompt
    assert f"actor:{actor.id}" not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,model,fields", [
    ("actor", ActorModel, {"name": "Private actor"}),
    ("feature", FeatureModel, {"name": "Private feature"}),
    ("flow", FlowModel, {"name": "Private flow"}),
    ("business_object", BusinessObjectModel, {"name": "Private data"}),
    ("rule", DomainRuleModel, {"title": "Private rule", "statement": "Private statement"}),
])
async def test_ai_node_paths_reject_another_workspace(env, monkeypatch, kind, model, fields):
    node = model(project_id=env.project.id, workspace_id=env.ws["work/b"].id, **fields)
    env.session.add(node)
    await env.session.flush()
    llm = SimpleNamespace(call_chat=AsyncMock())
    service = AIExplainService()
    monkeypatch.setattr(service, "_get_llm_handler", lambda: llm)
    monkeypatch.setattr(explain_routes, "_get_service", lambda: service)
    response = await env.client.post("/api/ai/explain?branch=work/a", json={
        "project_id": env.project.public_id,
        "scope": {"kind": "node", "target_type": kind, "target_id": node.id}, "question": "Explain",
    })
    assert response.status_code == 404, response.text
    llm.call_chat.assert_not_awaited()
    created = await env.client.post("/api/ai_add_sessions?branch=work/a", json={
        "project_id": env.project.public_id, "target_type": f"edit_{kind}", "anchor": {"target_id": node.id},
    })
    assert created.status_code == 400, created.text


@pytest.mark.asyncio
async def test_edit_generation_uses_workspace_requirements(env, monkeypatch):
    actor = ActorModel(project_id=env.project.id, workspace_id=env.ws["work/a"].id, name="Manager")
    env.session.add(actor)
    await env.session.flush()
    created = await env.client.post("/api/ai_add_sessions?branch=work/a", json={
        "project_id": env.project.public_id, "target_type": "edit_actor", "anchor": {"target_id": actor.id},
    })
    assert created.status_code == 200, created.text
    ai_session = await env.session.get(AIAddSessionModel, created.json()["sessionId"])
    ai_session.status = "ready"
    ai_session.ready_to_generate = True
    ai_session.summary_payload = {"known_facts": []}
    generator = SimpleNamespace(generate=AsyncMock(return_value={
        "diff": {"name": {"old": "Manager", "new": "Administrator"}}, "rationale": "Clarified name",
    }))
    service = AIAddSessionService()
    monkeypatch.setattr(service, "_get_generator", lambda *args: generator)
    monkeypatch.setattr(ai_routes, "_get_service", lambda: service)
    response = await env.client.post(f"/api/ai_add_sessions/{ai_session.id}/generate_draft?branch=work/a")
    assert response.status_code == 200, response.text
    assert generator.generate.await_args.args[0].user_requirements == "REQUIREMENTS_work/a"


@pytest.mark.asyncio
async def test_rule_link_resolves_logical_uuid_in_selected_workspace(env, monkeypatch):
    features = [FeatureModel(project_id=env.project.id, workspace_id=env.ws[branch].id,
                             logical_uuid="shared-feature", name=f"Feature_{branch}")
                for branch in ["work/a", "work/b"]]
    rule = DomainRuleModel(project_id=env.project.id, workspace_id=env.ws["work/a"].id,
                           title="Rule", statement="Applies to selected feature")
    env.session.add_all([*features, rule])
    await env.session.flush()
    env.session.add(RuleLinkModel(project_id=env.project.id, workspace_id=env.ws["work/a"].id,
                                  rule_id=rule.id, target_kind="feature", target_logical_uuid="shared-feature"))
    await env.session.flush()
    llm = SimpleNamespace(call_chat=AsyncMock(return_value="Answer"))
    service = AIExplainService()
    monkeypatch.setattr(service, "_get_llm_handler", lambda: llm)
    result = await service.explain(env.project.id, {"kind": "node", "target_type": "rule", "target_id": rule.id},
                                   "Explain", env.session, branch_name="work/a")
    assert result["answer"] == "Answer"
    prompt = llm.call_chat.await_args.args[0][0]["content"]
    assert "Feature_work/a" in prompt and "Feature_work/b" not in prompt
