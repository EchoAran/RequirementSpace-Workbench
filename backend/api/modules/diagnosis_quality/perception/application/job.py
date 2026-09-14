from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)
from backend.schemas import (
    NextSuggestion,
    PerceptionJobStatus,
)

from .job_executor import PerceptionJobExecutor
from .job_invalidator import PerceptionJobInvalidator


class PerceptionJobService:
    def __init__(self):
        self.executor = PerceptionJobExecutor()
        self.invalidator = PerceptionJobInvalidator()

    async def get_next_what_suggestion(
        self,
        project_id: int,
        session,
        workspace_id: int,
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> NextSuggestion | None:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )

        for perception_kind in ("ACTOR", "FEATURE"):
            suggestion = await self._get_perception_suggestion(
                project_id=project_id,
                stage="what",
                context=context,
                perception_kind=perception_kind,
                target_type="project",
                target_id="",
                context_hash=self._build_context_hash(
                    perception_kind=perception_kind,
                    target_id="",
                    context=context,
                ),
                session=session,
                background_tasks=background_tasks,
                public_project_id=public_project_id,
                workspace_id=workspace_id,
            )

            if suggestion is not None:
                return suggestion

        for perception_kind in ("SCENARIO", "ACCEPTANCE_CRITERION"):
            for target_pair in self._iter_pairs_with_scenarios(context):
                target_id = self._build_pair_target_id(*target_pair)
                suggestion = await self._get_perception_suggestion(
                    project_id=project_id,
                    stage="what",
                    context=context,
                    perception_kind=perception_kind,
                    target_type="feature_actor_pair",
                    target_id=target_id,
                    context_hash=self._build_context_hash(
                        perception_kind=perception_kind,
                        target_id=target_id,
                        context=context,
                    ),
                    session=session,
                    background_tasks=background_tasks,
                    public_project_id=public_project_id,
                    workspace_id=workspace_id,
                )

                if suggestion is not None:
                    return suggestion

        return None

    async def get_next_how_suggestion(
        self,
        project_id: int,
        session,
        workspace_id: int,
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> NextSuggestion | None:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )

        for perception_kind in ("RULE", "FLOW"):
            suggestion = await self._get_perception_suggestion(
                project_id=project_id,
                stage="how",
                context=context,
                perception_kind=perception_kind,
                target_type="project",
                target_id="",
                context_hash=self._build_context_hash(
                    perception_kind=perception_kind,
                    target_id="",
                    context=context,
                ),
                session=session,
                background_tasks=background_tasks,
                public_project_id=public_project_id,
                workspace_id=workspace_id,
            )

            if suggestion is not None:
                return suggestion

        return None

    async def get_active_slot_suggestion(
        self,
        project_id: int,
        stage: str,
        session,
        workspace_id: int,
        public_project_id: str | None = None,
    ) -> NextSuggestion | None:
        from backend.database.model import PerceptionJobModel, PerceptionSlotModel

        stmt = (
            select(PerceptionJobModel)
            .join(PerceptionSlotModel, PerceptionSlotModel.id == PerceptionJobModel.id)
            .where(
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage == stage,
                PerceptionJobModel.workspace_id == workspace_id,
                PerceptionJobModel.status == PerceptionJobStatus.DONE_WITH_SLOT.value,
            )
        )
        stmt = stmt.order_by(PerceptionJobModel.id.desc())

        result = await session.execute(stmt)
        job = result.scalars().first()
        if job is None:
            return None
        return self._build_slot_suggestion(project_id, job, public_project_id)

    # ------------------------------------------------------------------
    # Internal Delegation
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_matching_job(
        session,
        *,
        project_id: int,
        stage: str,
        perception_kind: str,
        target_type: str,
        target_id: str,
        context_hash: str,
        workspace_id: int,
    ):
        from backend.database.model import PerceptionJobModel

        stmt = select(PerceptionJobModel).where(
            PerceptionJobModel.project_id == project_id,
            PerceptionJobModel.stage == stage,
            PerceptionJobModel.perception_kind == perception_kind,
            PerceptionJobModel.target_type == target_type,
            PerceptionJobModel.target_id == target_id,
            PerceptionJobModel.context_hash == context_hash,
            PerceptionJobModel.workspace_id == workspace_id,
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _activate_and_schedule_job(
        self,
        job,
        background_tasks: BackgroundTasks,
        session,
        *,
        clear_result: bool,
    ) -> None:
        job.status = PerceptionJobStatus.RUNNING.value
        if clear_result:
            job.result_slot_payload = None
            job.error_message = ""
        await session.flush()
        await self._schedule_perception_job(
            background_tasks=background_tasks,
            session=session,
            job_id=job.id,
        )

    async def _create_perception_job(
        self,
        *,
        project_id: int,
        stage: str,
        perception_kind: str,
        target_type: str,
        target_id: str,
        context_hash: str,
        session,
        background_tasks: BackgroundTasks | None,
        workspace_id: int,
    ):
        from backend.database.model import PerceptionJobModel

        try:
            async with session.begin_nested():
                job = PerceptionJobModel(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    stage=stage,
                    perception_kind=perception_kind,
                    target_type=target_type,
                    target_id=target_id,
                    context_hash=context_hash,
                    status=(
                        PerceptionJobStatus.RUNNING.value
                        if background_tasks is not None
                        else PerceptionJobStatus.NOT_STARTED.value
                    ),
                )
                session.add(job)
                await session.flush()
                return job
        except IntegrityError:
            job = await self._load_matching_job(
                session,
                project_id=project_id,
                stage=stage,
                perception_kind=perception_kind,
                target_type=target_type,
                target_id=target_id,
                context_hash=context_hash,
                workspace_id=workspace_id,
            )
            if job is None:
                raise
            return job

    async def _resolve_missing_job(
        self,
        *,
        project_id: int,
        stage: str,
        perception_kind: str,
        target_type: str,
        target_id: str,
        context_hash: str,
        session,
        background_tasks: BackgroundTasks | None,
        workspace_id: int,
    ) -> NextSuggestion:
        active_job = await self._load_active_stage_job(
            project_id=project_id,
            stage=stage,
            session=session,
            workspace_id=workspace_id,
        )
        if active_job is not None:
            if (
                active_job.status
                == PerceptionJobStatus.NOT_STARTED.value
                and background_tasks is not None
            ):
                await self._activate_and_schedule_job(
                    active_job,
                    background_tasks,
                    session,
                    clear_result=False,
                )
            return self._build_running_suggestion(active_job)
        job = await self._create_perception_job(
            project_id=project_id,
            stage=stage,
            perception_kind=perception_kind,
            target_type=target_type,
            target_id=target_id,
            context_hash=context_hash,
            session=session,
            background_tasks=background_tasks,
            workspace_id=workspace_id,
        )
        if (
            background_tasks is not None
            and job.status == PerceptionJobStatus.RUNNING.value
        ):
            await self._schedule_perception_job(
                background_tasks=background_tasks,
                session=session,
                job_id=job.id,
            )
        return self._build_running_suggestion(job)

    async def _resolve_existing_job(
        self,
        job,
        *,
        project_id: int,
        session,
        background_tasks: BackgroundTasks | None,
        public_project_id: str | None,
    ) -> NextSuggestion | None:
        if job.status == PerceptionJobStatus.DONE_EMPTY.value:
            return None
        if job.status == PerceptionJobStatus.DONE_WITH_SLOT.value:
            return self._build_slot_suggestion(
                project_id=project_id,
                job=job,
                public_project_id=public_project_id,
            )
        if job.status == PerceptionJobStatus.FAILED.value:
            return self._build_failed_suggestion(job)
        if job.status == PerceptionJobStatus.STALE.value:
            if background_tasks is None:
                return None
            await self._activate_and_schedule_job(
                job,
                background_tasks,
                session,
                clear_result=True,
            )
            return self._build_running_suggestion(job)
        if (
            job.status == PerceptionJobStatus.NOT_STARTED.value
            and background_tasks is not None
        ):
            await self._activate_and_schedule_job(
                job,
                background_tasks,
                session,
                clear_result=True,
            )
        return self._build_running_suggestion(job)

    async def _get_perception_suggestion(
        self,
        project_id: int,
        stage: str,
        context: IssueProjectContext,
        perception_kind: str,
        target_type: str,
        target_id: str,
        context_hash: str,
        session,
        background_tasks: BackgroundTasks | None,
        workspace_id: int,
        public_project_id: str | None = None,
    ) -> NextSuggestion | None:
        await self._mark_stale_jobs(
            project_id=project_id,
            stage=stage,
            perception_kind=perception_kind,
            target_type=target_type,
            target_id=target_id,
            context_hash=context_hash,
            session=session,
            workspace_id=workspace_id,
        )

        job = await self._load_matching_job(
            session,
            project_id=project_id,
            stage=stage,
            perception_kind=perception_kind,
            target_type=target_type,
            target_id=target_id,
            context_hash=context_hash,
            workspace_id=workspace_id,
        )

        if job is None:
            return await self._resolve_missing_job(
                project_id=project_id,
                stage=stage,
                perception_kind=perception_kind,
                target_type=target_type,
                target_id=target_id,
                context_hash=context_hash,
                session=session,
                background_tasks=background_tasks,
                workspace_id=workspace_id,
            )
        return await self._resolve_existing_job(
            job,
            project_id=project_id,
            session=session,
            background_tasks=background_tasks,
            public_project_id=public_project_id,
        )

    async def _schedule_perception_job(
        self,
        background_tasks: BackgroundTasks,
        session,
        job_id: int,
    ) -> None:
        await self.executor._schedule_perception_job(background_tasks, session, job_id)

    async def run_perception_job(
        self,
        job_id: int,
        llm_context=None,
    ) -> None:
        await self.executor.run_perception_job(job_id, llm_context)

    def _build_context_hash(
        self,
        perception_kind: str,
        target_id: str,
        context: IssueProjectContext,
    ) -> str:
        return self.executor._build_context_hash(perception_kind, target_id, context)

    def _build_pair_target_id(self, feature_id: int, actor_id: int) -> str:
        return self.executor._build_pair_target_id(feature_id, actor_id)

    def _iter_pairs_with_scenarios(self, context: IssueProjectContext) -> list[tuple[int, int]]:
        return self.executor._iter_pairs_with_scenarios(context)

    async def _load_active_stage_job(
        self,
        project_id: int,
        stage: str,
        session,
        workspace_id: int,
    ):
        return await self.executor._load_active_stage_job(
            project_id,
            stage,
            session,
            workspace_id=workspace_id,
        )

    async def _mark_stale_jobs(
        self,
        project_id: int,
        stage: str,
        perception_kind: str,
        target_type: str,
        target_id: str,
        context_hash: str,
        session,
        workspace_id: int,
    ) -> None:
        await self.invalidator._mark_stale_jobs(
            project_id=project_id,
            stage=stage,
            perception_kind=perception_kind,
            target_type=target_type,
            target_id=target_id,
            context_hash=context_hash,
            session=session,
            workspace_id=workspace_id,
        )

    def _build_running_suggestion(self, job) -> NextSuggestion:
        return self.executor._build_running_suggestion(job)

    def _build_failed_suggestion(self, job) -> NextSuggestion:
        return self.executor._build_failed_suggestion(job)

    def _build_slot_suggestion(
        self,
        project_id: int,
        job,
        public_project_id: str | None = None,
    ) -> NextSuggestion:
        return self.executor._build_slot_suggestion(project_id, job, public_project_id)
