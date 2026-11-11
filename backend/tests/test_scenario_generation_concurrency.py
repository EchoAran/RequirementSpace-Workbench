import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.api.modules.requirements_core.scenario.application.scenario_generation_service import (
    ScenarioGenerationService,
)
from backend.integration.skill_backed_services.scenario_generation_service import (
    SkillBackedScenarioGenerationService,
)
from backend.schemas import ActorNode, FeatureNode, ScenarioNode
from backend.services.llm_handler_service import LLMCallFailedError


@pytest.mark.asyncio
async def test_legacy_scenario_candidates_share_one_concurrency_limit(monkeypatch):
    monkeypatch.setenv("SCENARIO_GENERATION_MAX_CONCURRENCY", "2")
    service = ScenarioGenerationService()
    active = 0
    peak = 0

    async def generate(_input):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"scenarios": [{"scenario_name": "name", "scenario_content": "content"}]}

    monkeypatch.setattr(service._scenarios_generator, "generate", generate)
    actors = {1: ActorNode(actorId=1, actorName="Actor", actorDescription="")}
    features = {1: FeatureNode(featureId=1, featureName="Feature", featureDescription="")}
    args = {
        "user_requirements": "requirements",
        "actor_node_map": actors,
        "feature_node_map": features,
        "target_pairs": [(1, 1)] * 3,
    }

    await asyncio.gather(
        service._generate_scenarios_concurrently(**args),
        service._generate_scenarios_concurrently(**args),
    )

    assert peak == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["targets", "steps"])
async def test_skill_failure_cancels_sibling_calls(operation, monkeypatch):
    monkeypatch.setenv("SCENARIO_GENERATION_MAX_CONCURRENCY", "2")
    service = SkillBackedScenarioGenerationService()
    started = asyncio.Event()
    cancelled = asyncio.Event()
    failure = LLMCallFailedError("API call failed: status_code=429")

    async def worker(key, _value):
        if key == "First":
            await started.wait()
            raise failure
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    if operation == "steps":
        generation = service._gather_step_dicts([("First", ""), ("Second", "")], worker)
    else:
        async def generate_result(requirement, feature):
            return await worker(feature.split(" [Role:", 1)[0], requirement)

        service._generate_scenario_result = generate_result
        generation = service._generate_with_skill(
            user_requirements="requirements",
            actor_node_map={1: ActorNode(actorId=1, actorName="Actor", actorDescription="")},
            feature_node_map={
                index: FeatureNode(featureId=index, featureName=name, featureDescription="")
                for index, name in enumerate(["First", "Second"], start=1)
            },
            target_pairs=[(1, 1), (2, 1)],
            user_feedback=None,
        )

    with pytest.raises(LLMCallFailedError) as caught:
        await asyncio.wait_for(generation, timeout=1)
    assert caught.value is failure
    assert cancelled.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize(("failure", "error_type"), [
    (LLMCallFailedError("API call failed: status_code=429"), "llm_error"),
    (ValueError("invalid_skill_json: expected object, got list"), "parse_error"),
    (ValueError("empty_scenarios"), "validation_error"),
    (RuntimeError("broken generator"), "internal_error"),
])
async def test_scenario_error_preserves_cause_and_target(failure, error_type):
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
        run_candidate_generation,
    )

    service = SkillBackedScenarioGenerationService()
    service._llm_json_client.ask_json = AsyncMock(side_effect=failure)

    async def generate_one(_context):
        return await service._generate_with_skill(
            user_requirements="requirements",
            actor_node_map={3: ActorNode(actorId=3, actorName="Actor", actorDescription="")},
            feature_node_map={7: FeatureNode(featureId=7, featureName="Feature", featureDescription="")},
            target_pairs=[(7, 3)],
            user_feedback=None,
        )

    result = await run_candidate_generation(
        count=1, max_concurrency=1, timeout_seconds=1, generate_one=generate_one,
    )
    assert result.success_count == 0
    assert result.failure_count == 1
    error = result.errors[0]
    assert error.error_type == error_type
    assert error.message == str(failure)
    assert "scenario_step=Features2Story.txt" in error.detail
    assert "feature_id=7 actor_id=3" in error.detail


@pytest.mark.asyncio
async def test_legacy_scenario_and_criteria_stages_share_one_concurrency_limit(monkeypatch):
    monkeypatch.setenv("SCENARIO_GENERATION_MAX_CONCURRENCY", "2")
    service = ScenarioGenerationService()
    active = 0
    peak = 0

    async def generate_scenarios(_input):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"scenarios": [{"scenario_name": "name", "scenario_content": "content"}]}

    async def generate_criteria(input_data):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {
            "scenario_acceptance_criteria": [
                {"scenario_id": item.scenarioId, "acceptance_criteria": ["criterion"]}
                for item in input_data.scenarios
            ]
        }

    monkeypatch.setattr(service._scenarios_generator, "generate", generate_scenarios)
    monkeypatch.setattr(
        service._acceptance_criteria_generation_service._acceptance_criteria_generator,
        "generate",
        generate_criteria,
    )
    actors = {1: ActorNode(actorId=1, actorName="Actor", actorDescription="")}
    features = {1: FeatureNode(featureId=1, featureName="Feature", featureDescription="")}
    scenarios = [
        ScenarioNode(
            scenarioId=index,
            scenarioName=f"Scenario {index}",
            scenarioContent="content",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[],
        )
        for index in range(1, 4)
    ]
    generation_args = {
        "user_requirements": "requirements",
        "actor_node_map": actors,
        "feature_node_map": features,
        "target_pairs": [(1, 1)] * 3,
    }
    criteria_args = {
        "user_requirements": "requirements",
        "actor_node_map": actors,
        "feature_node_map": features,
        "generated_scenarios": [
            {
                "scenario_name": item.scenarioName,
                "scenario_content": item.scenarioContent,
                "feature_id": item.featureId,
                "actor_id": item.actorId,
            }
            for item in scenarios
        ],
    }

    await asyncio.gather(
        service._generate_scenarios_concurrently(**generation_args),
        service._attach_acceptance_criteria_to_generated_scenarios(**criteria_args),
    )

    assert peak == 2


@pytest.mark.asyncio
async def test_scenario_llm_calls_share_one_concurrency_limit(monkeypatch):
    monkeypatch.setenv("SCENARIO_SKILL_STEP_MAX_CONCURRENCY", "2")
    service = SkillBackedScenarioGenerationService()
    active = 0
    peak = 0

    async def ask_json(*_args, **_kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {}

    monkeypatch.setattr(service._llm_json_client, "ask_json", ask_json)

    await asyncio.gather(*[
        service._do_scenario_step("Features2Story.txt", {})
        for _ in range(6)
    ])

    assert peak == 2
