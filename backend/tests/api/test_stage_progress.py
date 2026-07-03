import os
import pytest
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
    ActorModel, FeatureModel, FeatureRelationModel, ScenarioModel,
    ScenarioAcceptanceCriterionModel, PerceptionJobModel, ProjectModel,
    feature_actor_table
)

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def progress_test_db():
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


def _register_and_login(client):
    reg_payload = {"email": "test_progress_user@example.com", "password": "password123"}
    res = client.post("/api/auth/register", json=reg_payload)
    login_payload = {"email": "test_progress_user@example.com", "password": "password123"}
    client.post("/api/auth/login", json=login_payload)


@pytest.mark.asyncio
async def test_stage_progress_endpoints(progress_test_db):
    client = TestClient(app)
    _register_and_login(client)

    # 1. Create a blank project
    create_payload = {
        "user_requirements": "Test PRD requirements",
        "project_name": "Test Progress Project",
        "project_description": "Test Progress Description"
    }
    response = client.post("/api/blank_projects", json=create_payload)
    assert response.status_code == 200
    public_project_id = response.json()["project_id"]

    # Lookup internal project_id
    async with progress_test_db() as session:
        proj = (await session.execute(select(ProjectModel).where(ProjectModel.public_id == public_project_id))).scalars().first()
        internal_project_id = proj.id

    # 2. Get stage progress initially (should be unlocked_not_started for what)
    response = client.get(f"/api/projects/{public_project_id}/stage-progress")
    assert response.status_code == 200
    data = response.json()
    assert data["projectId"] == public_project_id
    
    what_stage = next(s for s in data["stages"] if s["stage"] == "what")
    assert what_stage["statusCode"] == "unlocked_not_started"
    assert what_stage["unlocked"] is True
    
    failed_codes = [c["code"] for c in what_stage["failedChecks"]]
    assert "missing_actors" in failed_codes
    assert "missing_leaf_features" in failed_codes

    # 3. Add an actor and a feature to move to 'in_progress', and verify 'leaf_feature_without_actor' check
    async with progress_test_db() as session:
        actor = ActorModel(project_id=internal_project_id, name="Test Actor", description="Desc")
        feature = FeatureModel(project_id=internal_project_id, name="Test Leaf Feature", description="Desc")
        session.add_all([actor, feature])
        await session.commit()

    response = client.get(f"/api/projects/{public_project_id}/stage-progress")
    data = response.json()
    what_stage = next(s for s in data["stages"] if s["stage"] == "what")
    assert what_stage["statusCode"] == "in_progress"
    
    failed_checks = what_stage["failedChecks"]
    failed_codes = [c["code"] for c in failed_checks]
    assert "missing_actors" not in failed_codes
    assert "missing_leaf_features" not in failed_codes
    assert "leaf_feature_without_actor" in failed_codes
    
    # Verify failed checks targets
    target_check = next(c for c in failed_checks if c["code"] == "leaf_feature_without_actor")
    assert len(target_check["targets"]) == 1
    assert target_check["targets"][0]["type"] == "feature"
    assert target_check["targets"][0]["name"] == "Test Leaf Feature"

    # 4. Associate feature with actor, add scenario without AC -> 'in_progress', verify 'leaf_feature_without_scenario' check
    async with progress_test_db() as session:
        # Fetch the feature and actor to link them
        f_db = (await session.execute(select(FeatureModel).where(FeatureModel.project_id == internal_project_id))).scalars().first()
        a_db = (await session.execute(select(ActorModel).where(ActorModel.project_id == internal_project_id))).scalars().first()
        
        # Link feature and actor using association table
        await session.execute(feature_actor_table.insert().values(feature_id=f_db.id, actor_id=a_db.id))
        
        scenario = ScenarioModel(
            project_id=internal_project_id, 
            feature_id=f_db.id, 
            actor_id=a_db.id, 
            name="Test Scenario", 
            content="GIVEN something WHEN action THEN result"
        )
        session.add(scenario)
        await session.commit()

    response = client.get(f"/api/projects/{public_project_id}/stage-progress")
    data = response.json()
    what_stage = next(s for s in data["stages"] if s["stage"] == "what")
    failed_checks = what_stage["failedChecks"]
    failed_codes = [c["code"] for c in failed_checks]
    assert "leaf_feature_without_actor" not in failed_codes
    assert "missing_acceptance_criteria" in failed_codes
    
    target_check = next(c for c in failed_checks if c["code"] == "missing_acceptance_criteria")
    assert len(target_check["targets"]) == 1
    assert target_check["targets"][0]["type"] == "scenario"
    assert target_check["targets"][0]["name"] == "Test Scenario"

    # 5. Add AC -> content complete, no findings -> 'ready_to_advance'
    async with progress_test_db() as session:
        s_db = (await session.execute(select(ScenarioModel).where(ScenarioModel.project_id == internal_project_id))).scalars().first()
        ac = ScenarioAcceptanceCriterionModel(
            scenario_id=s_db.id, 
            position=1, 
            content="Must satisfy acceptance criteria"
        )
        session.add(ac)
        await session.commit()

    response = client.get(f"/api/projects/{public_project_id}/stage-progress")
    data = response.json()
    what_stage = next(s for s in data["stages"] if s["stage"] == "what")
    assert what_stage["statusCode"] == "ready_to_advance"
    assert len(what_stage["failedChecks"]) == 0

    # 6. Mock running perception job -> 'analysis_running' (checks that running job status takes priority over ready_to_advance)
    async with progress_test_db() as session:
        job = PerceptionJobModel(
            project_id=internal_project_id, stage="what", perception_kind="what", status="running", 
            target_type="project", target_id=internal_project_id, context_hash="xyz"
        )
        session.add(job)
        await session.commit()

    response = client.get(f"/api/projects/{public_project_id}/stage-progress")
    data = response.json()
    what_stage = next(s for s in data["stages"] if s["stage"] == "what")
    assert what_stage["statusCode"] == "analysis_running"
    assert what_stage["analysisStatus"]["status"] == "running"
    assert what_stage["analysisStatus"]["jobId"] is not None

    # Check How stage is still locked and not started
    how_stage = next(s for s in data["stages"] if s["stage"] == "how")
    assert how_stage["unlocked"] is False
    assert how_stage["statusCode"] == "locked"
    assert how_stage["nextAction"]["kind"] == "none"
    assert how_stage["nextAction"]["route"] is None

    # 7. Transition What stage -> unlocks How stage, How stage becomes 'unlocked_not_started'
    # Complete/succeed the job first
    async with progress_test_db() as session:
        j_db = (await session.execute(select(PerceptionJobModel).where(PerceptionJobModel.project_id == internal_project_id))).scalars().first()
        j_db.status = "success"
        
        # Unlock what stage gate
        p_db = (await session.execute(select(ProjectModel).where(ProjectModel.id == internal_project_id))).scalars().first()
        p_db.unlocked_stages = "what"
        await session.commit()

    response = client.get(f"/api/projects/{public_project_id}/stage-progress")
    data = response.json()
    what_stage = next(s for s in data["stages"] if s["stage"] == "what")
    assert what_stage["statusCode"] == "ready"  # Completed because next stage is unlocked!
    
    how_stage = next(s for s in data["stages"] if s["stage"] == "how")
    assert how_stage["unlocked"] is True
    assert how_stage["statusCode"] == "unlocked_not_started"


