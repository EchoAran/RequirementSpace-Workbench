import os
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set up encryption key for security settings before main import
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import ProjectModel
from backend.api.dependencies.llm import get_llm_context
from backend.api.modules.preview_convergence.public import PrototypePreviewResponse, PrototypePageResponse

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session_factory.created_sessions = []

    async def override_get_session():
        async with session_factory() as session:
            session_factory.created_sessions.append(session)
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


@pytest.fixture
async def client_with_auth(test_db):
    client = TestClient(app)
    
    # Override get_llm_context to bypass LLM configuration checks
    async def override_get_llm_context():
        yield None
        
    app.dependency_overrides[get_llm_context] = override_get_llm_context
    
    # Register a user to get auth session cookie
    reg_payload = {
        "email": "test_owner@prototype.test",
        "password": "securepassword123"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 200
    user_id = int(response.json()["id"])
    cookie = client.cookies.get("auth_session")
    assert cookie
    
    # Keep the cookie active for future requests in this client
    client.cookies.set("auth_session", cookie)
    
    # Seed a project owned by this user
    async with test_db() as session:
        project = ProjectModel(
            name="Test Project",
            description="A project for testing routes",
            owner_user_id=user_id,
            user_requirements="Requirement detail"
        )
        session.add(project)
        await session.commit()
        project_id = project.public_id

    yield client, project_id
    
    app.dependency_overrides.pop(get_llm_context, None)


def test_post_prototype_preview_success(client_with_auth, test_db):
    """Test successful POST request to generate prototype preview."""
    client, project_id = client_with_auth
    
    mock_response = PrototypePreviewResponse(
        prototype_id=42,
        project_id=project_id,
        html="<html></html>",
        javascript="",
        css="",
        pages=[PrototypePageResponse(
            page_id="p1",
            role_id=1,
            role_name="User",
            feature_id=1,
            feature_name="Feature",
            html="<html></html>",
            javascript="",
            css="",
            source="placeholder",
            status="ready"
        )],
        source="placeholder",
        status="ready",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    async def fake_generate_preview(project_id, force_regenerate, **kwargs):
        # Assert that all database sessions created during dependency injection
        # are already closed/inactive (so they don't hold active transactions open during LLM calls)
        assert len(test_db.created_sessions) > 0
        for sess in test_db.created_sessions:
            assert not sess.is_active or not sess.in_transaction()
        return mock_response

    # Mock service call
    with patch("backend.api.modules.preview_convergence.routes.prototype.get_prototype_generation_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.generate_preview = AsyncMock(side_effect=fake_generate_preview)
        mock_get_service.return_value = mock_service

        response = client.post(f"/api/projects/{project_id}/prototype-preview", json={"force_regenerate": True})
        assert response.status_code == 200
        
        data = response.json()
        assert data["prototypeId"] == 42
        assert data["projectId"] == project_id
        assert data["source"] == "placeholder"
        assert len(data["pages"]) == 1


def test_post_prototype_preview_project_not_found(client_with_auth):
    """Test POST request when the project does not exist (returns 404)."""
    client, _ = client_with_auth
    
    with patch("backend.api.modules.preview_convergence.routes.prototype.get_prototype_generation_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.generate_preview = AsyncMock(side_effect=ValueError("project_not_found"))
        mock_get_service.return_value = mock_service
        response = client.post("/api/projects/999/prototype-preview", json={"force_regenerate": True})
        assert response.status_code == 404
        assert response.json()["detail"] == "project_not_found"


def test_post_prototype_preview_invalid_skill_payload(client_with_auth):
    """Test POST request when generation fails with invalid skill payload (returns 400)."""
    client, project_id = client_with_auth
    
    with patch("backend.api.modules.preview_convergence.routes.prototype.get_prototype_generation_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.generate_preview = AsyncMock(side_effect=ValueError("invalid_skill_payload"))
        mock_get_service.return_value = mock_service
        response = client.post(f"/api/projects/{project_id}/prototype-preview", json={"force_regenerate": True})
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_skill_payload"


def test_get_latest_prototype_preview_success(client_with_auth):
    """Test GET latest prototype preview when it exists."""
    client, project_id = client_with_auth
    
    mock_response = PrototypePreviewResponse(
        prototype_id=100,
        project_id=project_id,
        html="<p>Latest</p>",
        javascript="",
        css="",
        pages=[],
        source="placeholder",
        status="ready",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    with patch("backend.api.modules.preview_convergence.routes.prototype.get_prototype_generation_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_latest_preview = AsyncMock(return_value=mock_response)
        mock_get_service.return_value = mock_service

        response = client.get(f"/api/projects/{project_id}/prototype-preview/latest")
        assert response.status_code == 200
        assert response.json()["prototypeId"] == 100
        assert response.json()["html"] == "<p>Latest</p>"


def test_get_latest_prototype_preview_missing(client_with_auth):
    """Test GET latest prototype preview when no preview exists."""
    client, project_id = client_with_auth
    
    with patch("backend.api.modules.preview_convergence.routes.prototype.get_prototype_generation_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_latest_preview = AsyncMock(return_value=None)
        mock_get_service.return_value = mock_service

        response = client.get(f"/api/projects/{project_id}/prototype-preview/latest")
        assert response.status_code == 200
        assert response.json()["projectId"] == project_id
        assert "html" not in response.json()
