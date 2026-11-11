import asyncio
import os
from uuid import uuid4

from backend.api.modules.requirements_core.scenario.application.acceptance_criteria_generation_service import (
    AcceptanceCriteriaGenerationService,
)
from backend.core.generators.scenarios_generator import (
    ScenariosGenerator,
    ScenariosGeneratorInput,
)
from backend.core.notifier import get_notifier
from backend.schemas import ActorNode, FeatureNode, ScenarioNode

from .scenario_generation_context import load_scenario_generation_context


class ScenarioGenerationService:
    def __init__(self):
        self._scenarios_generator = ScenariosGenerator()
        self._acceptance_criteria_generation_service = (
            AcceptanceCriteriaGenerationService()
        )
        self._max_concurrency = self._read_int_env(
            "SCENARIO_GENERATION_MAX_CONCURRENCY",
            5,
        )
        self._batch_max_concurrency = self._read_int_env(
            "SCENARIO_BATCH_GENERATION_MAX_CONCURRENCY",
            10,
        )
        self._generation_semaphores = {
            self._max_concurrency: asyncio.Semaphore(self._max_concurrency),
            self._batch_max_concurrency: asyncio.Semaphore(self._batch_max_concurrency),
        }

    @staticmethod
    def _read_int_env(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return max(1, value)

    async def create_full_draft(
        self,
        project_id: int,
        owner_user_id: int,
        session,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        *,
        workspace_id: int,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            feature_id=None,
            actor_id=None,
            generation_mode="full",
            user_feedback=None,
            session=session,
            workspace_id=workspace_id,
        )

        draft_payload["draft_id"] = draft_id
        draft_payload["branch_name"] = branch_name
        draft_payload["head_commit_id"] = head_commit_id
        response_payload["draft_id"] = draft_id
        response_payload["branch_name"] = branch_name
        response_payload["head_commit_id"] = head_commit_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="scenario",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def create_single_draft(
        self,
        project_id: int,
        feature_id: int,
        owner_user_id: int,
        session,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        *,
        workspace_id: int,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            feature_id=feature_id,
            actor_id=None,
            generation_mode="single",
            user_feedback=None,
            session=session,
            workspace_id=workspace_id,
        )

        draft_payload["draft_id"] = draft_id
        draft_payload["branch_name"] = branch_name
        draft_payload["head_commit_id"] = head_commit_id
        response_payload["draft_id"] = draft_id
        response_payload["branch_name"] = branch_name
        response_payload["head_commit_id"] = head_commit_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="scenario",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def create_pair_draft(
        self,
        project_id: int,
        feature_id: int,
        actor_id: int,
        owner_user_id: int,
        session,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        *,
        workspace_id: int,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            feature_id=feature_id,
            actor_id=actor_id,
            generation_mode="pair",
            user_feedback=None,
            session=session,
            workspace_id=workspace_id,
        )

        draft_payload["draft_id"] = draft_id
        draft_payload["branch_name"] = branch_name
        draft_payload["head_commit_id"] = head_commit_id
        response_payload["draft_id"] = draft_id
        response_payload["branch_name"] = branch_name
        response_payload["head_commit_id"] = head_commit_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="scenario",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def regenerate_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        user_feedback: str | None,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        draft_payload, response_payload = await self._generate_preview(
            project_id=draft["project_id"],
            feature_id=draft.get("feature_id"),
            actor_id=draft.get("actor_id"),
            generation_mode=draft["generation_mode"],
            user_feedback=user_feedback,
            session=session,
                                                    workspace_id=draft["workspace_id"],
        )

        draft_payload["draft_id"] = draft_id
        draft_payload["branch_name"] = draft.get("branch_name")
        draft_payload["head_commit_id"] = draft.get("head_commit_id")
        response_payload["draft_id"] = draft_id
        response_payload["branch_name"] = draft.get("branch_name")
        response_payload["head_commit_id"] = draft.get("head_commit_id")

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

    async def confirm_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
        generate_acceptance_criteria: bool = False,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        *,
        workspace_id: int,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        draft_branch = draft.get("branch_name")
        if draft_branch and branch_name and draft_branch != branch_name:
            raise ValueError(f"draft_branch_mismatch: Draft created on branch '{draft_branch}' cannot be confirmed on '{branch_name}'")

        draft_commit = draft.get("head_commit_id")
        if draft_commit and head_commit_id and draft_commit != head_commit_id:
            raise ValueError("branch_drift_detected: Branch head commit has advanced since draft creation")

        result = await self._persist_scenario_generation_draft(
            draft=draft,
            session=session,
            workspace_id=workspace_id,
        )
        changed_targets = [
            ("scenario", uid)
            for uid in result.get("scenario_logical_uuids", [])
        ]
        await get_notifier().mark_stale(
            project_id=draft["project_id"],
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
            changed_targets=changed_targets,
        )
        result.pop("scenario_ids", None)
        result.pop("scenario_logical_uuids", None)

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)

        return result

    async def discard_draft(
        self,
        draft_id: str,
        owner_user_id: int,
    ) -> dict:
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.discard_draft_locally(draft_id, owner_user_id)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }

    async def _get_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, owner_user_id, session)

    async def _generate_preview(
        self,
        project_id: int,
        feature_id: int | None,
        actor_id: int | None,
        generation_mode: str,
        user_feedback: str | None,
        session,
        workspace_id: int,
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
            workspace_id=workspace_id,
        )

        generated_scenarios = await self._generate_scenarios_concurrently(
            user_requirements=user_requirements,
            actor_node_map=actor_node_map,
            feature_node_map=feature_node_map,
            target_pairs=target_pairs,
            user_feedback=user_feedback,
        )

        if not generated_scenarios:
            raise ValueError("empty_scenarios")

        generated_scenarios = await self._attach_acceptance_criteria_to_generated_scenarios(
            user_requirements=user_requirements,
            actor_node_map=actor_node_map,
            feature_node_map=feature_node_map,
            generated_scenarios=generated_scenarios,
            user_feedback=user_feedback,
        )

        draft_payload = {
            "project_id": project_id,
            "feature_id": feature_id,
            "actor_id": actor_id,
            "generation_mode": generation_mode,
            "scenarios": generated_scenarios,
        }

        response_payload = {
            "project_id": project_id,
            "feature_id": feature_id,
            "actor_id": actor_id,
            "generation_mode": generation_mode,
            "scenarios": generated_scenarios,
        }

        return draft_payload, response_payload

    @staticmethod
    async def _load_generation_context(
        project_id: int,
        feature_id: int | None,
        actor_id: int | None,
        generation_mode: str,
        session,
        workspace_id: int,
        feature_ids: list[int] | None = None,
    ):
        return await load_scenario_generation_context(
            project_id,
            feature_id,
            actor_id,
            generation_mode,
            session,
            workspace_id=workspace_id,
            feature_ids=feature_ids,
        )

    async def _generate_scenarios_concurrently(
        self,
        user_requirements: str,
        actor_node_map: dict[int, ActorNode],
        feature_node_map: dict[int, FeatureNode],
        target_pairs: list[tuple[int, int]],
        user_feedback: str | None = None,
        max_concurrency: int | None = None,
    ) -> list[dict]:
        concurrency = max_concurrency or self._max_concurrency
        semaphore = self._generation_semaphores.setdefault(
            concurrency,
            asyncio.Semaphore(concurrency),
        )

        async def generate_one(
            feature_id: int,
            actor_id: int,
        ) -> list[dict]:
            async with semaphore:
                actor_node = actor_node_map[actor_id]
                feature_node = feature_node_map[feature_id]

                raw = await self._scenarios_generator.generate(
                    ScenariosGeneratorInput(
                        user_requirements=user_requirements,
                        actor=actor_node,
                        feature=feature_node,
                        user_feedback=user_feedback,
                    )
                )

                scenarios = raw.get("scenarios", [])

                if not scenarios:
                    raise ValueError("empty_scenarios")

                result_ = []

                for scenario in scenarios:
                    scenario_name = scenario.get("scenario_name", "")
                    scenario_content = scenario.get("scenario_content", "")

                    if not scenario_name or not scenario_content:
                        raise ValueError("invalid_scenario_payload")

                    result_.append(
                        {
                            "feature_id": feature_id,
                            "feature_name": feature_node.featureName,
                            "actor_id": actor_id,
                            "actor_name": actor_node.actorName,
                            "scenario_name": scenario_name,
                            "scenario_content": scenario_content,
                        }
                    )

                return result_

        nested_results = await asyncio.gather(
            *[
                generate_one(
                    feature_id=feature_id,
                    actor_id=actor_id,
                )
                for feature_id, actor_id in target_pairs
            ]
        )

        generated_scenarios = []

        for result in nested_results:
            generated_scenarios.extend(result)

        return generated_scenarios

    async def _attach_acceptance_criteria_to_generated_scenarios(
        self,
        user_requirements: str,
        actor_node_map: dict[int, ActorNode],
        feature_node_map: dict[int, FeatureNode],
        generated_scenarios: list[dict],
        user_feedback: str | None = None,
        max_concurrency: int | None = None,
    ) -> list[dict]:
        concurrency = max_concurrency or self._max_concurrency
        semaphore = self._generation_semaphores.setdefault(
            concurrency,
            asyncio.Semaphore(concurrency),
        )
        scenario_nodes = [
            ScenarioNode(
                scenarioId=index,
                scenarioName=item["scenario_name"],
                scenarioContent=item["scenario_content"],
                featureId=item["feature_id"],
                actorId=item["actor_id"],
                acceptanceCriteria=[],
            )
            for index, item in enumerate(generated_scenarios, start=1)
        ]

        generated_acceptance_criteria = await (
            self._acceptance_criteria_generation_service
        )._generate_acceptance_criteria_concurrently(
            user_requirements=user_requirements,
            actor_node_map=actor_node_map,
            feature_node_map=feature_node_map,
            scenario_nodes=scenario_nodes,
            user_feedback=user_feedback,
            max_concurrency=max_concurrency,
            semaphore=semaphore,
        )

        criteria_by_scenario_id = {
            item["scenario_id"]: item["acceptance_criteria"]
            for item in generated_acceptance_criteria
        }

        scenarios_with_criteria = []
        for index, item in enumerate(generated_scenarios, start=1):
            acceptance_criteria = criteria_by_scenario_id.get(index, [])
            if not acceptance_criteria:
                raise ValueError("empty_acceptance_criteria")
            scenarios_with_criteria.append({
                **item,
                "acceptance_criteria": acceptance_criteria,
            })

        return scenarios_with_criteria

    @staticmethod
    async def _persist_scenario_generation_draft(
        draft: dict,
        session,
        workspace_id: int,
    ) -> dict:
        from backend.database.model import ScenarioAcceptanceCriterionModel, ScenarioModel

        project_id = draft["project_id"]
        scenarios = []
        acceptance_criterion_count = 0

        for item in draft["scenarios"]:
            acceptance_criteria = item.get("acceptance_criteria") or []
            if not acceptance_criteria:
                raise ValueError("empty_acceptance_criteria")

            scenario = ScenarioModel(
                project_id=project_id,
                workspace_id=workspace_id,
                feature_id=item["feature_id"],
                actor_id=item["actor_id"],
                name=item["scenario_name"],
                content=item["scenario_content"],
                confirmation_status='ai_assumption',
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
                        confirmation_status='ai_assumption',
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
            "scenario_logical_uuids": [
                scenario.logical_uuid
                for scenario in scenarios
            ],
            "message": "scenarios_created",
        }
