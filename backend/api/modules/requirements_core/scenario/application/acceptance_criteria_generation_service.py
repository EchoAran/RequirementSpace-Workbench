import asyncio
from uuid import uuid4

from sqlalchemy import select

from backend.core.generators.acceptance_criteria_generator import (
    AcceptanceCriteriaGenerator,
    AcceptanceCriteriaGeneratorInput,
)
from backend.api.modules.requirements_core.ports import get_notifier
from backend.schemas import (
    ActorNode,
    FeatureNode,
    ScenarioNode,
)


class AcceptanceCriteriaGenerationService:
    def __init__(self):
        self._acceptance_criteria_generator = AcceptanceCriteriaGenerator()
        self._max_concurrency = 5

    async def create_full_draft(
        self,
        project_id: int,
        owner_user_id: int,
        session,
    ) -> dict:
        return await self._create_draft_for_scenarios(
            project_id=project_id,
            scenario_ids=None,
            generation_mode="full",
            owner_user_id=owner_user_id,
            session=session,
        )

    async def create_single_draft(
        self,
        project_id: int,
        scenario_id: int,
        owner_user_id: int,
        session,
    ) -> dict:
        return await self._create_draft_for_scenarios(
            project_id=project_id,
            scenario_ids=[scenario_id],
            generation_mode="single",
            owner_user_id=owner_user_id,
            session=session,
        )

    async def create_batch_draft(
        self,
        project_id: int,
        scenario_ids: list[int],
        owner_user_id: int,
        session,
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
        )

    async def _create_draft_for_scenarios(
        self,
        project_id: int,
        scenario_ids: list[int] | None,
        generation_mode: str,
        owner_user_id: int,
        session,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            scenario_ids=scenario_ids,
            generation_mode=generation_mode,
            user_feedback=None,
            session=session,
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
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        result = await self._persist_acceptance_criteria_generation_draft(
            draft=draft,
            session=session,
        )
        await get_notifier().mark_stale(
            project_id=draft["project_id"],
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
        )

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
    ) -> dict:
        draft_payload, _ = await self._generate_preview(
            project_id=project_id,
            scenario_ids=scenario_ids,
            generation_mode="batch",
            user_feedback=None,
            session=session,
        )

        result = await self._persist_acceptance_criteria_generation_draft(
            draft=draft_payload,
            session=session,
        )
        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
        )

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
    ) -> tuple[
        str,
        dict[int, ActorNode],
        dict[int, FeatureNode],
        list[ScenarioNode],
    ]:
        from backend.database.model import (
            ActorModel,
            FeatureModel,
            ProjectModel,
            ScenarioAcceptanceCriterionModel,
            ScenarioModel,
        )

        project_result = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
            )
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        scenario_statement = select(ScenarioModel).where(
            ScenarioModel.project_id == project_id,
        )

        if scenario_ids is not None:
            scenario_id_set = set(scenario_ids)

            if not scenario_id_set:
                raise ValueError("empty_scenarios")

            if len(scenario_id_set) != len(scenario_ids):
                raise ValueError("duplicate_scenario_id")

            scenario_statement = scenario_statement.where(
                ScenarioModel.id.in_(scenario_id_set)
            )

        scenario_result = await session.execute(scenario_statement)
        scenario_models = scenario_result.scalars().all()

        if not scenario_models:
            if scenario_ids is None:
                raise ValueError("no_scenarios_found")
            raise ValueError("scenario_not_found")

        if scenario_ids is not None and len(scenario_models) != len(
            scenario_ids
        ):
            raise ValueError("scenario_not_found")

        scenario_model_ids = [
            scenario.id
            for scenario in scenario_models
        ]

        existing_criteria_result = await session.execute(
            select(ScenarioAcceptanceCriterionModel).where(
                ScenarioAcceptanceCriterionModel.scenario_id.in_(
                    scenario_model_ids
                )
            )
        )
        existing_criteria_models = existing_criteria_result.scalars().all()

        if existing_criteria_models:
            raise ValueError("acceptance_criteria_already_exist")

        actor_id_set = {
            scenario.actor_id
            for scenario in scenario_models
        }
        feature_id_set = {
            scenario.feature_id
            for scenario in scenario_models
        }

        actor_result = await session.execute(
            select(ActorModel).where(
                ActorModel.id.in_(actor_id_set),
                ActorModel.project_id == project_id,
            )
        )
        actor_models = actor_result.scalars().all()

        feature_result = await session.execute(
            select(FeatureModel).where(
                FeatureModel.id.in_(feature_id_set),
                FeatureModel.project_id == project_id,
            )
        )
        feature_models = feature_result.scalars().all()

        actor_node_map = {
            actor.id: ActorNode(
                actorId=actor.id,
                actorName=actor.name,
                actorDescription=actor.description,
            )
            for actor in actor_models
        }

        feature_node_map = {
            feature.id: FeatureNode(
                featureId=feature.id,
                featureName=feature.name,
                featureDescription=feature.description,
            )
            for feature in feature_models
        }

        if set(actor_node_map) != actor_id_set:
            raise ValueError("invalid_scenario_actor_reference")

        if set(feature_node_map) != feature_id_set:
            raise ValueError("invalid_scenario_feature_reference")

        scenario_nodes = [
            ScenarioNode(
                scenarioId=scenario.id,
                scenarioName=scenario.name,
                scenarioContent=scenario.content,
                featureId=scenario.feature_id,
                actorId=scenario.actor_id,
                acceptanceCriteria=[],
            )
            for scenario in scenario_models
        ]

        return (
            project.user_requirements,
            actor_node_map,
            feature_node_map,
            scenario_nodes,
        )

    async def _generate_acceptance_criteria_concurrently(
        self,
        user_requirements: str,
        actor_node_map: dict[int, ActorNode],
        feature_node_map: dict[int, FeatureNode],
        scenario_nodes: list[ScenarioNode],
        user_feedback: str | None = None,
    ) -> list[dict]:
        semaphore = asyncio.Semaphore(self._max_concurrency)

        scenarios_by_pair: dict[tuple[int, int], list[ScenarioNode]] = {}

        for scenario in scenario_nodes:
            scenarios_by_pair.setdefault(
                (
                    scenario.featureId,
                    scenario.actorId,
                ),
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
                raw = await self._acceptance_criteria_generator.generate(
                    AcceptanceCriteriaGeneratorInput(
                        user_requirements=user_requirements,
                        actor=actor_node_map[actor_id],
                        feature=feature_node_map[feature_id],
                        scenarios=scenarios,
                        user_feedback=user_feedback,
                    )
                )

                if not isinstance(raw, dict):
                    raise ValueError("invalid_acceptance_criteria_payload")

                scenario_acceptance_criteria = raw.get(
                    "scenario_acceptance_criteria",
                    [],
                )

                if not isinstance(scenario_acceptance_criteria, list):
                    raise ValueError("invalid_acceptance_criteria_payload")

                return scenario_acceptance_criteria

        nested_results = await asyncio.gather(
            *[
                generate_one(
                    feature_id=feature_id,
                    actor_id=actor_id,
                    scenarios=scenarios,
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
    ) -> dict:
        from backend.database.model import ScenarioAcceptanceCriterionModel

        project_id = draft["project_id"]
        scenario_ids = draft["scenario_ids"]

        existing_criteria_result = await session.execute(
            select(ScenarioAcceptanceCriterionModel.id).where(
                ScenarioAcceptanceCriterionModel.scenario_id.in_(
                    scenario_ids
                )
            )
        )

        if existing_criteria_result.first() is not None:
            raise ValueError("acceptance_criteria_already_exist")

        acceptance_criterion_count = 0

        for item in draft["scenario_acceptance_criteria"]:
            for position, criterion in enumerate(
                item["acceptance_criteria"],
                start=1,
            ):
                session.add(
                    ScenarioAcceptanceCriterionModel(
                        scenario_id=item["scenario_id"],
                        position=position,
                        content=criterion,
                        confirmation_status='ai_assumption',
                    )
                )
                acceptance_criterion_count += 1

        await session.flush()

        return {
            "project_id": project_id,
            "acceptance_criterion_count": acceptance_criterion_count,
            "message": "acceptance_criteria_created",
        }
