from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.api.schemas.prototype_generation_schema import PrototypePreviewResponse
from backend.api.services.prototype_generation_service import PrototypeGenerationService
from backend.database.model import PrototypePreviewModel
from backend.integration.skill_backed_services.llm_json_client import (
    SkillBackedLLMJsonClient,
    render_prompt,
)
from backend.integration.skill_backed_services.skill_imports import import_skill_module


class SkillBackedPrototypeGenerationService(PrototypeGenerationService):
    def __init__(self) -> None:
        super().__init__()
        gherkin2code_core = import_skill_module(
            "gherkin-code-skill",
            "gherkin2code_skill.core",
        )
        self._skill_generator = gherkin2code_core.Gherkin2Code()
        self._llm_json_client = SkillBackedLLMJsonClient()

    async def generate_preview(
        self,
        project_id: int,
        session,
        force_regenerate: bool = True,
    ) -> PrototypePreviewResponse:
        if not force_regenerate:
            latest = await self.get_latest_preview(
                project_id=project_id,
                session=session,
                raise_if_missing=False,
            )
            if latest is not None:
                return latest

        detail = await self._project_service.get_project_detail(
            project_id=project_id,
            session=session,
        )
        gherkin_specs = await self._load_gherkin_specs(
            project_id=project_id,
            session=session,
        )
        generator_input = self._build_generator_input(
            detail=detail,
            gherkin_specs=gherkin_specs,
        )
        targets = self._build_role_feature_targets(
            generator_input=generator_input,
            detail=detail,
        )
        pages = await self._generate_skill_pages_concurrently(targets)
        first_page = pages[0] if pages else self._empty_page(project_id)

        preview = PrototypePreviewModel(
            project_id=project_id,
            status="ready",
            source="role_feature_pages",
            html=first_page["html"],
            javascript=first_page["javascript"],
            css=first_page["css"],
            pages=pages,
            input_snapshot=detail.model_dump(
                mode="json",
                by_alias=True,
            ),
            gherkin_snapshot={"specs": gherkin_specs} if gherkin_specs else None,
        )
        session.add(preview)
        await session.flush()
        return self._to_response(preview)

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
                    source = "gherkin2code_skill"
                except Exception:
                    code = await self._generator.generate_page(target["input"])
                    source = "placeholder_fallback"
                return self._page_payload(
                    target=target,
                    code=code,
                    source=source,
                )

        return await asyncio.gather(
            *[
                generate_one(target)
                for target in targets
            ]
        )

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
        code = await self._llm_json_client.ask_json(prompt)
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
