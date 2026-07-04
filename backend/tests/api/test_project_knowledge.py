import os
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Configure key before import
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    ProjectModel,
    ProjectMemberModel,
    ProjectMemberRole,
    ProjectMemberStatus,
    KnowledgeWorkspaceModel,
    KnowledgeDocumentModel,
)

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def knowledge_test_db():
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


def _register_users(client):
    """Register two users and return (user_a_id, cookie_a, user_b_id, cookie_b)."""
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

    return user_a_id, cookie_a, user_b_id, cookie_b


def test_knowledge_workspace_creation_and_upload_flow(knowledge_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    # 1. User A creates a workspace
    client.cookies.set("auth_session", cookie_a)
    res = client.post("/api/knowledge_workspaces")
    assert res.status_code == 201
    workspace_data = res.json()
    workspace_public_id = workspace_data["public_id"]
    assert workspace_data["owner_user_id"] == user_a_id
    assert workspace_data["status"] == "active"

    # 2. User B tries to view/upload to A's workspace -> gets 404
    client.cookies.set("auth_session", cookie_b)
    res = client.get(f"/api/knowledge_workspaces/{workspace_public_id}/documents")
    assert res.status_code == 404

    file_payload = {
        "file": ("test.docx", b"dummy word content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    }
    res = client.post(
        f"/api/knowledge_workspaces/{workspace_public_id}/documents",
        files=file_payload,
    )
    assert res.status_code == 404

    # 3. User A uploads file successfully
    client.cookies.set("auth_session", cookie_a)
    res = client.post(
        f"/api/knowledge_workspaces/{workspace_public_id}/documents",
        files=file_payload,
    )
    assert res.status_code == 201
    doc_data = res.json()
    doc_public_id = doc_data["public_id"]
    assert doc_data["original_filename"] == "test.docx"
    assert doc_data["status"] == "uploaded"
    assert doc_data["ai_enabled"] is True

    # 4. User A uploads invalid extension -> gets 400
    invalid_file = {"file": ("test.exe", b"binary", "application/octet-stream")}
    res = client.post(
        f"/api/knowledge_workspaces/{workspace_public_id}/documents",
        files=invalid_file,
    )
    assert res.status_code == 400

    # 5. User A lists documents
    res = client.get(f"/api/knowledge_workspaces/{workspace_public_id}/documents")
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) == 1
    assert docs[0]["public_id"] == doc_public_id

    # 5b. User B tries to retry User A's workspace document -> 404
    client.cookies.set("auth_session", cookie_b)
    res = client.post(f"/api/knowledge_workspaces/{workspace_public_id}/documents/{doc_public_id}/retry")
    assert res.status_code == 404

    # 5c. User A retries workspace document -> 200
    client.cookies.set("auth_session", cookie_a)
    res = client.post(f"/api/knowledge_workspaces/{workspace_public_id}/documents/{doc_public_id}/retry")
    assert res.status_code == 200
    assert res.json()["status"] == "uploaded"

    # Seed mock chunk directly to DB to test cleanup logic
    import asyncio
    from sqlalchemy import select
    from backend.database.model import KnowledgeChunkModel
    async def seed_chunk():
        async with knowledge_test_db() as db_session:
            doc_res = await db_session.execute(
                select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.public_id == doc_public_id)
            )
            doc_obj = doc_res.scalar_one()
            doc_id = doc_obj.id
            chunk = KnowledgeChunkModel(
                document_id=doc_id,
                chunk_index=0,
                heading_path="test_h",
                text="test_body",
            )
            db_session.add(chunk)
            await db_session.commit()
            return doc_id

    loop = asyncio.get_event_loop()
    doc_id = loop.run_until_complete(seed_chunk())

    # 6. User B tries to delete A's document -> 404
    client.cookies.set("auth_session", cookie_b)
    res = client.delete(f"/api/knowledge_workspaces/{workspace_public_id}/documents/{doc_public_id}")
    assert res.status_code == 404

    # 7. User A deletes document
    client.cookies.set("auth_session", cookie_a)
    res = client.delete(f"/api/knowledge_workspaces/{workspace_public_id}/documents/{doc_public_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "document_deleted"

    # Verify associated chunks are deleted
    async def verify_chunks_deleted():
        async with knowledge_test_db() as db_session:
            chunk_res = await db_session.execute(
                select(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == doc_id)
            )
            assert len(chunk_res.scalars().all()) == 0

    loop.run_until_complete(verify_chunks_deleted())

    # 8. Check document is soft-deleted
    res = client.get(f"/api/knowledge_workspaces/{workspace_public_id}/documents")
    assert res.status_code == 200
    assert len(res.json()) == 0


def test_project_knowledge_permissions_and_lifecycle(knowledge_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    # 1. User A creates a project by seeding it directly in DB
    import asyncio
    async def seed_project():
        async with knowledge_test_db() as session:
            p = ProjectModel(
                name="Project A",
                description="CMS system",
                owner_user_id=user_a_id,
                user_requirements="Building a custom CMS system",
            )
            session.add(p)
            await session.commit()
            return p.public_id

    project_public_id = asyncio.run(seed_project())

    # 2. User B tries to access Project A knowledge -> 404 (non-member)
    client.cookies.set("auth_session", cookie_b)
    res = client.get(f"/api/projects/{project_public_id}/knowledge/documents")
    assert res.status_code == 404

    # 3. User A uploads file to Project A
    client.cookies.set("auth_session", cookie_a)
    file_payload = {"file": ("prd.pdf", b"pdf content", "application/pdf")}
    res = client.post(
        f"/api/projects/{project_public_id}/knowledge/documents",
        files=file_payload,
    )
    assert res.status_code == 201
    doc_data = res.json()
    doc_public_id = doc_data["public_id"]
    assert doc_data["original_filename"] == "prd.pdf"

    # 4. User A disables AI participation
    patch_res = client.patch(
        f"/api/projects/{project_public_id}/knowledge/documents/{doc_public_id}",
        json={"ai_enabled": False},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["ai_enabled"] is False

    # 5. User A retries processing (resets status to uploaded)
    retry_res = client.post(
        f"/api/projects/{project_public_id}/knowledge/documents/{doc_public_id}/retry"
    )
    assert retry_res.status_code == 200
    assert retry_res.json()["status"] == "uploaded"

    # 6. Add User B to Project A as a Viewer
    # Direct database insert to save time/routes mocking
    async def add_member():
        async with knowledge_test_db() as session:
            from sqlalchemy import select
            # get project id
            proj = (await session.execute(select(ProjectModel).where(ProjectModel.public_id == project_public_id))).scalar_one()
            member = ProjectMemberModel(
                project_id=proj.id,
                user_id=user_b_id,
                role=ProjectMemberRole.VIEWER.value,
                status=ProjectMemberStatus.ACTIVE.value,
            )
            session.add(member)
            await session.commit()
    
    import asyncio
    asyncio.run(add_member())

    # 7. User B tries to view documents -> succeeds
    client.cookies.set("auth_session", cookie_b)
    res = client.get(f"/api/projects/{project_public_id}/knowledge/documents")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # 8. User B (viewer) tries to upload/delete -> fails with 403
    res = client.post(
        f"/api/projects/{project_public_id}/knowledge/documents",
        files=file_payload,
    )
    assert res.status_code == 403

    res = client.delete(f"/api/projects/{project_public_id}/knowledge/documents/{doc_public_id}")
    assert res.status_code == 403

    # 9. User A (owner) deletes document -> succeeds
    client.cookies.set("auth_session", cookie_a)
    res = client.delete(f"/api/projects/{project_public_id}/knowledge/documents/{doc_public_id}")
    assert res.status_code == 200


def test_project_knowledge_detailed_permissions(knowledge_test_db):
    client = TestClient(app)
    # Register 3 users:
    # user_a (project owner),
    # user_b (project editor),
    # user_c (another project editor)
    res = client.post("/api/auth/register", json={"email": "user_a@perm.test", "password": "passwordA123"})
    user_a_id = res.json()["id"]
    cookie_a = client.cookies.get("auth_session")
    
    client.cookies.clear()
    res = client.post("/api/auth/register", json={"email": "user_b@perm.test", "password": "passwordB123"})
    user_b_id = res.json()["id"]
    cookie_b = client.cookies.get("auth_session")
    
    client.cookies.clear()
    res = client.post("/api/auth/register", json={"email": "user_c@perm.test", "password": "passwordC123"})
    user_c_id = res.json()["id"]
    cookie_c = client.cookies.get("auth_session")

    # Create two projects: Project A (owned by A), Project B (owned by B)
    import asyncio
    async def seed():
        async with knowledge_test_db() as session:
            pa = ProjectModel(name="Project A", description="", owner_user_id=user_a_id, user_requirements="req")
            pb = ProjectModel(name="Project B", description="", owner_user_id=user_b_id, user_requirements="req")
            session.add_all([pa, pb])
            await session.flush()
            
            # Add user_b to Project A as editor
            mb = ProjectMemberModel(
                project_id=pa.id,
                user_id=user_b_id,
                role=ProjectMemberRole.EDITOR.value,
                status=ProjectMemberStatus.ACTIVE.value,
            )
            session.add(mb)
            await session.commit()
            return pa.public_id, pb.public_id

    project_a_public_id, project_b_public_id = asyncio.run(seed())

    # User B (editor in Project A) uploads a file to Project A
    client.cookies.set("auth_session", cookie_b)
    file_payload = {"file": ("editor_file.txt", b"editor file content", "text/plain")}
    res = client.post(
        f"/api/projects/{project_a_public_id}/knowledge/documents",
        files=file_payload,
    )
    assert res.status_code == 201
    doc_data = res.json()
    doc_public_id = doc_data["public_id"]

    # 1. Mismatch check: try to access doc of Project A using Project B's ID in URL
    # GET Project B knowledge list doesn't include Project A doc
    res = client.get(f"/api/projects/{project_b_public_id}/knowledge/documents")
    assert res.status_code == 200
    assert doc_public_id not in [d["public_id"] for d in res.json()]

    # Patch doc using Project B's ID -> 404
    res = client.patch(
        f"/api/projects/{project_b_public_id}/knowledge/documents/{doc_public_id}",
        json={"ai_enabled": False},
    )
    assert res.status_code == 404

    # Retry doc using Project B's ID -> 404
    res = client.post(f"/api/projects/{project_b_public_id}/knowledge/documents/{doc_public_id}/retry")
    assert res.status_code == 404

    # Delete doc using Project B's ID -> 404
    res = client.delete(f"/api/projects/{project_b_public_id}/knowledge/documents/{doc_public_id}")
    assert res.status_code == 404

    # 2. Deletion permission checks:
    # Add User C to Project A as editor
    async def add_editor_c():
        async with knowledge_test_db() as session:
            from sqlalchemy import select
            proj = (await session.execute(select(ProjectModel).where(ProjectModel.public_id == project_a_public_id))).scalar_one()
            mc = ProjectMemberModel(
                project_id=proj.id,
                user_id=user_c_id,
                role=ProjectMemberRole.EDITOR.value,
                status=ProjectMemberStatus.ACTIVE.value,
            )
            session.add(mc)
            await session.commit()
    asyncio.run(add_editor_c())

    # User C (another editor, non-uploader) tries to delete B's document -> 403
    client.cookies.set("auth_session", cookie_c)
    res = client.delete(f"/api/projects/{project_a_public_id}/knowledge/documents/{doc_public_id}")
    assert res.status_code == 403

    # User A (project owner, non-uploader) deletes B's document -> 200 (succeeds)
    client.cookies.set("auth_session", cookie_a)
    res = client.delete(f"/api/projects/{project_a_public_id}/knowledge/documents/{doc_public_id}")
    assert res.status_code == 200

    # 3. Deleted document retry/patch checks:
    # Now doc_public_id is deleted. Attempting retry/patch on it -> 404
    client.cookies.set("auth_session", cookie_b)
    res = client.post(f"/api/projects/{project_a_public_id}/knowledge/documents/{doc_public_id}/retry")
    assert res.status_code == 404

    res = client.patch(
        f"/api/projects/{project_a_public_id}/knowledge/documents/{doc_public_id}",
        json={"ai_enabled": True},
    )
    assert res.status_code == 404


def test_document_conversion_pipeline(knowledge_test_db):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    # User A creates a workspace
    client.cookies.set("auth_session", cookie_a)
    res = client.post("/api/knowledge_workspaces")
    workspace_public_id = res.json()["public_id"]

    # 1. Test real (unmocked) conversion of a plain text file (.txt)
    real_payload = {
        "file": ("notes.txt", b"Hello, this is a plain text file for knowledge source.\n\n\n\nDouble spacing.", "text/plain")
    }
    res = client.post(
        f"/api/knowledge_workspaces/{workspace_public_id}/documents",
        files=real_payload,
    )
    assert res.status_code == 201
    real_doc_public_id = res.json()["public_id"]

    # Fetch document list to verify success
    res_list = client.get(f"/api/knowledge_workspaces/{workspace_public_id}/documents")
    assert res_list.status_code == 200
    docs_dict = {d["public_id"]: d for d in res_list.json()}
    assert docs_dict[real_doc_public_id]["status"] == "ready"

    # Verify Markdown file on disk and metadata headers
    import asyncio
    async def get_doc_db(pub_id):
        async with knowledge_test_db() as session:
            from sqlalchemy import select
            return (await session.execute(
                select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.public_id == pub_id)
            )).scalar_one()
    doc_model = asyncio.run(get_doc_db(real_doc_public_id))
    md_path = doc_model.markdown_path
    assert md_path is not None
    assert os.path.exists(md_path)
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    assert "original_filename: notes.txt" in md_text
    assert "converted_at: " in md_text
    assert "Hello, this is a plain text file for knowledge source." in md_text
    # Verify clean_markdown merged duplicate empty lines
    assert "\n\n\n" not in md_text

    # 2. Test successful conversion of multiple formats (.docx, .pdf, .xlsx, .md, .txt) using mocks
    from unittest.mock import MagicMock, patch
    class MockResult:
        def __init__(self, text):
            self.text_content = text

    mock_convert = MagicMock(return_value=MockResult("Successfully converted content\n\n\n\nDouble spacing."))

    with patch("markitdown.MarkItDown.convert", mock_convert):
        for ext, content_type in [
            (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (".pdf", "application/pdf"),
            (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            (".md", "text/markdown"),
            (".txt", "text/plain")
        ]:
            file_payload = {
                "file": (f"test_file{ext}", b"dummy content bytes", content_type)
            }
            res = client.post(
                f"/api/knowledge_workspaces/{workspace_public_id}/documents",
                files=file_payload,
            )
            assert res.status_code == 201
            doc_data = res.json()
            doc_public_id = doc_data["public_id"]
            assert doc_data["status"] == "uploaded"

            # Fetch document list to verify success
            res_list = client.get(f"/api/knowledge_workspaces/{workspace_public_id}/documents")
            assert res_list.status_code == 200
            docs_dict = {d["public_id"]: d for d in res_list.json()}
            assert docs_dict[doc_public_id]["status"] == "ready"

            # Verify Markdown file on disk and metadata headers
            # Fetch from DB directly as markdown_path is omitted in public API response for security
            import asyncio
            async def get_doc_db(pub_id):
                async with knowledge_test_db() as session:
                    from sqlalchemy import select
                    return (await session.execute(
                        select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.public_id == pub_id)
                    )).scalar_one()
            doc_model = asyncio.run(get_doc_db(doc_public_id))
            md_path = doc_model.markdown_path

            assert md_path is not None
            assert os.path.exists(md_path)
            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()

            assert f"original_filename: test_file{ext}" in md_text
            assert "converted_at: " in md_text
            assert "Successfully converted content" in md_text
            # Verify clean_markdown merged duplicate empty lines
            assert "\n\n\n" not in md_text

    # 2. Test failed conversion of invalid document
    from unittest.mock import patch
    with patch("markitdown.MarkItDown.convert", side_effect=ValueError("Mocked conversion error")):
        fail_payload = {
            "file": ("corrupt.docx", b"this is not a valid docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        res = client.post(
            f"/api/knowledge_workspaces/{workspace_public_id}/documents",
            files=fail_payload,
        )
        assert res.status_code == 201
        fail_doc_public_id = res.json()["public_id"]

        # Fetch to verify conversion failed
        res = client.get(f"/api/knowledge_workspaces/{workspace_public_id}/documents")
        docs_dict = {d["public_id"]: d for d in res.json()}
        assert docs_dict[fail_doc_public_id]["status"] == "failed"
        assert "Mocked conversion error" in docs_dict[fail_doc_public_id]["error_message"]

        # 3. Test retry mechanism
        import asyncio
        async def seed_project():
            async with knowledge_test_db() as session:
                p = ProjectModel(
                    name="Project for Conversion",
                    description="CMS",
                    owner_user_id=user_a_id,
                    user_requirements="reqs",
                )
                session.add(p)
                await session.commit()
                return p.public_id

        project_public_id = asyncio.run(seed_project())

        # Upload invalid file to project (should fail due to mock)
        res = client.post(
            f"/api/projects/{project_public_id}/knowledge/documents",
            files=fail_payload,
        )
        assert res.status_code == 201
        proj_doc_public_id = res.json()["public_id"]

        # Verify it failed
        res = client.get(f"/api/projects/{project_public_id}/knowledge/documents")
        docs_dict = {d["public_id"]: d for d in res.json()}
        assert docs_dict[proj_doc_public_id]["status"] == "failed"

        # Retry document (should fail again due to mock)
        res = client.post(f"/api/projects/{project_public_id}/knowledge/documents/{proj_doc_public_id}/retry")
        assert res.status_code == 200
        assert res.json()["status"] == "uploaded"

        # Verify after background execution it is failed again
        res = client.get(f"/api/projects/{project_public_id}/knowledge/documents")
        docs_dict = {d["public_id"]: d for d in res.json()}
        assert docs_dict[proj_doc_public_id]["status"] == "failed"


def test_project_knowledge_storage_limit(knowledge_test_db, monkeypatch):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    # Set storage limit config to 1MB for testing
    import backend.core.config as config
    monkeypatch.setattr(config, "KNOWLEDGE_MAX_PROJECT_STORAGE_MB", 1)
    monkeypatch.setattr(config, "KNOWLEDGE_MAX_FILE_SIZE_MB", 2)

    # Direct seed a project
    import asyncio
    async def seed_project():
        async with knowledge_test_db() as session:
            p = ProjectModel(
                name="Project Limit",
                description="CMS",
                owner_user_id=user_a_id,
                user_requirements="reqs",
            )
            session.add(p)
            await session.commit()
            return p.public_id

    project_public_id = asyncio.run(seed_project())

    # Try uploading a file that is 1.1MB -> should be rejected before upload
    client.cookies.set("auth_session", cookie_a)
    large_payload = {
        "file": ("large.txt", b"x" * (1024 * 1024 + 100), "text/plain")
    }
    
    res = client.post(
        f"/api/projects/{project_public_id}/knowledge/documents",
        files=large_payload,
    )
    assert res.status_code == 400
    assert "storage_limit_exceeded" in res.json()["detail"]


def test_project_knowledge_feature_flag_disabled(knowledge_test_db, monkeypatch):
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    # Disable KNOWLEDGE_BASE_ENABLED
    import backend.core.config as config
    monkeypatch.setattr(config, "KNOWLEDGE_BASE_ENABLED", False)

    # 1. Config endpoint should return enabled: False
    res = client.get("/api/knowledge/config")
    assert res.status_code == 200
    assert res.json()["enabled"] is False

    # 2. Workspace creation endpoint should return 403 Forbidden
    client.cookies.set("auth_session", cookie_a)
    res = client.post("/api/knowledge_workspaces")
    assert res.status_code == 403
    assert res.json()["detail"] == "knowledge_base_disabled"
