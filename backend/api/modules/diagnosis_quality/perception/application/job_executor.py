import asyncio
import hashlib
import json
import logging
import time
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)
from backend.core.logging import get_logger, log_event, sanitize_message
from backend.core.logging.events import (
    PERCEPTION_JOB_COMPLETED,
    PERCEPTION_JOB_FAILED,
    PERCEPTION_JOB_STARTED,
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

logger = get_logger(__name__)


class PerceptionJobExecutor:
    async def _schedule_perception_job(
        self,
        background_tasks: BackgroundTasks,
        session,
        job_id: int,
    ) -> None:
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

            start_time = time.perf_counter()
            log_event(
                logger,
                logging.INFO,
                "domain",
                PERCEPTION_JOB_STARTED,
                "Perception job started",
                project_id=job.project_id,
                stage=job.stage,
                target_type=job.target_type,
                target_id=job.target_id,
                perception_kind=job.perception_kind,
            )

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

                if current_hash != job.context_hash:
                    job.status = PerceptionJobStatus.STALE.value
                    await session.commit()
                    log_event(
                        logger,
                        logging.INFO,
                        "domain",
                        PERCEPTION_JOB_COMPLETED,
                        "Perception job completed",
                        project_id=job.project_id,
                        stage=job.stage,
                        target_type=job.target_type,
                        target_id=job.target_id,
                        perception_kind=job.perception_kind,
                        status=job.status,
                        duration_ms=int((time.perf_counter() - start_time) * 1000),
                    )
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
                    log_event(
                        logger,
                        logging.INFO,
                        "domain",
                        PERCEPTION_JOB_COMPLETED,
                        "Perception job completed",
                        project_id=job.project_id,
                        stage=job.stage,
                        target_type=job.target_type,
                        target_id=job.target_id,
                        perception_kind=job.perception_kind,
                        status=job.status,
                        duration_ms=int((time.perf_counter() - start_time) * 1000),
                    )
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

                from backend.database.model import ProjectModel, PerceptionSlotModel
                project_res = await session.execute(
                    select(ProjectModel)
                    .where(ProjectModel.id == job.project_id)
                    .options(selectinload(ProjectModel.perception_slot))
                )
                project = project_res.scalar_one_or_none()
                if project:
                    if project.perception_slot:
                        await session.delete(project.perception_slot)
                    slot_model = PerceptionSlotModel(
                        id=job.id,
                        project_id=job.project_id,
                        perception_kind=result_kind.value,
                        description=description
                    )
                    session.add(slot_model)

                await session.commit()
                log_event(
                    logger,
                    logging.INFO,
                    "domain",
                    PERCEPTION_JOB_COMPLETED,
                    "Perception job completed",
                    project_id=job.project_id,
                    stage=job.stage,
                    target_type=job.target_type,
                    target_id=job.target_id,
                    perception_kind=job.perception_kind,
                    status=job.status,
                    duration_ms=int((time.perf_counter() - start_time) * 1000),
                )

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
                log_event(
                    logger,
                    logging.ERROR,
                    "domain",
                    PERCEPTION_JOB_FAILED,
                    "Perception job failed",
                    project_id=job.project_id,
                    stage=job.stage,
                    target_type=job.target_type,
                    target_id=job.target_id,
                    perception_kind=job.perception_kind,
                    status=job.status,
                    error_type=type(error).__name__,
                    error_message=sanitize_message(str(error)),
                    duration_ms=int((time.perf_counter() - start_time) * 1000),
                )

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

    @staticmethod
    async def _run_perceptron(
        perception_kind: str,
        target_id: str,
        context: IssueProjectContext,
    ) -> dict | None:
        if perception_kind == "ACTOR":
            perceptron = ActorsPerceptron()
            return await perceptron.perceive(
                ActorsPerceptronInput(
                    user_requirements=context.user_requirements,
                    actors=PerceptionJobExecutor._build_actor_nodes(context),
                )
            )
        if perception_kind == "FEATURE":
            perceptron = FeaturesPerceptron()
            return await perceptron.perceive(
                FeaturesPerceptronInput(
                    user_requirements=context.user_requirements,
                    features=PerceptionJobExecutor._build_feature_nodes(context),
                )
            )
        if perception_kind == "SCENARIO":
            actor, feature, scenarios = PerceptionJobExecutor._load_pair_nodes(
                target_id=target_id,
                context=context,
            )
            perceptron = ScenariosPerceptron()
            return await perceptron.perceive(
                ScenariosPerceptronInput(
                    user_requirements=context.user_requirements,
                    actor=actor,
                    feature=feature,
                    scenarios=scenarios,
                )
            )
        if perception_kind == "ACCEPTANCE_CRITERION":
            actor, feature, scenarios = PerceptionJobExecutor._load_pair_nodes(
                target_id=target_id,
                context=context,
            )
            perceptron = AcceptanceCriteriaPerceptron()
            return await perceptron.perceive(
                AcceptanceCriteriaPerceptronInput(
                    user_requirements=context.user_requirements,
                    actor=actor,
                    feature=feature,
                    scenarios=scenarios,
                )
            )
        if perception_kind == "FLOW":
            perceptron = FlowsPerceptron()
            return await perceptron.perceive(
                FlowsPerceptronInput(
                    user_requirements=context.user_requirements,
                    features=PerceptionJobExecutor._build_feature_nodes(context),
                    flows=PerceptionJobExecutor._build_flow_nodes(context),
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

    @staticmethod
    def _load_pair_nodes(
        target_id: str,
        context: IssueProjectContext,
    ) -> tuple[ActorNode, FeatureNode, list[ScenarioNode]]:
        feature_id, actor_id = PerceptionJobExecutor._parse_pair_target_id(target_id)
        actor_node_map = {
            actor.actorId: actor
            for actor in PerceptionJobExecutor._build_actor_nodes(context)
        }
        feature_node_map = {
            feature.featureId: feature
            for feature in PerceptionJobExecutor._build_feature_nodes(context)
        }

        actor = actor_node_map.get(actor_id)
        feature = feature_node_map.get(feature_id)

        if actor is None or feature is None:
            raise ValueError("invalid_perception_target")

        scenarios = PerceptionJobExecutor._build_scenario_nodes(
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

        normalized = PerceptionJobExecutor._normalize_no_slot_marker(description)
        normalized_kind = PerceptionJobExecutor._normalize_no_slot_marker(raw_kind)

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
    def _build_running_suggestion(job) -> NextSuggestion:
        title_map = {
            "ACTOR": "正在分析参与者",
            "FEATURE": "正在分析功能",
            "SCENARIO": "正在分析场景",
            "ACCEPTANCE_CRITERION": "正在分析成功标准",
            "FLOW": "正在分析流程",
        }

        started_time = str(job.created_at) if getattr(job, "created_at", None) else ""
        stage_display = "What" if job.stage == "what" else ("How" if job.stage == "how" else "Scope")

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
                "status": "running",
                "job_id": job.id,
                "jobId": job.id,
                "stage": job.stage,
                "started_at": started_time,
                "startedAt": started_time,
                "message": f"AI 正在分析 {stage_display} 阶段...",
            },
        )

    @staticmethod
    def _build_failed_suggestion(job) -> NextSuggestion:
        err_msg = job.error_message or "感知器执行失败，可以稍后重试。"
        return NextSuggestion(
            sourceType="perception_slot",
            code=f"{job.perception_kind}_PERCEPTION_FAILED",
            title="感知分析失败",
            description=err_msg,
            status="failed",
            target={
                "type": job.target_type,
                "id": job.target_id,
            },
            action={
                "kind": "retry",
                "status": "failed",
                "error_message": err_msg,
                "errorMessage": err_msg,
                "retry_action": "rediagnose",
                "retryAction": "rediagnose",
                "payload": {
                    "perception_job_id": job.id,
                    "perceptionJobId": job.id,
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
