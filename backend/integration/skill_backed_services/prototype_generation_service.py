from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.api.modules.preview_convergence.ports.preview_generator import PrototypePageGeneratorPort
from backend.api.modules.preview_convergence.public import PrototypeGenerationService
from backend.core.llm_protected_inputs import collect_protected_texts
from backend.integration.skill_backed_services.llm_json_client import (
    SkillBackedLLMJsonClient,
    render_prompt,
)
from backend.integration.skill_backed_services.skill_imports import import_skill_module


class SkillBackedPrototypePageGenerator(PrototypePageGeneratorPort):
    def __init__(self) -> None:
        gherkin2code_core = import_skill_module(
            "gherkin-code-skill",
            "gherkin2code_skill.core",
        )
        self._skill_generator = gherkin2code_core.Gherkin2Code()
        self._llm_json_client = SkillBackedLLMJsonClient()
        self._max_concurrency = 2

    async def generate_pages(
        self,
        targets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return await self._generate_skill_pages_concurrently(targets)

    def preview_source(self) -> str:
        return "role_feature_pages"

    async def _generate_skill_pages_concurrently(
        self,
        targets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def generate_one(target: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                try:
                    code = await self._generate_with_skill(
                        user_requirement=self._requirement_payload_for_target(target),
                        acceptance_criteria=target["acceptance_criteria"],
                    )
                except Exception as error:
                    input_data = target["input"]
                    raise RuntimeError(
                        "prototype_page_generation_failed: "
                        f"page_id={target['page_id']}, "
                        f"role={input_data.actor.actorName}, "
                        f"feature={input_data.feature.featureName}: {error}"
                    ) from error
                return PrototypeGenerationService._page_payload(
                    target=target,
                    code=code,
                    source="gherkin2code_skill",
                )

        tasks = [asyncio.create_task(generate_one(target)) for target in targets]
        try:
            return await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _generate_with_skill(
        self,
        user_requirement: str,
        acceptance_criteria: dict[str, Any],
    ) -> dict[str, str]:
        prompt = render_prompt(
            self._skill_generator._prompts["gherkin2code.txt"],
            {
                "{User Requirement Replacement Flag}": user_requirement,
                "{Acceptance Criteria Replacement Flag}": json.dumps(
                    acceptance_criteria,
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        )
        code = await self._llm_json_client.ask_json(
            prompt,
            protected_inputs=collect_protected_texts(
                user_requirement,
                acceptance_criteria,
            ),
            timeout_seconds=300.0,
        )
        return self._validate_code_payload(code)

    @staticmethod
    def _validate_code_payload(code: dict[str, Any]) -> dict[str, str]:
        html = str(code.get("HTML", ""))
        javascript = str(code.get("Javascript", ""))
        css = str(code.get("CSS", ""))
        if not html and not javascript and not css:
            raise ValueError("invalid_skill_payload")
        return {
            "HTML": html,
            "Javascript": javascript,
            "CSS": css,
        }

    @staticmethod
    def _requirement_payload(detail) -> str:
        return "\n".join(
            part
            for part in [
                f"Project: {detail.project_name}",
                f"Description: {detail.project_description}",
                f"User Requirements: {detail.user_requirements}",
            ]
            if part.strip()
        )

    @staticmethod
    def _requirement_payload_for_target(target: dict[str, Any]) -> str:
        input_data = target["input"]
        return "\n".join(
            part
            for part in [
                f"Project: {input_data.project_name}",
                f"Description: {input_data.project_description}",
                f"User Requirements: {input_data.user_requirements}",
                f"Role: {input_data.actor.actorName} - {input_data.actor.actorDescription}",
                f"Feature: {input_data.feature.featureName} - {input_data.feature.featureDescription}",
            ]
            if part.strip()
        )

    @classmethod
    def _acceptance_criteria_payload(
        cls,
        detail,
        gherkin_specs: list[dict],
    ) -> dict[str, Any]:
        features = []
        for spec in gherkin_specs:
            features.extend(
                cls._feature_gherkin_items(spec.get("gherkin_json"))
            )

        if not features:
            features = cls._fallback_features_from_project_detail(detail)

        return {
            "Features": features,
        }

    @classmethod
    def _feature_gherkin_items(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, dict):
            return []

        if "Feature" in value and "Scenarios" in value:
            return [value]

        items = []
        for child in value.values():
            if isinstance(child, dict):
                if "Feature" in child and "Scenarios" in child:
                    items.append(child)
                else:
                    items.extend(cls._feature_gherkin_items(child))
        return items

    @staticmethod
    def _fallback_features_from_project_detail(detail) -> list[dict[str, Any]]:
        actor_name_by_id = {
            actor.actor_id: actor.actor_name
            for actor in detail.actors
        }

        features = []
        for feature in detail.features:
            scenarios = []
            for scenario in feature.scenarios:
                criteria_text = " ".join(
                    criterion.criterion_content
                    for criterion in scenario.acceptance_criteria
                ).strip()
                scenarios.append(
                    {
                        "Scenario": scenario.scenario_name,
                        "Given": scenario.scenario_content,
                        "When": "the user executes this scenario",
                        "Then": criteria_text
                        or "the system provides the expected result",
                    }
                )

            if not scenarios:
                continue

            actor_names = [
                actor_name_by_id[actor_id]
                for actor_id in feature.actor_ids
                if actor_id in actor_name_by_id
            ]
            features.append(
                {
                    "Feature": feature.feature_name,
                    "Narrative": {
                        "As": ", ".join(actor_names) or "a user",
                        "I want": feature.feature_name,
                        "So that": feature.feature_description,
                    },
                    "Scenarios": scenarios,
                }
            )

        return features
