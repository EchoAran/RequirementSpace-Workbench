import asyncio
import os
from uuid import uuid4

from sqlalchemy import select

from backend.api.services.acceptance_criteria_generation_service import (
    AcceptanceCriteriaGenerationService,
)

from backend.core.generators.scenarios_generator import (
    ScenariosGenerator,
    ScenariosGeneratorInput,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.schemas import ActorNode, FeatureNode


class ScenarioGenerationService:
    def __init__(self):
        self._drafts: dict[str, dict] = {}
        self._scenarios_generator = ScenariosGenerator()
        self._acceptance_criteria_generation_service = (
            AcceptanceCriteriaGenerationService()
        )
        self._max_concurrency = self._read_int_env(
            "SCENARIO_GENERATION_MAX_CONCURRENCY",
            5,
        )

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
        session,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            feature_id=None,
            actor_id=None,
            generation_mode="full",
            user_feedback=None,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        self._drafts[draft_id] = draft_payload

        return response_payload

    async def create_single_draft(
        self,
        project_id: int,
        feature_id: int,
        session,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            feature_id=feature_id,
            actor_id=None,
            generation_mode="single",
            user_feedback=None,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        self._drafts[draft_id] = draft_payload

        return response_payload

    async def create_pair_draft(
        self,
        project_id: int,
        feature_id: int,
        actor_id: int,
        session,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            feature_id=feature_id,
            actor_id=actor_id,
            generation_mode="pair",
            user_feedback=None,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        self._drafts[draft_id] = draft_payload

        return response_payload

    async def regenerate_draft(
        self,
        draft_id: str,
        user_feedback: str | None,
        session,
    ) -> dict:
        draft = self._get_draft(draft_id)

        draft_payload, response_payload = await self._generate_preview(
            project_id=draft["project_id"],
            feature_id=draft.get("feature_id"),
            actor_id=draft.get("actor_id"),
            generation_mode=draft["generation_mode"],
            user_feedback=user_feedback,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        self._drafts[draft_id] = draft_payload

        return response_payload

    async def confirm_draft(
        self,
        draft_id: str,
        session,
        generate_acceptance_criteria: bool = False,
    ) -> dict:
        draft = self._get_draft(draft_id)

        result = await self._persist_scenario_generation_draft(
            draft=draft,
            session=session,
        )
        await mark_perception_jobs_stale(
            project_id=draft["project_id"],
            stages={"what"},
            session=session,
        )
        scenario_ids = result.pop("scenario_ids")

        if generate_acceptance_criteria:
            acceptance_criteria_result = await (
                self._acceptance_criteria_generation_service
            ).create_and_persist_for_scenarios(
                project_id=draft["project_id"],
                scenario_ids=scenario_ids,
                session=session,
            )
            result["acceptance_criterion_count"] = (
                acceptance_criteria_result["acceptance_criterion_count"]
            )
        else:
            result["acceptance_criterion_count"] = 0

        self._drafts.pop(draft_id, None)

        return result

    async def discard_draft(
        self,
        draft_id: str,
    ) -> dict:
        self._drafts.pop(draft_id, None)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }

    def _get_draft(
        self,
        draft_id: str,
    ) -> dict:
        draft = self._drafts.get(draft_id)

        if draft is None:
            raise ValueError("draft_not_found")

        return draft

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

        generated_scenarios = await self._generate_scenarios_concurrently(
            user_requirements=user_requirements,
            actor_node_map=actor_node_map,
            feature_node_map=feature_node_map,
            target_pairs=target_pairs,
            user_feedback=user_feedback,
        )

        if not generated_scenarios:
            raise ValueError("empty_scenarios")

        draft_payload = {
            "project_id": project_id,
            "generation_mode": generation_mode,
            "feature_id": feature_id,
            "actor_id": actor_id,
            "scenarios": generated_scenarios,
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
                }
                for item in generated_scenarios
            ],
        }

        return draft_payload, response_payload

    @staticmethod
    async def _load_generation_context(
            project_id: int,
        feature_id: int | None,
        actor_id: int | None,
        generation_mode: str,
        session,
    ):
        from backend.database.model import (
            ActorModel,
            FeatureModel,
            FeatureRelationModel,
            ProjectModel,
            feature_actor_table,
        )

        project_result = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
            )
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        actor_result = await session.execute(
            select(ActorModel).where(
                ActorModel.project_id == project_id,
            )
        )
        actor_models = actor_result.scalars().all()

        if not actor_models:
            raise ValueError("empty_actors")

        feature_result = await session.execute(
            select(FeatureModel).where(
                FeatureModel.project_id == project_id,
            )
        )
        feature_models = feature_result.scalars().all()

        if not feature_models:
            raise ValueError("empty_features")

        feature_id_set = {
            feature.id
            for feature in feature_models
        }

        relation_result = await session.execute(
            select(FeatureRelationModel).where(
                FeatureRelationModel.parent_feature_id.in_(
                    feature_id_set
                )
            )
        )
        relation_models = relation_result.scalars().all()

        feature_actor_result = await session.execute(
            select(
                feature_actor_table.c.feature_id,
                feature_actor_table.c.actor_id,
            ).where(
                feature_actor_table.c.feature_id.in_(
                    feature_id_set
                )
            )
        )
        feature_actor_rows = feature_actor_result.all()

        children_map: dict[int, list[int]] = {}
        parent_map: dict[int, int] = {}

        for relation in relation_models:
            children_map.setdefault(
                relation.parent_feature_id,
                [],
            ).append(relation.child_feature_id)

            parent_map[
                relation.child_feature_id
            ] = relation.parent_feature_id

        actor_ids_map: dict[int, list[int]] = {}

        for current_feature_id, current_actor_id in feature_actor_rows:
            actor_ids_map.setdefault(
                current_feature_id,
                [],
            ).append(current_actor_id)

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
                actorIds=actor_ids_map.get(feature.id, []),
                parentId=parent_map.get(feature.id),
                childrenIds=children_map.get(feature.id, []),
            )
            for feature in feature_models
        }

        leaf_feature_nodes = [
            feature
            for feature in feature_node_map.values()
            if len(feature.childrenIds) == 0
        ]

        if not leaf_feature_nodes:
            raise ValueError("empty_leaf_features")

        if generation_mode in {
            "single",
            "pair",
        }:
            if feature_id is None:
                raise ValueError("feature_id_required")

            target_feature = feature_node_map.get(feature_id)

            if target_feature is None:
                raise ValueError("feature_not_found")

            if len(target_feature.childrenIds) != 0:
                raise ValueError("feature_is_not_leaf")

            target_features = [target_feature]

        else:
            target_features = leaf_feature_nodes

        target_pairs: list[tuple[int, int]] = []

        for feature in target_features:
            if not feature.actorIds:
                raise ValueError("leaf_feature_without_actor")

            for current_actor_id in feature.actorIds:
                if current_actor_id not in actor_node_map:
                    raise ValueError("invalid_feature_actor_reference")

                target_pairs.append(
                    (
                        feature.featureId,
                        current_actor_id,
                    )
                )

        if generation_mode == "pair":
            if actor_id is None:
                raise ValueError("actor_id_required")

            if actor_id not in actor_node_map:
                raise ValueError("actor_not_found")

            if (
                feature_id,
                actor_id,
            ) not in target_pairs:
                raise ValueError("invalid_feature_actor_reference")

            target_pairs = [
                (
                    feature_id,
                    actor_id,
                )
            ]

        if not target_pairs:
            raise ValueError("empty_generation_targets")

        return (
            project.user_requirements,
            actor_node_map,
            feature_node_map,
            target_pairs,
        )

    async def _generate_scenarios_concurrently(
        self,
        user_requirements: str,
        actor_node_map: dict[int, ActorNode],
        feature_node_map: dict[int, FeatureNode],
        target_pairs: list[tuple[int, int]],
        user_feedback: str | None = None,
    ) -> list[dict]:
        semaphore = asyncio.Semaphore(self._max_concurrency)

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

    @staticmethod
    async def _persist_scenario_generation_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import ScenarioModel

        project_id = draft["project_id"]
        scenarios = []

        for item in draft["scenarios"]:
            scenario = ScenarioModel(
                project_id=project_id,
                feature_id=item["feature_id"],
                actor_id=item["actor_id"],
                name=item["scenario_name"],
                content=item["scenario_content"],
            )

            session.add(scenario)
            scenarios.append(scenario)

        await session.flush()

        return {
            "project_id": project_id,
            "scenario_count": len(draft["scenarios"]),
            "scenario_ids": [
                scenario.id
                for scenario in scenarios
            ],
            "message": "scenarios_created",
        }
