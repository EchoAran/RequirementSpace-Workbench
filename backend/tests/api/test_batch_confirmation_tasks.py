import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlalchemy as sa
from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    ProjectModel,
    UserModel,
    ActorModel,
    FeatureModel,
    CollaborationTaskModel,
    ProjectMemberModel,
    AuditLogModel,
)

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

def register_user(client, email, password):
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 200
    user_id = int(res.json()["id"])
    cookie = client.cookies.get("auth_session")
    assert cookie
    return user_id, cookie

@pytest.mark.asyncio
async def test_batch_confirmation_tasks_workflow(test_db):
    client = TestClient(app)
    
    owner_id, owner_cookie = register_user(client, "owner@batch.com", "password123")
    editor_id, editor_cookie = register_user(client, "editor@batch.com", "password123")
    reviewer_id, reviewer_cookie = register_user(client, "reviewer@batch.com", "password123")
    viewer_id, viewer_cookie = register_user(client, "viewer@batch.com", "password123")

    async with test_db() as session:
        project = ProjectModel(
            name="Batch Project",
            owner_user_id=owner_id,
            user_requirements="Requirement details."
        )
        session.add(project)
        await session.commit()
        project_id = project.id
        project_public_id = project.public_id

        editor_member = ProjectMemberModel(project_id=project_id, user_id=editor_id, role="editor", status="active")
        session.add(editor_member)
        reviewer_member = ProjectMemberModel(project_id=project_id, user_id=reviewer_id, role="reviewer", status="active")
        session.add(reviewer_member)
        viewer_member = ProjectMemberModel(project_id=project_id, user_id=viewer_id, role="viewer", status="active")
        session.add(viewer_member)

        # Create two target nodes
        actor = ActorModel(project_id=project_id, name="Actor 1", description="hello", confirmation_status="ai_assumption")
        feat = FeatureModel(project_id=project_id, name="Feature 1", description="world", confirmation_status="ai_assumption")
        session.add(actor)
        session.add(feat)
        await session.commit()
        actor_id = actor.id
        feat_id = feat.id

    # 1. Create batch task
    client.cookies.set("auth_session", editor_cookie)
    res_create = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-nodes",
        json={
            "targets": [
                {"node_kind": "actor", "node_id": actor_id},
                {"node_kind": "feature", "node_id": feat_id}
            ],
            "assigned_to_user_id": reviewer_id,
            "title": "Batch verify targets",
            "description": "Please check both details",
            "priority": "high"
        }
    )
    assert res_create.status_code == 200
    task_data = res_create.json()
    assert task_data["taskType"] == "confirm_nodes"
    assert len(task_data["targets"]) == 2
    assert task_data["targets"][0]["node_name"] == "Actor 1"
    assert task_data["targets"][1]["node_name"] == "Feature 1"
    task_id = task_data["id"]

    client.cookies.set("auth_session", viewer_cookie)
    res_viewer_create = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-nodes",
        json={
            "targets": [
                {"node_kind": "actor", "node_id": actor_id},
                {"node_kind": "feature", "node_id": feat_id}
            ],
            "assigned_to_user_id": reviewer_id,
            "title": "Viewer should not create batch tasks"
        }
    )
    assert res_viewer_create.status_code == 403
    client.cookies.set("auth_session", editor_cookie)

    # Verify both targets confirmation_status updated to needs_confirmation
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        feat_db = await session.get(FeatureModel, feat_id)
        assert actor_db.confirmation_status == "needs_confirmation"
        assert feat_db.confirmation_status == "needs_confirmation"

    # 2. Test hash mismatch during decision
    # Modify Actor 1 description directly in DB to trigger hash mismatch
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.description = "hacked description"
        await session.commit()

    # Reviewer attempts to decide
    client.cookies.set("auth_session", reviewer_cookie)
    res_decide_fail = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id}/decision",
        json={"decision": "approve", "decision_note": "looks good"}
    )
    assert res_decide_fail.status_code == 409
    fail_detail = res_decide_fail.json()["detail"]
    assert fail_detail["message"] == "task_content_changed"
    assert len(fail_detail["mismatches"]) == 1
    assert fail_detail["mismatches"][0]["node_kind"] == "actor"

    # Verify task status is now superseded
    async with test_db() as session:
        task_db = await session.get(CollaborationTaskModel, task_id)
        assert task_db.status == "superseded"
        res_audit = await session.execute(
            sa.select(AuditLogModel).where(
                sa.and_(
                    AuditLogModel.task_id == task_id,
                    AuditLogModel.action_type == "task_superseded",
                )
            )
        )
        assert res_audit.scalar_one_or_none() is not None

    # 3. Create another batch task to test successful approval
    # Restore actor description so hash matches
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.description = "hello"
        await session.commit()

    client.cookies.set("auth_session", editor_cookie)
    res_create2 = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-nodes",
        json={
            "targets": [
                {"node_kind": "actor", "node_id": actor_id},
                {"node_kind": "feature", "node_id": feat_id}
            ],
            "assigned_to_user_id": reviewer_id,
            "title": "Batch verify targets 2"
        }
    )
    assert res_create2.status_code == 200
    task_id2 = res_create2.json()["id"]

    # Reviewer approves
    client.cookies.set("auth_session", reviewer_cookie)
    res_decide_ok = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id2}/decision",
        json={"decision": "approve", "decision_note": "everything matches"}
    )
    assert res_decide_ok.status_code == 200
    assert res_decide_ok.json()["status"] == "done"

    # Verify both target status updated to confirmed
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        feat_db = await session.get(FeatureModel, feat_id)
        assert actor_db.confirmation_status == "confirmed"
        assert feat_db.confirmation_status == "confirmed"

    # 4. Create another batch task to test rejection
    client.cookies.set("auth_session", editor_cookie)
    res_create3 = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-nodes",
        json={
            "targets": [
                {"node_kind": "actor", "node_id": actor_id},
                {"node_kind": "feature", "node_id": feat_id}
            ],
            "assigned_to_user_id": reviewer_id,
            "title": "Batch verify targets 3"
        }
    )
    assert res_create3.status_code == 200
    task_id3 = res_create3.json()["id"]

    # Reset one target directly in DB to verified, reviewer rejects task
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.confirmation_status = "confirmed"
        await session.commit()

    # Reviewer rejects
    client.cookies.set("auth_session", reviewer_cookie)
    res_reject = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id3}/decision",
        json={"decision": "reject", "decision_note": "bad style"}
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "rejected"

    # Verify rejected target is reset/kept needs_confirmation
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        assert actor_db.confirmation_status == "needs_confirmation"

    client.cookies.set("auth_session", editor_cookie)
    res_default_title = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-nodes",
        json={
            "targets": [
                {"node_kind": "actor", "node_id": actor_id},
                {"node_kind": "feature", "node_id": feat_id},
            ],
            "assigned_to_user_id": reviewer_id,
        },
    )
    assert res_default_title.status_code == 200
    assert res_default_title.json()["title"] == "collaboration.taskTitles.batchConfirmation"