@pytest.mark.asyncio
async def test_stage_progress_leaf_relation_requires_same_project_child(progress_test_db):
    client = TestClient(app)
    _register_and_login(client)

    response = client.post("/api/blank_projects", json={
        "user_requirements": "Project A requirements",
        "project_name": "Project A",
        "project_description": "Project A Description"
    })
    assert response.status_code == 200
    project_a_public_id = response.json()["project_id"]

    response = client.post("/api/blank_projects", json={
        "user_requirements": "Project B requirements",
        "project_name": "Project B",
        "project_description": "Project B Description"
    })
    assert response.status_code == 200
    project_b_public_id = response.json()["project_id"]

    async with progress_test_db() as session:
        project_a = (await session.execute(
            select(ProjectModel).where(ProjectModel.public_id == project_a_public_id)
        )).scalar_one()
        project_b = (await session.execute(
            select(ProjectModel).where(ProjectModel.public_id == project_b_public_id)
        )).scalar_one()

        actor = ActorModel(project_id=project_a.id, name="Project A Actor", description="Desc")
        parent_feature = FeatureModel(project_id=project_a.id, name="Project A Feature", description="Desc")
        foreign_child = FeatureModel(project_id=project_b.id, name="Project B Child", description="Desc")
        session.add_all([actor, parent_feature, foreign_child])
        await session.flush()
        session.add(FeatureRelationModel(
            parent_feature_id=parent_feature.id,
            child_feature_id=foreign_child.id,
            position=1,
        ))
        await session.commit()

    response = client.get(f"/api/projects/{project_a_public_id}/stage-progress")
    assert response.status_code == 200
    data = response.json()
    what_stage = next(s for s in data["stages"] if s["stage"] == "what")
    failed_codes = [c["code"] for c in what_stage["failedChecks"]]

    assert "missing_leaf_features" not in failed_codes
    assert "leaf_feature_without_actor" in failed_codes
