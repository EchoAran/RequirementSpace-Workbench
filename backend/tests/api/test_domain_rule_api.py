"""API tests for domain rules and rule discovery endpoints."""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.database.database import Base, get_session
from backend.database.model import BranchWorkspaceModel, ProjectModel, RequirementBranchModel
from backend.main import app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create test in-memory SQLite engine and session factory."""
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


@pytest.fixture
async def client_with_auth(test_db):
    """Setup authenticated test client and a project owned by the user."""
    client = TestClient(app)

    reg_payload = {
        "email": "rules_tester@requirementspace.internal",
        "password": "securepassword123",
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 200
    user_id = int(response.json()["id"])
    cookie = client.cookies.get("auth_session")
    assert cookie
    client.cookies.set("auth_session", cookie)

    from backend.database.model import FeatureModel

    async with test_db() as session:
        project = ProjectModel(
            name="Domain Rules API Test Project",
            description="Testing rules and discovery endpoints",
            owner_user_id=user_id,
        )
        session.add(project)
        await session.flush()

        branch = RequirementBranchModel(
            project_id=project.id,
            name="domain-rule-test",
            created_by_user_id=user_id,
        )
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(
            project_id=project.id,
            branch_id=branch.id,
            user_requirements="",
        )
        session.add(workspace)
        await session.flush()

        feature = FeatureModel(
            project_id=project.id,
            workspace_id=workspace.id,
            name="Payment Processing Feature",
            description="Handles online card transactions",
            confirmation_status="confirmed",
        )
        session.add(feature)
        await session.commit()
        project_public_id = project.public_id
        feature_logical_uuid = feature.logical_uuid
        branch_public_id = branch.public_id

    client.params = {"branch": branch_public_id}

    yield client, project_public_id, feature_logical_uuid


def test_list_and_create_domain_rules(client_with_auth):
    """Verify listing and creating domain rules via REST API."""
    client, project_id, _ = client_with_auth

    # Initial list is empty
    resp = client.get(f"/api/projects/{project_id}/rules")
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["total"] == 0
    assert data["rules"] == []

    # Create a rule
    create_payload = {
        "title": "Idempotent Transaction Rule",
        "statement": "Duplicate payment submissions with the same idempotency key must return cached result.",
        "origin": "manual",
        "confirmationStatus": "confirmed",
    }
    create_resp = client.post(f"/api/projects/{project_id}/rules", json=create_payload)
    assert create_resp.status_code == 201
    created_rule = create_resp.json()
    assert created_rule["title"] == create_payload["title"]
    assert created_rule["statement"] == create_payload["statement"]
    assert created_rule["confirmationStatus"] == "confirmed"
    rule_id = created_rule["id"]

    # List again
    list_resp = client.get(f"/api/projects/{project_id}/rules")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["rules"][0]["id"] == rule_id


def test_get_update_and_delete_domain_rule(client_with_auth):
    """Verify getting, updating, and deleting a single domain rule."""
    client, project_id, _ = client_with_auth

    # Create rule
    create_resp = client.post(
        f"/api/projects/{project_id}/rules",
        json={"title": "Original Title", "statement": "Original Statement"},
    )
    assert create_resp.status_code == 201
    rule_id = create_resp.json()["id"]

    # Get details
    get_resp = client.get(f"/api/projects/{project_id}/rules/{rule_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Original Title"

    # Update rule
    update_resp = client.put(
        f"/api/projects/{project_id}/rules/{rule_id}",
        json={"title": "Updated Title", "statement": "Updated Statement", "confirmationStatus": "confirmed"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Title"
    assert update_resp.json()["confirmationStatus"] == "confirmed"

    # Delete rule
    del_resp = client.delete(f"/api/projects/{project_id}/rules/{rule_id}")
    assert del_resp.status_code == 200

    # Ensure 404
    assert client.get(f"/api/projects/{project_id}/rules/{rule_id}").status_code == 404


def test_rule_link_endpoints(client_with_auth):
    """Verify creating, updating, locking, and deleting rule links."""
    client, project_id, feature_uuid = client_with_auth

    create_resp = client.post(
        f"/api/projects/{project_id}/rules",
        json={"title": "Link Test Rule", "statement": "Statement for link testing"},
    )
    assert create_resp.status_code == 201
    rule_id = create_resp.json()["id"]

    # Add link
    link_payload = {
        "targetKind": "feature",
        "targetLogicalUuid": feature_uuid,
        "linkPurpose": "source",
        "contextText": "Derived from business specification section 2.1",
    }
    link_resp = client.post(f"/api/projects/{project_id}/rules/{rule_id}/links", json=link_payload)
    assert link_resp.status_code == 201
    link_data = link_resp.json()
    assert link_data["targetKind"] == "feature"
    assert link_data["linkPurpose"] == "source"
    link_id = link_data["id"]

    # Verify link appears on rule detail
    get_resp = client.get(f"/api/projects/{project_id}/rules/{rule_id}")
    assert len(get_resp.json()["links"]) == 1
    assert get_resp.json()["links"][0]["id"] == link_id

    update_resp = client.patch(
        f"/api/projects/{project_id}/rules/{rule_id}/links/{link_id}",
        json={
            "linkPurpose": "applies_to",
            "contextText": "Applies to feature delivery",
            "lastSeenUpdatedAt": link_data["updatedAt"],
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["linkPurpose"] == "applies_to"
    assert update_resp.json()["contextText"] == "Applies to feature delivery"

    conflict_resp = client.patch(
        f"/api/projects/{project_id}/rules/{rule_id}/links/{link_id}",
        json={
            "contextText": "Stale update",
            "lastSeenUpdatedAt": link_data["updatedAt"],
        },
    )
    assert conflict_resp.status_code == 409

    # Delete link
    del_link_resp = client.delete(f"/api/projects/{project_id}/rules/{rule_id}/links/{link_id}")
    assert del_link_resp.status_code == 200

    # Verify link removed
    get_after = client.get(f"/api/projects/{project_id}/rules/{rule_id}")
    assert len(get_after.json()["links"]) == 0


def test_update_rule_optimistic_locking_conflict(client_with_auth):
    """Verify that updating a domain rule with a stale lastSeenUpdatedAt returns 409 Conflict."""
    client, project_id, _ = client_with_auth

    # Create rule
    create_payload = {
        "title": "Rule For 409 Conflict",
        "statement": "Statement to test concurrency conflict.",
        "origin": "manual",
    }
    resp = client.post(f"/api/projects/{project_id}/rules", json=create_payload)
    assert resp.status_code == 201
    rule_id = resp.json()["id"]

    # Attempt update with stale timestamp
    update_payload = {
        "title": "Conflicting Update",
        "lastSeenUpdatedAt": "2020-01-01T00:00:00Z",
    }
    conflict_resp = client.put(f"/api/projects/{project_id}/rules/{rule_id}", json=update_payload)
    assert conflict_resp.status_code == 409
    detail = conflict_resp.json()["detail"]
    assert detail["message"] == "node_content_changed"
    assert "current_snapshot" in detail
