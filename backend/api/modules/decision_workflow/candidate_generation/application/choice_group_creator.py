import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from backend.api.modules.decision_workflow.ports.ports import (
    CandidateContext,
    CandidateRunResult,
    GenerationCandidate,
)
from backend.core.ai_operation_monitor import log_ai_operation_result
from backend.core.llm_locale_validation import LLMContentLocaleMismatchError
from backend.core.logging import log_event
from backend.core.logging.events import (
    CHOICE_GROUP_CREATE_REQUESTED,
    CHOICE_GROUP_CREATED,
    CHOICE_GROUP_GENERATION_FAILED,
)
from backend.database.model import (
    AuditLogModel,
    ChoiceGroupModel,
    ChoiceModel,
)


@dataclass
class _GenerationPlan:
    adapter: Any
    resolved_strategies: list[Any] | None
    run_count: int
    candidate_concurrency: int
    candidate_timeout: int
    batch_feature_count: int


def _scenario_batch_feature_count(
    generation_type: str,
    target: dict | None,
) -> int:
    if (
        generation_type == "scenario"
        and (target or {}).get("generation_mode") == "batch"
    ):
        return len((target or {}).get("feature_ids") or [])
    return 0


async def _resolve_generation_plan(
    project_id: int,
    generation_type: str,
    target: dict | None,
    candidate_count: int | None,
    session,
    config,
    get_adapter,
    large_batch_threshold: int,
    timeout_feature_batch_size: int,
) -> _GenerationPlan:
    adapter = get_adapter(generation_type)
    resolved_strategies = None
    if project_id and session:
        from backend.api.modules.project_configuration.public import (
            resolve_generation_strategies,
        )

        resolved_strategies = await resolve_generation_strategies(
            project_id=project_id,
            generation_type=generation_type,
            requested_count=candidate_count,
            session=session,
        )

    batch_feature_count = _scenario_batch_feature_count(
        generation_type,
        target,
    )
    if (
        batch_feature_count > large_batch_threshold
        and resolved_strategies
    ):
        resolved_strategies = resolved_strategies[:1]
    run_count = (
        len(resolved_strategies)
        if resolved_strategies
        else config.candidate_count
    )
    if batch_feature_count > large_batch_threshold:
        run_count = 1
    candidate_timeout = config.timeout_seconds * max(
        1,
        (
            batch_feature_count + timeout_feature_batch_size - 1
        )
        // timeout_feature_batch_size,
    )
    scenario_mode = (target or {}).get("generation_mode", "pair")
    candidate_concurrency = config.max_concurrency
    if generation_type == "scenario":
        candidate_concurrency = (
            min(2, run_count)
            if scenario_mode in {"single", "pair"}
            else 1
        )
    return _GenerationPlan(
        adapter=adapter,
        resolved_strategies=resolved_strategies,
        run_count=run_count,
        candidate_concurrency=candidate_concurrency,
        candidate_timeout=candidate_timeout,
        batch_feature_count=batch_feature_count,
    )


def _deduplicate_candidates(
    candidates: list[GenerationCandidate],
    adapter,
) -> list[GenerationCandidate]:
    deduplicated = []
    for candidate in candidates:
        if not adapter.is_duplicate(candidate, deduplicated):
            deduplicated.append(candidate)
    return deduplicated


def _build_status_detail(
    result: CandidateRunResult,
    candidates: list[GenerationCandidate],
) -> dict:
    status_detail = {}
    if result.errors:
        status_detail["errors"] = [
            {
                "index": error.index,
                "strategy": error.strategy,
                "error_type": error.error_type,
                "message": error.message,
                "detail": error.detail,
            }
            for error in result.errors
        ]
        status_detail["error_summary"] = (
            f"{result.total_count} 个候选已生成，其中 "
            f"{result.success_count} 个成功，{result.failure_count} 个失败"
        )
    if len(candidates) > 1:
        status_detail["comparison_summary"] = " | ".join(
            f"{candidate.title}: {candidate.comparison_summary}"
            for candidate in candidates
        )
    status_detail["duration_ms"] = result.duration_ms
    return status_detail


async def _create_group(
    project_id: int,
    generation_type: str,
    target: dict | None,
    context_hash: str | None,
    result: CandidateRunResult,
    candidates: list[GenerationCandidate],
    status_detail: dict,
    is_partial_failure: bool,
    issue_fields: dict,
    session,
    workspace_id: int,
) -> ChoiceGroupModel:
    group = ChoiceGroupModel(
        project_id=project_id,
        workspace_id=workspace_id,
        status="failed" if is_partial_failure else "open",
        selection_mode="single",
        generation_type=generation_type,
        target=target,
        context_hash=context_hash,
        candidate_count=result.total_count,
        success_count=len(candidates),
        failure_count=result.failure_count,
        status_detail=status_detail if status_detail else None,
        **issue_fields,
    )
    if session:
        session.add(group)
        await session.flush()
    return group


