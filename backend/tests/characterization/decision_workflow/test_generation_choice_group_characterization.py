from unittest.mock import MagicMock

import pytest

from backend.api.modules.decision_workflow.candidate_generation.application import (
    generation_choice_service as service_module,
)
from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    GenerationChoiceService,
    GenerationChoiceSettings,
)


@pytest.mark.asyncio
async def test_disabled_choice_group_fails_before_adapter_lookup(monkeypatch):
    adapter_lookup = MagicMock()
    monkeypatch.setattr(service_module, "get_adapter", adapter_lookup)
    service = GenerationChoiceService(
        settings=GenerationChoiceSettings(enabled=False)
    )

    with pytest.raises(
        ValueError,
        match=r"^choice_group_disabled_for_type:actor ",
    ):
        await service.create_choice_group(
            project_id=1,
            generation_type="actor",
            workspace_id=2,
        )

    adapter_lookup.assert_not_called()
