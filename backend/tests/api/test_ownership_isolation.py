"""
Multi-user ownership isolation tests for P2.

Verifies that User A cannot access User B's resources (projects,
choice groups, drafts, AI sessions) and vice versa. All unauthorized
attempts must return HTTP 404 to prevent resource enumeration.
"""
import os
import pytest
import asyncio
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
    GenerativeDraftModel,
    ChoiceGroupModel,
    ChoiceModel,
    AIAddSessionModel,
    ActorModel,
    FeatureModel,
    ScenarioModel,
    BusinessObjectModel,
    FlowModel,
    ScopeModel,
    IssueRepairDraftModel,
    PreviewShadowDraftModel,
)

# Use StaticPool to share a single in-memory SQLite connection across
# all sessions — both the app dependency override and test seed functions.
DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def isolation_test_db():
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
    res = client.post("/api/auth/register", json={"email": "user_a@iso.test", "password": "passwordA123"})
    assert res.status_code == 200
    user_a_id = int(res.json()["id"])
    cookie_a = client.cookies.get("auth_session")
    assert cookie_a

    client.cookies.clear()

    res = client.post("/api/auth/register", json={"email": "user_b@iso.test", "password": "passwordB123"})
    assert res.status_code == 200
    user_b_id = int(res.json()["id"])
    cookie_b = client.cookies.get("auth_session")
    assert cookie_b

    return user_a_id, cookie_a, user_b_id, cookie_b


def test_project_listing_isolation(isolation_test_db):
    """User A and User B each only see their own projects."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            pb = ProjectModel(name="PB", description="", owner_user_id=user_b_id, user_requirements="B")
            session.add_all([pa, pb])
            await session.commit()
            return pa.public_id, pb.public_id

    loop = asyncio.get_event_loop()
    proj_a, proj_b = loop.run_until_complete(seed())

    # User A sees only PA
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    res = client.get("/api/projects")
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()]
    assert proj_a in ids
    assert proj_b not in ids

    # User B sees only PB
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)
    res = client.get("/api/projects")
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()]
    assert proj_b in ids
    assert proj_a not in ids


def test_project_detail_isolation(isolation_test_db):
    """User B cannot access User A's project detail endpoints — all return 404."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="d", owner_user_id=user_a_id, user_requirements="A")
            session.add(pa)
            await session.commit()
            return pa.public_id

    loop = asyncio.get_event_loop()
    proj_a = loop.run_until_complete(seed())

    # User B — all project endpoints on proj_a should 404
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    assert client.get(f"/api/projects/{proj_a}").status_code == 404
    assert client.delete(f"/api/projects/{proj_a}").status_code == 404
    assert client.put(f"/api/projects/{proj_a}", json={"name": "hack"}).status_code == 404
    assert client.get(f"/api/projects/{proj_a}/export/json").status_code == 404
    assert client.get(f"/api/projects/{proj_a}/export/markdown").status_code == 404

    # User A — can access their own project
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    assert client.get(f"/api/projects/{proj_a}").status_code == 200