def _create_candidate_choices(
    group: ChoiceGroupModel,
    candidates: list[GenerationCandidate],
    generation_type: str,
    session,
) -> list[ChoiceModel]:
    created_choices = []
    for candidate in candidates:
        choice = ChoiceModel(
            choice_group_id=group.id,
            workspace_id=group.workspace_id,
            title=candidate.title,
            rationale=candidate.rationale,
            status="candidate",
            patch=candidate.patch or {},
            payload=candidate.payload,
            draft_type=candidate.draft_type or generation_type,
            apply_mode=candidate.apply_mode,
            preview=candidate.preview,
            score=candidate.score if candidate.score else None,
            strategy_id=candidate.strategy_id,
            strategy_label=candidate.strategy_label,
        )
        if session:
            session.add(choice)
            created_choices.append(choice)
    return created_choices


def _strategy_label(error, resolved_strategies) -> str:
    strategy_label = None
    if resolved_strategies:
        strategy = next(
            (
                item
                for item in resolved_strategies
                if item.id == error.strategy
            ),
            None,
        )
        if strategy:
            strategy_label = strategy.label
    if strategy_label:
        return strategy_label
    from backend.api.modules.project_configuration.application.generation_strategy_config_service import (
        DEFAULT_STRATEGIES,
    )

    default_strategy = next(
        (
            item
            for item in DEFAULT_STRATEGIES
            if item["id"] == error.strategy
        ),
        None,
    )
    return (
        default_strategy["label"]
        if default_strategy
        else error.strategy
    )


def _create_failed_choices(
    group: ChoiceGroupModel,
    result: CandidateRunResult,
    generation_type: str,
    resolved_strategies,
    session,
) -> list[ChoiceModel]:
    created_choices = []
    for error in result.errors:
        strategy_label = _strategy_label(error, resolved_strategies)
        choice = ChoiceModel(
            choice_group_id=group.id,
            title=f"方案 {error.index + 1} ({strategy_label})",
            rationale="",
            status="failed",
            patch={},
            draft_type=generation_type,
            apply_mode="draft_payload",
            error={
                "error_type": error.error_type,
                "message": error.message,
                "detail": error.detail,
            },
            strategy_id=error.strategy,
            strategy_label=strategy_label,
        )
        if session:
            session.add(choice)
            created_choices.append(choice)
    return created_choices


async def _record_creation_audit(
    project_id: int,
    generation_type: str,
    group: ChoiceGroupModel,
    result: CandidateRunResult,
    session,
) -> None:
    if not session:
        return
    session.add(
        AuditLogModel(
            project_id=project_id,
            action_type="generation_choice_group_created",
            summary=(
                f"创建 {generation_type} 候选组 "
                f"({result.success_count}/{result.total_count})"
            ),
            target_type="choice_group",
            target_id=str(group.id),
            payload={
                "generation_type": generation_type,
                "candidate_count": result.total_count,
                "success_count": result.success_count,
                "failure_count": result.failure_count,
                "duration_ms": result.duration_ms,
                "status": group.status,
            },
        )
    )
    await session.flush()


def _log_creation_result(
    logger,
    project_id: int,
    generation_type: str,
    group: ChoiceGroupModel,
    result: CandidateRunResult,
    issue_code: str | None,
    source_type: str | None,
) -> None:
    log_ai_operation_result(
        "generation_choice_group",
        project_id=project_id,
        generation_type=generation_type,
        issue_code=issue_code,
        duration_ms=result.duration_ms,
        success_count=result.success_count,
        failure_count=result.failure_count,
        status=group.status,
    )
    log_event(
        logger,
        logging.INFO,
        "domain",
        CHOICE_GROUP_CREATED,
        "Choice group created",
        project_id=project_id,
        choice_group_id=group.id,
        generation_type=generation_type,
        candidate_count=result.total_count,
        success_count=result.success_count,
        failure_count=result.failure_count,
        duration_ms=result.duration_ms,
        issue_code=issue_code,
        source_type=source_type,
        status=group.status,
    )


def _log_creation_requested(
    logger,
    project_id: int,
    generation_type: str,
    candidate_count: int,
    issue_fields: dict,
) -> None:
    log_event(
        logger,
        logging.INFO,
        "domain",
        CHOICE_GROUP_CREATE_REQUESTED,
        "Choice group create requested",
        project_id=project_id,
        generation_type=generation_type,
        candidate_count=candidate_count,
        issue_code=issue_fields["issue_code"],
        source_type=issue_fields["source_type"],
    )


async def _run_candidates(
    plan: _GenerationPlan,
    project_id: int,
    target: dict | None,
    user_feedback: str | None,
    session,
    progress_callback,
    run_candidate_generation,
    workspace_id: int,
) -> CandidateRunResult:
    return await run_candidate_generation(
        count=plan.run_count,
        max_concurrency=plan.candidate_concurrency,
        timeout_seconds=plan.candidate_timeout,
        generate_one=plan.adapter.generate_candidate,
        progress_callback=progress_callback,
        base_context=CandidateContext(
            index=0,
            strategy="balanced",
            user_feedback=user_feedback,
            target=target,
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        ),
        resolved_strategies=plan.resolved_strategies,
    )


