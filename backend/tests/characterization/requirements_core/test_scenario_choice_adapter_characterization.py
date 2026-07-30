from unittest.mock import AsyncMock, patch

import pytest

from backend.api.modules.decision_workflow.ports.ports import CandidateContext
from backend.api.modules.requirements_core.scenario.application.choice_adapter import (
    ScenarioGenerationChoiceAdapter,
)


@pytest.mark.asyncio
async def test_generate_batch_candidate_preserves_filter_and_payload():
    adapter = ScenarioGenerationChoiceAdapter()
    adapter._service._load_generation_context = AsyncMock(
        return_value=(
            "Requirements",
            {},
            {},
            [(1, 10), (2, 20), (3, 30)],
        )
    )
    adapter._service._generate_scenarios_concurrently = AsyncMock(
        return_value=[{"generated": True}]
    )
    scenarios = [
        {
            "scenario_name": "Review order",
            "scenario_content": "x" * 120,
            "acceptance_criteria": ["Order is reviewed"],
        }
    ]
    adapter._service._attach_acceptance_criteria_to_generated_scenarios = (
        AsyncMock(return_value=scenarios)
    )
    context = CandidateContext(
        index=0,
        strategy="balanced",
        strategy_id="balanced",
        strategy_label="Balanced",
        project_id=99,
        target={"generation_mode": "batch", "feature_ids": [2]},
        user_feedback="Keep concise",
    )

    with patch(
        (
            "backend.api.modules.requirements_core.scenario.application."
            "choice_adapter.get_content_locale"
        ),
        return_value="en-US",
    ):
        candidate = await adapter.generate_candidate(context)

    generation_call = (
        adapter._service._generate_scenarios_concurrently.await_args.kwargs
    )
    assert generation_call["target_pairs"] == [(2, 20)]
    assert generation_call["max_concurrency"] == (
        adapter._service._batch_max_concurrency
    )
    assert candidate.payload == {
        "project_id": 99,
        "generation_mode": "batch",
        "feature_id": None,
        "feature_ids": [2],
        "actor_id": None,
        "scenarios": scenarios,
    }
    assert candidate.preview["scenario_count"] == 1
    assert candidate.preview["feature_name"] == "Batch Features"
    assert candidate.preview["actor_name"] == "Multiple Actors"
    assert candidate.preview["scenarios"] == [
        {
            "scenario_name": "Review order",
            "scenario_content": "x" * 100,
            "acceptance_criteria": ["Order is reviewed"],
        }
    ]
    assert candidate.draft_type == "scenario"
    assert candidate.apply_behavior == "overwrite"
