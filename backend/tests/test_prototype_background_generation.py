import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.preview_convergence.application.prototype_generation import (
    PrototypeGenerationService,
)
from backend.core.generators.prototype_generator import PrototypeGeneratorInput
from backend.database.model import Base, ProjectModel
from backend.integration.skill_backed_services.prototype_generation_service import (
    SkillBackedPrototypePageGenerator,
)
from backend.schemas import ActorNode, FeatureNode


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def project(session_factory):
    async with session_factory() as session:
        item = ProjectModel(
            name="Background prototype",
            description="Background prototype test",
            user_requirements="Generate a preview",
        )
        session.add(item)
        await session.commit()
        return item.id


@pytest.mark.asyncio
async def test_start_generation_persists_and_completes_in_background(
    session_factory,
    project,
):
    service = PrototypeGenerationService(session_factory=session_factory)
    started = asyncio.Event()
    release = asyncio.Event()

    async def generate_pages(_targets):
        started.set()
        await release.wait()
        return [{
            "page_id": "page-1",
            "role_id": 1,
            "role_name": "User",
            "feature_id": 1,
            "feature_name": "Feature",
            "html": "<main>ready</main>",
            "javascript": "",
            "css": "",
            "source": "test",
            "status": "ready",
        }]

    with patch.object(service, "_generate_pages", side_effect=generate_pages), \
         patch.object(service, "_preview_source", return_value="test_generator"):
        response = await service.start_generation(project, force_regenerate=True)
        assert response.status == "generating"
        assert response.html == ""

        await started.wait()
        task = service._background_tasks[response.prototype_id]
        release.set()
        await task

    async with session_factory() as session:
        latest = await service.get_latest_preview(project, session)
    assert latest.status == "ready"
    assert latest.html == "<main>ready</main>"


@pytest.mark.asyncio
async def test_background_failure_is_persisted(session_factory, project):
    service = PrototypeGenerationService(session_factory=session_factory)

    with patch.object(
        service,
        "_generate_pages",
        new=AsyncMock(side_effect=RuntimeError("provider unavailable")),
    ), patch.object(service, "_preview_source", return_value="test_generator"):
        response = await service.start_generation(project, force_regenerate=True)
        await service._background_tasks[response.prototype_id]

    async with session_factory() as session:
        latest = await service.get_latest_preview(project, session)
    assert latest.status == "failed"
    assert latest.error_message == "provider unavailable"


@pytest.mark.asyncio
async def test_skill_generation_calls_real_generator_for_every_page():
    generator = SkillBackedPrototypePageGenerator()
    actor = SimpleNamespace(actorId=1, actorName="User", actorDescription="User role")
    feature = SimpleNamespace(
        featureId=1,
        featureName="Feature",
        featureDescription="Feature description",
    )
    input_data = SimpleNamespace(
        project_name="Project",
        project_description="Description",
        user_requirements="Requirements",
        actor=actor,
        feature=feature,
    )
    targets = [
        {
            "page_id": f"page-{index}",
            "actor": actor,
            "feature": feature,
            "acceptance_criteria": {},
            "input": input_data,
        }
        for index in range(12)
    ]
    skill_code = {"HTML": "<main>skill</main>", "Javascript": "", "CSS": ""}
    active_calls = 0
    peak_calls = 0

    async def generate_skill_page(*args, **kwargs):
        nonlocal active_calls, peak_calls
        active_calls += 1
        peak_calls = max(peak_calls, active_calls)
        await asyncio.sleep(0.01)
        active_calls -= 1
        return skill_code

    with patch.object(
        generator,
        "_generate_with_skill",
        new=AsyncMock(side_effect=generate_skill_page),
    ) as skill_call, patch(
        "backend.integration.skill_backed_services.prototype_generation_service.asyncio.wait_for",
        side_effect=AssertionError("prototype generation must not impose an outer timeout"),
    ):
        pages = await generator.generate_pages(targets)

    assert len(pages) == 12
    assert skill_call.await_count == 12
    assert peak_calls == 2
    assert all(page["source"] == "gherkin2code_skill" for page in pages)


@pytest.mark.asyncio
async def test_skill_generation_failure_is_not_replaced_with_placeholder():
    generator = SkillBackedPrototypePageGenerator()
    actor = SimpleNamespace(actorId=1, actorName="User", actorDescription="User role")
    feature = SimpleNamespace(
        featureId=1,
        featureName="Feature",
        featureDescription="Feature description",
    )
    target = {
        "page_id": "page-1",
        "actor": actor,
        "feature": feature,
        "acceptance_criteria": {},
        "input": SimpleNamespace(
            project_name="Project",
            project_description="Description",
            user_requirements="Requirements",
            actor=actor,
            feature=feature,
        ),
    }

    with patch.object(
        generator,
        "_generate_with_skill",
        new=AsyncMock(side_effect=RuntimeError("real generation failed")),
    ):
        with pytest.raises(
            RuntimeError,
            match=(
                "prototype_page_generation_failed: page_id=page-1, "
                "role=User, feature=Feature: real generation failed"
            ),
        ):
            await generator.generate_pages([target])


def test_role_feature_targets_exclude_non_current_scope_features():
    actor = ActorNode(actorId=1, actorName="User", actorDescription="User role")
    generator_input = PrototypeGeneratorInput(
        project_id=1,
        project_name="Project",
        project_description="Description",
        user_requirements="Requirements",
        actors=[actor],
        features=[
            FeatureNode(
                featureId=1,
                featureName="Current",
                featureDescription="Current feature",
                actorIds=[1],
            ),
            FeatureNode(
                featureId=2,
                featureName="Postponed",
                featureDescription="Postponed feature",
                actorIds=[1],
            ),
        ],
    )
    detail = SimpleNamespace(features=[
        SimpleNamespace(
            feature_id=1,
            scope=SimpleNamespace(scope_status="current"),
            scenarios=[],
            actor_names=[],
        ),
        SimpleNamespace(
            feature_id=2,
            scope=SimpleNamespace(scope_status="postponed"),
            scenarios=[],
            actor_names=[],
        ),
    ])

    targets = PrototypeGenerationService._build_role_feature_targets(
        generator_input,
        detail,
    )

    assert [target["feature"].featureId for target in targets] == [1]
