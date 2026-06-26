from __future__ import annotations

import asyncio
import json

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.modules.requirements_core.public import (
    AcceptanceCriteriaGenerationService,
)
from backend.integration.skill_backed_services.gherkin_adapter import GherkinAdapter
from backend.integration.skill_backed_services.llm_json_client import (
    SkillBackedLLMJsonClient,
    render_prompt,
)
from backend.integration.skill_backed_services.skill_imports import import_skill_module
from backend.schemas import ScenarioNode


class SkillBackedAcceptanceCriteriaGenerationService(
    AcceptanceCriteriaGenerationService
):
    def __init__(self):
        super().__init__()
        feedback_core = import_skill_module(
            "scenario-feedback-skill",
            "scenario_feedback_skill.core",
        )
        self._feedback_generator = feedback_core.ScenarioFeedback()
        self._adapter = GherkinAdapter()
        self._llm_json_client = SkillBackedLLMJsonClient()

    async def _generate_preview(
        self,
        project_id: int,
        scenario_ids: list[int] | None,
        generation_mode: str,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        (
            user_requirements,
            actor_node_map,
            feature_node_map,
            scenario_nodes,
        ) = await self._load_generation_context(
            project_id=project_id,
            scenario_ids=scenario_ids,
            session=session,
        )

        gherkin_context_by_scenario_id = await self._load_gherkin_context(
            scenario_ids=[
                scenario.scenarioId
                for scenario in scenario_nodes
            ],
            session=session,
        )

        generated_acceptance_criteria = await self._generate_from_gherkin_context(
            user_requirements=user_requirements,
            actor_node_map=actor_node_map,
            feature_node_map=feature_node_map,
            scenario_nodes=scenario_nodes,
            gherkin_context_by_scenario_id=gherkin_context_by_scenario_id,
            user_feedback=user_feedback,
        )

        if not generated_acceptance_criteria:
            raise ValueError("empty_acceptance_criteria")

        generated_acceptance_criteria = self._validate_generated_acceptance_criteria(
            generated_acceptance_criteria,
            {
                scenario.scenarioId
                for scenario in scenario_nodes
            },
        )
        scenario_name_map = {
            scenario.scenarioId: scenario.scenarioName
            for scenario in scenario_nodes
        }

        raw_gherkin_by_spec = {}
        for context in gherkin_context_by_scenario_id.values():
            spec_id = context.get("gherkin_spec_id")
            if spec_id is not None:
                raw_gherkin_by_spec[str(spec_id)] = context["gherkin_json"]

        draft_payload = {
            "project_id": project_id,
            "generation_mode": generation_mode,
            "scenario_ids": [
                scenario.scenarioId
                for scenario in scenario_nodes
            ],
            "raw_gherkin_by_spec": raw_gherkin_by_spec,
            "scenario_acceptance_criteria": generated_acceptance_criteria,
        }

        response_payload = {
            "project_id": project_id,
            "scenario_acceptance_criteria": [
                {
                    "scenario_id": item["scenario_id"],
                    "scenario_name": scenario_name_map[item["scenario_id"]],
                    "acceptance_criteria": item["acceptance_criteria"],
                }
                for item in generated_acceptance_criteria
            ],
        }

        return draft_payload, response_payload

    async def _load_gherkin_context(
        self,
        scenario_ids: list[int],
        session,
    ) -> dict[int, dict]:
        from backend.database.model import ScenarioModel

        scenario_result = await session.execute(
            select(ScenarioModel)
            .where(ScenarioModel.id.in_(scenario_ids))
            .options(selectinload(ScenarioModel.gherkin_spec))
        )
        scenario_models = scenario_result.scalars().all()

        context_by_scenario_id = {}
        for scenario in scenario_models:
            spec = scenario.gherkin_spec
            if (
                spec is None
                or scenario.gherkin_scenario_index is None
            ):
                continue
            context_by_scenario_id[scenario.id] = {
                "gherkin_spec_id": spec.id,
                "gherkin_json": spec.gherkin_json,
                "gherkin_scenario_index": scenario.gherkin_scenario_index,
            }

        return context_by_scenario_id

    async def _generate_from_gherkin_context(
        self,
        user_requirements: str,
        actor_node_map,
        feature_node_map,
        scenario_nodes: list[ScenarioNode],
        gherkin_context_by_scenario_id: dict[int, dict],
        user_feedback: str | None,
    ) -> list[dict]:
        spec_backed_scenarios = [
            scenario
            for scenario in scenario_nodes
            if scenario.scenarioId in gherkin_context_by_scenario_id
        ]
        fallback_scenarios = [
            scenario
            for scenario in scenario_nodes
            if scenario.scenarioId not in gherkin_context_by_scenario_id
        ]

        generated = []

        if spec_backed_scenarios:
            if user_feedback:
                generated.extend(
                    await self._generate_from_revised_specs(
                        scenario_nodes=spec_backed_scenarios,
                        gherkin_context_by_scenario_id=gherkin_context_by_scenario_id,
                        user_feedback=user_feedback,
                        feature_node_map=feature_node_map,
                    )
                )
            else:
                generated.extend(
                    self._generate_directly_from_specs(
                        spec_backed_scenarios,
                        gherkin_context_by_scenario_id,
                    )
                )

        if fallback_scenarios:
            generated.extend(
                await self._generate_acceptance_criteria_concurrently(
                    user_requirements=user_requirements,
                    actor_node_map=actor_node_map,
                    feature_node_map=feature_node_map,
                    scenario_nodes=fallback_scenarios,
                    user_feedback=user_feedback,
                )
            )

        return generated

    def _generate_directly_from_specs(
        self,
        scenario_nodes: list[ScenarioNode],
        gherkin_context_by_scenario_id: dict[int, dict],
    ) -> list[dict]:
        generated = []
        for scenario in scenario_nodes:
            context = gherkin_context_by_scenario_id[scenario.scenarioId]
            raw_scenario = self._adapter.gherkin_scenario_at_index(
                context["gherkin_json"],
                context["gherkin_scenario_index"],
            )
            criteria = (
                self._adapter.acceptance_criteria_from_gherkin_scenario(raw_scenario)
                if raw_scenario is not None
                else []
            )
            if not criteria:
                criteria = [
                    (
                        f"Given {scenario.scenarioContent}, "
                        "When the scenario is executed, "
                        "Then the expected behavior is satisfied."
                    )
                ]
            generated.append(
                {
                    "scenario_id": scenario.scenarioId,
                    "acceptance_criteria": criteria,
                }
            )
        return generated

    async def _generate_from_revised_specs(
        self,
        scenario_nodes: list[ScenarioNode],
        gherkin_context_by_scenario_id: dict[int, dict],
        user_feedback: str,
        feature_node_map,
    ) -> list[dict]:
        scenarios_by_spec_id: dict[int, list[ScenarioNode]] = {}
        for scenario in scenario_nodes:
            context = gherkin_context_by_scenario_id[scenario.scenarioId]
            scenarios_by_spec_id.setdefault(
                context["gherkin_spec_id"],
                [],
            ).append(scenario)

        generated = []
        for scenarios in scenarios_by_spec_id.values():
            first_context = gherkin_context_by_scenario_id[
                scenarios[0].scenarioId
            ]
            feature_name = feature_node_map[
                scenarios[0].featureId
            ].featureName
            revised = await self._revise_gherkin(
                user_feedback=user_feedback,
                gherkin_content=first_context["gherkin_json"],
                feature_name=feature_name,
            )

            for scenario in scenarios:
                scenario_index = gherkin_context_by_scenario_id[
                    scenario.scenarioId
                ]["gherkin_scenario_index"]
                raw_scenario = self._adapter.gherkin_scenario_at_index(
                    revised,
                    scenario_index,
                )
                criteria = (
                    self._adapter.acceptance_criteria_from_gherkin_scenario(
                        raw_scenario
                    )
                    if raw_scenario is not None
                    else []
                )
                if not criteria:
                    criteria = [
                        (
                            f"Given {scenario.scenarioContent}, "
                            "When the scenario is executed, "
                            "Then the expected behavior is satisfied."
                        )
                    ]
                generated.append(
                    {
                        "scenario_id": scenario.scenarioId,
                        "acceptance_criteria": criteria,
                    }
                )

        return generated

    async def _generate_acceptance_criteria_concurrently(
        self,
        user_requirements: str,
        actor_node_map,
        feature_node_map,
        scenario_nodes: list[ScenarioNode],
        user_feedback: str | None = None,
    ) -> list[dict]:
        semaphore = asyncio.Semaphore(self._max_concurrency)

        scenarios_by_pair: dict[tuple[int, int], list[ScenarioNode]] = {}
        for scenario in scenario_nodes:
            scenarios_by_pair.setdefault(
                (scenario.featureId, scenario.actorId),
                [],
            ).append(scenario)

        target_scenario_id_set = {
            scenario.scenarioId
            for scenario in scenario_nodes
        }

        async def generate_one(
            feature_id: int,
            actor_id: int,
            scenarios: list[ScenarioNode],
        ) -> list[dict]:
            async with semaphore:
                feature = feature_node_map[feature_id]
                actor = actor_node_map[actor_id]
                gherkin = self._adapter.build_gherkin_from_scenarios(
                    feature=feature,
                    actor=actor,
                    scenarios=scenarios,
                )
                feedback = user_feedback or (
                    "Add precise Given/When/Then acceptance criteria for each "
                    "scenario while preserving the existing scenario titles, "
                    "order, intent, role, and business vocabulary."
                )
                revised = await self._revise_gherkin(
                    user_feedback=feedback,
                    gherkin_content=gherkin,
                    feature_name=feature.featureName,
                )
                return self._criteria_from_revised_gherkin(
                    revised_gherkin=revised,
                    scenarios=scenarios,
                )

        nested_results = await asyncio.gather(
            *[
                generate_one(feature_id, actor_id, scenarios)
                for (feature_id, actor_id), scenarios in scenarios_by_pair.items()
            ]
        )

        generated_acceptance_criteria = []
        for result in nested_results:
            generated_acceptance_criteria.extend(result)

        return self._validate_generated_acceptance_criteria(
            generated_acceptance_criteria,
            target_scenario_id_set,
        )

    def _criteria_from_revised_gherkin(
        self,
        revised_gherkin: dict,
        scenarios: list[ScenarioNode],
    ) -> list[dict]:
        raw_scenarios = revised_gherkin.get("Scenarios", [])
        if not isinstance(raw_scenarios, list):
            raw_scenarios = []

        result = []
        for index, scenario in enumerate(scenarios):
            raw = raw_scenarios[index] if index < len(raw_scenarios) else {}
            criteria = (
                self._adapter.acceptance_criteria_from_gherkin_scenario(raw)
                if isinstance(raw, dict)
                else []
            )
            if not criteria:
                criteria = [
                    (
                        f"Given {scenario.scenarioContent}, "
                        "When the scenario is executed, "
                        "Then the expected behavior is satisfied."
                    )
                ]
            result.append(
                {
                    "scenario_id": scenario.scenarioId,
                    "acceptance_criteria": criteria,
                }
            )
        return result

    async def _revise_gherkin(
        self,
        user_feedback: str,
        gherkin_content: dict,
        feature_name: str,
    ) -> dict:
        prompt = render_prompt(
            self._feedback_generator._prompts["feedback2Gherkin.txt"],
            {
                "{User Feedback Replacement Flag}": user_feedback,
                "{Gherkin Content Replacement Flag}": json.dumps(
                    gherkin_content,
                    ensure_ascii=False,
                    indent=2,
                ),
                "{Selected Feature Replacement Flag}": feature_name,
            },
        )
        return await self._llm_json_client.ask_json(prompt)