def test_choice_group_isolation(isolation_test_db):
    """User B cannot operate on User A's choice groups / choices."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="r")
            session.add(pa)
            await session.flush()

            cg = ChoiceGroupModel(project_id=pa.id, generation_type="actor", status="open")
            session.add(cg)
            await session.flush()

            choice = ChoiceModel(
                choice_group_id=cg.id, title="C1", rationale="", status="candidate", patch={}
            )
            session.add(choice)
            await session.commit()
            return pa.public_id, cg.id, choice.id

    loop = asyncio.get_event_loop()
    proj_a, group_id, choice_id = loop.run_until_complete(seed())

    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    assert client.get(f"/api/projects/{proj_a}/choice_groups").status_code == 404
    assert client.post(f"/api/projects/{proj_a}/choices/{choice_id}/accept").status_code == 404
    assert client.post(f"/api/projects/{proj_a}/choices/{choice_id}/reject").status_code == 404
    assert client.post(f"/api/projects/{proj_a}/choice_groups/{group_id}/discard").status_code == 404
    assert client.post(f"/api/projects/{proj_a}/choice_groups/{group_id}/regenerate").status_code == 404

    # Generation choice group creation for someone else's project
    payload = {"project_id": proj_a, "generation_type": "actor", "candidate_count": 2}
    assert client.post("/api/generation_choice_groups", json=payload).status_code == 404


def test_onboarding_draft_isolation(isolation_test_db):
    """User B cannot access User A's onboarding drafts."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            draft = GenerativeDraftModel(
                draft_id="onb_a_001",
                owner_user_id=user_a_id,
                draft_type="project_creation_choice_group",
                payload={
                    "draft_type": "project_creation_choice_group",
                    "choice_group_id": "onb_a_001",
                    "status": "open",
                    "generation_type": "project_creation",
                    "user_requirements": "test",
                    "candidate_count": 1,
                    "success_count": 1,
                    "failure_count": 0,
                    "choices": [
                        {
                            "id": "c1",
                            "title": "方案1",
                            "rationale": "理由",
                            "status": "candidate",
                            "draft_type": "project_creation",
                            "apply_mode": "draft_payload",
                            "payload": {"project_name": "Test"},
                            "preview": {},
                        }
                    ],
                },
            )
            session.add(draft)
            await session.commit()
            return draft.draft_id

    loop = asyncio.get_event_loop()
    draft_id = loop.run_until_complete(seed())

    # User B — 404
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)
    assert client.get(f"/api/project_creation_choice_groups/{draft_id}").status_code == 404
    assert client.post(f"/api/project_creation_choice_groups/{draft_id}/discard").status_code == 404
    assert client.post(f"/api/project_creation_choice_groups/{draft_id}/defer").status_code == 404

    # User A — 200
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    assert client.get(f"/api/project_creation_choice_groups/{draft_id}").status_code == 200


def test_ai_add_session_isolation(isolation_test_db):
    """User B cannot access User A's AI add sessions."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="r")
            session.add(pa)
            await session.flush()

            ai_sess = AIAddSessionModel(project_id=pa.id, target_type="actor", status="interviewing")
            session.add(ai_sess)
            await session.commit()
            return ai_sess.id

    loop = asyncio.get_event_loop()
    ai_sess_id = loop.run_until_complete(seed())

    # User B — 404 on all session endpoints
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)
    assert client.get(f"/api/ai_add_sessions/{ai_sess_id}").status_code == 404
    assert client.get(f"/api/ai_add_sessions/{ai_sess_id}/messages").status_code == 404
    assert client.post(f"/api/ai_add_sessions/{ai_sess_id}/messages", json={"content": "hi"}).status_code == 404
    assert client.post(f"/api/ai_add_sessions/{ai_sess_id}/generate_draft").status_code == 404

    # User A — 200
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    assert client.get(f"/api/ai_add_sessions/{ai_sess_id}").status_code == 200


def test_unauthenticated_returns_401(isolation_test_db):
    """All resource endpoints return 401 without auth cookie."""
    client = TestClient(app)
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/projects/1").status_code == 401
    assert client.get("/api/ai_add_sessions/1").status_code == 401
    assert client.get("/api/project_creation_choice_groups/abc").status_code == 401


def test_llm_test_endpoint_requires_auth(isolation_test_db):
    """/api/llm_test endpoint must return 401 when unauthenticated, 403 for regular user, and succeed for admin."""
    client = TestClient(app)
    # 1. Unauthenticated returns 401
    assert client.get("/api/llm_test").status_code == 401

    # 2. Authenticated regular user gets 403 (since it is now admin-only)
    user_a_id, cookie_a, _, _ = _register_users(client)
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    assert client.get("/api/llm_test").status_code == 403

    # 3. Authenticated admin user gets response (200, 409 or 500 depending on env LLM config)
    from unittest.mock import patch
    from backend.core.security import hash_password
    import backend.api.services.auth_service

    invite_code = "admin_secret_999"
    hashed_code = hash_password(invite_code)

    with patch.object(backend.api.services.auth_service, "ADMIN_INVITE_CODE_HASH", hashed_code):
        client.cookies.clear()
        res = client.post("/api/auth/register", json={
            "email": "admin_test@iso.test",
            "password": "passwordAdmin123",
            "invite_code": invite_code
        })
        assert res.status_code == 200
        cookie_admin = client.cookies.get("auth_session")
        assert cookie_admin

        client.cookies.clear()
        client.cookies.set("auth_session", cookie_admin)
        assert client.get("/api/llm_test").status_code in (200, 409, 500)


def test_subresource_table_isolation(isolation_test_db):
    """User B cannot query/modify sub-resources of User A's project (all return 404)."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            session.add(pa)
            await session.commit()
            return pa.public_id

    loop = asyncio.get_event_loop()
    proj_a_id = loop.run_until_complete(seed())

    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    # All sub-resource endpoints on User A's project must return 404 for User B
    assert client.get(f"/api/projects/{proj_a_id}/actors").status_code == 404
    assert client.get(f"/api/projects/{proj_a_id}/features").status_code == 404

    assert client.post(
        f"/api/projects/{proj_a_id}/scenarios",
        json={"name": "S", "content": "Given x", "actor_id": 1, "feature_id": 1}
    ).status_code == 404

    assert client.post(
        f"/api/projects/{proj_a_id}/business_objects",
        json={"name": "BO", "description": "desc"}
    ).status_code == 404

    assert client.post(
        f"/api/projects/{proj_a_id}/flows",
        json={"name": "F", "description": "desc"}
    ).status_code == 404

    assert client.put(
        f"/api/projects/{proj_a_id}/features/1/scope",
        json={"status": "in_scope", "reason": "test"}
    ).status_code == 404



