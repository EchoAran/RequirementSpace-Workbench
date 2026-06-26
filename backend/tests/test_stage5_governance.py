import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from backend.database.model import (
    Base,
    ProjectModel,
    ActorModel,
    FeatureModel,
    PerceptionJobModel,
    GenerativeDraftModel,
)
from backend.schemas import PerceptionJobStatus
from backend.api.modules.diagnosis_quality.next_suggestion.application.next_suggestion_service import (
    NextSuggestionService,
)
from backend.api.modules.diagnosis_quality.perception.application.slot_filling import (
    PerceptionSlotFillingService,
)
from backend.api.modules.diagnosis_quality.perception.application.draft_creator import (
    PerceptionDraftCreator,
)
from backend.api.modules.diagnosis_quality.perception.application.draft_discarder import (
    PerceptionDraftDiscarder,
)
from backend.api.modules.decision_workflow.public import GenerativeDraftStore

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_next_suggestion_perception_insertion_order(db_session):
    # Setup: Create a project
    project = ProjectModel(
        name="Governance Test Project",
        description="Testing perception insertion order",
        owner_user_id=1,
        user_requirements="Default requirement space",
        unlocked_stages="what,how",
    )
    db_session.add(project)
    await db_session.commit()
    project_id = project.id
    public_id = project.public_id

    # Seed actors/features to make the project state valid
    actor = ActorModel(project_id=project_id, name="User", description="Normal User")
    feature = FeatureModel(project_id=project_id, name="Home", description="Home page")
    db_session.add_all([actor, feature])
    await db_session.commit()

    # Bind actor to feature
    from backend.database.model import feature_actor_table
    await db_session.execute(feature_actor_table.insert().values(feature_id=feature.id, actor_id=actor.id))
    await db_session.commit()

    # Seed scenario and acceptance criterion
    from backend.database.model import ScenarioModel, ScenarioAcceptanceCriterionModel
    scenario = ScenarioModel(
        project_id=project_id,
        feature_id=feature.id,
        actor_id=actor.id,
        name="Test Scenario",
        content="Scenario Content",
        confirmation_status="confirmed",
    )
    db_session.add(scenario)
    await db_session.commit()

    ac = ScenarioAcceptanceCriterionModel(
        scenario_id=scenario.id,
        position=1,
        content="AC Content",
        confirmation_status="confirmed",
    )
    db_session.add(ac)
    await db_session.commit()

    # Define NextSuggestionService
    suggestion_service = NextSuggestionService()

    # Verify that without perception jobs, next suggestion triggers running perception
    res = await suggestion_service.get_next_suggestion(
        project_id=project_id,
        stage="what",
        session=db_session,
        public_project_id=public_id,
    )
    assert res["suggestion"]["code"] in ("ACTOR_PERCEPTION_RUNNING", "ACTOR_PERCEPTION_NOT_STARTED")

    # Load actual context and compute correct context hashes
    from backend.core.detectors.issue_context_loader import load_issue_project_context
    from backend.api.modules.diagnosis_quality.perception.application.job import PerceptionJobService
    context = await load_issue_project_context(project_id=project_id, session=db_session)
    job_service = PerceptionJobService()
    hash_actor = job_service._build_context_hash("ACTOR", "", context)
    hash_feature = job_service._build_context_hash("FEATURE", "", context)

    # Find the existing ACTOR job created by suggestion_service and update it
    stmt = select(PerceptionJobModel).where(
        PerceptionJobModel.project_id == project_id,
        PerceptionJobModel.stage == "what",
        PerceptionJobModel.perception_kind == "ACTOR"
    )
    res_job = await db_session.execute(stmt)
    job_actor = res_job.scalar_one()
    job_actor.status = PerceptionJobStatus.DONE_WITH_SLOT.value
    job_actor.result_slot_payload = {
        "perception_kind_code": "ACTOR",
        "perception_description": "Found a missing actor: Admin",
    }

    # Seed FEATURE perception job (which hasn't been created yet)
    job_feature = PerceptionJobModel(
        project_id=project_id,
        stage="what",
        perception_kind="FEATURE",
        target_type="project",
        target_id="",
        context_hash=hash_feature,
        status=PerceptionJobStatus.DONE_WITH_SLOT.value,
        result_slot_payload={
            "perception_kind_code": "FEATURE",
            "perception_description": "Found a missing feature: Login",
        },
    )
    db_session.add(job_feature)
    await db_session.commit()

    # Now run get_next_suggestion. ACTOR must have priority over FEATURE!
    res_ready = await suggestion_service.get_next_suggestion(
        project_id=project_id,
        stage="what",
        session=db_session,
        public_project_id=public_id,
    )
    assert res_ready["suggestion"]["code"] == "ACTOR_SLOT"
    assert res_ready["suggestion"]["description"] == "Found a missing actor: Admin"

    # Now mark the ACTOR job as done (empty or stale or none) so only FEATURE is left
    job_actor.status = PerceptionJobStatus.DONE_EMPTY.value
    await db_session.commit()

    # Feature should now be suggested
    res_ready_2 = await suggestion_service.get_next_suggestion(
        project_id=project_id,
        stage="what",
        session=db_session,
        public_project_id=public_id,
    )
    assert res_ready_2["suggestion"]["code"] == "FEATURE_SLOT"
    assert res_ready_2["suggestion"]["description"] == "Found a missing feature: Login"


