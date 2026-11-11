from unittest.mock import AsyncMock, patch

import pytest

from backend.api.modules.decision_workflow.ports.ports import CandidateContext
from backend.api.modules.requirements_core.scenario.application.choice_adapter import (
    ScenarioGenerationChoiceAdapter,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [
    {"generation_mode": "pair", "feature_id": 2, "actor_id": 20},
    {"generation_mode": "single", "feature_id": 2},
    {"generation_mode": "batch", "feature_ids": [2, 3]},
    {"generation_mode": "full"},
])
async def test_scenario_candidate_preserves_generation_payload(target):
    adapter = ScenarioGenerationChoiceAdapter()
    scenarios = [
        {
            "feature_id": 2,
            "feature_name": "Review",
            "actor_id": 20,
            "actor_name": "Operator",
            "scenario_name": "Review order",
            "scenario_content": "x" * 120,
            "acceptance_criteria": ["Order is reviewed"],
            "gherkin_target_key": "2:20",
            "gherkin_scenario_index": 0,
        }
    ]
    payload = {
        "project_id": 99,
        **target,
        "scenarios": scenarios,
        "gherkin_by_target": {"2:20": {"Review": {"Scenarios": [{"Then": "Reviewed"}]}}},
    }
    adapter._service._generate_preview = AsyncMock(
        return_value=(payload, {"scenarios": scenarios})
    )
    adapter._service._generate_scenarios_concurrently = AsyncMock()
    adapter._service._attach_acceptance_criteria_to_generated_scenarios = AsyncMock()
    context = CandidateContext(
        index=0,
        strategy="balanced",
        strategy_id="balanced",
        strategy_label="Balanced",
        project_id=99,
        target=target,
        user_feedback="Keep concise",
        workspace_id=7,
    )

    with patch(
        (
            "backend.api.modules.requirements_core.scenario.application."
            "choice_adapter.get_content_locale"
        ),
        return_value="en-US",
    ):
        candidate = await adapter.generate_candidate(context)

    generation_call = adapter._service._generate_preview.await_args.kwargs
    assert generation_call["generation_mode"] == target["generation_mode"]
    assert generation_call["feature_ids"] == target.get("feature_ids")
    assert generation_call["workspace_id"] == 7
    assert "Keep concise" in generation_call["user_feedback"]
    adapter._service._generate_scenarios_concurrently.assert_not_awaited()
    adapter._service._attach_acceptance_criteria_to_generated_scenarios.assert_not_awaited()
    assert candidate.payload == payload
    assert candidate.preview["scenario_count"] == 1
    assert candidate.preview["feature_name"] == (
        "Batch Features" if target["generation_mode"] == "batch" else "Review"
    )
    assert candidate.preview["actor_name"] == (
        "Multiple Actors" if target["generation_mode"] == "batch" else "Operator"
    )
    assert candidate.preview["scenarios"] == [
        {
            "scenario_name": "Review order",
            "scenario_content": "x" * 100,
            "acceptance_criteria": ["Order is reviewed"],
        }
    ]
    assert candidate.draft_type == "scenario"
    assert candidate.apply_behavior == "overwrite"
