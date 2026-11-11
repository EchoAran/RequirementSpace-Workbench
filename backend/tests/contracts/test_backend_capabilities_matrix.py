"""Contract tests verifying capability implementation matrix boundaries and negative contract behavior."""

import pytest

from backend.api.bootstrap import bootstrap_services
from backend.api.modules.requirements_core.domain_rule.domain.model_invariants import (
    validate_rule_confirmation_status,
    validate_rule_origin,
    validate_rule_text,
)
from backend.api.modules.requirements_core.domain_rule.ports import get_domain_rule_service
from backend.api.modules.requirements_core.ports import get_flow_generation_service


def test_flow_generation_is_local_only():
    bootstrap_services()
    assert get_flow_generation_service().__class__.__name__ == "FlowGenerationService"


def test_domain_rule_service_is_local_only():
    bootstrap_services()
    rule_service = get_domain_rule_service()
    assert rule_service.__class__.__name__ == "DomainRuleService"
    assert "skill" not in rule_service.__class__.__module__.lower()


def test_domain_rule_empty_and_whitespace_rejections():
    """Empty and pure whitespace titles/statements must be strictly rejected without fallback."""
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_rule_text("", "Valid statement")

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_rule_text("   ", "Valid statement")

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_rule_text("Valid Title", "")

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_rule_text("Valid Title", "   \n\t  ")


def test_domain_rule_invalid_origin_rejections():
    """Unrecognized origins must raise explicit ValueError without silent fallback."""
    with pytest.raises(ValueError, match="Invalid rule origin"):
        validate_rule_origin("external_sync")

    with pytest.raises(ValueError, match="Invalid rule origin"):
        validate_rule_origin("auto_magic")


def test_domain_rule_invalid_confirmation_status_rejections():
    """Unrecognized confirmation status must raise explicit ValueError."""
    with pytest.raises(ValueError, match="Invalid confirmation status"):
        validate_rule_confirmation_status("approved_by_boss")

    with pytest.raises(ValueError, match="Invalid confirmation status"):
        validate_rule_confirmation_status("pending")


def test_shipped_generation_implementation_classes():
    from backend.api.modules.requirements_core.ports import (
        get_actor_generation_service,
        get_feature_generation_service,
        get_scenario_generation_service,
        get_acceptance_criteria_generation_service,
        get_scope_generation_service,
    )

    registry = bootstrap_services()
    assert registry.generation_backend == "skill"
    assert get_actor_generation_service().__class__.__name__ == "ActorGenerationService"
    assert get_feature_generation_service().__class__.__name__ == "SkillBackedFeatureGenerationService"
    assert get_scenario_generation_service().__class__.__name__ == "SkillBackedScenarioGenerationService"
    assert get_acceptance_criteria_generation_service().__class__.__name__ == "SkillBackedAcceptanceCriteriaGenerationService"
    assert get_scope_generation_service().__class__.__name__ == "SkillBackedScopeGenerationService"


@pytest.mark.parametrize("obsolete_backend", ["legacy", "skill", "non_existent_backend"])
def test_obsolete_backend_environment_does_not_change_services(monkeypatch, obsolete_backend):
    from backend.api.modules.requirements_core.ports import get_feature_generation_service

    monkeypatch.setenv("REQUIREMENTSPACE_GENERATION_BACKEND", obsolete_backend)
    assert bootstrap_services().generation_backend == "skill"
    assert get_feature_generation_service().__class__.__name__ == "SkillBackedFeatureGenerationService"


@pytest.fixture
def mocker():
    from unittest.mock import patch
    class PatchWrapper:
        def __call__(self, *args, **kwargs):
            return patch(*args, **kwargs).start()
        def object(self, target, attribute, *args, **kwargs):
            return patch.object(target, attribute, *args, **kwargs).start()
    class Mocker:
        patch = PatchWrapper()
    yield Mocker()
    patch.stopall()


