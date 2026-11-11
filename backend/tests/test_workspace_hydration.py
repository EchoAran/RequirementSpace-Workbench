import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.diagnosis_quality.finding.application.finding_service import FindingService
from backend.api.modules.project_lifecycle.application.project_service import ProjectService
from backend.api.modules.project_lifecycle.schemas.project import FindingsByView
from backend.api.modules.version_control.application.clean_initialization import create_initial_workspace
from backend.database.model import (
    ActorModel,
    Base,
    FeatureModel,
    ProjectModel,
    UserModel,
)


@pytest.fixture
async def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def seeded_project(db_session) -> tuple[int, int, int]:
    """Create a user and seed project."""
    user = UserModel(
        email="test@example.com",
        password_hash="fake_hash_password",
    )
    db_session.add(user)
    await db_session.flush()

    project = ProjectModel(
        name="Hydration Test Project",
        description="Unified hydration benchmark project",
        user_requirements="User needs a fast workbench",
        kano_status="pending",
        unlocked_stages="what,how",
        owner_user_id=user.id,
    )
    db_session.add(project)
    await db_session.flush()
    # New-world invariant: hydration resolves the branch context and loads
    # workspace-scoped entities, so attach the seed entities to the main workspace.
    _branch, main_ws = await db_session.run_sync(lambda s: create_initial_workspace(s, project))
    main_ws_id = main_ws.id

    actor = ActorModel(
        project_id=project.id,
        workspace_id=main_ws_id,
        name="Admin",
        description="System Administrator",
    )
    db_session.add(actor)

    feature = FeatureModel(
        project_id=project.id,
        workspace_id=main_ws_id,
        name="Dashboard",
        description="Analytics Dashboard",
    )
    db_session.add(feature)
    await db_session.flush()

    return project.id, user.id, main_ws_id


@pytest.mark.asyncio
async def test_list_all_findings_views_single_pass(db_session, seeded_project):
    """Test that list_all_findings_views partitions findings in a single pass."""
    project_id, _, workspace_id = seeded_project
    service = FindingService()

    views = await service.list_all_findings_views(
        project_id=project_id,
        session=db_session,
        stage="all",
        workspace_id=workspace_id,
    )

    assert isinstance(views, dict)
    assert "issues" in views
    assert "health" in views
    assert "gate" in views
    assert "next_action" in views
    assert isinstance(views["issues"], list)
    assert isinstance(views["health"], list)
    assert isinstance(views["gate"], list)
    assert isinstance(views["next_action"], list)


@pytest.mark.asyncio
async def test_get_workspace_hydration_full_structure(db_session, seeded_project):
    """Test that get_workspace_hydration aggregates project detail, findings, and stage progress."""
    project_id, user_id, _ = seeded_project
    service = ProjectService()

    hydration = await service.get_workspace_hydration(
        project_id=project_id,
        session=db_session,
        user_id=user_id,
    )

    assert hydration.project_id is not None
    assert hydration.project_detail is not None
    assert hydration.project_detail.project_name == "Hydration Test Project"
    assert len(hydration.project_detail.actors) >= 1
    assert len(hydration.project_detail.features) >= 1
    assert hydration.findings_by_view is not None
    assert isinstance(hydration.backend_findings, list)
    assert hydration.stage_progress is not None


def test_findings_by_view_uses_camel_case_wire_key():
    serialized = FindingsByView(
        issues=[],
        next_action=[],
        gate=[],
        health=[],
    ).model_dump(by_alias=True)

    assert "nextAction" in serialized
    assert "next_action" not in serialized