def test_cross_project_linking_association_blocking(isolation_test_db):
    """User B cannot create or link sub-resources under User A's project (returns 404)."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            session.add(pa)
            await session.commit()
            return pa.public_id

    loop = asyncio.get_event_loop()
    proj_a_id = loop.run_until_complete(seed())

    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    # User B attempts to write to User A's project -> returns 404
    assert client.post(
        f"/api/projects/{proj_a_id}/actors",
        json={"name": "Hacked Actor", "description": "hack"}
    ).status_code == 404

    assert client.post(
        f"/api/projects/{proj_a_id}/features",
        json={"name": "Hacked Feature", "description": "hack"}
    ).status_code == 404


def test_generation_draft_isolation(isolation_test_db):
    """User B cannot confirm, regenerate, or discard User A's actor generation drafts."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            session.add(pa)
            await session.flush()

            draft = GenerativeDraftModel(
                draft_id="actor_gen_a_001",
                owner_user_id=user_a_id,
                project_id=pa.id,
                draft_type="actor_generation",
                payload={"actors": [{"name": "Actor A", "description": "desc"}]},
            )
            session.add(draft)
            await session.commit()
            return pa.public_id, draft.draft_id

    loop = asyncio.get_event_loop()
    proj_a_id, draft_id = loop.run_until_complete(seed())

    # User B gets 404 trying to manipulate User A's draft
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    assert client.post(f"/api/actor_generation_drafts/{draft_id}/confirm").status_code == 404
    assert client.post(f"/api/actor_generation_drafts/{draft_id}/regenerate").status_code == 404
    assert client.delete(f"/api/actor_generation_drafts/{draft_id}").status_code == 404

    # Direct creation for another user's project is blocked
    assert client.post(
        "/api/actor_generation_drafts",
        json={"project_id": proj_a_id}
    ).status_code == 404