@pytest.mark.asyncio
async def test_perception_slot_filling_flow(db_session):
    # Setup: Create a project
    project = ProjectModel(
        name="Slot Filling Test Project",
        description="Testing slot filling confirmation flow",
        owner_user_id=1,
        user_requirements="Default requirement space",
        unlocked_stages="what,how",
    )
    db_session.add(project)
    await db_session.commit()
    project_id = project.id

    # Seed a perception job
    job = PerceptionJobModel(
        project_id=project_id,
        stage="what",
        perception_kind="ACTOR",
        target_type="project",
        target_id="",
        context_hash="hash_actor_flow",
        status=PerceptionJobStatus.DONE_WITH_SLOT.value,
    )
    db_session.add(job)
    await db_session.commit()

    # Create a slot filling draft payload
    draft_id = "test_actor_draft_id"
    draft_payload = {
        "project_id": project_id,
        "filler_kind": "actor",
        "perception_job_id": job.id,
        "actors": [
            {
                "actor_name": "Auditor",
                "actor_description": "Performs system audits",
            }
        ],
    }

    # Save the draft in GenerativeDraftStore
    await GenerativeDraftStore.save_draft(
        project_id=project_id,
        draft_id=draft_id,
        draft_type="perception_slot_filling",
        payload=draft_payload,
        owner_user_id=1,
        session=db_session,
    )

    # Instantiate slot filling service
    slot_filling_service = PerceptionSlotFillingService()

    # Confirm the draft
    res = await slot_filling_service.confirm_draft(
        draft_id=draft_id,
        owner_user_id=1,
        session=db_session,
    )
    assert res["message"] == "perception_slot_filled"
    assert res["created_count"] == 1

    # 1. Verify actor is persisted in database
    actors_result = await db_session.execute(
        select(ActorModel).where(ActorModel.project_id == project_id)
    )
    actors = actors_result.scalars().all()
    assert len(actors) == 1
    assert actors[0].name == "Auditor"
    assert actors[0].confirmation_status == "ai_assumption"

    # 2. Verify draft is deleted from GenerativeDraftStore
    draft_db = await db_session.execute(
        select(GenerativeDraftModel).where(GenerativeDraftModel.draft_id == draft_id)
    )
    assert draft_db.scalar_one_or_none() is None

    # 3. Verify perception job status is marked STALE
    # Since confirming an actor draft modifies the project context, related perception jobs must be updated to STALE
    job_db = await db_session.get(PerceptionJobModel, job.id)
    assert job_db.status == PerceptionJobStatus.STALE.value


