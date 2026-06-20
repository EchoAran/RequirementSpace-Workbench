import asyncio
import hashlib
import json

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)
from backend.core.perceptrons.acceptance_criteria_perceptron import (
    AcceptanceCriteriaPerceptron,
    AcceptanceCriteriaPerceptronInput,
)
from backend.core.perceptrons.actors_perceptron import (
    ActorsPerceptron,
    ActorsPerceptronInput,
)
from backend.core.perceptrons.features_perceptron import (
    FeaturesPerceptron,
    FeaturesPerceptronInput,
)
from backend.core.perceptrons.flows_perceptron import (
    FlowsPerceptron,
    FlowsPerceptronInput,
)
from backend.core.perceptrons.scenarios_perceptron import (
    ScenariosPerceptron,
    ScenariosPerceptronInput,
)
from backend.database.database import AsyncSessionLocal
from backend.schemas import (
    AcceptanceCriterionNode,
    ActorNode,
    FeatureNode,
    FlowNode,
    FlowStepNode,
    FlowStepType,
    NextSuggestion,
    PerceptionJobStatus,
    PerceptionKindType,
    ScenarioNode,
)


class PerceptionJobService:
    def __init__(self):
        self._actors_perceptron = ActorsPerceptron()
        self._features_perceptron = FeaturesPerceptron()
        self._scenarios_perceptron = ScenariosPerceptron()
        self._acceptance_criteria_perceptron = AcceptanceCriteriaPerceptron()
        self._flows_perceptron = FlowsPerceptron()

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
                # The nested transaction is automatically rolled back, so session is valid!
                # Now we query again to fetch the concurrently inserted job!
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
        # FastAPI runs BackgroundTasks before yield-dependency cleanup.
        # With SQLite, keeping this request transaction open can lock the
        # background session when it updates the same job row.
        await session.commit()
        background_tasks.add_task(
            self.run_perception_job,
            job_id,
        )

    @staticmethod
    async def _load_active_stage_job(
        project_id: int,
        stage: str,
        session,
    ):
        from backend.database.model import PerceptionJobModel

        result = await session.execute(
            select(PerceptionJobModel)
            .where(
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage == stage,
                PerceptionJobModel.status.in_(
                    [
                        PerceptionJobStatus.NOT_STARTED.value,
                        PerceptionJobStatus.RUNNING.value,
                    ]
                ),
            )
            .order_by(PerceptionJobModel.id.asc())
        )

        return result.scalars().first()

    async def run_perception_job(self, job_id: int) -> None:
        async with AsyncSessionLocal() as session:
            job = await self._load_job_with_retry(
                job_id=job_id,
                session=session,
            )

            if job is None:
                return

            try:
                context = await load_issue_project_context(
                    project_id=job.project_id,
                    session=session,
                )
                current_hash = self._build_context_hash(
                    perception_kind=job.perception_kind,
                    target_id=job.target_id,
                    context=context,
                )

                # AI results are only valid for the exact snapshot that
                # scheduled the job. New edits make the older job stale.
                if current_hash != job.context_hash:
                    job.status = PerceptionJobStatus.STALE.value
                    await session.commit()
                    return

                raw = await self._run_perceptron(
                    perception_kind=job.perception_kind,
                    target_id=job.target_id,
                    context=context,
                )

                description = self._normalize_perception_description(raw)

                if description is None:
                    job.status = PerceptionJobStatus.DONE_EMPTY.value
                    job.result_slot_payload = None
                    await self._delete_slot_for_job(
                        project_id=job.project_id,
                        job_id=job.id,
                        session=session,
                    )
                    await session.commit()
                    return

                result_kind_code = self._resolve_result_perception_kind(
                    job.perception_kind,
                    raw,
                )
                result_kind = PerceptionKindType[result_kind_code]

                job.status = PerceptionJobStatus.DONE_WITH_SLOT.value
                job.result_slot_payload = {
                    "perception_slot_id": job.id,
                    "perception_kind": result_kind.value,
                    "perception_kind_code": result_kind_code,
                    "perception_description": description,
                }

                # Also populate ProjectModel.perception_slot!
                from backend.database.model import ProjectModel, PerceptionSlotModel
                project_res = await session.execute(
                    select(ProjectModel)
                    .where(ProjectModel.id == job.project_id)
                    .options(selectinload(ProjectModel.perception_slot))
                )
                project = project_res.scalar_one_or_none()
                if project:
                    # Clean up existing slot if any (since it's a 1-to-1 unique relationship)
                    if project.perception_slot:
                        await session.delete(project.perception_slot)
                    # Create new slot
                    slot_model = PerceptionSlotModel(
                        id=job.id, # Use job id to align with job.result_slot_payload's slot id
                        project_id=job.project_id,
                        perception_kind=result_kind.value,
                        description=description
                    )
                    session.add(slot_model)

                await session.commit()

            except Exception as error:
                await session.rollback()
                job = await self._load_job_with_retry(
                    job_id=job_id,
                    session=session,
                )
                if job is None:
                    return

                job.status = PerceptionJobStatus.FAILED.value
                job.error_message = f"{type(error).__name__}: {error}"
                await session.commit()

    @staticmethod
    async def _load_job_with_retry(job_id: int, session):
        from backend.database.model import PerceptionJobModel

        for _attempt in range(10):
            result = await session.execute(
                select(PerceptionJobModel).where(
                    PerceptionJobModel.id == job_id
                )
            )
            job = result.scalar_one_or_none()

            if job is not None:
                return job

            await asyncio.sleep(0.1)

        return None

    async def _run_perceptron(
        self,
        perception_kind: str,
        target_id: str,
        context: IssueProjectContext,
    ) -> dict | None:
        if perception_kind == "ACTOR":
            return await self._actors_perceptron.perceive(
                ActorsPerceptronInput(
                    user_requirements=context.user_requirements,
                    actors=self._build_actor_nodes(context),
                )
            )

        if perception_kind == "FEATURE":
            return await self._features_perceptron.perceive(
                FeaturesPerceptronInput(
                    user_requirements=context.user_requirements,
                    features=self._build_feature_nodes(context),
                )
            )

        if perception_kind == "SCENARIO":
            actor, feature, scenarios = self._load_pair_nodes(
                target_id=target_id,
                context=context,
            )
            return await self._scenarios_perceptron.perceive(
                ScenariosPerceptronInput(
                    user_requirements=context.user_requirements,
                    actor=actor,
                    feature=feature,
                    scenarios=scenarios,
                )
            )

        if perception_kind == "ACCEPTANCE_CRITERION":
            actor, feature, scenarios = self._load_pair_nodes(
                target_id=target_id,
                context=context,
            )
            return await self._acceptance_criteria_perceptron.perceive(
                AcceptanceCriteriaPerceptronInput(
                    user_requirements=context.user_requirements,
                    actor=actor,
                    feature=feature,
                    scenarios=scenarios,
                )
            )

        if perception_kind == "FLOW":
            return await self._flows_perceptron.perceive(
                FlowsPerceptronInput(
                    user_requirements=context.user_requirements,
                    features=self._build_feature_nodes(context),
                    flows=self._build_flow_nodes(context),
                )
            )

        raise ValueError("unsupported_perception_kind")

    def _build_context_hash(
        self,
        perception_kind: str,
        target_id: str,
        context: IssueProjectContext,
    ) -> str:
        if perception_kind == "ACTOR":
            return self._build_actor_context_hash(context)

        if perception_kind == "FEATURE":
            return self._build_feature_context_hash(context)

        if perception_kind in {
            "SCENARIO",
            "ACCEPTANCE_CRITERION",
        }:
            return self._build_pair_context_hash(
                target_id=target_id,
                context=context,
            )

        if perception_kind == "FLOW":
            return self._build_flow_context_hash(context)

        raise ValueError("unsupported_perception_kind")

    @staticmethod
    def _build_actor_nodes(context: IssueProjectContext) -> list[ActorNode]:
        return [
            ActorNode(
                actorId=actor.actor_id,
                actorName=actor.name,
                actorDescription=actor.description,
            )
            for actor in context.actors
        ]

    @staticmethod
    def _build_feature_nodes(context: IssueProjectContext) -> list[FeatureNode]:
        return [
            FeatureNode(
                featureId=feature.feature_id,
                featureName=feature.name,
                featureDescription=feature.description,
                actorIds=feature.actor_ids,
                parentId=feature.parent_id,
                childrenIds=feature.child_ids,
            )
            for feature in context.features
        ]

    @staticmethod
    def _build_flow_nodes(context: IssueProjectContext) -> list[FlowNode]:
        return [
            FlowNode(
                flowId=flow.flow_id,
                flowName=flow.name,
                flowDescription=flow.description,
                featureIds=flow.feature_ids,
                flowSteps=[
                    FlowStepNode(
                        stepId=step.step_id,
                        stepName=step.name,
                        stepDescription=step.description,
                        stepType=(
                            FlowStepType(step.step_type)
                            if step.step_type in FlowStepType._value2member_map_
                            else FlowStepType.SYSTEM_ACTION
                        ),
                        actorIds=step.actor_ids,
                        nextStepIds=step.next_step_ids,
                    )
                    for step in flow.steps
                ],
            )
            for flow in context.flows
        ]

    def _load_pair_nodes(
        self,
        target_id: str,
        context: IssueProjectContext,
    ) -> tuple[ActorNode, FeatureNode, list[ScenarioNode]]:
        feature_id, actor_id = self._parse_pair_target_id(target_id)
        actor_node_map = {
            actor.actorId: actor
            for actor in self._build_actor_nodes(context)
        }
        feature_node_map = {
            feature.featureId: feature
            for feature in self._build_feature_nodes(context)
        }

        actor = actor_node_map.get(actor_id)
        feature = feature_node_map.get(feature_id)

        if actor is None or feature is None:
            raise ValueError("invalid_perception_target")

        scenarios = self._build_scenario_nodes(
            context=context,
            feature_id=feature_id,
            actor_id=actor_id,
        )

        if not scenarios:
            raise ValueError("empty_scenarios")

        return actor, feature, scenarios

    @staticmethod
    def _build_scenario_nodes(
        context: IssueProjectContext,
        feature_id: int,
        actor_id: int,
    ) -> list[ScenarioNode]:
        return [
            ScenarioNode(
                scenarioId=scenario.scenario_id,
                scenarioName=scenario.name,
                scenarioContent=scenario.content,
                featureId=scenario.feature_id,
                actorId=scenario.actor_id,
                acceptanceCriteria=[
                    AcceptanceCriterionNode(
                        criterionId=criterion.criterion_id,
                        criterionContent=criterion.content,
                    )
                    for criterion in scenario.acceptance_criteria
                ],
            )
            for scenario in context.scenarios
            if (
                scenario.feature_id == feature_id
                and scenario.actor_id == actor_id
            )
        ]

    @staticmethod
    def _iter_pairs_with_scenarios(
        context: IssueProjectContext,
    ) -> list[tuple[int, int]]:
        pair_set = {
            (
                scenario.feature_id,
                scenario.actor_id,
            )
            for scenario in context.scenarios
        }
        pairs = []

        for feature in sorted(
            context.leaf_features,
            key=lambda item: item.feature_id,
        ):
            for actor_id in sorted(feature.actor_ids):
                if (feature.feature_id, actor_id) in pair_set:
                    pairs.append((feature.feature_id, actor_id))

        return pairs

    @staticmethod
    def _build_pair_target_id(
        feature_id: int,
        actor_id: int,
    ) -> str:
        return f"{feature_id}:{actor_id}"

    @staticmethod
    def _parse_pair_target_id(target_id: str) -> tuple[int, int]:
        try:
            feature_id_text, actor_id_text = target_id.split(":", 1)
            return int(feature_id_text), int(actor_id_text)
        except (ValueError, TypeError) as error:
            raise ValueError("invalid_perception_target") from error

    def _build_actor_context_hash(self, context: IssueProjectContext) -> str:
        payload = {
            "user_requirements": context.user_requirements,
            "actors": [
                {
                    "actor_id": actor.actor_id,
                    "name": actor.name,
                    "description": actor.description,
                }
                for actor in context.actors
            ],
            "features": self._build_feature_hash_payload(context),
        }

        return self._hash_payload(payload)

    def _build_feature_context_hash(self, context: IssueProjectContext) -> str:
        payload = {
            "user_requirements": context.user_requirements,
            "features": self._build_feature_hash_payload(context),
        }

        return self._hash_payload(payload)

    def _build_pair_context_hash(
        self,
        target_id: str,
        context: IssueProjectContext,
    ) -> str:
        feature_id, actor_id = self._parse_pair_target_id(target_id)
        scenarios = self._build_scenario_nodes(
            context=context,
            feature_id=feature_id,
            actor_id=actor_id,
        )

        payload = {
            "user_requirements": context.user_requirements,
            "target_id": target_id,
            "actors": [
                {
                    "actor_id": actor.actor_id,
                    "name": actor.name,
                    "description": actor.description,
                }
                for actor in context.actors
                if actor.actor_id == actor_id
            ],
            "features": [
                item
                for item in self._build_feature_hash_payload(context)
                if item["feature_id"] == feature_id
            ],
            "scenarios": [
                {
                    "scenario_id": scenario.scenarioId,
                    "name": scenario.scenarioName,
                    "content": scenario.scenarioContent,
                    "acceptance_criteria": [
                        {
                            "criterion_id": criterion.criterionId,
                            "content": criterion.criterionContent,
                        }
                        for criterion in scenario.acceptanceCriteria
                    ],
                }
                for scenario in scenarios
            ],
        }

        return self._hash_payload(payload)

    def _build_flow_context_hash(self, context: IssueProjectContext) -> str:
        payload = {
            "user_requirements": context.user_requirements,
            "features": self._build_feature_hash_payload(context),
            "flows": [
                {
                    "flow_id": flow.flow_id,
                    "name": flow.name,
                    "description": flow.description,
                    "feature_ids": sorted(flow.feature_ids),
                    "steps": [
                        {
                            "step_id": step.step_id,
                            "position": step.position,
                            "name": step.name,
                            "description": step.description,
                            "step_type": step.step_type,
                            "actor_ids": sorted(step.actor_ids),
                            "next_step_ids": sorted(step.next_step_ids),
                        }
                        for step in flow.steps
                    ],
                }
                for flow in context.flows
            ],
        }

        return self._hash_payload(payload)

    @staticmethod
    def _build_feature_hash_payload(context: IssueProjectContext) -> list[dict]:
        return [
            {
                "feature_id": feature.feature_id,
                "name": feature.name,
                "description": feature.description,
                "actor_ids": sorted(feature.actor_ids),
                "parent_id": feature.parent_id,
                "child_ids": sorted(feature.child_ids),
            }
            for feature in context.features
        ]

    @staticmethod
    def _hash_payload(payload: dict) -> str:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_perception_description(raw: dict | None) -> str | None:
        if raw is None:
            raise ValueError("empty_perception_response")
        if not isinstance(raw, dict):
            raise ValueError("invalid_perception_response")

        description = str(raw.get("perception_description", "")).strip()
        raw_kind = str(raw.get("perception_kind", "")).strip()

        if not description:
            return None

        normalized = PerceptionJobService._normalize_no_slot_marker(description)
        normalized_kind = PerceptionJobService._normalize_no_slot_marker(raw_kind)

        no_slot_markers = {
            "不需要",
            "无需",
            "无需要",
            "无需补充",
            "不需补充",
            "不需要补充",
            "没有需要补充",
            "无需新增",
            "不需要新增",
            "no need",
            "none",
            "not needed",
            "not required",
        }

        if (
            normalized in no_slot_markers
            or normalized_kind in no_slot_markers
            or any(normalized.startswith(marker) for marker in no_slot_markers)
        ):
            return None

        return description

    @staticmethod
    def _normalize_no_slot_marker(value: str) -> str:
        return (
            value
            .replace("\ufeff", "")
            .replace("\u200b", "")
            .replace("\u200c", "")
            .replace("\u200d", "")
            .strip()
            .strip("\"'“”‘’`")
            .replace("。", "")
            .replace(".", "")
            .replace("！", "")
            .replace("!", "")
            .replace("，", "")
            .replace(",", "")
            .strip()
            .lower()
        )

    @staticmethod
    async def _delete_slot_for_job(
        project_id: int,
        job_id: int,
        session,
    ) -> None:
        from backend.database.model import ChoiceGroupModel, PerceptionSlotModel

        slot_result = await session.execute(
            select(PerceptionSlotModel).where(
                PerceptionSlotModel.project_id == project_id,
                PerceptionSlotModel.id == job_id,
            )
        )
        slot = slot_result.scalar_one_or_none()
        if slot is None:
            return

        # DONE_EMPTY means this exact perception job no longer has actionable
        # content. Clear any open choice group still pointing at its old slot.
        group_result = await session.execute(
            select(ChoiceGroupModel).where(
                ChoiceGroupModel.project_id == project_id,
                ChoiceGroupModel.slot_id == slot.id,
            )
        )
        for group in group_result.scalars().all():
            if group.status == "open":
                group.status = "resolved"
            group.slot_id = None

        await session.delete(slot)

    @staticmethod
    def _resolve_result_perception_kind(
        perception_kind: str,
        raw: dict | None,
    ) -> str:
        if perception_kind in {
            "ACTOR",
            "SCENARIO",
            "ACCEPTANCE_CRITERION",
            "FLOW",
        }:
            return perception_kind

        raw_kind = str((raw or {}).get("perception_kind", "")).lower()

        if "leaf" in raw_kind or "叶" in raw_kind:
            return "FEATURE_LEAF"

        return "FEATURE_BRANCH"

    @staticmethod
    async def _mark_stale_jobs(
        project_id: int,
        stage: str,
        perception_kind: str,
        target_type: str,
        target_id: str,
        context_hash: str,
        session,
    ) -> None:
        from backend.database.model import PerceptionJobModel

        result = await session.execute(
            select(PerceptionJobModel).where(
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage == stage,
                PerceptionJobModel.perception_kind == perception_kind,
                PerceptionJobModel.target_type == target_type,
                PerceptionJobModel.target_id == target_id,
                PerceptionJobModel.context_hash != context_hash,
                PerceptionJobModel.status.in_(
                    [
                        PerceptionJobStatus.DONE_EMPTY.value,
                        PerceptionJobStatus.DONE_WITH_SLOT.value,
                        PerceptionJobStatus.FAILED.value,
                    ]
                ),
            )
        )

        for job in result.scalars().all():
            job.status = PerceptionJobStatus.STALE.value

    @staticmethod
    def _build_running_suggestion(job) -> NextSuggestion:
        title_map = {
            "ACTOR": "正在分析参与者",
            "FEATURE": "正在分析功能",
            "SCENARIO": "正在分析场景",
            "ACCEPTANCE_CRITERION": "正在分析成功标准",
            "FLOW": "正在分析流程",
        }

        return NextSuggestion(
            sourceType="perception_slot",
            code=f"{job.perception_kind}_PERCEPTION_RUNNING",
            title=title_map.get(job.perception_kind, "正在分析"),
            description="系统正在后台判断当前阶段是否还有需要补充的内容。",
            status="running",
            target={
                "type": job.target_type,
                "id": job.target_id,
            },
            action={
                "kind": "wait",
            },
        )

    @staticmethod
    def _build_failed_suggestion(job) -> NextSuggestion:
        return NextSuggestion(
            sourceType="perception_slot",
            code=f"{job.perception_kind}_PERCEPTION_FAILED",
            title="感知分析失败",
            description=job.error_message or "感知器执行失败，可以稍后重试。",
            status="failed",
            target={
                "type": job.target_type,
                "id": job.target_id,
            },
            action={
                "kind": "retry",
                "payload": {
                    "perception_job_id": job.id,
                },
            },
        )

    @staticmethod
    def _build_slot_suggestion(
        project_id: int,
        job,
        public_project_id: str | None = None,
    ) -> NextSuggestion:
        slot_payload = job.result_slot_payload or {}
        perception_kind_code = slot_payload.get(
            "perception_kind_code",
            job.perception_kind,
        )
        pub_id = public_project_id or str(project_id)

        return NextSuggestion(
            sourceType="perception_slot",
            code=f"{perception_kind_code}_SLOT",
            title="补充建议",
            description=slot_payload.get("perception_description", ""),
            status="ready",
            target={
                "type": job.target_type,
                "id": job.target_id,
            },
            action={
                "kind": "open_panel",
                "route": f"/projects/{pub_id}/{job.stage}",
                "panel": "perception_slot",
                "payload": {
                    "perception_job_id": job.id,
                    "perception_kind": perception_kind_code,
                },
            },
        )
