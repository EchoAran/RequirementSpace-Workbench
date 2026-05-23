import re
from uuid import uuid4

from sqlalchemy import insert, select

from backend.core.generators.features_generator import (
    FeaturesGenerator,
    FeaturesGeneratorInput,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.schemas import ActorNode


class FeatureGenerationService:
    _feature_number_pattern = re.compile(
        r"^F\d{3}(?:-\d{3})*$"
    )

    def __init__(self):
        self._drafts: dict[str, dict] = {}
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
    ) -> dict:
        draft = self._get_draft(draft_id)

        result = await self._persist_feature_generation_draft(
            draft=draft,
            session=session,
        )
        await mark_perception_jobs_stale(
            project_id=draft["project_id"],
            stages={"what", "how", "scope"},
            session=session,
        )

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

    async def _persist_feature_generation_draft(
        self,
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import (
            FeatureModel,
            FeatureRelationModel,
            ProjectModel,
            feature_actor_table,
        )

        project_id = draft["project_id"]

        project_result = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
            )
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        existing_feature_result = await session.execute(
            select(FeatureModel.id).where(
                FeatureModel.project_id == project_id,
            )
        )

        if existing_feature_result.first() is not None:
            raise ValueError("features_already_exist")

        feature_number_to_model = {}

        for feature in draft["features"]:
            model = FeatureModel(
                project_id=project_id,
                name=feature["feature_name"],
                description=feature["feature_description"],
            )

            session.add(model)
            feature_number_to_model[feature["feature_number"]] = model

        await session.flush()

        feature_actor_rows = []

        for feature in draft["features"]:
            feature_model = feature_number_to_model[
                feature["feature_number"]
            ]

            for actor_id in feature.get("actor_ids", []):
                feature_actor_rows.append(
                    {
                        "feature_id": feature_model.id,
                        "actor_id": actor_id,
                    }
                )

        if feature_actor_rows:
            await session.execute(
                insert(feature_actor_table),
                feature_actor_rows,
            )

        root_feature = self._find_root_feature(draft["features"])

        if not project.name.strip():
            project.name = root_feature["feature_name"]

        if not project.description.strip():
            project.description = root_feature["feature_description"]

        for feature in draft["features"]:
            feature_number = feature["feature_number"]

            parent_number = self._get_parent_feature_number(
                feature_number
            )

            if parent_number is None:
                continue

            parent_model = feature_number_to_model[parent_number]
            child_model = feature_number_to_model[feature_number]

            relation = FeatureRelationModel(
                parent_feature_id=parent_model.id,
                child_feature_id=child_model.id,
                position=self._get_feature_position(feature_number),
            )

            session.add(relation)

        await session.flush()

        return {
            "project_id": project_id,
            "feature_count": len(draft["features"]),
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