@pytest.mark.asyncio
async def test_perception_slot_filling_discard_draft(db_session):
    """Verify discard_draft returns expected response and discards locally."""
    project = ProjectModel(
        name="Discard Test",
        description="Testing discard flow",
        owner_user_id=1,
        user_requirements="test",
        unlocked_stages="what",
    )
    db_session.add(project)
    await db_session.commit()

    job = PerceptionJobModel(
        project_id=project.id,
        stage="what",
        perception_kind="ACTOR",
        target_type="project", target_id="",
        context_hash="h",
        status=PerceptionJobStatus.DONE_WITH_SLOT.value,
    )
    db_session.add(job)
    await db_session.commit()

    draft_id = "discard_test_draft"
    await GenerativeDraftStore.save_draft(
        project_id=project.id,
        draft_id=draft_id,
        draft_type="perception_slot_filling",
        payload={"project_id": project.id, "filler_kind": "actor", "perception_job_id": job.id, "actors": []},
        owner_user_id=1,
        session=db_session,
    )

    result = await PerceptionSlotFillingService().discard_draft(
        draft_id=draft_id,
        owner_user_id=1,
    )
    assert result["draft_id"] == draft_id
    assert result["message"] == "draft_discarded"


@pytest.mark.asyncio
async def test_perception_slot_filling_confirm_unsupported_kind(db_session):
    """Confirm with an unsupported filler_kind raises ValueError."""
    project = ProjectModel(
        name="Unsupported Kind",
        description="Test unsupported filler kind",
        owner_user_id=1,
        user_requirements="test",
        unlocked_stages="what",
    )
    db_session.add(project)
    await db_session.commit()

    draft_id = "unsupported_kind_draft"
    await GenerativeDraftStore.save_draft(
        project_id=project.id,
        draft_id=draft_id,
        draft_type="perception_slot_filling",
        payload={
            "project_id": project.id,
            "filler_kind": "unknown_type",
            "perception_job_id": 0,
            "actors": [],
        },
        owner_user_id=1,
        session=db_session,
    )

    with pytest.raises(ValueError, match="unsupported_filler_kind"):
        await PerceptionSlotFillingService().confirm_draft(
            draft_id=draft_id,
            owner_user_id=1,
            session=db_session,
        )


@pytest.mark.asyncio
async def test_perception_slot_filling_confirm_nonexistent_draft(db_session):
    """Confirming a non-existent draft raises ValueError."""
    with pytest.raises(ValueError, match="draft_not_found"):
        await PerceptionSlotFillingService().confirm_draft(
            draft_id="nonexistent",
            owner_user_id=1,
            session=db_session,
        )


@pytest.mark.asyncio
async def test_perception_slot_filling_regenerate_nonexistent_draft(db_session):
    """Regenerating a non-existent draft raises ValueError."""
    with pytest.raises(ValueError, match="draft_not_found"):
        await PerceptionDraftCreator().regenerate_draft(
            draft_id="nonexistent",
            owner_user_id=1,
            session=db_session,
        )


@pytest.mark.asyncio
async def test_perception_draft_creator_can_instantiate_independently():
    """PerceptionDraftCreator can be instantiated and holds 5 fillers."""
    creator = PerceptionDraftCreator()
    assert creator._actors_filler is not None
    assert creator._features_filler is not None
    assert creator._scenarios_filler is not None
    assert creator._acceptance_criteria_filler is not None
    assert creator._flows_filler is not None


@pytest.mark.asyncio
async def test_perception_draft_discarder_can_instantiate_independently():
    """PerceptionDraftDiscarder can be instantiated independently."""
    discarder = PerceptionDraftDiscarder()
    assert discarder is not None
