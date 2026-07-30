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
from backend.api.modules.project_lifecycle.ports import ActorFeaturePreviewGeneratorPort

_feature_number_pattern = re.compile(r"^F\d{3}(?:-\d{3})*$")

def _get_parent_feature_number(feature_number: str) -> str | None:
    if "-" not in feature_number:
        return None
    return feature_number.rsplit("-", 1)[0]

def _get_feature_position(feature_number: str) -> int:
    return int(feature_number.rsplit("-", 1)[-1].replace("F", ""))

def _validate_feature_tree_by_number(features: list[dict]) -> None:
    if len(features) == 0:
        raise ValueError("empty_features")
    feature_numbers = [feature["feature_number"] for feature in features]
    feature_number_set = set(feature_numbers)
    if len(feature_number_set) != len(feature_numbers):
        raise ValueError("duplicate_feature_number")
    root_numbers = []
    for feature_number in feature_numbers:
        if _feature_number_pattern.match(feature_number) is None:
            raise ValueError("invalid_feature_number_format")
        parent_number = _get_parent_feature_number(feature_number)
        if parent_number is None:
            root_numbers.append(feature_number)
            continue
        if parent_number not in feature_number_set:
            raise ValueError("missing_parent_feature")
    if len(root_numbers) != 1:
        raise ValueError("invalid_root_feature_count")


