import pytest
from datetime import datetime, timedelta, timezone
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
    CollaborationTaskModel,
    ProjectMemberModel,
    AuditLogModel,
    ConfirmationStatus,
    BusinessObjectModel,
    BusinessObjectAttributeModel,
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
async def test_confirmation_tasks_workflow(test_db):
    client = TestClient(app)
    
    # 1. Register users: owner, editor, reviewer, viewer, non_member
    owner_id, owner_cookie = register_user(client, "owner@test.com", "password123")
    editor_id, editor_cookie = register_user(client, "editor@test.com", "password123")
    reviewer_id, reviewer_cookie = register_user(client, "reviewer@test.com", "password123")
    viewer_id, viewer_cookie = register_user(client, "viewer@test.com", "password123")
    non_member_id, non_member_cookie = register_user(client, "non_member@test.com", "password123")

    # 2. Create Project and add members
    async with test_db() as session:
        project = ProjectModel(
            name="Tasks Project",
            owner_user_id=owner_id,
            user_requirements="Requirement details."
        )
        session.add(project)
        await session.commit()
        project_id = project.id
        project_public_id = project.public_id

        # Register members
        # Owner is automatically registered as owner by SQL event auto_create_project_owner_member
        
        # Add Editor
        editor_member = ProjectMemberModel(project_id=project_id, user_id=editor_id, role="editor", status="active")
        session.add(editor_member)
        # Add Reviewer
        reviewer_member = ProjectMemberModel(project_id=project_id, user_id=reviewer_id, role="reviewer", status="active")
        session.add(reviewer_member)
        # Add Viewer
        viewer_member = ProjectMemberModel(project_id=project_id, user_id=viewer_id, role="viewer", status="active")
        session.add(viewer_member)
        
        # Add an Actor under project to confirm
        actor = ActorModel(project_id=project_id, name="Original Actor", description="Original Desc", confirmation_status="confirmed")
        session.add(actor)
        await session.commit()
        actor_id = actor.id

    # 3. Test Task Creation: editor creates confirmation task for actor assigned to reviewer
    client.cookies.set("auth_session", editor_cookie)
    res = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "node_kind": "actor",
            "node_id": actor_id,
            "assigned_to_user_id": reviewer_id,
            "title": "Confirm Actor Creation",
            "description": "Please review this actor details.",
            "priority": "high",
            "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        }
    )
    assert res.status_code == 200
    task_data = res.json()
    task_id = task_data["id"]
    assert task_data["status"] == "open"
    assert task_data["priority"] == "high"
    assert task_data["creatorEmail"] == "editor@test.com"
    assert task_data["assigneeEmail"] == "reviewer@test.com"
    assert task_data["nodeName"] == "Original Actor"

    # Verify that creating task changes actor confirmation_status to needs_confirmation
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        assert actor_db.confirmation_status == ConfirmationStatus.NEEDS_CONFIRMATION.value

    # 4. Test Assignee Restriction: editor tries to create a task assigned to viewer (should fail with 400)
    res_viewer = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "node_kind": "actor",
            "node_id": actor_id,
            "assigned_to_user_id": viewer_id,
        }
    )
    assert res_viewer.status_code == 400

    # 5. Test Non-member Restriction: editor tries to create a task assigned to non_member (should fail with 400)
    res_non_member = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "node_kind": "actor",
            "node_id": actor_id,
            "assigned_to_user_id": non_member_id,
        }
    )
    assert res_non_member.status_code == 400

    # Viewer can read project data but cannot create confirmation tasks.
    client.cookies.set("auth_session", viewer_cookie)
    res_viewer_creator = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "node_kind": "actor",
            "node_id": actor_id,
            "assigned_to_user_id": reviewer_id,
        }
    )
    assert res_viewer_creator.status_code == 403
    client.cookies.set("auth_session", editor_cookie)

    # 6. Test Query Tasks:
    # Get all project tasks
    client.cookies.set("auth_session", editor_cookie)
    res_list = client.get(f"/api/projects/{project_public_id}/tasks")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # Get my tasks as reviewer
    client.cookies.set("auth_session", reviewer_cookie)
    res_my = client.get("/api/me/tasks?status=open")
    assert res_my.status_code == 200
    assert len(res_my.json()) == 1
    assert res_my.json()[0]["task"]["id"] == task_id

    # 7. Test Non-Assignee permission rejection: editor tries to decide task (should fail with 403)
    client.cookies.set("auth_session", editor_cookie)
    res_decide_fail = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id}/decision",
        json={"decision": "approve", "decision_note": "Approved by non-assignee"}
    )
    # Wait, the patch is registered in routes.py!
    # Let's check status code
    assert res_decide_fail.status_code == 403

    # 8. Test Reviewer Assignee Decision (Approve):
    client.cookies.set("auth_session", reviewer_cookie)
    res_approve = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id}/decision",
        json={"decision": "approve", "decision_note": "Looks perfect!"}
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "done"

    # Verify that actor confirmation_status is now confirmed
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        assert actor_db.confirmation_status == ConfirmationStatus.CONFIRMED.value

        # Verify audit logs generated with task_id
        res_audit = await session.execute(
            sa.select(AuditLogModel).where(AuditLogModel.task_id == task_id)
        )
        logs = res_audit.scalars().all()
        assert len(logs) >= 2  # task_created, task_approved

    # 9. Test direct confirmation status change by reviewer (should fail with 403 because reviewer is not an editor)
    client.cookies.set("auth_session", reviewer_cookie)
    res_status_fail = client.patch(
        f"/api/projects/{project_public_id}/node-status",
        json={"node_kind": "actor", "node_id": actor_id, "confirmation_status": "confirmed"}
    )
    assert res_status_fail.status_code == 403

    # 10. Create another task to test Admin/Owner override & acted_as_admin=True in audit log
    client.cookies.set("auth_session", editor_cookie)
    res_new_task = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "node_kind": "actor",
            "node_id": actor_id,
            "assigned_to_user_id": reviewer_id,
            "title": "Task to test Admin override"
        }
    )
    assert res_new_task.status_code == 200
    task_id2 = res_new_task.json()["id"]

    # Owner decides task on behalf of assignee (reviewer)
    client.cookies.set("auth_session", owner_cookie)
    res_override = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id2}/decision",
        json={"decision": "approve", "decision_note": "Approved by Owner"}
    )
    assert res_override.status_code == 200
    assert res_override.json()["status"] == "done"

    # Verify audit logs for override contain acted_as_admin
    async with test_db() as session:
        res_audit2 = await session.execute(
            sa.select(AuditLogModel).where(
                sa.and_(
                    AuditLogModel.task_id == task_id2,
                    AuditLogModel.action_type == "task_approved"
                )
            )
        )
        log2 = res_audit2.scalar_one()
        assert log2.payload.get("acted_as_admin") is True

    # 11. Test content change hash mismatch (supersede on decision attempt)
    # Create another task
    client.cookies.set("auth_session", editor_cookie)
    res_task3 = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "node_kind": "actor",
            "node_id": actor_id,
            "assigned_to_user_id": reviewer_id,
            "title": "Task to test Hash mismatch"
        }
    )
    task_id3 = res_task3.json()["id"]

    # Modify the actor's semantic field (description) using Editor
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.description = "Mutated semantic description"
        await session.commit()

    # Attempt to decide the task. Should fail with 409 and mark task as superseded.
    client.cookies.set("auth_session", reviewer_cookie)
    res_decide_mismatch = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id3}/decision",
        json={"decision": "approve"}
    )
    assert res_decide_mismatch.status_code == 409
    assert res_decide_mismatch.json()["detail"] == "task_content_changed"

    # Verify task status is now superseded in database
    async with test_db() as session:
        task_db = await session.get(CollaborationTaskModel, task_id3)
        assert task_db.status == "superseded"

    # 12. Test directly setting node status to confirmed supersedes open tasks
    # Create another task
    client.cookies.set("auth_session", editor_cookie)
    res_task4 = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "node_kind": "actor",
            "node_id": actor_id,
            "assigned_to_user_id": reviewer_id,
            "title": "Task to test direct status change override"
        }
    )
    task_id4 = res_task4.json()["id"]

    # First, let's reset status to ai_assumption so it actually changes and triggers the hook
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.confirmation_status = "ai_assumption"
        await session.commit()

    # Editor directly updates node status to confirmed via /node-status
    client.cookies.set("auth_session", editor_cookie)
    res_direct_status = client.patch(
        f"/api/projects/{project_public_id}/node-status",
        json={"node_kind": "actor", "node_id": actor_id, "confirmation_status": "confirmed"}
    )
    assert res_direct_status.status_code == 200

    # Verify the task has been automatically superseded
    async with test_db() as session:
        task_db4 = await session.get(CollaborationTaskModel, task_id4)
        assert task_db4.status == "superseded"

    # 13. Test business_object_attribute snapshot generation and task creation
    async with test_db() as session:
        bo = BusinessObjectModel(project_id=project_id, name="UserBO", description="User business object")
        session.add(bo)
        await session.commit()
        bo_id = bo.id

        attr = BusinessObjectAttributeModel(
            business_object_id=bo_id,
            name="email",
            description="User email",
            data_type="string",
            example="test@test.com"
        )
        session.add(attr)
        await session.commit()
        attr_id = attr.id

    client.cookies.set("auth_session", editor_cookie)
    res_attr_task = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "node_kind": "business_object_attribute",
            "node_id": attr_id,
            "assigned_to_user_id": reviewer_id,
            "title": "Confirm Attribute email"
        }
    )
    assert res_attr_task.status_code == 200
    attr_task_id = res_attr_task.json()["id"]

    # 14. Test reject reset to needs_confirmation and audit log verification
    # Reset status of business object attribute to ai_assumption directly in db
    async with test_db() as session:
        attr_db = await session.get(BusinessObjectAttributeModel, attr_id)
        attr_db.confirmation_status = "ai_assumption"
        await session.commit()

    # Reviewer rejects the task
    client.cookies.set("auth_session", reviewer_cookie)
    res_reject = client.patch(
        f"/api/projects/{project_public_id}/tasks/{attr_task_id}/decision",
        json={"decision": "reject", "decision_note": "Invalid data type"}
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "rejected"

    # Verify that the attribute status is now set to needs_confirmation
    async with test_db() as session:
        attr_db = await session.get(BusinessObjectAttributeModel, attr_id)
        assert attr_db.confirmation_status == ConfirmationStatus.NEEDS_CONFIRMATION.value

        # Verify update_confirmation_status audit log is recorded with the correct task_id
        res_audit3 = await session.execute(
            sa.select(AuditLogModel).where(
                sa.and_(
                    AuditLogModel.task_id == attr_task_id,
                    AuditLogModel.action_type == "update_confirmation_status"
                )
            ).order_by(AuditLogModel.id.asc())
        )
        logs3 = res_audit3.scalars().all()
        assert len(logs3) >= 1
        log3 = logs3[-1]
        assert log3.diff["confirmation_status"]["before"] == "ai_assumption"
        assert log3.diff["confirmation_status"]["after"] == "needs_confirmation"
