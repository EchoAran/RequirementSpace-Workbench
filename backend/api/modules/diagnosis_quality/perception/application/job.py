import asyncio
from fastapi import BackgroundTasks
from sqlalchemy import select

from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)
from backend.database.database import AsyncSessionLocal
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
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> NextSuggestion | None:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
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
                )

                if suggestion is not None:
                    return suggestion

        return None

    async def get_next_how_suggestion(
        self,
        project_id: int,
        session,
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> NextSuggestion | None:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )

        return await self._get_perception_suggestion(
            project_id=project_id,
            stage="how",
            context=context,
            perception_kind="FLOW",
            target_type="project",
            target_id="",
            context_hash=self._build_context_hash(
                perception_kind="FLOW",
                target_id="",
                context=context,
            ),
            session=session,
            background_tasks=background_tasks,
            public_project_id=public_project_id,
        )

    # ------------------------------------------------------------------
    # Compatibility Shims & Internal Delegation
    # ------------------------------------------------------------------

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
        public_project_id: str | None = None,
    ) -> NextSuggestion | None:
        from backend.database.model import PerceptionJobModel

        await self._mark_stale_jobs(
            project_id=project_id,
            stage=stage,
            perception_kind=perception_kind,
            target_type=target_type,
            target_id=target_id,
            context_hash=context_hash,
            session=session,
        )

        job_result = await session.execute(
            select(PerceptionJobModel).where(
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage == stage,
                PerceptionJobModel.perception_kind == perception_kind,
                PerceptionJobModel.target_type == target_type,
                PerceptionJobModel.target_id == target_id,
                PerceptionJobModel.context_hash == context_hash,
            )
        )
        job = job_result.scalar_one_or_none()

        if job is None:
            active_job = await self._load_active_stage_job(
                project_id=project_id,
                stage=stage,
                session=session,
            )

            if active_job is not None:
                if (
                    active_job.status == PerceptionJobStatus.NOT_STARTED.value
                    and background_tasks is not None
                ):
                    active_job.status = PerceptionJobStatus.RUNNING.value
                    await session.flush()
                    await self._schedule_perception_job(
                        background_tasks=background_tasks,
                        session=session,
                        job_id=active_job.id,
                    )

                return self._build_running_suggestion(active_job)

            try:
                async with session.begin_nested():
                    job = PerceptionJobModel(
                        project_id=project_id,
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
            except Exception:
                job_result = await session.execute(
                    select(PerceptionJobModel).where(
                        PerceptionJobModel.project_id == project_id,
                        PerceptionJobModel.stage == stage,
                        PerceptionJobModel.perception_kind == perception_kind,
                        PerceptionJobModel.target_type == target_type,
                        PerceptionJobModel.target_id == target_id,
                        PerceptionJobModel.context_hash == context_hash,
                    )
                )
                job = job_result.scalar_one_or_none()
                if job is None:
                    raise

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

        if job.status == PerceptionJobStatus.DONE_EMPTY.value:
            return None

        if job.status == PerceptionJobStatus.DONE_WITH_SLOT.value:
            return self._build_slot_suggestion(
                project_id=project_id,
                job=job,
                public_project_id=public_project_id,
            )

        if job.status == PerceptionJobStatus.FAILED.value:
            if background_tasks is not None:
                job.status = PerceptionJobStatus.RUNNING.value
                job.result_slot_payload = None
                job.error_message = ""
                await session.flush()
                await self._schedule_perception_job(
                    background_tasks=background_tasks,
                    session=session,
                    job_id=job.id,
                )
                return self._build_running_suggestion(job)
            return self._build_failed_suggestion(job)

        if job.status == PerceptionJobStatus.STALE.value:
            if background_tasks is not None:
                job.status = PerceptionJobStatus.RUNNING.value
                job.result_slot_payload = None
                job.error_message = ""
                await session.flush()
                await self._schedule_perception_job(
                    background_tasks=background_tasks,
                    session=session,
                    job_id=job.id,
                )
                return self._build_running_suggestion(job)
            return None

        if (
            job.status == PerceptionJobStatus.NOT_STARTED.value
            and background_tasks is not None
        ):
            job.status = PerceptionJobStatus.RUNNING.value
            job.result_slot_payload = None
            job.error_message = ""
            await session.flush()
            await self._schedule_perception_job(
                background_tasks=background_tasks,
                session=session,
                job_id=job.id,
            )

        return self._build_running_suggestion(job)

    async def _schedule_perception_job(
        self,
        background_tasks: BackgroundTasks,
        session,
        job_id: int,
    ) -> None:
        await self.executor._schedule_perception_job(background_tasks, session, job_id)

    async def run_perception_job(self, job_id: int) -> None:
        await self.executor.run_perception_job(job_id)

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

    async def _load_active_stage_job(self, project_id: int, stage: str, session):
        return await self.executor._load_active_stage_job(project_id, stage, session)

    async def _mark_stale_jobs(
        self,
        project_id: int,
        stage: str,
        perception_kind: str,
        target_type: str,
        target_id: str,
        context_hash: str,
        session,
    ) -> None:
        await self.invalidator._mark_stale_jobs(
            project_id=project_id,
            stage=stage,
            perception_kind=perception_kind,
            target_type=target_type,
            target_id=target_id,
            context_hash=context_hash,
            session=session,
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
