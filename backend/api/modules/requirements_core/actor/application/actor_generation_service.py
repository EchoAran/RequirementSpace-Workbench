from uuid import uuid4

from sqlalchemy import select

from backend.core.generators.actors_generator import (
    ActorsGenerator,
    ActorsGeneratorInput,
)
from backend.core.notifier import get_notifier


class ActorGenerationService:
    def __init__(self):
        self._actors_generator = ActorsGenerator()

    async def create_draft(
        self,
        project_id: int,
        owner_user_id: int,
        session,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        workspace_id: int | None = None,
    ) -> dict:
        draft_id = uuid4().hex

        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
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
        draft_payload["branch_name"] = draft.get("branch_name")
        draft_payload["head_commit_id"] = draft.get("head_commit_id")
        response_payload["draft_id"] = draft_id
        response_payload["branch_name"] = draft.get("branch_name")
        response_payload["head_commit_id"] = draft.get("head_commit_id")

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
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
        branch_name: str | None = None,
        head_commit_id: str | None = None,
        workspace_id: int | None = None,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        draft_branch = draft.get("branch_name")
        if draft_branch and branch_name and draft_branch != branch_name:
            raise ValueError(f"draft_branch_mismatch: Draft created on branch '{draft_branch}' cannot be confirmed on '{branch_name}'")

        draft_commit = draft.get("head_commit_id")
        if draft_commit and head_commit_id and draft_commit != head_commit_id:
            raise ValueError("branch_drift_detected: Branch head commit has advanced since draft creation")

        result = await self._persist_actor_generation_draft(
            draft=draft,
            session=session,
            workspace_id=workspace_id,
        )
        await get_notifier().mark_stale(
            project_id=draft["project_id"],
            stages={"what", "how"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
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
        workspace_id: int | None = None,
    ) -> tuple[dict, dict]:
        user_requirements = await self._load_user_requirements(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
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
        workspace_id: int | None = None,
    ) -> str:
        from backend.database.model import BranchWorkspaceModel, ProjectModel

        async def _exec(stmt):
            res = session.execute(stmt)
            if hasattr(res, "__await__"):
                return await res
            return res

        if workspace_id is not None:
            ws_res = await _exec(select(BranchWorkspaceModel.user_requirements).where(BranchWorkspaceModel.id == workspace_id))
            ws_reqs = ws_res.scalar_one_or_none()
            if ws_reqs is not None:
                return ws_reqs

        project_result = await _exec(
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
        workspace_id: int | None = None,
    ) -> dict:
        from backend.database.model import ActorModel

        project_id = draft["project_id"]

        for item in draft["actors"]:
            session.add(
                ActorModel(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    name=item["actor_name"],
                    description=item["actor_description"],
                    confirmation_status='ai_assumption',
                )
            )

        flush_res = session.flush()
        if hasattr(flush_res, "__await__"):
            await flush_res

        return {
            "project_id": project_id,
            "actor_count": len(draft["actors"]),
            "message": "actors_created",
        }
