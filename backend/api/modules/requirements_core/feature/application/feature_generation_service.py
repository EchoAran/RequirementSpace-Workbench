import re
from uuid import uuid4

from sqlalchemy import insert, select

from backend.core.generators.features_generator import (
    FeaturesGenerator,
    FeaturesGeneratorInput,
)
from backend.core.notifier import get_notifier
from backend.schemas import ActorNode


class FeatureGenerationService:
    _feature_number_pattern = re.compile(
        r"^F\d{3}(?:-\d{3})*$"
    )

    def __init__(self):
        self._features_generator = FeaturesGenerator()

    @staticmethod
    def _get_parent_feature_number(
        feature_number: str,
    ) -> str | None:
        if "-" not in feature_number:
            return None

        return feature_number.rsplit("-", 1)[0]

    @staticmethod
    def _get_feature_position(
        feature_number: str,
    ) -> int:
        return int(feature_number.rsplit("-", 1)[-1].replace("F", ""))

    def _validate_feature_tree_by_number(
        self,
        features: list[dict],
    ) -> None:
        if len(features) == 0:
            raise ValueError("empty_features")

        feature_numbers = [
            feature["feature_number"]
            for feature in features
        ]

        feature_number_set = set(feature_numbers)

        if len(feature_number_set) != len(feature_numbers):
            raise ValueError("duplicate_feature_number")

        root_numbers = []

        for feature_number in feature_numbers:
            if self._feature_number_pattern.match(feature_number) is None:
                raise ValueError("invalid_feature_number_format")

            parent_number = self._get_parent_feature_number(
                feature_number
            )

            if parent_number is None:
                root_numbers.append(feature_number)
                continue

            if parent_number not in feature_number_set:
                raise ValueError("missing_parent_feature")

        if len(root_numbers) != 1:
            raise ValueError("invalid_root_feature_count")

    async def create_draft(
        self,
        project_id: int,
        owner_user_id: int,
        session,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            user_feedback=None,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="feature",
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
            user_feedback=user_feedback,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=draft["project_id"],
            draft_id=draft_id,
            draft_type="feature",
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

        result = await self._persist_feature_generation_draft(
            draft=draft,
            session=session,
        )
        await get_notifier().mark_stale(
            project_id=draft["project_id"],
            stages={"what", "how", "scope"},
            perception_kinds={
                "FEATURE",
                "SCENARIO",
                "ACCEPTANCE_CRITERION",
                "FLOW",
            },
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
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        user_requirements, actor_nodes = await self._load_project_context(
            project_id=project_id,
            session=session,
        )

        raw = await self._features_generator.generate(
            FeaturesGeneratorInput(
                user_requirements=user_requirements,
                actors=actor_nodes,
                user_feedback=user_feedback,
            )
        )

        raw_features = raw.get("features", [])
        self._validate_feature_tree_by_number(raw_features)

        actor_id_set = {
            actor.actorId
            for actor in actor_nodes
        }
        actor_name_map = {
            actor.actorId: actor.actorName
            for actor in actor_nodes
        }

        features = []

        for raw_feature in raw_features:
            actor_ids = self._normalize_actor_ids(
                raw_feature.get("actor_ids", [])
            )

            for actor_id in actor_ids:
                if actor_id not in actor_id_set:
                    raise ValueError("invalid_actor_reference")

            features.append(
                {
                    "feature_number": raw_feature["feature_number"],
                    "feature_name": raw_feature["feature_name"],
                    "feature_description": raw_feature[
                        "feature_description"
                    ],
                    "actor_ids": actor_ids,
                }
            )

        draft_payload = {
            "project_id": project_id,
            "features": features,
        }

        response_payload = {
            "project_id": project_id,
            "features": [
                {
                    "feature_name": feature["feature_name"],
                    "feature_description": feature[
                        "feature_description"
                    ],
                    "actor_names": [
                        actor_name_map[actor_id]
                        for actor_id in feature.get("actor_ids", [])
                    ],
                }
                for feature in features
            ],
        }

        return draft_payload, response_payload

    @staticmethod
    async def _load_project_context(
        project_id: int,
        session,
    ) -> tuple[str, list[ActorNode]]:
        from backend.database.model import ActorModel, ProjectModel

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

        actor_nodes = [
            ActorNode(
                actorId=actor.id,
                actorName=actor.name,
                actorDescription=actor.description,
            )
            for actor in actor_models
        ]

        return project.user_requirements, actor_nodes

    @staticmethod
    def _normalize_actor_ids(raw_actor_ids) -> list[int]:
        if raw_actor_ids is None:
            return []

        actor_ids = []

        for raw_actor_id in raw_actor_ids:
            try:
                actor_ids.append(int(raw_actor_id))
            except (TypeError, ValueError) as error:
                raise ValueError("invalid_actor_reference") from error

        return actor_ids

    @staticmethod
    async def _load_project_for_feature_persistence(
        session,
        project_id: int,
    ):
        from backend.database.model import FeatureModel, ProjectModel

        result = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError("project_not_found")
        existing_result = await session.execute(
            select(FeatureModel.id).where(
                FeatureModel.project_id == project_id
            )
        )
        if existing_result.first() is not None:
            raise ValueError("features_already_exist")
        return project

    @staticmethod
    async def _create_feature_models(
        session,
        project_id: int,
        features: list[dict],
    ) -> dict:
        from backend.database.model import FeatureModel

        models_by_number = {}
        for feature in features:
            model = FeatureModel(
                project_id=project_id,
                name=feature["feature_name"],
                description=feature["feature_description"],
                confirmation_status="ai_assumption",
            )
            session.add(model)
            models_by_number[feature["feature_number"]] = model
        await session.flush()
        return models_by_number

    @staticmethod
    async def _write_feature_actor_links(
        session,
        features: list[dict],
        models_by_number: dict,
    ) -> None:
        from backend.database.model import feature_actor_table

        rows = [
            {
                "feature_id": models_by_number[
                    feature["feature_number"]
                ].id,
                "actor_id": actor_id,
            }
            for feature in features
            for actor_id in feature.get("actor_ids", [])
        ]
        if rows:
            await session.execute(insert(feature_actor_table), rows)

    def _update_project_from_root(
        self,
        project,
        features: list[dict],
    ) -> None:
        root = self._find_root_feature(features)
        if not project.name.strip():
            project.name = root["feature_name"]
        if not project.description.strip():
            project.description = root["feature_description"]

    def _add_feature_relations(
        self,
        session,
        features: list[dict],
        models_by_number: dict,
    ) -> None:
        from backend.database.model import FeatureRelationModel

        for feature in features:
            feature_number = feature["feature_number"]
            parent_number = self._get_parent_feature_number(feature_number)
            if parent_number is None:
                continue
            session.add(
                FeatureRelationModel(
                    parent_feature_id=models_by_number[parent_number].id,
                    child_feature_id=models_by_number[feature_number].id,
                    position=self._get_feature_position(feature_number),
                )
            )

    async def _persist_feature_generation_draft(
        self,
        draft: dict,
        session,
    ) -> dict:
        project_id = draft["project_id"]
        features = draft["features"]
        project = await self._load_project_for_feature_persistence(
            session,
            project_id,
        )
        models_by_number = await self._create_feature_models(
            session,
            project_id,
            features,
        )
        await self._write_feature_actor_links(
            session,
            features,
            models_by_number,
        )
        self._update_project_from_root(project, features)
        self._add_feature_relations(
            session,
            features,
            models_by_number,
        )
        await session.flush()
        return {
            "project_id": project_id,
            "feature_count": len(features),
            "message": "features_created",
        }

    def _find_root_feature(
        self,
        features: list[dict],
    ) -> dict:
        self._validate_feature_tree_by_number(features)

        for feature in features:
            parent_number = self._get_parent_feature_number(
                feature["feature_number"]
            )

            if parent_number is None:
                return feature

        raise ValueError("invalid_root_feature_count")