def test_issue_repair_draft_isolation(isolation_test_db):
    """User B cannot access or manipulate User A's issue repair drafts."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            session.add(pa)
            await session.flush()

            repair_draft = IssueRepairDraftModel(
                draft_id="repair_a_001",
                project_id=pa.id,
                issue_code="DUP_ACTOR",
                issue_id="issue123",
                stage="what",
                target={},
                issue_fingerprint="fp123",
                context_hash="hash123",
                repair_type="rename",
                title="Repair",
                rationale="Reason",
                proposal={},
                status="pending",
            )
            session.add(repair_draft)
            await session.commit()
            return pa.public_id, repair_draft.draft_id

    loop = asyncio.get_event_loop()
    proj_a_id, draft_id = loop.run_until_complete(seed())

    # User B gets 404 on User A's project issue repair drafts
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    assert client.post(f"/api/projects/{proj_a_id}/issue_repair_drafts/{draft_id}/confirm").status_code == 404
    assert client.post(f"/api/projects/{proj_a_id}/issue_repair_drafts/{draft_id}/discard").status_code == 404


def test_preview_shadow_draft_isolation(isolation_test_db):
    """User B cannot generate or access preview shadow drafts of User A's project."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            session.add(pa)
            await session.commit()
            return pa.public_id

    loop = asyncio.get_event_loop()
    proj_a_id = loop.run_until_complete(seed())

    # User B gets 404 trying to interact with shadow drafts on PA
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    assert client.post(f"/api/projects/{proj_a_id}/preview-shadow-drafts").status_code == 404


def test_associate_another_project_actor_to_own_feature(isolation_test_db):
    """User B cannot link an actor belonging to User A's project to User B's feature."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            pb = ProjectModel(name="PB", description="", owner_user_id=user_b_id, user_requirements="B")
            session.add_all([pa, pb])
            await session.flush()

            actor_a = ActorModel(project_id=pa.id, name="Actor A", description="A desc")
            feature_b = FeatureModel(project_id=pb.id, name="Feature B", description="B desc")
            session.add_all([actor_a, feature_b])
            await session.commit()
            return pb.public_id, feature_b.id, actor_a.id

    loop = asyncio.get_event_loop()
    proj_b_id, feat_b_id, actor_a_id = loop.run_until_complete(seed())

    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    # B attempts to associate actor_a to feature_b in PB -> returns 400
    res = client.put(
        f"/api/projects/{proj_b_id}/features/{feat_b_id}",
        json={"actor_ids": [actor_a_id]}
    )
    assert res.status_code == 400
    assert "invalid_actor_reference" in res.json()["detail"]


def test_scenario_referencing_another_project_entities(isolation_test_db):
    """User B cannot create a scenario referencing User A's feature or User A's actor."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            pb = ProjectModel(name="PB", description="", owner_user_id=user_b_id, user_requirements="B")
            session.add_all([pa, pb])
            await session.flush()

            feat_a = FeatureModel(project_id=pa.id, name="Feat A", description="A desc")
            actor_a = ActorModel(project_id=pa.id, name="Actor A", description="A desc")
            feat_b = FeatureModel(project_id=pb.id, name="Feat B", description="B desc")
            actor_b = ActorModel(project_id=pb.id, name="Actor B", description="B desc")
            session.add_all([feat_a, actor_a, feat_b, actor_b])
            await session.commit()
            return pb.public_id, feat_a.id, actor_a.id, feat_b.id, actor_b.id

    loop = asyncio.get_event_loop()
    proj_b_id, feat_a_id, actor_a_id, feat_b_id, actor_b_id = loop.run_until_complete(seed())

    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    # Case 1: own project, own actor, but another project's feature -> 400 (feature_not_found)
    res = client.post(
        f"/api/projects/{proj_b_id}/scenarios",
        json={"name": "Scenario B1", "feature_id": feat_a_id, "actor_id": actor_b_id, "content": "G"}
    )
    assert res.status_code == 400
    assert "feature_not_found" in res.json()["detail"]

    # Case 2: own project, own feature, but another project's actor -> 400 (actor_not_found)
    res = client.post(
        f"/api/projects/{proj_b_id}/scenarios",
        json={"name": "Scenario B2", "feature_id": feat_b_id, "actor_id": actor_a_id, "content": "G"}
    )
    assert res.status_code == 400
    assert "actor_not_found" in res.json()["detail"]


