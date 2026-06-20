from sqlalchemy import select

from fastapi import BackgroundTasks

from backend.api.services.perception_job_service import PerceptionJobService
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.core.suggestions import (
    HowSuggestionPolicy,
    ScopeSuggestionPolicy,
    WhatSuggestionPolicy,
)
from backend.schemas import NextSuggestion


class NextSuggestionService:
    def __init__(self):
        self._policies = {
            "what": WhatSuggestionPolicy(),
            "how": HowSuggestionPolicy(),
            "scope": ScopeSuggestionPolicy(),
        }
        self._perception_job_service = PerceptionJobService()

    async def get_next_suggestion(
        self,
        project_id: int,
        stage: str,
        session,
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> dict:
        stage = self._normalize_stage(stage)
        pub_id = public_project_id or str(project_id)

        if not await self._is_stage_visible(project_id, stage, session):
            return {
                "project_id": pub_id,
                "stage": stage,
                "suggestion": self._build_locked_stage_suggestion(
                    project_id=project_id,
                    stage=stage,
                    public_project_id=pub_id,
                ).to_dict(),
            }

        policy = self._policies.get(stage)

        if policy is None:
            await self._ensure_project_exists(project_id, session)
            suggestion = NextSuggestion(
                sourceType="predefined",
                code="PREVIEW_READY",
                title="查看预览",
                description="当前已处于预览阶段。",
                action={
                    "kind": "navigate",
                    "route": f"/projects/{pub_id}/preview",
                },
            ).to_dict()
        else:
            suggestion_node = await policy.get_next(
                project_id=project_id,
                session=session,
                public_project_id=pub_id,
            )

            if stage == "what" and suggestion_node.code == "ENTER_HOW":
                perception_suggestion = await (
                    self._perception_job_service
                ).get_next_what_suggestion(
                    project_id=project_id,
                    session=session,
                    background_tasks=background_tasks,
                    public_project_id=pub_id,
                )

                if perception_suggestion is not None:
                    suggestion_node = perception_suggestion

            if stage == "how" and suggestion_node.code == "ENTER_SCOPE":
                perception_suggestion = await (
                    self._perception_job_service
                ).get_next_how_suggestion(
                    project_id=project_id,
                    session=session,
                    background_tasks=background_tasks,
                    public_project_id=pub_id,
                )

                if perception_suggestion is not None:
                    suggestion_node = perception_suggestion

            suggestion = suggestion_node.to_dict()

            # Defensive assertion checks for internal ID leakage
            if "action" in suggestion and isinstance(suggestion["action"], dict):
                act = suggestion["action"]
                if "route" in act and isinstance(act["route"], str):
                    if f"/projects/{project_id}/" in act["route"] or act["route"].endswith(f"/projects/{project_id}"):
                        raise AssertionError(
                            f"Internal integer project ID {project_id} leaked in route: {act['route']}"
                        )
                if "payload" in act and isinstance(act["payload"], dict):
                    val = act["payload"].get("project_id")
                    if val == project_id or val == str(project_id):
                        raise AssertionError(
                            f"Internal integer project ID {project_id} leaked in payload: {act['payload']}"
                        )

        return {
            "project_id": pub_id,
            "stage": stage,
            "suggestion": suggestion,
        }

    async def rediagnose_next_suggestion(
        self,
        project_id: int,
        stage: str,
        session,
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> dict:
        stage = self._normalize_stage(stage)
        await self._ensure_project_exists(project_id, session)
        pub_id = public_project_id or str(project_id)

        if not await self._is_stage_visible(project_id, stage, session):
            return {
                "project_id": pub_id,
                "stage": stage,
                "suggestion": self._build_locked_stage_suggestion(
                    project_id=project_id,
                    stage=stage,
                    public_project_id=pub_id,
                ).to_dict(),
            }

        # A manual "rediagnose" must not reuse a previous AI perception slot.
        # Clear the current stage cache first; normal next-suggestion reads can
        # still reuse cache through get_next_suggestion().
        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={stage},
            session=session,
        )

        return await self.get_next_suggestion(
            project_id=project_id,
            stage=stage,
            session=session,
            background_tasks=background_tasks,
            public_project_id=pub_id,
        )

    @staticmethod
    def _normalize_stage(stage: str) -> str:
        normalized_stage = stage.strip().lower()

        if normalized_stage not in {
            "what",
            "how",
            "scope",
            "preview",
        }:
            raise ValueError("invalid_stage")

        return normalized_stage

    @staticmethod
    async def _ensure_project_exists(project_id: int, session) -> None:
        from backend.database.model import ProjectModel

        project_result = await session.execute(
            select(ProjectModel.id).where(ProjectModel.id == project_id)
        )

        if project_result.scalar_one_or_none() is None:
            raise ValueError("project_not_found")

    @classmethod
    async def _is_stage_visible(
        cls,
        project_id: int,
        stage: str,
        session,
    ) -> bool:
        from backend.database.model import ProjectModel

        project_result = await session.execute(
            select(ProjectModel.unlocked_stages).where(
                ProjectModel.id == project_id,
            )
        )
        unlocked_text = project_result.scalar_one_or_none()

        if unlocked_text is None:
            raise ValueError("project_not_found")

        return cls._is_stage_unlocked_for_detection(
            stage=stage,
            unlocked_stages=unlocked_text,
        )

    @staticmethod
    def _is_stage_unlocked_for_detection(
        stage: str,
        unlocked_stages: str,
    ) -> bool:
        unlocked = {
            item.strip()
            for item in (unlocked_stages or "").split(",")
            if item.strip()
        }

        if stage == "what":
            return True
        if stage == "how":
            return "what" in unlocked
        if stage == "scope":
            return "how" in unlocked
        if stage == "preview":
            return "scope" in unlocked

        return False

    @staticmethod
    def _build_locked_stage_suggestion(
        project_id: int,
        stage: str,
        public_project_id: str | None = None,
    ) -> NextSuggestion:
        previous_stage = {
            "how": "what",
            "scope": "how",
            "preview": "scope",
        }.get(stage, "what")

        pub_id = public_project_id or str(project_id)

        return NextSuggestion(
            sourceType="predefined",
            code="STAGE_LOCKED",
            title="阶段尚未解锁",
            description="请先完成并确认上一阶段，再进行当前阶段的感知与建议。",
            status="blocked",
            action={
                "kind": "navigate",
                "route": f"/projects/{pub_id}/{previous_stage}",
            },
        )
