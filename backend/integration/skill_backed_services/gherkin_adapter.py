from __future__ import annotations

import json
from typing import Any

from backend.schemas import ActorNode, FeatureNode, ScenarioNode


STEP_KEYS = (
    "Given",
    "And",
    "When",
    "Then",
    "But",
)


class GherkinAdapter:
    @staticmethod
    def feature_prompt_text(feature: FeatureNode, actor: ActorNode) -> str:
        return f"{feature.featureName} [Role: {actor.actorName}]"

    def scenario_items_from_skill_result(
        self,
        raw_result: dict[str, Any],
        feature: FeatureNode,
        actor: ActorNode,
    ) -> tuple[list[dict], dict[str, Any]]:
        gherkin = raw_result.get("gherkin", raw_result)
        if not isinstance(gherkin, dict) or not gherkin:
            raise ValueError("invalid_scenario_payload")

        story = raw_result.get("story", {})
        scenario_items: list[dict] = []
        raw_gherkin_by_feature: dict[str, Any] = {}
        target_key = f"{feature.featureId}:{actor.actorId}"
        gherkin_scenario_index = 0

        for feature_key, feature_gherkin in gherkin.items():
            if not isinstance(feature_gherkin, dict):
                continue

            raw_gherkin_by_feature[str(feature_key)] = feature_gherkin
            scenario_content = self._scenario_content(
                feature_key=str(feature_key),
                feature_gherkin=feature_gherkin,
                story=story,
                actor=actor,
                feature=feature,
            )

            scenarios = feature_gherkin.get("Scenarios", [])
            if not isinstance(scenarios, list) or not scenarios:
                continue

            for index, scenario in enumerate(scenarios, start=1):
                if not isinstance(scenario, dict):
                    continue
                scenario_name = (
                    scenario.get("Scenario")
                    or scenario.get("Scenario Outline")
                    or f"{feature.featureName} Scenario {index}"
                )
                criteria = self.acceptance_criteria_from_gherkin_scenario(scenario)
                scenario_items.append(
                    {
                        "feature_id": feature.featureId,
                        "feature_name": feature.featureName,
                        "actor_id": actor.actorId,
                        "actor_name": actor.actorName,
                        "scenario_name": str(scenario_name).strip(),
                        "scenario_content": scenario_content,
                        "acceptance_criteria": criteria,
                        "raw_gherkin": scenario,
                        "gherkin_target_key": target_key,
                        "gherkin_scenario_index": gherkin_scenario_index,
                    }
                )
                gherkin_scenario_index += 1

        if not scenario_items:
            raise ValueError("empty_scenarios")

        return scenario_items, raw_gherkin_by_feature

    def scenario_items_from_revised_gherkin(
        self,
        revised_gherkin: dict[str, Any],
        feature: FeatureNode,
        actor: ActorNode,
    ) -> tuple[list[dict], dict[str, Any]]:
        if "Feature" in revised_gherkin and "Scenarios" in revised_gherkin:
            feature_key = str(revised_gherkin.get("Feature") or feature.featureName)
            wrapped = {feature_key: revised_gherkin}
        else:
            wrapped = revised_gherkin
        return self.scenario_items_from_skill_result(
            {"gherkin": wrapped},
            feature=feature,
            actor=actor,
        )

    def acceptance_criteria_for_existing_scenarios(
        self,
        scenarios: list[ScenarioNode],
    ) -> list[dict]:
        result = []
        for scenario in scenarios:
            result.append(
                {
                    "scenario_id": scenario.scenarioId,
                    "acceptance_criteria": [
                        self._criterion_from_scenario_content(scenario.scenarioContent)
                    ],
                }
            )
        return result

    def build_gherkin_from_scenarios(
        self,
        feature: FeatureNode,
        actor: ActorNode,
        scenarios: list[ScenarioNode],
        acceptance_criteria_by_scenario_id: dict[int, list[str]] | None = None,
    ) -> dict[str, Any]:
        return {
            "Feature": feature.featureName,
            "Narrative": {
                "As": actor.actorName,
                "I want": feature.featureName,
                "So that": feature.featureDescription,
            },
            "Background": {
                "Given": f"the {actor.actorName} is using the system",
                "And": f"the {feature.featureName} capability is available",
            },
            "Scenarios": [
                self._scenario_node_to_gherkin(
                    scenario,
                    acceptance_criteria_by_scenario_id or {},
                )
                for scenario in scenarios
            ],
        }

    @staticmethod
    def acceptance_criteria_from_gherkin_scenario(scenario: dict[str, Any]) -> list[str]:
        parts = []
        for key, value in scenario.items():
            if key in {"Scenario", "Scenario Outline"}:
                continue
            if key == "Examples":
                parts.append(f"Examples: {json.dumps(value, ensure_ascii=False)}")
                continue
            if key in STEP_KEYS or isinstance(value, str):
                if isinstance(value, list):
                    for item in value:
                        parts.append(f"{key} {item}")
                else:
                    parts.append(f"{key} {value}")
        criterion = ", ".join(str(part).strip() for part in parts if str(part).strip())
        return [criterion] if criterion else []

    def gherkin_scenario_at_index(
        self,
        gherkin_content: dict[str, Any],
        scenario_index: int,
    ) -> dict[str, Any] | None:
        current_index = 0
        for feature_gherkin in self._iter_feature_gherkin(gherkin_content):
            scenarios = feature_gherkin.get("Scenarios", [])
            if not isinstance(scenarios, list):
                continue
            for scenario in scenarios:
                if not isinstance(scenario, dict):
                    continue
                if current_index == scenario_index:
                    return scenario
                current_index += 1
        return None

    @staticmethod
    def _iter_feature_gherkin(
        gherkin_content: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if (
            isinstance(gherkin_content, dict)
            and "Feature" in gherkin_content
            and "Scenarios" in gherkin_content
        ):
            return [gherkin_content]

        if not isinstance(gherkin_content, dict):
            return []

        return [
            value
            for value in gherkin_content.values()
            if isinstance(value, dict)
        ]

    def _scenario_content(
        self,
        feature_key: str,
        feature_gherkin: dict[str, Any],
        story: Any,
        actor: ActorNode,
        feature: FeatureNode,
    ) -> str:
        narrative = feature_gherkin.get("Narrative")
        if isinstance(narrative, dict):
            as_part = str(narrative.get("As") or actor.actorName).strip()
            want_part = str(narrative.get("I want") or feature.featureName).strip()
            so_part = str(narrative.get("So that") or feature.featureDescription).strip()
            return f"As a {as_part}, I want to {want_part}, So that {so_part}"

        if isinstance(story, dict) and story.get(feature_key):
            return str(story[feature_key]).strip()

        return (
            f"As a {actor.actorName}, I want to {feature.featureName}, "
            f"So that {feature.featureDescription}"
        )

    @staticmethod
    def _criterion_from_scenario_content(content: str) -> str:
        return f"Given {content}, When the scenario is executed, Then the expected behavior is satisfied."

    def _scenario_node_to_gherkin(
        self,
        scenario: ScenarioNode,
        acceptance_criteria_by_scenario_id: dict[int, list[str]],
    ) -> dict[str, Any]:
        criteria = acceptance_criteria_by_scenario_id.get(scenario.scenarioId, [])
        if criteria:
            return {
                "Scenario": scenario.scenarioName,
                "Given": "the scenario context is prepared",
                "When": scenario.scenarioContent,
                "Then": " ".join(criteria),
            }
        return {
            "Scenario": scenario.scenarioName,
            "Given": scenario.scenarioContent,
            "When": "the user performs the scenario",
            "Then": "the system provides the expected result",
        }
