import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import patch

from backend.database.model import Base, ProjectModel, ActorModel, FeatureModel
from backend.api.modules.project_lifecycle.application.project_service import ProjectService
from backend.api.modules.diagnosis_quality.finding.application.finding_service import FindingService
from backend.schemas import Finding, FindingType, BlockingScope, IssueStage, IssueSeverity

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
async def seeded_project(db_session) -> int:
    """Create a seed project and return its ID."""
    project = ProjectModel(
        name="Gate findings test project",
        description="Used to test project details, markdown export append gate findings",
        user_requirements="Requirement details",
        kano_status="pending",
        unlocked_stages="what",
    )
    db_session.add(project)
    await db_session.flush()
    return project.id


@pytest.mark.asyncio
async def test_gate_findings_action_filtering(db_session, seeded_project):
    service = FindingService()
    
    # Mock list_findings internal policies to return a gate with EXPORT blocking scope
    mock_gate = Finding(
        findingId="what:EXPORT_TEST_GATE:feature:1",
        type=FindingType.GATE_CONDITION,
        stage=IssueStage.WHAT,
        code="EXPORT_TEST_GATE",
        severity=IssueSeverity.BLOCKING,
        title="测试导出阻塞门禁",
        description="描述测试导出阻塞门禁",
        blockingScope=BlockingScope.EXPORT,
        metadata={}
    )
    
    with patch.object(service._policies["what"], "get_findings", return_value=[mock_gate]):
        # Query with export action, should return the mock gate
        export_gates = await service.list_findings(
            project_id=seeded_project,
            stage="all",
            view="gate",
            action="export",
            session=db_session
        )
        assert len(export_gates) == 1
        assert export_gates[0].code == "EXPORT_TEST_GATE"
        
        # Query with enter_how action, should not return the export gate
        enter_how_gates = await service.list_findings(
            project_id=seeded_project,
            stage="all",
            view="gate",
            action="enter_how",
            session=db_session
        )
        assert len(enter_how_gates) == 0


@pytest.mark.asyncio
async def test_get_project_detail_with_unresolved_gates(db_session, seeded_project):
    project_service = ProjectService()
    
    # Mock list_findings to return a gate blocker for export
    mock_gate = Finding(
        findingId="what:EXPORT_TEST_GATE:feature:1",
        type=FindingType.GATE_CONDITION,
        stage=IssueStage.WHAT,
        code="EXPORT_TEST_GATE",
        severity=IssueSeverity.BLOCKING,
        title="测试导出阻塞门禁",
        description="描述测试导出阻塞门禁",
        blockingScope=BlockingScope.EXPORT,
        metadata={}
    )
    
    with patch.object(FindingService, "list_findings", return_value=[mock_gate]):
        detail = await project_service.get_project_detail(seeded_project, db_session)
        assert len(detail.unresolved_gates) == 1
        assert detail.unresolved_gates[0].code == "EXPORT_TEST_GATE"
        assert detail.unresolved_gates[0].title == "测试导出阻塞门禁"


@pytest.mark.asyncio
async def test_export_project_markdown_appends_gates(db_session, seeded_project):
    project_service = ProjectService()
    
    # Mock list_findings to return a gate blocker for export
    mock_gate = Finding(
        findingId="what:EXPORT_TEST_GATE:feature:1",
        type=FindingType.GATE_CONDITION,
        stage=IssueStage.WHAT,
        code="EXPORT_TEST_GATE",
        severity=IssueSeverity.BLOCKING,
        title="测试导出阻塞门禁",
        description="描述测试导出阻塞门禁",
        blockingScope=BlockingScope.EXPORT,
        metadata={}
    )
    
    # Patch list_findings for project_service.export_project_markdown internally
    with patch.object(FindingService, "list_findings", return_value=[mock_gate]):
        markdown = await project_service.export_project_markdown(seeded_project, db_session)
        assert "## 附录：未处理阶段检查项 (Gates)" in markdown
        assert "测试导出阻塞门禁" in markdown
