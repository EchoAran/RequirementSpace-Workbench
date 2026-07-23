import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.modules.requirements_core.feature.application.feature_generation_service import (
    FeatureGenerationService,
)
from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    GenerationChoiceService,
    GenerationChoiceSettings,
)
from backend.api.modules.project_lifecycle.application.creation_choice_service import (
    ProjectCreationChoiceGroupService,
)
from backend.api.modules.decision_workflow.ports.ports import GenerationCandidate
from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.core.llm_locale_validation import LLMContentLocaleMismatchError
from backend.schemas import ActorNode


def _feature_response(description: str) -> str:
    return json.dumps(
        {
            "features": [
                {
                    "feature_number": "F001",
                    "feature_name": "English feature title",
                    "feature_description": description,
                    "actor_ids": [1],
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_corrected_feature_response_is_the_only_draft_saved():
    service = FeatureGenerationService()
    service._features_generator._llm_handler.temperature = "0.7"
    service._load_project_context = AsyncMock(
        return_value=(
            "Create a music player",
            [ActorNode(actorId=1, actorName="Listener", actorDescription="Listens to local music")],
        )
    )
    wrong = _feature_response("This English description is wrong for the Chinese project locale.")
    corrected_payload = json.loads(_feature_response("这是纠正后写入草稿的中文功能说明。"))
    corrected = json.dumps(corrected_payload, ensure_ascii=False)
    service._features_generator._llm_handler._call_api = AsyncMock(
        side_effect=[wrong, corrected]
    )
    saved = AsyncMock()
    token = current_llm_context.set(
        LLMRequestContext("https://llm.example.com", "sk-test", "test-model", "zh-CN")
    )
    try:
        with patch(
            "backend.api.modules.decision_workflow.draft_store.GenerativeDraftStore.save_draft",
            saved,
        ):
            await service.create_draft(project_id=1, owner_user_id=7, session=AsyncMock())
    finally:
        current_llm_context.reset(token)

    saved.assert_awaited_once()
    saved_payload = saved.await_args.kwargs["payload"]
    assert saved_payload["features"][0]["feature_description"] == "这是纠正后写入草稿的中文功能说明。"
    assert "wrong for the Chinese" not in str(saved_payload)


@pytest.mark.asyncio
async def test_two_wrong_feature_responses_do_not_create_a_draft():
    service = FeatureGenerationService()
    service._features_generator._llm_handler.temperature = "0.7"
    service._load_project_context = AsyncMock(
        return_value=(
            "Create a music player",
            [ActorNode(actorId=1, actorName="Listener", actorDescription="Listens to local music")],
        )
    )
    wrong = _feature_response("This feature description remains in English after correction.")
    service._features_generator._llm_handler._call_api = AsyncMock(side_effect=[wrong, wrong])
    saved = AsyncMock()
    token = current_llm_context.set(
        LLMRequestContext("https://llm.example.com", "sk-test", "test-model", "zh-CN")
    )
    try:
        with patch(
            "backend.api.modules.decision_workflow.draft_store.GenerativeDraftStore.save_draft",
            saved,
        ):
            with pytest.raises(LLMContentLocaleMismatchError):
                await service.create_draft(project_id=1, owner_user_id=7, session=AsyncMock())
    finally:
        current_llm_context.reset(token)

    saved.assert_not_awaited()


@pytest.mark.asyncio
async def test_locale_mismatch_does_not_create_a_generation_choice_group():
    adapter = MagicMock()
    adapter.generate_candidate = AsyncMock(side_effect=LLMContentLocaleMismatchError())
    session = MagicMock()
    session.flush = AsyncMock()
    service = GenerationChoiceService(
        GenerationChoiceSettings(candidate_count=2, max_concurrency=2)
    )

    with patch(
        "backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service.get_adapter",
        return_value=adapter,
    ), patch(
        "backend.api.modules.project_configuration.public.resolve_generation_strategies",
        AsyncMock(return_value=[]),
    ):
        with pytest.raises(LLMContentLocaleMismatchError):
            await service.create_choice_group(
                project_id=1,
                generation_type="actor",
                session=session,
            )

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_mixed_locale_mismatch_does_not_create_a_generation_choice_group():
    adapter = MagicMock()
    adapter.generate_candidate = AsyncMock(
        side_effect=[
            GenerationCandidate("Valid candidate", "Valid rationale", {"value": "valid"}),
            LLMContentLocaleMismatchError(),
        ]
    )
    session = MagicMock()
    session.flush = AsyncMock()
    service = GenerationChoiceService(
        GenerationChoiceSettings(candidate_count=2, max_concurrency=1)
    )

    with patch(
        "backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service.get_adapter",
        return_value=adapter,
    ), patch(
        "backend.api.modules.project_configuration.public.resolve_generation_strategies",
        AsyncMock(return_value=[]),
    ):
        with pytest.raises(LLMContentLocaleMismatchError):
            await service.create_choice_group(
                project_id=1,
                generation_type="actor",
                session=session,
            )

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_locale_mismatch_does_not_save_onboarding_choice_group_draft():
    service = ProjectCreationChoiceGroupService()
    service._settings = GenerationChoiceSettings(candidate_count=2, max_concurrency=2)
    service._adapter.generate_candidate = AsyncMock(
        side_effect=LLMContentLocaleMismatchError()
    )
    saved = AsyncMock()

    with patch(
        "backend.api.modules.decision_workflow.draft_store.GenerativeDraftStore.save_draft",
        saved,
    ):
        with pytest.raises(LLMContentLocaleMismatchError):
            await service.create_choice_group(
                user_requirements="Create a music player",
                owner_user_id=7,
                session=MagicMock(),
            )

    saved.assert_not_awaited()


@pytest.mark.asyncio
async def test_mixed_locale_mismatch_does_not_save_onboarding_choice_group_draft():
    service = ProjectCreationChoiceGroupService()
    service._settings = GenerationChoiceSettings(candidate_count=2, max_concurrency=1)
    service._adapter.generate_candidate = AsyncMock(
        side_effect=[
            GenerationCandidate("Valid candidate", "Valid rationale", {"value": "valid"}),
            LLMContentLocaleMismatchError(),
        ]
    )
    saved = AsyncMock()

    with patch(
        "backend.api.modules.decision_workflow.draft_store.GenerativeDraftStore.save_draft",
        saved,
    ):
        with pytest.raises(LLMContentLocaleMismatchError):
            await service.create_choice_group(
                user_requirements="Create a music player",
                owner_user_id=7,
                session=MagicMock(),
            )

    saved.assert_not_awaited()