@pytest.mark.asyncio
async def test_llm_malformed_response_fails_without_draft_persistence(mocker):
    """Verify that malformed or empty LLM generation results fail explicitly with zero draft persistence."""
    from backend.integration.skill_backed_services.llm_json_client import SkillBackedLLMJsonClient

    client = SkillBackedLLMJsonClient()

    # 1. Empty/None response
    mocker.patch.object(client._llm_handler, "call_llm", return_value=None)
    with pytest.raises(ValueError, match="invalid_skill_payload"):
        await client.ask_json("dummy prompt")

    # 2. HTML Error Gateway response
    mocker.patch.object(client._llm_handler, "call_llm", return_value="<html>502 Bad Gateway</html>")
    with pytest.raises(ValueError, match="invalid_skill_json"):
        await client.ask_json("dummy prompt")

    # 3. Invalid JSON structure
    mocker.patch.object(client._llm_handler, "call_llm", return_value="{invalid_json: true}")
    with pytest.raises(ValueError, match="invalid_skill_json"):
        await client.ask_json("dummy prompt")

    # 4. Valid JSON but not an object (e.g., list or scalar)
    mocker.patch.object(client._llm_handler, "call_llm", return_value='["item1", "item2"]')
    with pytest.raises(ValueError, match="invalid_skill_json: expected object"):
        await client.ask_json("dummy prompt")


import asyncio
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database.database import Base
from backend.database.model import BranchWorkspaceModel, RequirementBranchModel, FeatureModel, GenerativeDraftModel, ProjectModel
from backend.api.modules.requirements_core.public import FeatureGenerationService
from backend.integration.skill_backed_services.feature_generation_service import (
    SkillBackedFeatureGenerationService,
)


