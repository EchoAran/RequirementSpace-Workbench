from uuid import uuid4

from sqlalchemy import select

from backend.core.generators.actors_generator import (
    ActorsGenerator,
    ActorsGeneratorInput,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)


class ActorGenerationService:
    def __init__(self):
        self._actors_generator = ActorsGenerator()

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

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="actor",
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

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=draft["project_id"],
            draft_id=draft_id,
            draft_type="actor",
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

        result = await self._persist_actor_generation_draft(
            draft=draft,
            session=session,
        )
        await mark_perception_jobs_stale(
            project_id=draft["project_id"],
            stages={"what", "how"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)

        return result

    async def discard_draft(
        self,
        draft_id: str,
        owner_user_id: int,
    ) -> dict:
        from backend.api.services.draft_store import GenerativeDraftStore
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
        from backend.api.services.draft_store import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, owner_user_id, session)

    async def _generate_preview(
        self,
        project_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        user_requirements = await self._load_user_requirements(
            project_id=project_id,
            session=session,
        )

        raw = await self._actors_generator.generate(
            ActorsGeneratorInput(
                user_requirements=user_requirements,
                user_feedback=user_feedback,
            )
        )

        actors = self._normalize_generated_actors(raw)

        draft_payload = {
            "project_id": project_id,
            "actors": actors,
        }

        response_payload = {
            "project_id": project_id,
            "actors": actors,
        }

        return draft_payload, response_payload

    @staticmethod
    async def _load_user_requirements(
        project_id: int,
        session,
    ) -> str:
        from backend.database.model import ProjectModel

        project_result = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
            )
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        return project.user_requirements

    @staticmethod
    def _normalize_generated_actors(raw: dict) -> list[dict]:
        raw_actors = raw.get("actors", [])

        if not raw_actors:
            raise ValueError("empty_actors")

        actors = []

        for item in raw_actors:
            actor_name = item.get("actor_name")
            actor_description = item.get("actor_description")

            if not actor_name or not actor_description:
                raise ValueError("invalid_actor_payload")

            actors.append(
                {
                    "actor_name": actor_name,
                    "actor_description": actor_description,
                }
            )

        return actors

    @staticmethod
    async def _persist_actor_generation_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import ActorModel

        project_id = draft["project_id"]

        for item in draft["actors"]:
            session.add(
                ActorModel(
                    project_id=project_id,
                    name=item["actor_name"],
                    description=item["actor_description"],
                    confirmation_status='ai_assumption',
                )
            )

        await session.flush()

        return {
            "project_id": project_id,
            "actor_count": len(draft["actors"]),
            "message": "actors_created",
        }
