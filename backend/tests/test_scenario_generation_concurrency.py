import asyncio

import pytest

from backend.api.modules.requirements_core.scenario.application.scenario_generation_service import (
    ScenarioGenerationService,
)
from backend.integration.skill_backed_services.scenario_generation_service import (
    SkillBackedScenarioGenerationService,
)
from backend.schemas import ActorNode, FeatureNode, ScenarioNode


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
