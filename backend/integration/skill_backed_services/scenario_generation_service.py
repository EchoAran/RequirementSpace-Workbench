from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4

from backend.api.modules.requirements_core.public import (
    ScenarioGenerationService,
    get_notifier,
)
from backend.integration.skill_backed_services.gherkin_adapter import GherkinAdapter
from backend.integration.skill_backed_services.llm_json_client import (
    SkillBackedLLMJsonClient,
    render_prompt,
)
from backend.integration.skill_backed_services.skill_imports import import_skill_module


logger = logging.getLogger(__name__)


class SkillBackedScenarioGenerationService(ScenarioGenerationService):
    def __init__(self):
        super().__init__()
        scenario_core = import_skill_module(
            "scenario-generation-skill",
            "scenario_generation_skill.core",
        )
        feedback_core = import_skill_module(
            "scenario-feedback-skill",
            "scenario_feedback_skill.core",
        )
        self._skill_generator = scenario_core.ScenarioGeneration()
        self._feedback_generator = feedback_core.ScenarioFeedback()
        self._adapter = GherkinAdapter()
        self._llm_json_client = SkillBackedLLMJsonClient()
        self._step_max_concurrency = self._read_int_env(
            "SCENARIO_SKILL_STEP_MAX_CONCURRENCY",
            self._max_concurrency,
        )

    async def regenerate_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        user_feedback: str | None,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        if not user_feedback or not draft.get("gherkin_by_target"):
            return await super().regenerate_draft(
                draft_id=draft_id,
                owner_user_id=owner_user_id,
                user_feedback=user_feedback,
                session=session,
            )

        (
            _user_requirements,
            actor_node_map,
            feature_node_map,
            target_pairs,
        ) = await self._load_generation_context(
            project_id=draft["project_id"],
            feature_id=draft.get("feature_id"),
            actor_id=draft.get("actor_id"),
            generation_mode=draft["generation_mode"],
            session=session,
        )

        generated_scenarios = []
        gherkin_by_target = {}

        for feature_id, actor_id in target_pairs:
            key = self._target_key(feature_id, actor_id)
            raw_gherkin = draft.get("gherkin_by_target", {}).get(key)
            if raw_gherkin is None:
                continue

            feature_node = feature_node_map[feature_id]
            actor_node = actor_node_map[actor_id]
            revised = await self._revise_gherkin(
                user_feedback=user_feedback,
                gherkin_content=raw_gherkin,
                feature_name=feature_node.featureName,
            )
            items, target_gherkin = self._adapter.scenario_items_from_revised_gherkin(
                revised,
                feature=feature_node,
                actor=actor_node,
            )
            generated_scenarios.extend(items)
            gherkin_by_target[key] = target_gherkin

        if not generated_scenarios:
            return await super().regenerate_draft(
                draft_id=draft_id,
                owner_user_id=owner_user_id,
                user_feedback=user_feedback,
                session=session,
            )

        draft_payload, response_payload = self._build_draft_response(
            project_id=draft["project_id"],
            feature_id=draft.get("feature_id"),
            actor_id=draft.get("actor_id"),
            generation_mode=draft["generation_mode"],
            generated_scenarios=generated_scenarios,
            gherkin_by_target=gherkin_by_target,
        )
        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=draft["project_id"],
            draft_id=draft_id,
            draft_type="scenario",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )
        return response_payload

    async def _generate_preview(
        self,
        project_id: int,
        feature_id: int | None,
        actor_id: int | None,
        generation_mode: str,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        (
            user_requirements,
            actor_node_map,
            feature_node_map,
            target_pairs,
        ) = await self._load_generation_context(
            project_id=project_id,
            feature_id=feature_id,
            actor_id=actor_id,
            generation_mode=generation_mode,
            session=session,
        )

        generated_scenarios, gherkin_by_target = await self._generate_with_skill(
            user_requirements=user_requirements,
            actor_node_map=actor_node_map,
            feature_node_map=feature_node_map,
            target_pairs=target_pairs,
            user_feedback=user_feedback,
        )

        if not generated_scenarios:
            raise ValueError("empty_scenarios")

        return self._build_draft_response(
            project_id=project_id,
            feature_id=feature_id,
            actor_id=actor_id,
            generation_mode=generation_mode,
            generated_scenarios=generated_scenarios,
            gherkin_by_target=gherkin_by_target,
        )

    async def confirm_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
        generate_acceptance_criteria: bool = False,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        result = await self._persist_scenario_generation_draft(
            draft=draft,
            session=session,
        )
        await get_notifier().mark_stale(
            project_id=draft["project_id"],
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )
        result.pop("scenario_ids")

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)
        return result

    async def _generate_with_skill(
        self,
        user_requirements: str,
        actor_node_map,
        feature_node_map,
        target_pairs: list[tuple[int, int]],
        user_feedback: str | None,
    ) -> tuple[list[dict], dict[str, dict]]:
        semaphore = asyncio.Semaphore(self._max_concurrency)
        logger.info(
            "Scenario skill generation targets=%s target_concurrency=%s step_concurrency=%s",
            len(target_pairs),
            self._max_concurrency,
            self._step_max_concurrency,
        )

        requirement_text = user_requirements
        if user_feedback:
            requirement_text = (
                f"{user_requirements}\n\nUser feedback for regeneration:\n{user_feedback}"
            )

        async def generate_one(feature_id: int, actor_id: int):
            async with semaphore:
                feature_node = feature_node_map[feature_id]
                actor_node = actor_node_map[actor_id]
                feature_text = self._adapter.feature_prompt_text(feature_node, actor_node)
                raw = await self._generate_scenario_result(
                    requirement=requirement_text,
                    feature=feature_text,
                )
                items, target_gherkin = self._adapter.scenario_items_from_skill_result(
                    raw,
                    feature=feature_node,
                    actor=actor_node,
                )
                return self._target_key(feature_id, actor_id), items, target_gherkin

        nested_results = await asyncio.gather(
            *[
                generate_one(feature_id, actor_id)
                for feature_id, actor_id in target_pairs
            ]
        )

        generated_scenarios = []
        gherkin_by_target = {}
        for key, items, target_gherkin in nested_results:
            generated_scenarios.extend(items)
            gherkin_by_target[key] = target_gherkin
        return generated_scenarios, gherkin_by_target

    async def _generate_scenario_result(
        self,
        requirement: str,
        feature: str,
    ) -> dict:
        story = await self._do_scenario_step(
            "Features2Story.txt",
            {
                "{Features Replacement Flag}": feature,
                "{Requirement Replacement Flag}": requirement,
            },
        )

        async def story_to_system(story_key: str, story_val) -> dict:
            return await self._do_scenario_step(
                "Story2Sys.txt",
                {
                    "{Story Key Replacement Flag}": story_key,
                    "{User Story Replacement Flag}": str(story_val),
                },
            )

        system = await self._gather_step_dicts(
            list(story.items()),
            story_to_system,
        )

        async def system_to_gherkin(sys_key: str, sys_val) -> dict:
            return await self._do_scenario_step(
                "sys2Gherkin.txt",
                {
                    "{Story Key Replacement Flag}": sys_key,
                    "{System Requirement Replacement Flag}": str(sys_val),
                },
            )

        gherkin = await self._gather_step_dicts(
            list(system.items()),
            system_to_gherkin,
        )

        return {"story": story, "system": system, "gherkin": gherkin}

    async def _gather_step_dicts(
        self,
        items: list[tuple[str, object]],
        worker,
    ) -> dict:
        if not items:
            return {}

        semaphore = asyncio.Semaphore(self._step_max_concurrency)

        async def run_one(item: tuple[str, object]) -> dict:
            async with semaphore:
                return await worker(item[0], item[1])

        results = await asyncio.gather(
            *[
                run_one(item)
                for item in items
            ]
        )
        merged: dict = {}
        for result in results:
            merged.update(result)
        return merged

    async def _do_scenario_step(
        self,
        prompt_name: str,
        replacements: dict[str, str],
    ) -> dict:
        prompt = render_prompt(self._skill_generator._prompts[prompt_name], replacements)
        return await self._llm_json_client.ask_json(prompt)

    async def _revise_gherkin(
        self,
        user_feedback: str,
        gherkin_content,
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

    @staticmethod
    async def _persist_scenario_generation_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import (
            GherkinSpecModel,
            ScenarioAcceptanceCriterionModel,
            ScenarioModel,
        )

        project_id = draft["project_id"]
        specs_by_target: dict[str, GherkinSpecModel] = {}

        for target_key, gherkin_content in draft.get("gherkin_by_target", {}).items():
            try:
                feature_id_text, actor_id_text = str(target_key).split(":", 1)
                feature_id = int(feature_id_text)
                actor_id = int(actor_id_text)
            except (TypeError, ValueError):
                raise ValueError("invalid_scenario_payload")

            spec = GherkinSpecModel(
                project_id=project_id,
                feature_id=feature_id,
                actor_id=actor_id,
                gherkin_json=gherkin_content,
                source="scenario_generation_skill",
            )
            session.add(spec)
            specs_by_target[str(target_key)] = spec

        await session.flush()

        scenarios = []
        acceptance_criterion_count = 0
        for item in draft["scenarios"]:
            acceptance_criteria = item.get("acceptance_criteria") or []
            if not acceptance_criteria:
                raise ValueError("empty_acceptance_criteria")

            target_key = item.get("gherkin_target_key") or (
                f"{item['feature_id']}:{item['actor_id']}"
            )
            spec = specs_by_target.get(str(target_key))

            scenario = ScenarioModel(
                project_id=project_id,
                feature_id=item["feature_id"],
                actor_id=item["actor_id"],
                name=item["scenario_name"],
                content=item["scenario_content"],
                gherkin_spec_id=spec.id if spec is not None else None,
                gherkin_scenario_index=item.get("gherkin_scenario_index"),
            )

            session.add(scenario)
            scenarios.append(scenario)

        await session.flush()

        for scenario, item in zip(scenarios, draft["scenarios"], strict=True):
            for position, criterion in enumerate(item["acceptance_criteria"], start=1):
                session.add(
                    ScenarioAcceptanceCriterionModel(
                        scenario_id=scenario.id,
                        position=position,
                        content=criterion,
                        confirmation_status="ai_assumption",
                    )
                )
                acceptance_criterion_count += 1

        await session.flush()

        return {
            "project_id": project_id,
            "scenario_count": len(draft["scenarios"]),
            "acceptance_criterion_count": acceptance_criterion_count,
            "scenario_ids": [
                scenario.id
                for scenario in scenarios
            ],
            "message": "scenarios_created",
        }

    @staticmethod
    def _build_draft_response(
        project_id: int,
        feature_id: int | None,
        actor_id: int | None,
        generation_mode: str,
        generated_scenarios: list[dict],
        gherkin_by_target: dict[str, dict],
    ) -> tuple[dict, dict]:
        draft_payload = {
            "project_id": project_id,
            "generation_mode": generation_mode,
            "feature_id": feature_id,
            "actor_id": actor_id,
            "scenarios": generated_scenarios,
            "gherkin_by_target": gherkin_by_target,
        }

        response_payload = {
            "project_id": project_id,
            "generation_mode": generation_mode,
            "feature_id": feature_id,
            "actor_id": actor_id,
            "scenarios": [
                {
                    "feature_id": item["feature_id"],
                    "feature_name": item["feature_name"],
                    "actor_id": item["actor_id"],
                    "actor_name": item["actor_name"],
                    "scenario_name": item["scenario_name"],
                    "scenario_content": item["scenario_content"],
                    "acceptance_criteria": item["acceptance_criteria"],
                }
                for item in generated_scenarios
            ],
        }
        return draft_payload, response_payload

    @staticmethod
    def _target_key(feature_id: int, actor_id: int) -> str:
        return f"{feature_id}:{actor_id}"