class LocalActorFeaturePreviewGenerator(ActorFeaturePreviewGeneratorPort):
    def __init__(self):
        self._actors_generator = ActorsGenerator()
        self._features_generator = FeaturesGenerator()

    async def generate_actor_and_feature_previews(
        self,
        user_requirements: str,
        user_feedback: str | None,
        knowledge_context: str | None = None,
    ) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        actors_raw = await self._actors_generator.generate(
            ActorsGeneratorInput(
                user_requirements=user_requirements,
                user_feedback=user_feedback,
                knowledge_context=knowledge_context,
            )
        )
        actor_previews_for_draft, actor_nodes = self._build_actor_previews(
            actors_raw["actors"]
        )

        features_raw = await self._features_generator.generate(
            FeaturesGeneratorInput(
                user_requirements=user_requirements,
                actors=actor_nodes,
                user_feedback=user_feedback,
                knowledge_context=knowledge_context,
            )
        )
        feature_previews_for_draft = self._build_feature_previews(
            features_raw["features"],
            actor_previews_for_draft,
        )
        actor_previews_for_response = self._build_actor_response_previews(
            actor_previews_for_draft
        )
        feature_previews_for_response = self._build_feature_response_previews(
            feature_previews_for_draft,
            actor_previews_for_draft,
        )
        return (
            actor_previews_for_draft,
            actor_previews_for_response,
            feature_previews_for_draft,
            feature_previews_for_response,
        )

    @staticmethod
    def _build_actor_previews(
        raw_actors: list[dict],
    ) -> tuple[list[dict], list[ActorNode]]:
        draft_previews = []
        actor_nodes = []
        for index, raw_actor in enumerate(raw_actors, start=1):
            actor_number = f"A{index:03d}"
            draft_previews.append(
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
        return draft_previews, actor_nodes

    @staticmethod
    def _build_feature_previews(
        raw_features: list[dict],
        actor_previews: list[dict],
    ) -> list[dict]:
        _validate_feature_tree_by_number(raw_features)
        id_to_actor_number = {
            index: actor["actor_number"]
            for index, actor in enumerate(actor_previews, start=1)
        }
        return [
            {
                "feature_number": feature["feature_number"],
                "feature_name": feature["feature_name"],
                "feature_description": feature["feature_description"],
                "actor_numbers": [
                    id_to_actor_number[actor_id]
                    for actor_id in feature.get("actor_ids", [])
                ],
            }
            for feature in raw_features
        ]

    @staticmethod
    def _build_actor_response_previews(
        actor_previews: list[dict],
    ) -> list[dict]:
        return [
            {
                "actor_name": actor["actor_name"],
                "actor_description": actor["actor_description"],
            }
            for actor in actor_previews
        ]

    @staticmethod
    def _build_feature_response_previews(
        feature_previews: list[dict],
        actor_previews: list[dict],
    ) -> list[dict]:
        actor_number_to_name = {
            actor["actor_number"]: actor["actor_name"]
            for actor in actor_previews
        }
        return [
            {
                "feature_number": feature["feature_number"],
                "feature_name": feature["feature_name"],
                "feature_description": feature["feature_description"],
                "actor_names": [
                    actor_number_to_name[actor_number]
                    for actor_number in feature.get("actor_numbers", [])
                ],
            }
            for feature in feature_previews
        ]


class ProjectCreationService:
    def __init__(self, preview_generator: ActorFeaturePreviewGeneratorPort = None):
        self._preview_generator = preview_generator or LocalActorFeaturePreviewGenerator()
        self._blank_project_generator = BlankProjectGenerator()

    async def create_draft(
            self,
            user_requirements: str,
            owner_user_id: int,
            session,
            project_name: str | None = None,
            project_description: str | None = None,
            knowledge_workspace_id: str | None = None,
    ) -> dict:
        draft_id = uuid4().hex

        # 1. Retrieve knowledge base context if workspace is active and belongs to user
        knowledge_context = None
        from backend.core.config import KNOWLEDGE_BASE_ENABLED
        if knowledge_workspace_id and KNOWLEDGE_BASE_ENABLED:
            from backend.database.model import KnowledgeWorkspaceModel
            from sqlalchemy import select
            from fastapi import HTTPException

            ws_res = await session.execute(
                select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.public_id == knowledge_workspace_id)
            )
            ws = ws_res.scalar_one_or_none()
            if not ws:
                raise HTTPException(status_code=404, detail="workspace_not_found")
            if ws.owner_user_id != owner_user_id:
                raise HTTPException(status_code=403, detail="forbidden")
            if ws.status != "active":
                raise HTTPException(status_code=400, detail="workspace_inactive")

            # Construct combined query for context retrieval
            query_parts = [user_requirements]
            if project_name:
                query_parts.append(project_name)
            if project_description:
                query_parts.append(project_description)
            query_parts.append("生成项目名称、项目描述、参与者、功能树、业务边界")
            combined_query = " ".join(query_parts)

            from backend.services.knowledge.context_builder import KnowledgeContextBuilder
            knowledge_context = await KnowledgeContextBuilder.build(
                workspace_id=ws.id,
                purpose="project_creation",
                query=combined_query,
                token_budget=4000,
                session=session
            )

        draft_payload, response_payload = await self._generate_preview(
            user_requirements=user_requirements,
            project_name=project_name,
            project_description=project_description,
            user_feedback=None,
            knowledge_context=knowledge_context,
        )

        draft_payload["draft_id"] = draft_id
        draft_payload["knowledge_workspace_id"] = knowledge_workspace_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=None,
            draft_id=draft_id,
            draft_type="project_creation",
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
        knowledge_workspace_id = draft.get("knowledge_workspace_id")

        # Re-build knowledge context if workspace is active
        knowledge_context = None
        if knowledge_workspace_id:
            from backend.database.model import KnowledgeWorkspaceModel
            from sqlalchemy import select
            ws_res = await session.execute(
                select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.public_id == knowledge_workspace_id)
            )
            ws = ws_res.scalar_one_or_none()
            if ws and ws.status == "active":
                query_parts = [draft["user_requirements"]]
                if user_feedback:
                    query_parts.append(user_feedback)
                query_parts.append("生成项目名称、项目描述、参与者、功能树、业务边界")
                combined_query = " ".join(query_parts)

                from backend.services.knowledge.context_builder import KnowledgeContextBuilder
                knowledge_context = await KnowledgeContextBuilder.build(
                    workspace_id=ws.id,
                    purpose="project_creation",
                    query=combined_query,
                    token_budget=4000,
                    session=session
                )

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
            knowledge_context=knowledge_context,
        )

        draft_payload["draft_id"] = draft_id
        draft_payload["knowledge_workspace_id"] = knowledge_workspace_id
        response_payload["draft_id"] = draft_id

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=None,
            draft_id=draft_id,
            draft_type="project_creation",
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

        project = await self._persist_project_creation_draft(
            draft=draft,
            owner_user_id=owner_user_id,
            session=session,
        )

        # Confirm & bind workspace documents/chunks to the new project
        workspace_public_id = draft.get("knowledge_workspace_id")
        if workspace_public_id:
            from backend.services.knowledge.workspace import KnowledgeWorkspaceService
            await KnowledgeWorkspaceService.bind_workspace_to_project(
                session=session,
                workspace_public_id=workspace_public_id,
                project_id=project.id,
                owner_user_id=owner_user_id,
            )

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)

        return {
            "project_id": project.public_id,
            "project_name": project.name,
            "project_description": project.description,
            "message": "project_created",
        }

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

    async def _generate_preview(
            self,
            user_requirements: str,
            project_name: str | None = None,
            project_description: str | None = None,
            user_feedback: str | None = None,
            knowledge_context: str | None = None,
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
                knowledge_context=knowledge_context,
            )
        )
        actor_feature_task = asyncio.create_task(
            self._preview_generator.generate_actor_and_feature_previews(
                user_requirements=user_requirements,
                user_feedback=user_feedback,
                knowledge_context=knowledge_context,
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
        knowledge_context: str | None = None,
    ) -> dict:
        if project_name is not None and project_description is not None:
            return {
                "project_name": project_name,
                "project_description": project_description,
            }

        raw = await self._blank_project_generator.generate(
            BlankProjectGeneratorInput(
                user_requirements=user_requirements,
                knowledge_context=knowledge_context,
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

    def _find_root_feature(
        self,
        features: list[dict],
    ) -> dict:
        _validate_feature_tree_by_number(features)

        for feature in features:
            parent_number = _get_parent_feature_number(
                feature["feature_number"]
            )

            if parent_number is None:
                return feature

        raise ValueError("invalid_root_feature_count")

    async def _get_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, owner_user_id, session)

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    async def _persist_project_creation_draft(
        self,
        draft: dict,
        owner_user_id: int,
        session,
    ):
        from backend.database.model import (
            ProjectModel,
        )

        project_preview = draft["project_preview"]

        project = ProjectModel(
            name=project_preview["project_name"],
            description=project_preview["project_description"],
            user_requirements=draft["user_requirements"],
            owner_user_id=owner_user_id,
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
        project_preview = draft["project_preview"]
        project.name = project_preview["project_name"]
        project.description = project_preview["project_description"]
        project.user_requirements = draft["user_requirements"]
        await session.flush()

        if replace_existing:
            await self._clear_existing_project_graph(project.id, session)

        actor_number_to_model = await self._add_draft_actors(
            project.id,
            draft["actors"],
            session,
        )
        feature_number_to_model = await self._add_draft_features(
            project.id,
            draft["features"],
            session,
        )
        await self._add_draft_feature_actor_links(
            draft["features"],
            actor_number_to_model,
            feature_number_to_model,
            session,
        )
        await self._add_draft_feature_relations(
            draft["features"],
            feature_number_to_model,
            session,
        )

    @staticmethod
    async def _clear_existing_project_graph(project_id: int, session) -> None:
        from backend.database.model import (
            ActorModel,
            BusinessObjectModel,
            FeatureModel,
            FlowModel,
            GherkinSpecModel,
            PrototypePreviewModel,
            ScenarioModel,
        )

        for model in (
            PrototypePreviewModel,
            FlowModel,
            BusinessObjectModel,
            ScenarioModel,
            GherkinSpecModel,
            FeatureModel,
            ActorModel,
        ):
            await session.execute(delete(model).where(model.project_id == project_id))
        await session.flush()

    @staticmethod
    async def _add_draft_actors(
        project_id: int,
        actors: list[dict],
        session,
    ) -> dict:
        from backend.database.model import ActorModel

        actor_number_to_model = {}
        for actor in actors:
            model = ActorModel(
                project_id=project_id,
                name=actor["actor_name"],
                description=actor["actor_description"],
                confirmation_status=ConfirmationStatus.AI_ASSUMPTION.value,
            )
            session.add(model)
            actor_number_to_model[actor["actor_number"]] = model

        await session.flush()
        return actor_number_to_model

    @staticmethod
    async def _add_draft_features(
        project_id: int,
        features: list[dict],
        session,
    ) -> dict:
        from backend.database.model import FeatureModel

        feature_number_to_model = {}
        for feature in features:
            model = FeatureModel(
                project_id=project_id,
                name=feature["feature_name"],
                description=feature["feature_description"],
                confirmation_status=ConfirmationStatus.AI_ASSUMPTION.value,
            )
            session.add(model)
            feature_number_to_model[feature["feature_number"]] = model

        await session.flush()
        return feature_number_to_model

    @staticmethod
    async def _add_draft_feature_actor_links(
        features: list[dict],
        actor_number_to_model: dict,
        feature_number_to_model: dict,
        session,
    ) -> None:
        from backend.database.model import feature_actor_table

        feature_actor_rows = []
        for feature in features:
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

    @staticmethod
    async def _add_draft_feature_relations(
        features: list[dict],
        feature_number_to_model: dict,
        session,
    ) -> None:
        from backend.database.model import FeatureRelationModel

        for feature in features:
            feature_number = feature["feature_number"]
            parent_number = _get_parent_feature_number(feature_number)
            if parent_number is None:
                continue

            session.add(
                FeatureRelationModel(
                    parent_feature_id=feature_number_to_model[parent_number].id,
                    child_feature_id=feature_number_to_model[feature_number].id,
                    position=_get_feature_position(feature_number),
                )
            )

        await session.flush()
