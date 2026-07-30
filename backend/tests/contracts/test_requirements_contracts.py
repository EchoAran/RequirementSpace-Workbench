import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    AuditLogModel,
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    FlowModel,
    FlowStepModel,
    flow_step_next_table,
)
from backend.api.modules.requirements_core.ports import set_notifier

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def req_test_db():
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

    from backend.api.dependencies.ownership import require_owned_generative_draft
    from backend.database.model import GenerativeDraftModel

    mock_draft = GenerativeDraftModel(
        draft_id="draft-123",
        project_id=1,
        draft_type="actor",
        payload={},
        owner_user_id=1
    )

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[require_owned_generative_draft] = lambda: mock_draft
    yield session_factory
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(require_owned_generative_draft, None)
    await engine.dispose()


def _register_login_and_create_project(client):
    reg_payload = {"email": "test_user@example.com", "password": "password123"}
    client.post("/api/auth/register", json=reg_payload)
    login_payload = {"email": "test_user@example.com", "password": "password123"}
    client.post("/api/auth/login", json=login_payload)
    
    create_payload = {
        "user_requirements": "Requirements info",
        "project_name": "Test project",
        "project_description": "Desc"
    }
    res = client.post("/api/blank_projects", json=create_payload)
    project_id = res.json()["project_id"]
    
    # Configure dummy LLM config to avoid 409 Conflict (llm_config_required)
    client.put("/api/account/llm-config", json={
        "api_url": "https://api.openai.com/v1",
        "api_key": "sk-dummy-test-key-string-long-enough",
        "model_name": "gpt-4-turbo"
    })
    return project_id


# ═══════════════════════════════════════════════════════════════════
# 1. CRUD Contracts Tests
# ═══════════════════════════════════════════════════════════════════

