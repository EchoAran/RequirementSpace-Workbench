import asyncio
from uuid import uuid4

from sqlalchemy import select

from backend.core.generators.acceptance_criteria_generator import (
    AcceptanceCriteriaGenerator,
    AcceptanceCriteriaGeneratorInput,
)
from backend.core.notifier import get_notifier
from backend.schemas import (
    ActorNode,
    FeatureNode,
    ScenarioNode,
)

from .acceptance_criteria_generation_context import (
    load_acceptance_criteria_generation_context,
)


class AcceptanceCriteriaGenerationService:
    def __init__(self):
        self._acceptance_criteria_generator = AcceptanceCriteriaGenerator()
        self._max_concurrency = 5
        self._generation_semaphores = {
            self._max_concurrency: asyncio.Semaphore(self._max_concurrency),
        }

    async def create_full_draft(
        self,
        project_id: int,
        owner_user_id: int,
        session,
        workspace_id: int,
    ) -> dict:
        return await self._create_draft_for_scenarios(
            project_id=project_id,
            scenario_ids=None,
            generation_mode="full",
            owner_user_id=owner_user_id,
            session=session,
            workspace_id=workspace_id,
        )

    async def create_single_draft(
        self,
        project_id: int,
        scenario_id: int,
        owner_user_id: int,
        session,
        workspace_id: int,
    ) -> dict:
        return await self._create_draft_for_scenarios(
            project_id=project_id,
            scenario_ids=[scenario_id],
            generation_mode="single",
            owner_user_id=owner_user_id,
            session=session,
            workspace_id=workspace_id,
        )

    async def create_batch_draft(
        self,
        project_id: int,
        scenario_ids: list[int],
        owner_user_id: int,
        session,
        workspace_id: int,
    ) -> dict:
        if not scenario_ids:
            raise ValueError("empty_scenarios")

        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("duplicate_scenario_id")

        return await self._create_draft_for_scenarios(
            project_id=project_id,
            scenario_ids=scenario_ids,
            generation_mode="batch",
            owner_user_id=owner_user_id,
            session=session,
            workspace_id=workspace_id,
        )

    async def _create_draft_for_scenarios(
        self,
        project_id: int,
        scenario_ids: list[int] | None,
        generation_mode: str,
        owner_user_id: int,
        session,
        workspace_id: int,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            scenario_ids=scenario_ids,
            generation_mode=generation_mode,
            user_feedback=None,
            session=session,
            workspace_id=workspace_id,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="acceptance_criteria",
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
            scenario_ids=draft["scenario_ids"],
            generation_mode=draft.get("generation_mode", "batch"),
            user_feedback=user_feedback,
            session=session,
                                                    workspace_id=draft["workspace_id"],
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=draft["project_id"],
            draft_id=draft_id,
            draft_type="acceptance_criteria",
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
        workspace_id: int,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        result = await self._persist_acceptance_criteria_generation_draft(
            draft=draft,
            session=session,
            workspace_id=workspace_id,
        )
        changed_targets = [
            ("acceptance_criterion", uid)
            for uid in result.get("ac_logical_uuids", [])
        ]
        await get_notifier().mark_stale(
            project_id=draft["project_id"],
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
            changed_targets=changed_targets,
        )
        result.pop("ac_logical_uuids", None)

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

    async def create_and_persist_for_scenarios(
        self,
        project_id: int,
        scenario_ids: list[int],
        session,
        workspace_id: int,
    ) -> dict:
        draft_payload, _ = await self._generate_preview(
            project_id=project_id,
            scenario_ids=scenario_ids,
            generation_mode="batch",
            user_feedback=None,
            session=session,
            workspace_id=workspace_id,
        )

        result = await self._persist_acceptance_criteria_generation_draft(
            draft=draft_payload,
            session=session,
            workspace_id=workspace_id,
        )
        changed_targets = [
            ("acceptance_criterion", uid)
            for uid in result.get("ac_logical_uuids", [])
        ]
        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
            changed_targets=changed_targets,
        )
        result.pop("ac_logical_uuids", None)

        return result

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
        scenario_ids: list[int] | None,
        generation_mode: str,
        user_feedback: str | None,
        session,
        workspace_id: int,
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
            workspace_id=workspace_id,
        )

        generated_acceptance_criteria = (
            await self._generate_acceptance_criteria_concurrently(
                user_requirements=user_requirements,
                actor_node_map=actor_node_map,
                feature_node_map=feature_node_map,
                scenario_nodes=scenario_nodes,
                user_feedback=user_feedback,
            )
        )

        if not generated_acceptance_criteria:
            raise ValueError("empty_acceptance_criteria")

        scenario_name_map = {
            scenario.scenarioId: scenario.scenarioName
            for scenario in scenario_nodes
        }

        draft_payload = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "generation_mode": generation_mode,
            "scenario_ids": [
                scenario.scenarioId
                for scenario in scenario_nodes
            ],
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

    @staticmethod
    async def _load_generation_context(
        project_id: int,
        scenario_ids: list[int] | None,
        session,
        workspace_id: int,
    ) -> tuple[
        str,
        dict[int, ActorNode],
        dict[int, FeatureNode],
        list[ScenarioNode],
    ]:
        return await load_acceptance_criteria_generation_context(
            project_id,
            scenario_ids,
            session,
            workspace_id=workspace_id,
        )

    @staticmethod
    def _group_scenarios_by_pair(
        scenario_nodes: list[ScenarioNode],
    ) -> dict[tuple[int, int], list[ScenarioNode]]:
        scenarios_by_pair = {}
        for scenario in scenario_nodes:
            scenarios_by_pair.setdefault(
                (scenario.featureId, scenario.actorId),
                [],
            ).append(scenario)
        return scenarios_by_pair

    async def _generate_acceptance_criteria_for_pair(
        self,
        *,
        user_requirements: str,
        actor: ActorNode,
        feature: FeatureNode,
        scenarios: list[ScenarioNode],
        user_feedback: str | None,
        semaphore: asyncio.Semaphore,
    ) -> list[dict]:
        async with semaphore:
            raw = await self._acceptance_criteria_generator.generate(
                AcceptanceCriteriaGeneratorInput(
                    user_requirements=user_requirements,
                    actor=actor,
                    feature=feature,
                    scenarios=scenarios,
                    user_feedback=user_feedback,
                )
            )
        if not isinstance(raw, dict):
            raise ValueError("invalid_acceptance_criteria_payload")
        items = raw.get("scenario_acceptance_criteria", [])
        if not isinstance(items, list):
            raise ValueError("invalid_acceptance_criteria_payload")
        return items

    async def _generate_acceptance_criteria_concurrently(
        self,
        user_requirements: str,
        actor_node_map: dict[int, ActorNode],
        feature_node_map: dict[int, FeatureNode],
        scenario_nodes: list[ScenarioNode],
        user_feedback: str | None = None,
        max_concurrency: int | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> list[dict]:
        concurrency = max_concurrency or self._max_concurrency
        if semaphore is None:
            semaphore = self._generation_semaphores.setdefault(
                concurrency,
                asyncio.Semaphore(concurrency),
            )

        scenarios_by_pair = self._group_scenarios_by_pair(scenario_nodes)
        target_scenario_id_set = {
            scenario.scenarioId
            for scenario in scenario_nodes
        }

        nested_results = await asyncio.gather(
            *[
                self._generate_acceptance_criteria_for_pair(
                    user_requirements=user_requirements,
                    actor=actor_node_map[actor_id],
                    feature=feature_node_map[feature_id],
                    scenarios=scenarios,
                    user_feedback=user_feedback,
                    semaphore=semaphore,
                )
                for (
                    feature_id,
                    actor_id,
                ), scenarios in scenarios_by_pair.items()
            ]
        )

        generated_acceptance_criteria = []

        for result in nested_results:
            generated_acceptance_criteria.extend(result)

        return self._validate_generated_acceptance_criteria(
            generated_acceptance_criteria,
            target_scenario_id_set,
        )

    @staticmethod
    def _validate_generated_acceptance_criteria(
        raw_items: list[dict],
        target_scenario_id_set: set[int],
    ) -> list[dict]:
        if not isinstance(raw_items, list):
            raise ValueError("invalid_acceptance_criteria_payload")

        if not raw_items:
            raise ValueError("empty_acceptance_criteria")

        scenario_ids = []

        for item in raw_items:
            if not isinstance(item, dict):
                raise ValueError("invalid_acceptance_criteria_payload")

            try:
                scenario_ids.append(int(item.get("scenario_id")))
            except (TypeError, ValueError):
                raise ValueError("invalid_scenario_reference")

        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("duplicate_scenario_id")

        if set(scenario_ids) != target_scenario_id_set:
            raise ValueError("invalid_scenario_reference")

        normalized_items = []

        for item in raw_items:
            scenario_id = int(item.get("scenario_id"))

            if scenario_id not in target_scenario_id_set:
                raise ValueError("invalid_scenario_reference")

            raw_criteria = item.get("acceptance_criteria", [])

            if not isinstance(raw_criteria, list) or not raw_criteria:
                raise ValueError("empty_acceptance_criteria")

            acceptance_criteria = []

            for criterion in raw_criteria:
                if not isinstance(criterion, str):
                    raise ValueError("invalid_acceptance_criteria_payload")

                criterion = criterion.strip()

                if not criterion:
                    raise ValueError("invalid_acceptance_criteria_payload")

                acceptance_criteria.append(criterion)

            normalized_items.append(
                {
                    "scenario_id": scenario_id,
                    "acceptance_criteria": acceptance_criteria,
                }
            )

        return normalized_items

    @staticmethod
    async def _persist_acceptance_criteria_generation_draft(
        draft: dict,
        session,
        workspace_id: int,
    ) -> dict:
        from backend.database.model import ScenarioAcceptanceCriterionModel

        project_id = draft["project_id"]
        scenario_ids = draft["scenario_ids"]

        stmt = select(ScenarioAcceptanceCriterionModel.id).where(
            ScenarioAcceptanceCriterionModel.scenario_id.in_(
                scenario_ids
            )
        )
        stmt = stmt.where(ScenarioAcceptanceCriterionModel.workspace_id == workspace_id)
        existing_criteria_result = await session.execute(stmt)

        if existing_criteria_result.first() is not None:
            raise ValueError("acceptance_criteria_already_exist")

        acceptance_criterion_count = 0
        created_acs = []

        for item in draft["scenario_acceptance_criteria"]:
            for position, criterion in enumerate(
                item["acceptance_criteria"],
                start=1,
            ):
                ac = ScenarioAcceptanceCriterionModel(
                    workspace_id=workspace_id,
                    scenario_id=item["scenario_id"],
                    position=position,
                    content=criterion,
                    confirmation_status='ai_assumption',
                )
                session.add(ac)
                created_acs.append(ac)
                acceptance_criterion_count += 1

        await session.flush()

        return {
            "project_id": project_id,
            "acceptance_criterion_count": acceptance_criterion_count,
            "ac_logical_uuids": [ac.logical_uuid for ac in created_acs],
            "message": "acceptance_criteria_created",
        }
