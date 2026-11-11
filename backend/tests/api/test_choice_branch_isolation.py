from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.api.modules.decision_workflow.choice_group import routes
from backend.api.modules.decision_workflow.choice_group.application import choice_service as service_module
from backend.database.model import Base, BranchWorkspaceModel, ChoiceGroupModel, ChoiceModel, ProjectModel, RequirementBranchModel, UserModel


@pytest.fixture
async def branch_client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        project = ProjectModel(id=1, public_id="project", name="Project", description="", user_requirements="", owner_user_id=1)
        session.add(project)
        await session.flush()
        for index, name in enumerate(["main", "test", "other"], 1):
            session.add(RequirementBranchModel(id=index, project_id=1, name=name, is_protected=name == "main", created_by_user_id=1))
            await session.flush()
            session.add(BranchWorkspaceModel(id=index, project_id=1, branch_id=index))
        await session.flush()
        for index in range(1, 5):
            session.add(ChoiceGroupModel(id=index, project_id=1, workspace_id=index if index < 4 else None, status="open", generation_type="rule"))
            await session.flush()
            session.add(ChoiceModel(id=index, choice_group_id=index, workspace_id=index if index < 4 else None, title="Rules", rationale="", status="candidate", patch={}, apply_mode="draft_payload", draft_type="rule", payload={"rules": []}))
        await session.flush()
        user = await session.get(UserModel, 1)

        async def project_access(*args):
            return project

        @asynccontextmanager
        async def llm_context(*args, **kwargs):
            yield

        monkeypatch.setattr(routes, "require_owned_project", project_access)
        monkeypatch.setattr(routes, "require_project_member", project_access)
        monkeypatch.setattr(routes, "llm_context_manager", llm_context)
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[routes.get_current_user] = lambda: user
        app.dependency_overrides[routes.get_session] = lambda: session
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client, session
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_excludes_other_branches_and_unassigned_groups(branch_client):
    client, _ = branch_client
    for branch, expected in [("main", 1), ("test", 2), ("other", 3)]:
        response = await client.get(f"/api/projects/project/choice_groups?branch={branch}&status=open")
        assert response.status_code == 200, response.text
        assert [group["id"] for group in response.json()] == [expected]


@pytest.mark.parametrize("path", [
    "choices/3/accept", "choices/3/reject", "choices/3/regenerate",
    "choice_groups/3/discard", "choice_groups/3/regenerate",
    "choices/4/accept", "choice_groups/4/discard",
])
@pytest.mark.asyncio
async def test_cross_branch_operations_do_not_mutate_foreign_groups(branch_client, path):
    client, session = branch_client
    response = await client.post(f"/api/projects/project/{path}?branch=test", json={"force": True})
    assert response.status_code == 404, response.text
    assert (await session.get(ChoiceGroupModel, 3)).status == "open"
    assert (await session.get(ChoiceModel, 3)).status == "candidate"
    assert (await session.get(ChoiceGroupModel, 4)).status == "open"


@pytest.mark.parametrize("path", [
    "choices/1/accept", "choices/1/reject", "choices/1/regenerate",
    "choice_groups/1/discard", "choice_groups/1/regenerate",
])
@pytest.mark.asyncio
async def test_main_choice_operations_are_read_only(branch_client, path):
    client, session = branch_client
    response = await client.post(f"/api/projects/project/{path}?branch=main")
    assert response.status_code == 403, response.text
    assert (await session.get(ChoiceGroupModel, 1)).status == "open"


@pytest.mark.asyncio
async def test_generation_cannot_write_to_main_or_default_main(branch_client, monkeypatch):
    client, _ = branch_client
    create = AsyncMock()
    monkeypatch.setattr(routes.generation_choice_service, "create_choice_group", create)
    for query in ["", "?branch=main"]:
        response = await client.post(f"/api/generation_choice_groups{query}", json={"project_id": "project", "generation_type": "rule"})
        assert response.status_code == 403, response.text
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_generation_passes_test_workspace_to_creator(branch_client, monkeypatch):
    client, session = branch_client
    group = (await routes.choice_service.list_choice_groups(1, "open", session, workspace_id=2))[0]
    create = AsyncMock(return_value=group)
    monkeypatch.setattr(routes.generation_choice_service, "create_choice_group", create)
    response = await client.post("/api/generation_choice_groups?branch=test", json={"project_id": "project", "generation_type": "rule"})
    assert response.status_code == 200, response.text
    assert create.await_args.kwargs["workspace_id"] == 2


@pytest.mark.asyncio
async def test_acceptance_uses_owning_workspace_and_resolves_only_its_group(branch_client, monkeypatch):
    client, session = branch_client
    monkeypatch.setattr(routes.choice_service, "_check_generation_choice_staleness", AsyncMock(return_value=None))
    apply = AsyncMock(return_value={})
    monkeypatch.setattr(service_module, "get_generation_choice_applier", lambda: SimpleNamespace(apply=apply))
    response = await client.post("/api/projects/project/choices/2/accept?branch=test")
    assert response.status_code == 200, response.text
    assert apply.await_args.kwargs["workspace_id"] == 2
    assert (await session.get(ChoiceGroupModel, 2)).status == "resolved"
    assert (await session.get(ChoiceGroupModel, 1)).status == "open"
    assert (await session.get(ChoiceGroupModel, 3)).status == "open"


@pytest.mark.asyncio
async def test_service_rejects_workspace_mismatch_before_staleness_or_apply(branch_client, monkeypatch):
    _, session = branch_client
    check = AsyncMock()
    monkeypatch.setattr(routes.choice_service, "_check_generation_choice_staleness", check)
    with pytest.raises(ValueError, match="choice_group_not_found"):
        await routes.choice_service.accept_choice(1, 3, session, workspace_id=2, force=True)
    check.assert_not_awaited()
    assert (await session.get(ChoiceGroupModel, 3)).status == "open"
