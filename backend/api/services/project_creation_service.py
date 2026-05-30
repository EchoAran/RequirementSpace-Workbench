import asyncio
from uuid import uuid4
import re
from sqlalchemy import delete, insert

from backend.core.generators.actors_generator import (
    ActorsGenerator,
    ActorsGeneratorInput,
)
from backend.core.generators.blank_project_generator import (
    BlankProjectGenerator,
    BlankProjectGeneratorInput,
)
from backend.core.generators.features_generator import (
    FeaturesGenerator,
    FeaturesGeneratorInput,
)
from backend.schemas import ActorNode
from backend.database.model import ConfirmationStatus


class ProjectCreationService:
    def __init__(self):
        self._actors_generator = ActorsGenerator()
        self._blank_project_generator = BlankProjectGenerator()
        self._features_generator = FeaturesGenerator()

    _feature_number_pattern = re.compile(
        r"^F\d{3}(?:-\d{3})*$"
    )

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
            user_requirements: str,
            session,
            project_name: str | None = None,
            project_description: str | None = None,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            user_requirements=user_requirements,
            project_name=project_name,
            project_description=project_description,
            user_feedback=None,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=None,
            draft_id=draft_id,
            draft_type="project_creation",
            payload=draft_payload,
            session=session,
        )

        return response_payload

    async def regenerate_draft(
            self,
            draft_id: str,
            user_feedback: str | None,
            session,
    ) -> dict:
        draft = await self._get_draft(draft_id, session)

        draft_payload, response_payload = await self._generate_preview(
            user_requirements=draft["user_requirements"],
            project_name=(
                draft["project_preview"]["project_name"]
                if draft.get("project_name_provided")
                else None
            ),
            project_description=(
                draft["project_preview"]["project_description"]
                if draft.get("project_description_provided")
                else None
            ),
            user_feedback=user_feedback,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=None,
            draft_id=draft_id,
            draft_type="project_creation",
            payload=draft_payload,
            session=session,
        )

        return response_payload

    async def confirm_draft(
        self,
        draft_id: str,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, session)

        project = await self._persist_project_creation_draft(
            draft=draft,
            session=session,
        )

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, session)

        return {
            "project_id": project.id,
            "project_name": project.name,
            "project_description": project.description,
            "message": "project_created",
        }

    async def discard_draft(
        self,
        draft_id: str,
    ) -> dict:
        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.discard_draft_locally(draft_id)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }

    async def _generate_preview(
            self,
            user_requirements: str,
            project_name: str | None = None,
            project_description: str | None = None,
            user_feedback: str | None = None,
    ) -> tuple[dict, dict]:
        normalized_project_name = self._normalize_optional_text(
            project_name
        )
        normalized_project_description = self._normalize_optional_text(
            project_description
        )

        project_preview_task = asyncio.create_task(
            self._generate_project_preview(
                user_requirements=user_requirements,
                project_name=normalized_project_name,
                project_description=normalized_project_description,
            )
        )
        actor_feature_task = asyncio.create_task(
            self._generate_actor_and_feature_previews(
                user_requirements=user_requirements,
                user_feedback=user_feedback,
            )
        )

        (
            project_preview,
            (
                actor_previews_for_draft,
                actor_previews_for_response,
                feature_previews_for_draft,
                feature_previews_for_response,
            ),
        ) = await asyncio.gather(
            project_preview_task,
            actor_feature_task,
        )

        draft_payload = {
            "user_requirements": user_requirements,
            "project_preview": project_preview,
            "project_name_provided": normalized_project_name is not None,
            "project_description_provided": (
                normalized_project_description is not None
            ),
            "actors": actor_previews_for_draft,
            "features": feature_previews_for_draft,
        }

        response_payload = {
            "user_requirements": user_requirements,
            "project_preview": project_preview,
            "actors": actor_previews_for_response,
            "features": feature_previews_for_response,
        }

        return draft_payload, response_payload

    async def _generate_project_preview(
        self,
        user_requirements: str,
        project_name: str | None,
        project_description: str | None,
    ) -> dict:
        if project_name is not None and project_description is not None:
            return {
                "project_name": project_name,
                "project_description": project_description,
            }

        raw = await self._blank_project_generator.generate(
            BlankProjectGeneratorInput(
                user_requirements=user_requirements,
            )
        )

        generated_project_name = raw.get("project_name")
        generated_project_description = raw.get("project_description")

        if not generated_project_name or not generated_project_description:
            raise ValueError("invalid_project_payload")

        return {
            "project_name": project_name or generated_project_name,
            "project_description": (
                project_description or generated_project_description
            ),
        }

    async def _generate_actor_and_feature_previews(
        self,
        user_requirements: str,
        user_feedback: str | None,
    ) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        actors_raw = await self._actors_generator.generate(
            ActorsGeneratorInput(
                user_requirements=user_requirements,
                user_feedback=user_feedback,
            )
        )

        actor_previews_for_draft = []
        actor_nodes = []

        for index, raw_actor in enumerate(
                actors_raw["actors"],
                start=1,
        ):
            actor_number = f"A{index:03d}"

            actor_previews_for_draft.append(
                {
                    "actor_number": actor_number,
                    "actor_name": raw_actor["actor_name"],
                    "actor_description": raw_actor["actor_description"],
                }
            )

            actor_nodes.append(
                ActorNode(
                    actorId=index,
                    actorName=raw_actor["actor_name"],
                    actorDescription=raw_actor["actor_description"],
                )
            )

        features_raw = await self._features_generator.generate(
            FeaturesGeneratorInput(
                user_requirements=user_requirements,
                actors=actor_nodes,
                user_feedback=user_feedback,
            )
        )

        id_to_actor_number = {
            index: actor["actor_number"]
            for index, actor in enumerate(
                actor_previews_for_draft,
                start=1,
            )
        }

        raw_features = features_raw["features"]

        self._validate_feature_tree_by_number(raw_features)

        feature_previews_for_draft = []

        for raw_feature in raw_features:
            feature_number = raw_feature["feature_number"]

            feature_previews_for_draft.append(
                {
                    "feature_number": feature_number,
                    "feature_name": raw_feature["feature_name"],
                    "feature_description": raw_feature["feature_description"],
                    "actor_numbers": [
                        id_to_actor_number[actor_id]
                        for actor_id in raw_feature.get("actor_ids", [])
                    ],
                }
            )

        actor_number_to_name = {
            actor["actor_number"]: actor["actor_name"]
            for actor in actor_previews_for_draft
        }

        actor_previews_for_response = [
            {
                "actor_name": actor["actor_name"],
                "actor_description": actor["actor_description"],
            }
            for actor in actor_previews_for_draft
        ]

        feature_previews_for_response = [
            {
                "feature_number": feature["feature_number"],
                "feature_name": feature["feature_name"],
                "feature_description": feature["feature_description"],
                "actor_names": [
                    actor_number_to_name[actor_number]
                    for actor_number in feature.get("actor_numbers", [])
                ],
            }
            for feature in feature_previews_for_draft
        ]

        return (
            actor_previews_for_draft,
            actor_previews_for_response,
            feature_previews_for_draft,
            feature_previews_for_response,
        )

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

    async def _get_draft(
        self,
        draft_id: str,
        session,
    ) -> dict:
        from backend.api.services.draft_store import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, session)

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    async def _persist_project_creation_draft(
        self,
        draft: dict,
        session,
    ):
        from backend.database.model import (
            ActorModel,
            FeatureModel,
            FeatureRelationModel,
            ProjectModel,
            feature_actor_table,
        )

        project_preview = draft["project_preview"]

        project = ProjectModel(
            name=project_preview["project_name"],
            description=project_preview["project_description"],
            user_requirements=draft["user_requirements"],
        )

        session.add(project)
        await session.flush()
        await self._apply_project_creation_draft_to_project(
            project=project,
            draft=draft,
            session=session,
            replace_existing=False,
        )
        return project

    async def _apply_project_creation_draft_to_existing_project(
        self,
        project_id: int,
        draft: dict,
        session,
    ):
        from backend.database.model import ProjectModel

        project = await session.get(ProjectModel, project_id)
        if project is None:
            raise ValueError("project_not_found")

        await self._apply_project_creation_draft_to_project(
            project=project,
            draft=draft,
            session=session,
            replace_existing=True,
        )
        return project

    async def _apply_project_creation_draft_to_project(
        self,
        project,
        draft: dict,
        session,
        replace_existing: bool,
    ) -> None:
        from backend.database.model import (
            ActorModel,
            BusinessObjectModel,
            FeatureModel,
            FeatureRelationModel,
            FlowModel,
            GherkinSpecModel,
            PrototypePreviewModel,
            ScenarioModel,
            feature_actor_table,
        )

        project_preview = draft["project_preview"]
        project.name = project_preview["project_name"]
        project.description = project_preview["project_description"]
        project.user_requirements = draft["user_requirements"]
        await session.flush()

        if replace_existing:
            await session.execute(
                delete(PrototypePreviewModel).where(
                    PrototypePreviewModel.project_id == project.id
                )
            )
            await session.execute(
                delete(FlowModel).where(FlowModel.project_id == project.id)
            )
            await session.execute(
                delete(BusinessObjectModel).where(
                    BusinessObjectModel.project_id == project.id
                )
            )
            await session.execute(
                delete(ScenarioModel).where(ScenarioModel.project_id == project.id)
            )
            await session.execute(
                delete(GherkinSpecModel).where(
                    GherkinSpecModel.project_id == project.id
                )
            )
            await session.execute(
                delete(FeatureModel).where(FeatureModel.project_id == project.id)
            )
            await session.execute(
                delete(ActorModel).where(ActorModel.project_id == project.id)
            )
            await session.flush()

        actor_number_to_model = {}
        for actor in draft["actors"]:
            model = ActorModel(
                project_id=project.id,
                name=actor["actor_name"],
                description=actor["actor_description"],
                confirmation_status=ConfirmationStatus.AI_ASSUMPTION.value,
            )
            session.add(model)
            actor_number_to_model[actor["actor_number"]] = model

        await session.flush()

        feature_number_to_model = {}
        for feature in draft["features"]:
            model = FeatureModel(
                project_id=project.id,
                name=feature["feature_name"],
                description=feature["feature_description"],
                confirmation_status=ConfirmationStatus.AI_ASSUMPTION.value,
            )
            session.add(model)
            feature_number_to_model[feature["feature_number"]] = model

        await session.flush()

        feature_actor_rows = []
        for feature in draft["features"]:
            feature_model = feature_number_to_model[feature["feature_number"]]
            for actor_number in feature.get("actor_numbers", []):
                actor_model = actor_number_to_model[actor_number]
                feature_actor_rows.append(
                    {
                        "feature_id": feature_model.id,
                        "actor_id": actor_model.id,
                    }
                )

        if feature_actor_rows:
            await session.execute(insert(feature_actor_table), feature_actor_rows)

        for feature in draft["features"]:
            feature_number = feature["feature_number"]
            parent_number = self._get_parent_feature_number(feature_number)
            if parent_number is None:
                continue

            session.add(
                FeatureRelationModel(
                    parent_feature_id=feature_number_to_model[parent_number].id,
                    child_feature_id=feature_number_to_model[feature_number].id,
                    position=self._get_feature_position(feature_number),
                )
            )

        await session.flush()
