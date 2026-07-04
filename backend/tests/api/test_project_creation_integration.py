# -*- coding: utf-8 -*-
import os
import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.future import select

# Configure key before main main imports
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    ProjectModel,
    KnowledgeWorkspaceModel,
    KnowledgeDocumentModel,
    KnowledgeChunkModel,
    UserLLMConfigModel,
)

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def creation_test_db():
    engine = create_async_engine(
        DATABASE_URL,
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

    app.dependency_overrides[get_session] = override_get_session
    yield session_factory
    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


async def _register_users(client, db_session_creator):
    res = client.post(
        "/api/auth/register",
        json={"email": "user_a@know.test", "password": "passwordA123"},
    )
    assert res.status_code == 200
    user_a_id = int(res.json()["id"])
    cookie_a = client.cookies.get("auth_session")
    assert cookie_a

    client.cookies.clear()

    res = client.post(
        "/api/auth/register",
        json={"email": "user_b@know.test", "password": "passwordB123"},
    )
    assert res.status_code == 200
    user_b_id = int(res.json()["id"])
    cookie_b = client.cookies.get("auth_session")
    assert cookie_b

    # Seed UserLLMConfigModel for both users
    from backend.core.security.encryption import encrypt_llm_api_key
    async with db_session_creator() as session:
        config_a = UserLLMConfigModel(
            user_id=user_a_id,
            api_url="http://mock-llm.api/v1",
            encrypted_api_key=encrypt_llm_api_key("mocked-api-key"),
            api_key_last4="4321",
            model_name="mock-model",
        )
        config_b = UserLLMConfigModel(
            user_id=user_b_id,
            api_url="http://mock-llm.api/v1",
            encrypted_api_key=encrypt_llm_api_key("mocked-api-key"),
            api_key_last4="4321",
            model_name="mock-model",
        )
        session.add(config_a)
        session.add(config_b)
        await session.commit()

    return user_a_id, cookie_a, user_b_id, cookie_b


async def mock_call_llm_factory(prompt_tracker=None):
    async def mock_call_llm(prompt, query=None, print_log=False):
        if prompt_tracker is not None:
            prompt_tracker.append(prompt)

        if "你是一个善于分析目标系统参与者" in prompt:
            return json.dumps({
                "actors": [
                    {
                        "actor_name": "Mocked Actor",
                        "actor_description": "Mocked Actor Description"
                    }
                ]
            })
        elif "你是一个善于分析项目需求的需求工程师" in prompt and "特征树" in prompt:
            return json.dumps({
                "features": [
                    {
                        "feature_number": "F001",
                        "feature_name": "Mocked Root Feature",
                        "feature_description": "Mocked Root Feature Description",
                        "actor_ids": [1]
                    }
                ]
            })
        elif "你是一个善于分析用户需求的需求工程师" in prompt:
            return json.dumps({
                "project_name": "Mocked Project Name",
                "project_description": "Mocked Project Description"
            })
        return "{}"
    return mock_call_llm


@pytest.mark.anyio
async def test_project_creation_without_workspace(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, _, _ = await _register_users(client, creation_test_db)

    client.cookies.set("auth_session", cookie_a)

    mock_llm = await mock_call_llm_factory()
    with patch("backend.services.LLM_service.LLMHandler.call_llm", new_callable=AsyncMock, side_effect=mock_llm):
        # 1. Create creation draft without workspace_id
        res = client.post(
            "/api/project_creation_drafts",
            json={"user_requirements": "Test project requirements"}
        )
        assert res.status_code == 200
        draft_data = res.json()
        assert "draft_id" in draft_data
        draft_id = draft_data["draft_id"]

        # 2. Confirm creation draft
        confirm_res = client.post(f"/api/project_creation_drafts/{draft_id}/confirm")
        assert confirm_res.status_code == 200
        confirm_data = confirm_res.json()
        assert confirm_data["message"] == "project_created"
        assert "project_id" in confirm_data


@pytest.mark.anyio
async def test_project_creation_with_nonexistent_workspace(creation_test_db):
    client = TestClient(app)
    _, cookie_a, _, _ = await _register_users(client, creation_test_db)

    client.cookies.set("auth_session", cookie_a)

    res = client.post(
        "/api/project_creation_drafts",
        json={
            "user_requirements": "Test requirements",
            "knowledge_workspace_id": "nonexistent-uuid"
        }
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "workspace_not_found"


@pytest.mark.anyio
async def test_project_creation_with_another_users_workspace(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = await _register_users(client, creation_test_db)

    # User A creates a workspace
    client.cookies.set("auth_session", cookie_a)
    ws_res = client.post("/api/knowledge_workspaces")
    assert ws_res.status_code == 201
    workspace_public_id = ws_res.json()["public_id"]

    # User B tries to use A's workspace in project creation
    client.cookies.set("auth_session", cookie_b)
    res = client.post(
        "/api/project_creation_drafts",
        json={
            "user_requirements": "Test requirements",
            "knowledge_workspace_id": workspace_public_id
        }
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "forbidden"


@pytest.mark.anyio
async def test_project_creation_with_inactive_workspace(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, _, _ = await _register_users(client, creation_test_db)

    # User A creates a workspace
    client.cookies.set("auth_session", cookie_a)
    ws_res = client.post("/api/knowledge_workspaces")
    assert ws_res.status_code == 201
    workspace_public_id = ws_res.json()["public_id"]

    # Explicitly set workspace status to 'attached' in DB
    async with creation_test_db() as session:
        ws_res = await session.execute(
            select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.public_id == workspace_public_id)
        )
        ws = ws_res.scalar_one()
        ws.status = "attached"
        await session.commit()

    # User A tries to use the attached workspace to create draft
    res = client.post(
        "/api/project_creation_drafts",
        json={
            "user_requirements": "Test requirements",
            "knowledge_workspace_id": workspace_public_id
        }
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "workspace_inactive"


@pytest.mark.anyio
async def test_project_creation_with_active_workspace_empty_documents(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, _, _ = await _register_users(client, creation_test_db)

    client.cookies.set("auth_session", cookie_a)
    ws_res = client.post("/api/knowledge_workspaces")
    workspace_public_id = ws_res.json()["public_id"]

    mock_llm = await mock_call_llm_factory()
    with patch("backend.services.LLM_service.LLMHandler.call_llm", new_callable=AsyncMock, side_effect=mock_llm):
        res = client.post(
            "/api/project_creation_drafts",
            json={
                "user_requirements": "Test requirements",
                "knowledge_workspace_id": workspace_public_id
            }
        )
        assert res.status_code == 200
        draft_data = res.json()
        assert "draft_id" in draft_data


@pytest.mark.anyio
async def test_project_creation_with_active_workspace_having_documents(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, _, _ = await _register_users(client, creation_test_db)

    client.cookies.set("auth_session", cookie_a)
    ws_res = client.post("/api/knowledge_workspaces")
    workspace_public_id = ws_res.json()["public_id"]

    # Insert ready document and chunk directly to workspace in DB
    async with creation_test_db() as session:
        ws_res = await session.execute(
            select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.public_id == workspace_public_id)
        )
        ws = ws_res.scalar_one()
        ws_id = ws.id

        doc = KnowledgeDocumentModel(
            workspace_id=ws_id,
            owner_user_id=user_a_id,
            original_filename="refund.md",
            content_type="text/markdown",
            file_size=100,
            sha256="sha256hash",
            storage_path="path/refund.md",
            markdown_path="path/refund.md",
            status="ready",
            ai_enabled=True,
        )
        session.add(doc)
        await session.flush()

        chunk = KnowledgeChunkModel(
            workspace_id=ws_id,
            document_id=doc.id,
            chunk_index=0,
            heading_path="Refund Rule",
            text="The system must support refund requests.",
            token_estimate=50,
        )
        session.add(chunk)
        await session.commit()

    # Track prompt to check if knowledge context was injected
    tracker = []
    mock_llm = await mock_call_llm_factory(tracker)
    with patch("backend.services.LLM_service.LLMHandler.call_llm", new_callable=AsyncMock, side_effect=mock_llm):
        # 1. Create creation draft with workspace
        res = client.post(
            "/api/project_creation_drafts",
            json={
                "user_requirements": "Require refund functionality",
                "knowledge_workspace_id": workspace_public_id
            }
        )
        assert res.status_code == 200
        draft_data = res.json()
        draft_id = draft_data["draft_id"]

        # Check prompt tracker to verify knowledge context was injected
        prompt_with_context = False
        for p in tracker:
            if "The system must support refund requests" in p and "Refund Rule" in p:
                prompt_with_context = True
                break
        assert prompt_with_context, "Knowledge base context was not injected into generator prompts!"

        # 2. Confirm creation draft -> bindings should occur
        confirm_res = client.post(f"/api/project_creation_drafts/{draft_id}/confirm")
        assert confirm_res.status_code == 200
        confirm_data = confirm_res.json()
        project_public_id = confirm_data["project_id"]

        # 3. Verify DB bindings
        async with creation_test_db() as session:
            # Check project
            proj_res = await session.execute(
                select(ProjectModel).where(ProjectModel.public_id == project_public_id)
            )
            proj = proj_res.scalar_one()
            proj_id = proj.id

            # Check workspace
            ws_res_after = await session.execute(
                select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.id == ws_id)
            )
            ws_after = ws_res_after.scalar_one()
            assert ws_after.status == "attached"
            assert ws_after.project_id == proj_id

            # Check documents project_id binding
            doc_res = await session.execute(
                select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.workspace_id == ws_id)
            )
            doc_after = doc_res.scalar_one()
            assert doc_after.project_id == proj_id

            # Check chunks project_id binding
            chunk_res = await session.execute(
                select(KnowledgeChunkModel).where(KnowledgeChunkModel.workspace_id == ws_id)
            )
            chunk_after = chunk_res.scalar_one()
            assert chunk_after.project_id == proj_id


@pytest.mark.anyio
async def test_project_creation_with_discard_draft(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, _, _ = await _register_users(client, creation_test_db)

    client.cookies.set("auth_session", cookie_a)
    ws_res = client.post("/api/knowledge_workspaces")
    workspace_public_id = ws_res.json()["public_id"]

    # Insert ready document
    async with creation_test_db() as session:
        ws_res = await session.execute(
            select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.public_id == workspace_public_id)
        )
        ws = ws_res.scalar_one()
        ws_id = ws.id

        doc = KnowledgeDocumentModel(
            workspace_id=ws_id,
            owner_user_id=user_a_id,
            original_filename="doc.md",
            content_type="text/markdown",
            file_size=10,
            sha256="sha256hash",
            storage_path="path/doc.md",
            markdown_path="path/doc.md",
            status="ready",
            ai_enabled=True,
        )
        session.add(doc)
        await session.commit()

    mock_llm = await mock_call_llm_factory()
    with patch("backend.services.LLM_service.LLMHandler.call_llm", new_callable=AsyncMock, side_effect=mock_llm):
        # 1. Create creation draft
        res = client.post(
            "/api/project_creation_drafts",
            json={
                "user_requirements": "Requirements info",
                "knowledge_workspace_id": workspace_public_id
            }
        )
        assert res.status_code == 200
        draft_id = res.json()["draft_id"]

        # 2. Discard draft
        discard_res = client.delete(f"/api/project_creation_drafts/{draft_id}")
        assert discard_res.status_code == 200

        # 3. Verify workspace remains active, project_id is not set, document remains unbound
        async with creation_test_db() as session:
            ws_res_after = await session.execute(
                select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.id == ws_id)
            )
            ws_after = ws_res_after.scalar_one()
            assert ws_after.status == "active"
            assert ws_after.project_id is None

            doc_res = await session.execute(
                select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.workspace_id == ws_id)
            )
            doc_after = doc_res.scalar_one()
            assert doc_after.project_id is None


@pytest.mark.anyio
async def test_skill_backed_generator_signature_compatibility():
    from unittest.mock import MagicMock
    from backend.integration.skill_backed_services.project_creation_service import SkillBackedActorFeaturePreviewGenerator
    
    # Mock import_skill_module
    with patch("backend.integration.skill_backed_services.project_creation_service.import_skill_module") as mock_import:
        mock_core = MagicMock()
        mock_import.return_value = mock_core
        mock_nl2 = MagicMock()
        mock_core.NL2FeaturesGeneration.return_value = mock_nl2
        mock_nl2._build_prompt.return_value = "mock prompt"
        
        generator = SkillBackedActorFeaturePreviewGenerator()
        
        with patch.object(generator._actors_generator, "generate", new_callable=AsyncMock) as mock_actors, \
             patch.object(generator._llm_json_client, "ask_json", new_callable=AsyncMock) as mock_ask_json:
             
            mock_actors.return_value = {
                "actors": [
                    {
                        "actor_name": "Test Actor",
                        "actor_description": "Test Description"
                    }
                ]
            }
            
            mock_ask_json.return_value = {
                "L1": "Mocked System"
            }
            
            res = await generator.generate_actor_and_feature_previews(
                user_requirements="Requirement test text",
                user_feedback=None,
                knowledge_context="My Knowledge Context"
            )
            
            # Assertions
            assert len(res) == 4
            mock_actors.assert_called_once()
            args, kwargs = mock_actors.call_args
            assert args[0].knowledge_context == "My Knowledge Context"
            
            mock_nl2._build_prompt.assert_called_once()
            prompt_req_text = mock_nl2._build_prompt.call_args[0][0]
            assert "My Knowledge Context" in prompt_req_text


@pytest.mark.anyio
async def test_project_creation_blank_path_binds_workspace(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = await _register_users(client, creation_test_db)

    # 1. Create a workspace, document and chunk
    async with creation_test_db() as session:
        ws = KnowledgeWorkspaceModel(
            public_id="ws_blank_test",
            owner_user_id=user_a_id,
            status="active"
        )
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        ws_id = ws.id

        doc = KnowledgeDocumentModel(
            public_id="doc_blank_test",
            workspace_id=ws_id,
            owner_user_id=user_a_id,
            original_filename="ref.txt",
            content_type="text/plain",
            file_size=100,
            sha256="abc",
            storage_path="ref.txt",
            status="ready",
            ai_enabled=True
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

        chunk = KnowledgeChunkModel(
            document_id=doc_id,
            workspace_id=ws_id,
            chunk_index=0,
            heading_path="h1",
            text="some body",
        )
        session.add(chunk)
        await session.commit()

    # 2. Call blank project endpoint with knowledge_workspace_id
    client.cookies.set("auth_session", cookie_a)
    with patch("backend.core.generators.blank_project_generator.BlankProjectGenerator.generate", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {
            "project_name": "Blank Test Project Name",
            "project_description": "Blank Test Desc"
        }
        res = client.post(
            "/api/blank_projects",
            json={
                "user_requirements": "TestRequirements",
                "knowledge_workspace_id": "ws_blank_test"
            }
        )
        assert res.status_code == 200
        proj_id = res.json()["project_id"]

    # 3. Assert workspace is attached and project_id is set
    async with creation_test_db() as session:
        # Verify project is created
        proj_res = await session.execute(
            select(ProjectModel).where(ProjectModel.public_id == proj_id)
        )
        proj = proj_res.scalar_one()

        ws_res = await session.execute(
            select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.id == ws_id)
        )
        ws_after = ws_res.scalar_one()
        assert ws_after.status == "attached"
        assert ws_after.project_id == proj.id

        doc_res = await session.execute(
            select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == doc_id)
        )
        doc_after = doc_res.scalar_one()
        assert doc_after.project_id == proj.id

        chunk_res = await session.execute(
            select(KnowledgeChunkModel).where(KnowledgeChunkModel.workspace_id == ws_id)
        )
        chunk_after = chunk_res.scalar_one()
        assert chunk_after.project_id == proj.id


@pytest.mark.anyio
async def test_project_creation_blank_path_rejects_foreign_workspace(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = await _register_users(client, creation_test_db)

    async with creation_test_db() as session:
        ws = KnowledgeWorkspaceModel(
            public_id="ws_blank_foreign_test",
            owner_user_id=user_a_id,
            status="active",
        )
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        ws_id = ws.id

    client.cookies.set("auth_session", cookie_b)
    res = client.post(
        "/api/blank_projects",
        json={
            "user_requirements": "TestRequirements",
            "project_name": "No Bind",
            "project_description": "Should fail",
            "knowledge_workspace_id": "ws_blank_foreign_test",
        },
    )
    assert res.status_code == 403

    async with creation_test_db() as session:
        ws_after = await session.get(KnowledgeWorkspaceModel, ws_id)
        assert ws_after.status == "active"
        assert ws_after.project_id is None


@pytest.mark.anyio
async def test_project_creation_choice_accept_binds_workspace(creation_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = await _register_users(client, creation_test_db)

    # 1. Create a workspace, document and chunk
    async with creation_test_db() as session:
        ws = KnowledgeWorkspaceModel(
            public_id="ws_choice_test",
            owner_user_id=user_a_id,
            status="active"
        )
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        ws_id = ws.id

        doc = KnowledgeDocumentModel(
            public_id="doc_choice_test",
            workspace_id=ws_id,
            owner_user_id=user_a_id,
            original_filename="ref.txt",
            content_type="text/plain",
            file_size=100,
            sha256="abc",
            storage_path="ref.txt",
            status="ready",
            ai_enabled=True
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

        chunk = KnowledgeChunkModel(
            document_id=doc_id,
            workspace_id=ws_id,
            chunk_index=0,
            heading_path="h1",
            text="some body",
        )
        session.add(chunk)
        await session.commit()

    # 2. Mock choice group preview generation
    with patch("backend.api.modules.project_lifecycle.application.creation_service.LocalActorFeaturePreviewGenerator.generate_actor_and_feature_previews", new_callable=AsyncMock) as mock_actor_feat, \
         patch("backend.api.modules.project_lifecycle.application.creation_service.ProjectCreationService._generate_project_preview", new_callable=AsyncMock) as mock_proj_preview:
        
        mock_proj_preview.return_value = {
            "project_name": "Choice Test Project Name",
            "project_description": "Choice Test Desc"
        }
        
        mock_actor_feat.return_value = (
            # actor_previews_for_draft
            [{"actor_number": "A001", "actor_name": "Actor A", "actor_description": "Desc A"}],
            # actor_previews_for_response
            [{"actor_number": "A001", "actor_name": "Actor A", "actor_description": "Desc A"}],
            # feature_previews_for_draft
            [{"feature_number": "F001", "feature_name": "Feat A", "feature_description": "Desc Feat", "actor_numbers": []}],
            # feature_previews_for_response
            [{"feature_number": "F001", "feature_name": "Feat A", "feature_description": "Desc Feat", "actor_numbers": []}],
        )

        client.cookies.set("auth_session", cookie_a)
        res = client.post(
            "/api/project_creation_choice_groups",
            json={
                "user_requirements": "Choice Requirements",
                "knowledge_workspace_id": "ws_choice_test",
                "candidate_count": 1
            }
        )
        assert res.status_code == 200
        group_id = res.json()["id"]
        choice_id = res.json()["choices"][0]["id"]

    # 3. Accept choice
    accept_res = client.post(
        f"/api/project_creation_choice_groups/{group_id}/choices/{choice_id}/accept"
    )
    assert accept_res.status_code == 200
    proj_id = accept_res.json()["projectId"]

    # 4. Assert workspace is attached and project_id is set
    async with creation_test_db() as session:
        proj_res = await session.execute(
            select(ProjectModel).where(ProjectModel.public_id == proj_id)
        )
        proj = proj_res.scalar_one()

        ws_res = await session.execute(
            select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.id == ws_id)
        )
        ws_after = ws_res.scalar_one()
        assert ws_after.status == "attached"
        assert ws_after.project_id == proj.id

        doc_res = await session.execute(
            select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == doc_id)
        )
        doc_after = doc_res.scalar_one()
        assert doc_after.project_id == proj.id

        chunk_res = await session.execute(
            select(KnowledgeChunkModel).where(KnowledgeChunkModel.workspace_id == ws_id)
        )
        chunk_after = chunk_res.scalar_one()
        assert chunk_after.project_id == proj.id