def test_actor_crud_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    # Create Actor
    res = client.post(f"/api/projects/{project_id}/actors", json={"name": "Admin", "description": "Admin desc"})
    assert res.status_code == 200
    data = res.json()
    assert "actor_id" in data
    assert data["name"] == "Admin"
    assert data["description"] == "Admin desc"
    assert data["confirmation_status"] == "needs_confirmation"  # Manual creation gets needs_confirmation status
    actor_id = data["actor_id"]

    # List Actors
    res = client.get(f"/api/projects/{project_id}/actors")
    assert res.status_code == 200
    actors = res.json()
    assert len(actors) == 1
    assert actors[0]["actor_id"] == actor_id

    # Update Actor
    res = client.put(f"/api/projects/{project_id}/actors/{actor_id}", json={"name": "SuperAdmin"})
    assert res.status_code == 200
    assert res.json()["name"] == "SuperAdmin"

    # Delete Actor
    res = client.delete(f"/api/projects/{project_id}/actors/{actor_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "actor_deleted"


def test_feature_crud_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    # Create Feature
    res = client.post(f"/api/projects/{project_id}/features", json={"name": "Auth", "description": "Auth desc"})
    assert res.status_code == 200
    data = res.json()
    assert "feature_id" in data
    assert data["name"] == "Auth"
    feature_id = data["feature_id"]

    # List Features
    res = client.get(f"/api/projects/{project_id}/features")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Update Feature
    res = client.put(f"/api/projects/{project_id}/features/{feature_id}", json={"name": "Authorization"})
    assert res.status_code == 200
    assert res.json()["name"] == "Authorization"

    # Delete Feature
    res = client.delete(f"/api/projects/{project_id}/features/{feature_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "feature_deleted"


@pytest.mark.asyncio
async def test_feature_parent_and_actor_relationships_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)
    actor_id = client.post(
        f"/api/projects/{project_id}/actors",
        json={"name": "Customer"},
    ).json()["actor_id"]
    parent_id = client.post(
        f"/api/projects/{project_id}/features",
        json={"name": "Checkout"},
    ).json()["feature_id"]
    child_ids = [
        client.post(
            f"/api/projects/{project_id}/features",
            json={"name": name, "parent_id": parent_id},
        ).json()["feature_id"]
        for name in ("Review", "Submit")
    ]

    response = client.put(
        f"/api/projects/{project_id}/features/{child_ids[0]}",
        json={"actorIds": [actor_id]},
    )

    assert response.status_code == 200
    assert response.json()["parent_id"] == parent_id
    assert response.json()["actor_ids"] == [actor_id]

    response = client.put(
        f"/api/projects/{project_id}/features/{child_ids[0]}",
        json={"actorIds": [actor_id + 100_000]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_actor_reference"

    response = client.put(
        f"/api/projects/{project_id}/features/{child_ids[0]}",
        json={"description": "Still linked"},
    )
    assert response.status_code == 200
    assert response.json()["actor_ids"] == [actor_id]

    async with req_test_db() as session:
        relations = (
            await session.execute(
                select(FeatureRelationModel)
                .where(
                    FeatureRelationModel.parent_feature_id == parent_id
                )
                .order_by(FeatureRelationModel.position)
            )
        ).scalars().all()
    assert [
        (relation.child_feature_id, relation.position)
        for relation in relations
    ] == [(child_ids[0], 0), (child_ids[1], 1)]


def test_scope_update_create_and_preserve_summaries_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)
    feature_id = client.post(
        f"/api/projects/{project_id}/features",
        json={"name": "Checkout"},
    ).json()["feature_id"]
    endpoint = (
        f"/api/projects/{project_id}/features/{feature_id}/scope"
    )

    response = client.put(
        endpoint,
        json={
            "status": "current",
            "reason": "Needed now",
            "positiveSummary": "Customer value",
            "negativeSummary": "Delivery cost",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "current"
    assert response.json()["reason"] == "Needed now"
    assert response.json()["positive_summary"] == "Customer value"
    assert response.json()["negative_summary"] == "Delivery cost"
    assert response.json()["confirmation_status"] == "ai_assumption"

    response = client.put(
        endpoint,
        json={"status": "postponed", "reason": "Later"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "postponed"
    assert response.json()["reason"] == "Later"
    assert response.json()["positive_summary"] == "Customer value"
    assert response.json()["negative_summary"] == "Delivery cost"


def test_scenario_and_ac_crud_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    # Create Actor and Feature first to satisfy Foreign Keys if needed (SQLite doesn't always enforce unless enabled, but good practice)
    actor_res = client.post(f"/api/projects/{project_id}/actors", json={"name": "User"})
    actor_id = actor_res.json()["actor_id"]
    feature_res = client.post(f"/api/projects/{project_id}/features", json={"name": "Login"})
    feature_id = feature_res.json()["feature_id"]

    # Create Scenario
    scenario_payload = {
        "feature_id": feature_id,
        "actor_id": actor_id,
        "name": "Successful Login",
        "content": "Given a valid user, When they login, Then success"
    }
    res = client.post(f"/api/projects/{project_id}/scenarios", json=scenario_payload)
    assert res.status_code == 200
    data = res.json()
    assert "scenario_id" in data
    assert data["name"] == "Successful Login"
    scenario_id = data["scenario_id"]



    # Update Scenario
    res = client.put(f"/api/projects/{project_id}/scenarios/{scenario_id}", json={"name": "Login Success"})
    assert res.status_code == 200
    assert res.json()["name"] == "Login Success"

    # Create Acceptance Criterion (AC)
    ac_payload = {
        "content": "User sees dashboard",
        "scenario_id": scenario_id
    }
    res = client.post(f"/api/projects/{project_id}/scenarios/{scenario_id}/acceptance_criteria", json=ac_payload)
    assert res.status_code == 200
    ac_data = res.json()
    assert "criterion_id" in ac_data
    assert ac_data["content"] == "User sees dashboard"
    ac_id = ac_data["criterion_id"]

    # Update AC
    res = client.put(f"/api/projects/{project_id}/scenarios/{scenario_id}/acceptance_criteria/{ac_id}", json={"content": "Dashboard visible"})
    assert res.status_code == 200
    assert res.json()["content"] == "Dashboard visible"

    # Delete AC
    res = client.delete(f"/api/projects/{project_id}/scenarios/{scenario_id}/acceptance_criteria/{ac_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "acceptance_criterion_deleted"

    # Delete Scenario
    res = client.delete(f"/api/projects/{project_id}/scenarios/{scenario_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "scenario_deleted"


def test_business_object_crud_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    # Create Business Object
    res = client.post(f"/api/projects/{project_id}/business_objects", json={"name": "Order", "description": "Customer order"})
    assert res.status_code == 200
    data = res.json()
    assert "business_object_id" in data
    assert data["name"] == "Order"
    bo_id = data["business_object_id"]

    # Update BO
    res = client.put(f"/api/projects/{project_id}/business_objects/{bo_id}", json={"name": "PurchaseOrder"})
    assert res.status_code == 200
    assert res.json()["name"] == "PurchaseOrder"

    # Create Attribute
    res = client.post(f"/api/projects/{project_id}/business_objects/{bo_id}/attributes", json={"name": "total_amount", "data_type": "decimal", "description": "Order total"})
    assert res.status_code == 200
    attr_data = res.json()
    assert "attribute_id" in attr_data
    assert attr_data["name"] == "total_amount"
    attr_id = attr_data["attribute_id"]

    # Update Attribute
    res = client.put(f"/api/projects/{project_id}/business_objects/{bo_id}/attributes/{attr_id}", json={"name": "total"})
    assert res.status_code == 200
    assert res.json()["name"] == "total"

    # Delete Attribute
    res = client.delete(f"/api/projects/{project_id}/business_objects/{bo_id}/attributes/{attr_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "attribute_deleted"

    # Delete BO
    res = client.delete(f"/api/projects/{project_id}/business_objects/{bo_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "business_object_deleted"


def test_business_object_attribute_update_fields_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)
    business_object_id = client.post(
        f"/api/projects/{project_id}/business_objects",
        json={"name": "Order"},
    ).json()["business_object_id"]
    attribute_id = client.post(
        (
            f"/api/projects/{project_id}/business_objects/"
            f"{business_object_id}/attributes"
        ),
        json={
            "name": "total",
            "description": "Old description",
            "data_type": "integer",
            "example": "1",
        },
    ).json()["attribute_id"]

    response = client.put(
        (
            f"/api/projects/{project_id}/business_objects/"
            f"{business_object_id}/attributes/{attribute_id}"
        ),
        json={
            "name": "totalAmount",
            "description": "New description",
            "dataType": "decimal",
            "example": "12.50",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "attribute_id": attribute_id,
        "business_object_id": business_object_id,
        "name": "totalAmount",
        "description": "New description",
        "data_type": "decimal",
        "example": "12.50",
        "confirmation_status": "needs_confirmation",
    }

    response = client.put(
        (
            f"/api/projects/{project_id}/business_objects/"
            f"{business_object_id}/attributes/{attribute_id}"
        ),
        json={"description": "Only description changes"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "totalAmount"
    assert response.json()["data_type"] == "decimal"
    assert response.json()["example"] == "12.50"


def test_flow_crud_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    # Create Flow
    res = client.post(f"/api/projects/{project_id}/flows", json={"name": "Checkout", "description": "Checkout flow"})
    assert res.status_code == 200
    data = res.json()
    assert "flow_id" in data
    assert data["name"] == "Checkout"
    flow_id = data["flow_id"]

    # Update Flow
    res = client.put(f"/api/projects/{project_id}/flows/{flow_id}", json={"name": "CheckoutFlow"})
    assert res.status_code == 200
    assert res.json()["name"] == "CheckoutFlow"

    # Create Step
    res = client.post(f"/api/projects/{project_id}/flows/{flow_id}/steps", json={"name": "Add to cart", "step_type": "systemAction"})
    assert res.status_code == 200
    step_data = res.json()
    assert "step_id" in step_data
    step_id = step_data["step_id"]

    # Update Step
    res = client.put(f"/api/projects/{project_id}/flows/{flow_id}/steps/{step_id}", json={"name": "Add item to cart"})
    assert res.status_code == 200
    assert res.json()["name"] == "Add item to cart"

    # Reorder Steps
    res = client.put(f"/api/projects/{project_id}/flows/{flow_id}/steps/reorder", json={"step_ids": [step_id]})
    if res.status_code != 200:
        print(f"DEBUG: reorder status_code={res.status_code} body={res.text}")
    assert res.status_code == 200

    # Delete Step
    res = client.delete(f"/api/projects/{project_id}/flows/{flow_id}/steps/{step_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "flow_step_deleted"

    # Delete Flow
    res = client.delete(f"/api/projects/{project_id}/flows/{flow_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "flow_deleted"


def test_flow_step_update_relationships_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    actor_id = client.post(
        f"/api/projects/{project_id}/actors",
        json={"name": "Customer"},
    ).json()["actor_id"]
    input_bo_id = client.post(
        f"/api/projects/{project_id}/business_objects",
        json={"name": "Cart"},
    ).json()["business_object_id"]
    output_bo_id = client.post(
        f"/api/projects/{project_id}/business_objects",
        json={"name": "Order"},
    ).json()["business_object_id"]
    flow_id = client.post(
        f"/api/projects/{project_id}/flows",
        json={"name": "Checkout"},
    ).json()["flow_id"]
    current_step_id = client.post(
        f"/api/projects/{project_id}/flows/{flow_id}/steps",
        json={"name": "Review", "step_type": "systemAction"},
    ).json()["step_id"]
    next_step_id = client.post(
        f"/api/projects/{project_id}/flows/{flow_id}/steps",
        json={"name": "Submit", "step_type": "systemAction"},
    ).json()["step_id"]

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}/steps/{current_step_id}",
        json={
            "stepType": "actorAction",
            "actorIds": [actor_id],
            "inputBusinessObjectIds": [input_bo_id],
            "outputBusinessObjectIds": [output_bo_id],
            "nextStepIds": [next_step_id],
        },
    )

    assert response.status_code == 200
    assert response.json()["step_type"] == "actorAction"
    assert response.json()["actor_ids"] == [actor_id]
    assert response.json()["input_business_object_ids"] == [input_bo_id]
    assert response.json()["output_business_object_ids"] == [output_bo_id]
    assert response.json()["next_step_ids"] == [next_step_id]

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}/steps/{current_step_id}",
        json={"name": "Review order"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Review order"
    assert response.json()["actor_ids"] == [actor_id]
    assert response.json()["input_business_object_ids"] == [input_bo_id]
    assert response.json()["output_business_object_ids"] == [output_bo_id]
    assert response.json()["next_step_ids"] == [next_step_id]

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}/steps/{current_step_id}",
        json={"actorIds": [actor_id + 100_000]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_actor_ids"

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}/steps/{current_step_id}",
        json={"description": "Still valid"},
    )
    assert response.status_code == 200
    assert response.json()["actor_ids"] == [actor_id]


def test_flow_update_features_contract(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)
    feature_id = client.post(
        f"/api/projects/{project_id}/features",
        json={"name": "Checkout"},
    ).json()["feature_id"]
    flow_id = client.post(
        f"/api/projects/{project_id}/flows",
        json={"name": "Purchase"},
    ).json()["flow_id"]

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}",
        json={"featureIds": [feature_id]},
    )

    assert response.status_code == 200
    assert response.json()["feature_ids"] == [feature_id]

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}",
        json={"featureIds": [feature_id + 100_000]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_feature_ids"

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}",
        json={"description": "Still linked"},
    )
    assert response.status_code == 200
    assert response.json()["feature_ids"] == [feature_id]


@pytest.mark.asyncio
async def test_delete_flow_step_repairs_topology_and_positions(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)
    flow_id = client.post(
        f"/api/projects/{project_id}/flows",
        json={"name": "Checkout"},
    ).json()["flow_id"]
    successor_id = client.post(
        f"/api/projects/{project_id}/flows/{flow_id}/steps",
        json={"name": "Successor", "step_type": "systemAction"},
    ).json()["step_id"]
    middle_id = client.post(
        f"/api/projects/{project_id}/flows/{flow_id}/steps",
        json={
            "name": "Middle",
            "step_type": "systemAction",
            "next_step_ids": [successor_id],
        },
    ).json()["step_id"]
    predecessor_id = client.post(
        f"/api/projects/{project_id}/flows/{flow_id}/steps",
        json={
            "name": "Predecessor",
            "step_type": "systemAction",
            "next_step_ids": [middle_id],
        },
    ).json()["step_id"]

    response = client.delete(
        f"/api/projects/{project_id}/flows/{flow_id}/steps/{middle_id}"
    )

    assert response.status_code == 200
    async with req_test_db() as session:
        edge_rows = (
            await session.execute(
                select(
                    flow_step_next_table.c.source_step_id,
                    flow_step_next_table.c.target_step_id,
                )
            )
        ).all()
        remaining_steps = (
            await session.execute(
                select(FlowStepModel)
                .where(FlowStepModel.flow_id == flow_id)
                .order_by(FlowStepModel.position)
            )
        ).scalars().all()

    assert edge_rows == [(predecessor_id, successor_id)]
    assert [
        (step.id, step.position)
        for step in remaining_steps
    ] == [(successor_id, 1), (predecessor_id, 2)]


@pytest.mark.asyncio
async def test_reorder_flow_steps_rebuilds_linear_topology(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)
    flow_id = client.post(
        f"/api/projects/{project_id}/flows",
        json={"name": "Checkout"},
    ).json()["flow_id"]
    step_ids = [
        client.post(
            f"/api/projects/{project_id}/flows/{flow_id}/steps",
            json={"name": name, "step_type": "systemAction"},
        ).json()["step_id"]
        for name in ("First", "Second", "Third")
    ]
    reordered_ids = [step_ids[2], step_ids[0], step_ids[1]]

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}/steps/reorder",
        json={"step_ids": reordered_ids},
    )

    assert response.status_code == 200
    assert [
        (step["step_id"], step["position"], step["next_step_ids"])
        for step in response.json()["steps"]
    ] == [
        (reordered_ids[0], 1, [reordered_ids[1]]),
        (reordered_ids[1], 2, [reordered_ids[2]]),
        (reordered_ids[2], 3, []),
    ]

    response = client.put(
        f"/api/projects/{project_id}/flows/{flow_id}/steps/reorder",
        json={"step_ids": [step_ids[0], step_ids[0], step_ids[1]]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "duplicate_step_ids"

    async with req_test_db() as session:
        edge_rows = (
            await session.execute(
                select(
                    flow_step_next_table.c.source_step_id,
                    flow_step_next_table.c.target_step_id,
                ).order_by(flow_step_next_table.c.source_step_id)
            )
        ).all()
    assert set(edge_rows) == {
        (reordered_ids[0], reordered_ids[1]),
        (reordered_ids[1], reordered_ids[2]),
    }


# ═══════════════════════════════════════════════════════════════════
# 2. Node Status and Audit Contracts
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_node_status_and_audit_flow(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    # Create an Actor (manually created, confirmation_status starts as 'needs_confirmation')
    actor_res = client.post(f"/api/projects/{project_id}/actors", json={"name": "Guest"})
    actor_id = actor_res.json()["actor_id"]

    # Modify Node Status
    res = client.patch(
        f"/api/projects/{project_id}/node-status",
        json={"node_kind": "actor", "node_id": actor_id, "confirmation_status": "confirmed"}
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["confirmation_status"] == "confirmed"

    # Verify Actor in database is updated
    async with req_test_db() as session:
        actor = await session.get(ActorModel, actor_id)
        assert actor.confirmation_status == "confirmed"

        # Check Audit Log was written
        stmt = select(AuditLogModel).where(AuditLogModel.project_id == 1)
        logs = (await session.execute(stmt)).scalars().all()
        assert len(logs) > 0
        latest_log = logs[-1]
        assert latest_log.action_type == "update_confirmation_status"
        assert f"id={actor_id}" in latest_log.summary
        assert "confirmed" in latest_log.payload["new_status"]


@pytest.mark.asyncio
async def test_node_status_batch_update(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    actor1 = client.post(f"/api/projects/{project_id}/actors", json={"name": "A1"}).json()["actor_id"]
    actor2 = client.post(f"/api/projects/{project_id}/actors", json={"name": "A2"}).json()["actor_id"]

    # Batch Update
    res = client.patch(
        f"/api/projects/{project_id}/node-status/batch",
        json={
            "nodes": [
                {"node_kind": "actor", "node_id": actor1, "confirmation_status": "needs_confirmation"},
                {"node_kind": "actor", "node_id": actor2, "confirmation_status": "needs_confirmation"}
            ],
            "confirmation_status": "needs_confirmation"
        }
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["updated_count"] == 2

    # Verify database
    async with req_test_db() as session:
        a1 = await session.get(ActorModel, actor1)
        a2 = await session.get(ActorModel, actor2)
        assert a1.confirmation_status == "needs_confirmation"
        assert a2.confirmation_status == "needs_confirmation"


@pytest.mark.asyncio
async def test_node_status_supports_attribute_and_flow_step(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    bo_id = client.post(
        f"/api/projects/{project_id}/business_objects",
        json={"name": "Order", "description": "Customer order"},
    ).json()["business_object_id"]
    attr_id = client.post(
        f"/api/projects/{project_id}/business_objects/{bo_id}/attributes",
        json={
            "name": "status",
            "description": "Order status",
            "data_type": "string",
            "example": "paid",
        },
    ).json()["attribute_id"]

    feature_id = client.post(
        f"/api/projects/{project_id}/features",
        json={"name": "Checkout", "description": "Checkout flow"},
    ).json()["feature_id"]
    flow_id = client.post(
        f"/api/projects/{project_id}/flows",
        json={
            "name": "Checkout flow",
            "description": "Places an order",
            "feature_ids": [feature_id],
        },
    ).json()["flow_id"]
    step_id = client.post(
        f"/api/projects/{project_id}/flows/{flow_id}/steps",
        json={
            "name": "Persist order",
            "description": "Save order data",
            "step_type": "systemAction",
            "actor_ids": [],
            "input_business_object_ids": [bo_id],
            "output_business_object_ids": [bo_id],
            "next_step_ids": [],
        },
    ).json()["step_id"]

    attr_res = client.patch(
        f"/api/projects/{project_id}/node-status",
        json={
            "node_kind": "business_object_attribute",
            "node_id": attr_id,
            "confirmation_status": "confirmed",
        },
    )
    assert attr_res.status_code == 200

    step_res = client.patch(
        f"/api/projects/{project_id}/node-status",
        json={
            "node_kind": "flow_step",
            "node_id": step_id,
            "confirmation_status": "confirmed",
        },
    )
    assert step_res.status_code == 200

    async with req_test_db() as session:
        attr = await session.get(BusinessObjectAttributeModel, attr_id)
        step = await session.get(FlowStepModel, step_id)
        assert attr.confirmation_status == "confirmed"
        assert step.confirmation_status == "confirmed"

    detail = client.get(f"/api/projects/{project_id}").json()
    attrs = detail["businessObjects"][0]["businessObjectAttributes"]
    steps = detail["flows"][0]["flowSteps"]
    assert detail["features"][0]["updatedAt"]
    assert detail["businessObjects"][0]["updatedAt"]
    assert detail["flows"][0]["updatedAt"]
    assert attrs[0]["confirmationStatus"] == "confirmed"
    assert attrs[0]["updatedAt"]
    assert steps[0]["confirmationStatus"] == "confirmed"
    assert steps[0]["updatedAt"]


# ═══════════════════════════════════════════════════════════════════
# 3. Generation Draft Contracts (Mocked Services)
# ═══════════════════════════════════════════════════════════════════

@patch("backend.api.modules.requirements_core.actor.routes.actor_generation_service")
def test_actor_generation_draft_contracts(mock_service, req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    # 1. Create Draft
    mock_service.create_draft = AsyncMock(return_value={
        "draft_id": "draft-123", "project_id": str(project_id), "actors": [{"actor_name": "AI Admin", "actor_description": "AI desc"}]
    })
    res = client.post("/api/actor_generation_drafts", json={"project_id": str(project_id)})
    assert res.status_code == 200
    assert res.json()["draft_id"] == "draft-123"

    # 2. Regenerate Draft
    mock_service.regenerate_draft = AsyncMock(return_value={
        "draft_id": "draft-123", "project_id": str(project_id), "actors": [{"actor_name": "AI Admin Revised", "actor_description": "Revised desc"}]
    })
    res = client.post("/api/actor_generation_drafts/draft-123/regenerate", json={"user_feedback": "more roles"})
    if res.status_code != 200:
        print(f"DEBUG: regenerate draft status_code={res.status_code} body={res.text}")
    assert res.status_code == 200
    assert res.json()["actors"][0]["actor_name"] == "AI Admin Revised"

    # 3. Confirm Draft
    mock_service.confirm_draft = AsyncMock(return_value={
        "project_id": str(project_id), "actor_count": 1, "message": "actors_created"
    })
    res = client.post("/api/actor_generation_drafts/draft-123/confirm")
    assert res.status_code == 200
    assert res.json()["message"] == "actors_created"

    # 4. Discard Draft
    mock_service.discard_draft = AsyncMock(return_value={
        "draft_id": "draft-123", "message": "draft_discarded"
    })
    res = client.delete("/api/actor_generation_drafts/draft-123")
    assert res.status_code == 200
    assert res.json()["message"] == "draft_discarded"


# ═══════════════════════════════════════════════════════════════════
# 4. Requirements Change Side Effects (Perception Invalidation)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_requirements_change_triggering_perception_stale(req_test_db):
    client = TestClient(app)
    project_id = _register_login_and_create_project(client)

    # Lock / mock the notifier to verify it receives notification calls
    mock_notifier = MagicMock()
    mock_notifier.mark_stale = AsyncMock()
    set_notifier(mock_notifier)

    try:
        # Performing a mutation (CRUD Create Actor) should trigger notifier
        res = client.post(f"/api/projects/{project_id}/actors", json={"name": "AuditTester"})
        assert res.status_code == 200
        
        # Verify notifier was called
        mock_notifier.mark_stale.assert_called_once()
        args, kwargs = mock_notifier.mark_stale.call_args
        assert kwargs["project_id"] == 1
        assert "what" in kwargs["stages"]
        assert "ACTOR" in kwargs["perception_kinds"]
    finally:
        # Restore real notifier for other tests (it's globally set in conftest)
        from backend.tests.conftest import TestPerceptionStaleNotifier
        set_notifier(TestPerceptionStaleNotifier())


def test_public_facade_naming_compatibility():
    from backend.api.modules.requirements_core.public import (
        AcceptanceCriterionCreateRequest, ACCreateRequest,
        AcceptanceCriterionUpdateRequest, ACUpdateRequest,
        AcceptanceCriterionResponse, ACResponse,
        BusinessObjectCreateRequest, BOCreateRequest,
        BusinessObjectUpdateRequest, BOUpdateRequest,
        BusinessObjectResponse, BOResponse,
        BusinessObjectAttributeCreateRequest, BOAttributeCreateRequest,
        BusinessObjectAttributeUpdateRequest, BOAttributeUpdateRequest,
        BusinessObjectAttributeResponse, BOAttributeResponse,
    )
    
    assert AcceptanceCriterionCreateRequest is ACCreateRequest
    assert AcceptanceCriterionUpdateRequest is ACUpdateRequest
    assert AcceptanceCriterionResponse is ACResponse
    assert BusinessObjectCreateRequest is BOCreateRequest
    assert BusinessObjectUpdateRequest is BOUpdateRequest
    assert BusinessObjectResponse is BOResponse
    assert BusinessObjectAttributeCreateRequest is BOAttributeCreateRequest
    assert BusinessObjectAttributeUpdateRequest is BOAttributeUpdateRequest
    assert BusinessObjectAttributeResponse is BOAttributeResponse
