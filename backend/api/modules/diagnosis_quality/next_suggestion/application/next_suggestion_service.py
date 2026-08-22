from fastapi import BackgroundTasks
from sqlalchemy import select

from backend.api.modules.diagnosis_quality.perception.application.invalidation import (
    mark_perception_jobs_stale,
)
from backend.api.modules.diagnosis_quality.perception.application.job import (
    PerceptionJobService,
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

    async def _build_preview_suggestion(
        self,
        project_id: int,
        public_project_id: str,
        session,
    ) -> dict:
        await self._ensure_project_exists(project_id, session)
        return NextSuggestion(
            sourceType="predefined",
            code="PREVIEW_READY",
            title="查看预览",
            description="当前已处于预览阶段。",
            action={
                "kind": "navigate",
                "route": f"/projects/{public_project_id}/preview",
            },
        ).to_dict()

    async def _replace_transition_suggestion(
        self,
        suggestion,
        *,
        project_id: int,
        stage: str,
        session,
        background_tasks: BackgroundTasks | None,
        public_project_id: str,
        include_perception: bool,
        transition_code: str | None,
        workspace_id: int | None = None,
    ):
        if not include_perception and suggestion.code == transition_code:
            active_slot = (
                await self._perception_job_service
                .get_active_slot_suggestion(
                    project_id=project_id,
                    stage=stage,
                    session=session,
                    public_project_id=public_project_id,
                    workspace_id=workspace_id,
                )
            )
            if active_slot is not None:
                suggestion = active_slot
        if (
            include_perception
            and stage == "what"
            and suggestion.code == "ENTER_HOW"
        ):
            perception = (
                await self._perception_job_service
                .get_next_what_suggestion(
                    project_id=project_id,
                    session=session,
                    background_tasks=background_tasks,
                    public_project_id=public_project_id,
                    workspace_id=workspace_id,
                )
            )
            if perception is not None:
                suggestion = perception
        if (
            include_perception
            and stage == "how"
            and suggestion.code == "ENTER_SCOPE"
        ):
            perception = (
                await self._perception_job_service
                .get_next_how_suggestion(
                    project_id=project_id,
                    session=session,
                    background_tasks=background_tasks,
                    public_project_id=public_project_id,
                    workspace_id=workspace_id,
                )
            )
            if perception is not None:
                suggestion = perception
        return suggestion

    @staticmethod
    def _assert_public_project_id(
        suggestion: dict | None,
        project_id: int,
    ) -> None:
        if not suggestion or not isinstance(suggestion.get("action"), dict):
            return
        action = suggestion["action"]
        route = action.get("route")
        if isinstance(route, str) and (
            f"/projects/{project_id}/" in route
            or route.endswith(f"/projects/{project_id}")
        ):
            raise AssertionError(
                f"Internal integer project ID {project_id} "
                f"leaked in route: {route}"
            )
        payload = action.get("payload")
        if isinstance(payload, dict):
            value = payload.get("project_id")
            if value == project_id or value == str(project_id):
                raise AssertionError(
                    f"Internal integer project ID {project_id} "
                    f"leaked in payload: {payload}"
                )

    async def _build_policy_suggestion(
        self,
        policy,
        *,
        project_id: int,
        stage: str,
        session,
        background_tasks: BackgroundTasks | None,
        public_project_id: str,
        include_perception: bool,
        workspace_id: int | None = None,
    ) -> dict | None:
        suggestion = await policy.get_next(
            project_id=project_id,
            session=session,
            public_project_id=public_project_id,
            workspace_id=workspace_id,
        )
        transition_code = {
            "what": "ENTER_HOW",
            "how": "ENTER_SCOPE",
            "scope": "ENTER_PREVIEW",
        }.get(stage)
        suggestion = await self._replace_transition_suggestion(
            suggestion,
            project_id=project_id,
            stage=stage,
            session=session,
            background_tasks=background_tasks,
            public_project_id=public_project_id,
            include_perception=include_perception,
            transition_code=transition_code,
            workspace_id=workspace_id,
        )
        if (
            suggestion.code == transition_code
            and await self._is_stage_advanced(project_id, stage, session, workspace_id=workspace_id)
        ):
            return None
        result = suggestion.to_dict()
        self._assert_public_project_id(result, project_id)
        return result

    async def get_next_suggestion(
        self,
        project_id: int,
        stage: str,
        session,
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
        include_perception: bool = False,
        workspace_id: int | None = None,
    ) -> dict:
        stage = self._normalize_stage(stage)
        pub_id = public_project_id or str(project_id)

        if not await self._is_stage_visible(project_id, stage, session, workspace_id=workspace_id):
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
            suggestion = await self._build_preview_suggestion(
                project_id,
                pub_id,
                session,
            )
        else:
            suggestion = await self._build_policy_suggestion(
                policy,
                project_id=project_id,
                stage=stage,
                session=session,
                background_tasks=background_tasks,
                public_project_id=pub_id,
                include_perception=include_perception,
                workspace_id=workspace_id,
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
        workspace_id: int | None = None,
    ) -> dict:
        stage = self._normalize_stage(stage)
        await self._ensure_project_exists(project_id, session)
        pub_id = public_project_id or str(project_id)

        if not await self._is_stage_visible(project_id, stage, session, workspace_id=workspace_id):
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
            workspace_id=workspace_id,
        )

        return await self.get_next_suggestion(
            project_id=project_id,
            stage=stage,
            session=session,
            background_tasks=background_tasks,
            public_project_id=pub_id,
            include_perception=True,
            workspace_id=workspace_id,
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
        workspace_id: int | None = None,
    ) -> bool:
        from backend.database.model import BranchWorkspaceModel, ProjectModel

        unlocked_text = None
        if workspace_id is not None:
            ws_res = await session.execute(
                select(BranchWorkspaceModel.unlocked_stages).where(
                    BranchWorkspaceModel.id == workspace_id,
                )
            )
            unlocked_text = ws_res.scalar_one_or_none()

        if unlocked_text is None:
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
        return stage == "preview"

    @staticmethod
    async def _is_stage_advanced(
        project_id: int,
        stage: str,
        session,
        workspace_id: int | None = None,
    ) -> bool:
        next_stage_map = {
            "what": "how",
            "how": "scope",
            "scope": "preview",
        }
        next_stage = next_stage_map.get(stage)
        if not next_stage:
            return False

        from backend.database.model import BranchWorkspaceModel, ProjectModel

        unlocked_text = None
        if workspace_id is not None:
            ws_res = await session.execute(
                select(BranchWorkspaceModel.unlocked_stages).where(
                    BranchWorkspaceModel.id == workspace_id,
                )
            )
            unlocked_text = ws_res.scalar_one_or_none()

        if unlocked_text is None:
            result = await session.execute(
                select(ProjectModel.unlocked_stages).where(ProjectModel.id == project_id)
            )
            unlocked_text = result.scalar_one_or_none()

        if unlocked_text is None:
            raise ValueError("project_not_found")
        unlocked = {
            item.strip() for item in unlocked_text.split(",") if item.strip()
        }
        return next_stage in unlocked

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
