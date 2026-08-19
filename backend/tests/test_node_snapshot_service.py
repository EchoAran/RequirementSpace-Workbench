import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database.model import (
    Base,
    ActorModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    CollaborationTaskModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
)
from backend.api.modules.optimistic_lock.snapshot_service import NodeSnapshotService

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
    yield session_factory
    await engine.dispose()

@pytest.mark.asyncio
async def test_node_snapshot_semantic_hashing(test_db):
    service = NodeSnapshotService()

    async with test_db() as session:
        # Create a test project and actor
        project = ProjectModel(
            name="Test Hash Project",
            owner_user_id=1,
            user_requirements="Initial reqs"
        )
        session.add(project)
        await session.commit()
        project_id = project.id

        actor = ActorModel(
            project_id=project_id,
            name="Semantic Actor",
            description="This is a test actor",
            confirmation_status="ai_assumption"
        )
        session.add(actor)
        await session.commit()
        actor_id = actor.id

    # 1. Fetch initial snapshot and hash
    async with test_db() as session:
        res1 = await service.get_snapshot_and_hash(session, "actor", actor_id)
        hash1 = res1["hash"]
        snapshot1 = res1["snapshot"]
        assert snapshot1 == {"name": "Semantic Actor", "description": "This is a test actor"}

    # 2. Modify non-semantic field (confirmation_status) and verify hash remains unchanged
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.confirmation_status = "confirmed"
        await session.commit()

    async with test_db() as session:
        res2 = await service.get_snapshot_and_hash(session, "actor", actor_id)
        hash2 = res2["hash"]
        assert hash1 == hash2

    # 3. Modify semantic field (description) and verify hash changes
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.description = "Updated description"
        await session.commit()

    async with test_db() as session:
        res3 = await service.get_snapshot_and_hash(session, "actor", actor_id)
        hash3 = res3["hash"]
        assert hash1 != hash3
        assert res3["snapshot"] == {"name": "Semantic Actor", "description": "Updated description"}