def _evaluate_candidates(
    logger,
    project_id: int,
    generation_type: str,
    result: CandidateRunResult,
    plan: _GenerationPlan,
    config,
    issue_fields: dict,
    large_batch_threshold: int,
) -> tuple[list[GenerationCandidate], bool, dict]:
    if any(
        error.message == LLMContentLocaleMismatchError.code
        for error in result.errors
    ):
        raise LLMContentLocaleMismatchError()
    candidates = _deduplicate_candidates(
        result.candidates,
        plan.adapter,
    )
    required_successes = (
        1
        if plan.batch_feature_count > large_batch_threshold
        else config.partial_success_min
    )
    is_partial_failure = len(candidates) < required_successes
    if is_partial_failure:
        log_event(
            logger,
            logging.WARNING,
            "domain",
            CHOICE_GROUP_GENERATION_FAILED,
            "Choice group generation failed",
            project_id=project_id,
            generation_type=generation_type,
            candidate_count=result.total_count,
            success_count=len(candidates),
            failure_count=result.failure_count,
            duration_ms=result.duration_ms,
            issue_code=issue_fields["issue_code"],
            source_type=issue_fields["source_type"],
            status="failed",
        )
    return (
        candidates,
        is_partial_failure,
        _build_status_detail(result, candidates),
    )


async def _persist_creation(
    project_id: int,
    generation_type: str,
    target: dict | None,
    result: CandidateRunResult,
    candidates: list[GenerationCandidate],
    status_detail: dict,
    is_partial_failure: bool,
    issue_fields: dict,
    plan: _GenerationPlan,
    session,
    workspace_id: int,
) -> tuple[ChoiceGroupModel, list[ChoiceModel]]:
    context_hash = issue_fields.pop("context_hash")
    if context_hash is None and session:
        context_hash = plan.adapter.compute_context_hash(target, session)
    group = await _create_group(
        project_id,
        generation_type,
        target,
        context_hash,
        result,
        candidates,
        status_detail,
        is_partial_failure,
        issue_fields,
        session,
        workspace_id=workspace_id,
    )
    created_choices = _create_candidate_choices(
        group,
        candidates,
        generation_type,
        session,
    )
    created_choices.extend(
        _create_failed_choices(
            group,
            result,
            generation_type,
            plan.resolved_strategies,
            session,
        )
    )
    if session:
        await session.flush()
    return group, created_choices


async def _finalize_creation(
    logger,
    project_id: int,
    generation_type: str,
    group: ChoiceGroupModel,
    choices: list[ChoiceModel],
    result: CandidateRunResult,
    issue_fields: dict,
    session,
    build_choice_group_response,
) -> dict:
    _log_creation_result(
        logger,
        project_id,
        generation_type,
        group,
        result,
        issue_fields["issue_code"],
        issue_fields["source_type"],
    )
    await _record_creation_audit(
        project_id,
        generation_type,
        group,
        result,
        session,
    )
    project_public_id = None
    if session:
        from backend.database.model import ProjectModel
        project_res = await session.execute(
            select(ProjectModel.public_id).where(ProjectModel.id == project_id)
        )
        project_public_id = project_res.scalar_one_or_none()
    return build_choice_group_response(
        group,
        choices,
        project_public_id=project_public_id,
    )


async def create_choice_group(
    *, settings, project_id: int, generation_type: str,
    target: dict | None, candidate_count: int | None,
    user_feedback: str | None, session, progress_callback,
    issue_fields: dict, get_adapter, run_candidate_generation,
    build_choice_group_response, logger, large_batch_threshold: int,
    timeout_feature_batch_size: int,
    workspace_id: int,
) -> dict:
    config = settings.with_overrides(candidate_count)
    _log_creation_requested(
        logger, project_id, generation_type,
        config.candidate_count, issue_fields,
    )
    if not config.is_generation_type_enabled(generation_type):
        raise ValueError(
            f"choice_group_disabled_for_type:{generation_type} "
            "? set GENERATION_CHOICE_GROUP_ENABLED=true or remove "
            f"'{generation_type}' from GENERATION_CHOICE_GROUP_DISABLED_TYPES"
        )
    plan = await _resolve_generation_plan(
        project_id, generation_type, target, candidate_count, session,
        config, get_adapter, large_batch_threshold,
        timeout_feature_batch_size,
    )
    result = await _run_candidates(
        plan, project_id, target, user_feedback, session,
        progress_callback, run_candidate_generation,
        workspace_id=workspace_id,
    )
    candidates, is_partial_failure, status_detail = _evaluate_candidates(
        logger, project_id, generation_type, result, plan, config,
        issue_fields, large_batch_threshold,
    )
    group, choices = await _persist_creation(
        project_id, generation_type, target, result, candidates,
        status_detail, is_partial_failure, issue_fields, plan, session,
        workspace_id=workspace_id,
    )
    return await _finalize_creation(
        logger, project_id, generation_type, group, choices, result,
        issue_fields, session, build_choice_group_response,
    )