def test_flow_referencing_another_project_entities(isolation_test_db):
    """User B cannot create flow or step referencing User A's feature, actor, or business object."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            pb = ProjectModel(name="PB", description="", owner_user_id=user_b_id, user_requirements="B")
            session.add_all([pa, pb])
            await session.flush()

            feat_a = FeatureModel(project_id=pa.id, name="Feat A", description="")
            actor_a = ActorModel(project_id=pa.id, name="Actor A", description="")
            bo_a = BusinessObjectModel(project_id=pa.id, name="BO A", description="")

            flow_b = FlowModel(project_id=pb.id, name="Flow B", description="")
            session.add_all([feat_a, actor_a, bo_a, flow_b])
            await session.commit()
            return pb.public_id, flow_b.id, feat_a.id, actor_a.id, bo_a.id

    loop = asyncio.get_event_loop()
    proj_b_id, flow_b_id, feat_a_id, actor_a_id, bo_a_id = loop.run_until_complete(seed())

    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    # 1. Flow references feature of another project -> 400 (invalid_feature_ids)
    res = client.post(
        f"/api/projects/{proj_b_id}/flows",
        json={"name": "Flow Cross", "description": "", "feature_ids": [feat_a_id]}
    )
    assert res.status_code == 400
    assert "invalid_feature_ids" in res.json()["detail"]

    # 2. Flow step references actor of another project -> 400 (invalid_actor_ids)
    res = client.post(
        f"/api/projects/{proj_b_id}/flows/{flow_b_id}/steps",
        json={
            "name": "Step Cross Actor",
            "step_type": "actorAction",
            "actor_ids": [actor_a_id],
        }
    )
    assert res.status_code == 400
    assert "invalid_actor_ids" in res.json()["detail"]

    # 3. Flow step references business object of another project as input -> 400
    res = client.post(
        f"/api/projects/{proj_b_id}/flows/{flow_b_id}/steps",
        json={
            "name": "Step Cross BO",
            "step_type": "systemAction",
            "input_business_object_ids": [bo_a_id],
        }
    )
    assert res.status_code == 400
    assert "invalid_input_business_object_ids" in res.json()["detail"]


def test_feature_parent_child_cross_project(isolation_test_db):
    """User B cannot create a feature with parent_id belonging to User A's project."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            pb = ProjectModel(name="PB", description="", owner_user_id=user_b_id, user_requirements="B")
            session.add_all([pa, pb])
            await session.flush()

            feat_a = FeatureModel(project_id=pa.id, name="Feat A", description="")
            session.add(feat_a)
            await session.commit()
            return pb.public_id, feat_a.id

    loop = asyncio.get_event_loop()
    proj_b_id, feat_a_id = loop.run_until_complete(seed())

    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    # Create a feature in PB with parent_id = feat_a_id (belonging to PA) -> 400
    res = client.post(
        f"/api/projects/{proj_b_id}/features",
        json={"name": "Feat B Child", "parent_id": feat_a_id}
    )
    assert res.status_code == 400
    assert "parent_feature_not_found" in res.json()["detail"]


def test_generative_draft_owner_project_mismatch(isolation_test_db):
    """If User B's generative draft is associated with User A's project, User B gets 404 upon access."""
    client = TestClient(app)
    user_a_id, cookie_a, user_b_id, cookie_b = _register_users(client)

    async def seed():
        async with isolation_test_db() as session:
            pa = ProjectModel(name="PA", description="", owner_user_id=user_a_id, user_requirements="A")
            session.add(pa)
            await session.flush()

            draft = GenerativeDraftModel(
                draft_id="cross_draft_001",
                owner_user_id=user_b_id,  # Owned by User B
                project_id=pa.id,        # Associated with User A's project PA
                draft_type="actor_generation",
                payload={"actors": [{"name": "Actor", "description": "desc"}]},
            )
            session.add(draft)
            await session.commit()
            return pa.public_id, draft.draft_id

    loop = asyncio.get_event_loop()
    proj_a_id, draft_id = loop.run_until_complete(seed())

    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)

    # User B tries to confirm the draft, but it should return 404 because project owner != User B
    assert client.post(f"/api/actor_generation_drafts/{draft_id}/confirm").status_code == 404