@pytest_asyncio.fixture
async def matrix_db_session():
    """Isolated in-memory sqlite session for generation persistence boundary tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        project = ProjectModel(
            id=201,
            name="Persistence Boundary Project",
            user_requirements="A complete project management system with tasks and boards.",
            owner_user_id=1,
        )
        session.add(project)
        await session.flush()
        branch = RequirementBranchModel(project_id=project.id, name="codex/matrix", created_by_user_id=1)
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id)
        session.add(workspace)
        await session.flush()
        workspace_id = workspace.id
        await session.commit()
        yield session, workspace_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_feature_generation_service_negative_persistence_boundary(mocker, matrix_db_session):
    """Test FeatureGenerationService persistence boundary under 502/HTML, empty, timeout, and schema error."""
    service = FeatureGenerationService()
    session, workspace_id = matrix_db_session

    # Verify initial database state: 0 drafts, 0 features
    draft_cnt = (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar()
    feat_cnt = (await session.execute(select(func.count(FeatureModel.id)))).scalar()
    assert draft_cnt == 0
    assert feat_cnt == 0

    # Ensure skill client is NOT called
    from backend.integration.skill_backed_services.llm_json_client import SkillBackedLLMJsonClient
    mock_skill_ask = mocker.patch.object(SkillBackedLLMJsonClient, "ask_json", side_effect=AssertionError("Skill client must not be invoked by the local feature service"))

    # Case 1: 502 / HTML error
    mocker.patch.object(service._features_generator, "generate", side_effect=ValueError("502 Bad Gateway: <html>Error</html>"))
    with pytest.raises(ValueError, match="502 Bad Gateway"):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 2: Empty response
    mocker.patch.object(service._features_generator, "generate", return_value={"features": []})
    with pytest.raises(ValueError, match="empty_features"):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 3: Timeout error
    mocker.patch.object(service._features_generator, "generate", side_effect=asyncio.TimeoutError("Generation call timed out"))
    with pytest.raises(asyncio.TimeoutError):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 4: Schema error (child node missing root parent)
    mocker.patch.object(service._features_generator, "generate", return_value={
        "features": [
            {"feature_number": "F001-001", "feature_name": "Child without root", "feature_description": "desc"}
        ]
    })
    with pytest.raises(ValueError, match="missing_parent_feature"):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 5: Locale conflict / mismatch error
    from backend.core.llm_locale_validation import LLMContentLocaleMismatchError
    mocker.patch.object(service._features_generator, "generate", side_effect=LLMContentLocaleMismatchError())
    with pytest.raises(LLMContentLocaleMismatchError, match="llm_content_locale_mismatch"):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 6: Mid-persistence failure and transaction rollback boundary
    corrupt_draft = {
        "project_id": 201,
        "features": [
            {"feature_number": "F001", "feature_name": "Root Feature", "feature_description": "Valid root", "actor_ids": []},
            {"feature_number": "F002-001", "feature_name": "Child without F002", "feature_description": "Broken relation", "actor_ids": []},
        ],
    }
    with pytest.raises(ValueError, match="missing_parent_feature"):
        try:
            await service._persist_feature_generation_draft(corrupt_draft, session, workspace_id=workspace_id)
        except Exception:
            await session.rollback()
            raise
    # Assert zero persisted features in DB after rollback
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Final assert: Skill client was never called (zero cross-adapter fallback)
    assert mock_skill_ask.call_count == 0


@pytest.mark.asyncio
async def test_skill_backed_feature_generation_negative_persistence_boundary(mocker, matrix_db_session):
    """Test SkillBackedFeatureGenerationService persistence boundary under 502/HTML, empty, timeout, schema, and locale error."""
    service = SkillBackedFeatureGenerationService()
    session, workspace_id = matrix_db_session

    # Ensure legacy generator is NOT called
    from backend.core.generators.features_generator import FeaturesGenerator
    mock_legacy_gen = mocker.patch.object(FeaturesGenerator, "generate", side_effect=AssertionError("Local generator must not be invoked by the skill feature service"))

    # Case 1: 502 / HTML error
    mocker.patch.object(service._llm_json_client._llm_handler, "call_llm", return_value="<html>502 Bad Gateway</html>")
    with pytest.raises(ValueError, match="invalid_skill_json"):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 2: Empty / None response
    mocker.patch.object(service._llm_json_client._llm_handler, "call_llm", return_value="")
    with pytest.raises(ValueError, match="invalid_skill_json"):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 3: Timeout error
    mocker.patch.object(service._llm_json_client._llm_handler, "call_llm", side_effect=asyncio.TimeoutError("Network timeout to LLM provider"))
    with pytest.raises(asyncio.TimeoutError):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 4: Schema error (tightened to specific explicit ValueError)
    mocker.patch.object(service._llm_json_client._llm_handler, "call_llm", return_value='{"completely_unknown_schema": true}')
    with pytest.raises(ValueError, match="invalid_root_feature_count"):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 5: Locale conflict / mismatch error
    from backend.core.llm_locale_validation import LLMContentLocaleMismatchError
    mocker.patch.object(service._llm_json_client, "ask_json", side_effect=LLMContentLocaleMismatchError())
    with pytest.raises(LLMContentLocaleMismatchError, match="llm_content_locale_mismatch"):
        await service.create_draft(project_id=201, owner_user_id=1, session=session, workspace_id=workspace_id)
    assert (await session.execute(select(func.count(GenerativeDraftModel.id)))).scalar() == 0
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Case 6: Mid-persistence failure and transaction rollback boundary
    corrupt_draft = {
        "project_id": 201,
        "features": [
            {"feature_number": "F001", "feature_name": "Root Feature", "feature_description": "Valid root", "actor_ids": []},
            {"feature_number": "F002-001", "feature_name": "Child without F002", "feature_description": "Broken relation", "actor_ids": []},
        ],
    }
    with pytest.raises(ValueError, match="missing_parent_feature"):
        try:
            await service._persist_feature_generation_draft(corrupt_draft, session, workspace_id=workspace_id)
        except Exception:
            await session.rollback()
            raise
    # Assert zero persisted features in DB after rollback
    assert (await session.execute(select(func.count(FeatureModel.id)))).scalar() == 0

    # Final assert: Legacy generator was never called (zero cross-adapter fallback)
    assert mock_legacy_gen.call_count == 0