@pytest.mark.asyncio
async def test_build_snapshot_preserves_each_node_kind_shape():
    service = NodeSnapshotService()
    session = AsyncMock()
    actor = ActorModel(
        id=1,
        project_id=1,
        name="Actor",
        description="Actor description",
    )
    parent = FeatureModel(
        id=2,
        project_id=1,
        name="Parent",
        description="Parent description",
    )
    feature = FeatureModel(
        id=3,
        project_id=1,
        name="Feature",
        description="Feature description",
        actors=[actor],
    )
    feature.parent_relation = FeatureRelationModel(
        parent_feature_id=parent.id,
        child_feature_id=feature.id,
        position=1,
    )
    scenario = ScenarioModel(
        id=4,
        project_id=1,
        feature_id=feature.id,
        actor_id=actor.id,
        name="Scenario",
        content="Given input",
    )
    criterion = ScenarioAcceptanceCriterionModel(
        id=5,
        scenario_id=scenario.id,
        position=1,
        content="Then output",
    )
    attribute = BusinessObjectAttributeModel(
        id=6,
        business_object_id=7,
        name="Code",
        description="Object code",
        data_type="string",
        example="A-1",
    )
    business_object = BusinessObjectModel(
        id=7,
        project_id=1,
        name="Object",
        description="Object description",
        attributes=[attribute],
    )
    flow_step = FlowStepModel(
        id=8,
        flow_id=9,
        position=1,
        name="Step",
        description="Step description",
        step_type="task",
        actors=[actor],
        input_business_objects=[business_object],
        output_business_objects=[business_object],
    )
    flow = FlowModel(
        id=9,
        project_id=1,
        name="Flow",
        description="Flow description",
        steps=[flow_step],
    )
    scope = ScopeModel(
        id=10,
        feature_id=feature.id,
        status="CURRENT",
        positive_summary="Included",
        negative_summary=None,
        reason="Core",
        kano_category="M",
    )

    snapshots = {
        kind: await service.build_snapshot(session, kind, node)
        for kind, node in (
            ("actor", actor),
            ("feature", feature),
            ("scenario", scenario),
            ("acceptance_criterion", criterion),
            ("business_object", business_object),
            ("flow", flow),
            ("flow_step", flow_step),
            ("scope", scope),
            ("business_object_attribute", attribute),
        )
    }

    assert snapshots == {
        "actor": {
            "name": "Actor",
            "description": "Actor description",
        },
        "feature": {
            "name": "Feature",
            "description": "Feature description",
            "parent_id": 2,
            "actor_ids": [1],
        },
        "scenario": {
            "name": "Scenario",
            "content": "Given input",
            "feature_id": 3,
            "actor_id": 1,
        },
        "acceptance_criterion": {
            "content": "Then output",
            "position": 1,
            "scenario_id": 4,
        },
        "business_object": {
            "name": "Object",
            "description": "Object description",
            "attributes": [
                {
                    "name": "Code",
                    "description": "Object code",
                    "data_type": "string",
                    "example": "A-1",
                }
            ],
        },
        "flow": {
            "name": "Flow",
            "description": "Flow description",
            "steps": [
                {
                    "position": 1,
                    "name": "Step",
                    "description": "Step description",
                    "step_type": "task",
                }
            ],
        },
        "flow_step": {
            "name": "Step",
            "description": "Step description",
            "position": 1,
            "step_type": "task",
            "flow_id": 9,
            "actor_ids": [1],
            "input_business_object_ids": [7],
            "output_business_object_ids": [7],
        },
        "scope": {
            "feature_id": 3,
            "status": "CURRENT",
            "positive_summary": "Included",
            "negative_summary": "",
            "reason": "Core",
            "kano_category": "M",
        },
        "business_object_attribute": {
            "name": "Code",
            "description": "Object code",
            "data_type": "string",
            "example": "A-1",
        },
    }
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_supersede_tasks_preserves_single_and_batch_behavior():
    service = NodeSnapshotService()
    service.get_snapshot_and_hash = AsyncMock(
        return_value={"hash": "new-hash"}
    )
    unchanged_single_task = CollaborationTaskModel(
        id=20,
        project_id=1,
        task_type="confirm_node",
        target_type="actor",
        target_id="1",
        title="Unchanged",
        status="open",
        content_hash="new-hash",
        assigned_to_user_id=2,
        created_by_user_id=1,
    )
    stale_single_task = CollaborationTaskModel(
        id=21,
        project_id=1,
        task_type="confirm_node",
        target_type="actor",
        target_id="1",
        title="Stale",
        status="open",
        content_hash="old-hash",
        assigned_to_user_id=2,
        created_by_user_id=1,
    )
    stale_batch_task = CollaborationTaskModel(
        id=22,
        project_id=1,
        task_type="confirm_nodes",
        target_type="batch",
        target_id="batch",
        title="Batch",
        status="open",
        content_hash="batch-hash",
        targets=[
            {
                "node_kind": "actor",
                "node_id": 1,
                "hash": "old-hash",
            }
        ],
        assigned_to_user_id=2,
        created_by_user_id=1,
    )

    def result_for(tasks):
        result = MagicMock()
        result.scalars.return_value.all.return_value = tasks
        return result

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            result_for([unchanged_single_task, stale_single_task]),
            result_for([stale_batch_task]),
        ]
    )
    node = ActorModel(
        id=1,
        project_id=1,
        name="Actor",
        description="Updated",
    )

    await service.supersede_tasks_on_node_update(
        session,
        "ACTOR",
        node,
    )

    assert unchanged_single_task.status == "open"
    assert stale_single_task.status == "superseded"
    assert stale_batch_task.status == "superseded"
    assert session.execute.await_count == 2
    assert session.add.call_count == 4


@pytest.mark.asyncio
async def test_node_optimistic_locking(test_db):
    service = NodeSnapshotService()
    from datetime import datetime, timedelta
    from fastapi import HTTPException

    async with test_db() as session:
        project = ProjectModel(
            name="Test Lock Project",
            owner_user_id=1,
            user_requirements="Initial requirements text"
        )
        session.add(project)
        await session.commit()
        project_id = project.id

        actor = ActorModel(
            project_id=project_id,
            name="Locking Actor",
            description="Testing optimistic locking description"
        )
        session.add(actor)
        await session.commit()
        actor_id = actor.id
        initial_updated_at = actor.updated_at

    # 1. Matching timestamps should pass without error
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        await service.check_optimistic_lock(session, "actor", actor_db, initial_updated_at)
        await service.check_optimistic_lock(session, "actor", actor_db, initial_updated_at.isoformat())

    # 2. Mismatched timestamps should raise 409 HTTPException
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        stale_updated_at = initial_updated_at - timedelta(seconds=10)
        with pytest.raises(HTTPException) as exc_info:
            await service.check_optimistic_lock(session, "actor", actor_db, stale_updated_at)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["message"] == "node_content_changed"
        assert exc_info.value.detail["current_snapshot"]["name"] == "Locking Actor"
