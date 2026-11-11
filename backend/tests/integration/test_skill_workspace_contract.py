from unittest.mock import AsyncMock, patch

import pytest

from backend.api.modules.decision_workflow.ports.ports import CandidateContext
from backend.integration.skill_backed_services.scenario_generation_service import (
    SkillBackedScenarioGenerationService,
)


@pytest.mark.asyncio
async def test_scenario_confirmation_uses_resolved_workspace():
    service = object.__new__(SkillBackedScenarioGenerationService)
    service._get_draft = AsyncMock(return_value={"project_id": 1, "workspace_id": 99})
    service._persist_scenario_generation_draft = AsyncMock(return_value={})
    notifier = AsyncMock()
    with (
        patch("backend.integration.skill_backed_services.scenario_generation_service.get_notifier", return_value=notifier),
        patch("backend.api.modules.decision_workflow.public.GenerativeDraftStore.delete_draft", new_callable=AsyncMock),
    ):
        await service.confirm_draft("draft", 1, None, workspace_id=2)
    assert service._persist_scenario_generation_draft.call_args.kwargs["workspace_id"] == 2
    assert notifier.mark_stale.call_args.kwargs["workspace_id"] == 2


def test_creation_candidate_can_precede_project_workspace():
    context = CandidateContext(index=0, strategy="balanced")
    assert context.project_id is None
    assert context.workspace_id is None
