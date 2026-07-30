from backend.api.modules.diagnosis_quality.public import FindingService

from .checks import (
    how_stage_checks,
    scope_stage_checks,
    stage_analysis_status,
    stage_next_action,
    stage_status,
    what_stage_checks,
)
from .loader import StageProgressData, load_stage_progress_data


STAGES_ORDER = ("what", "how", "scope")


def _is_stage_unlocked(stage: str, unlocked_stages: set[str]) -> bool:
    if stage == "what":
        return True
    if stage == "how":
        return "what" in unlocked_stages
    if stage == "scope":
        return "how" in unlocked_stages
    return False


def _stage_failed_checks(stage: str, data: StageProgressData) -> list[dict]:
    if stage == "what":
        return what_stage_checks(
            len(data.what.actor_ids),
            data.what.leaf_features,
            data.what.feature_actor_map,
            data.what.feature_scenario_map,
            data.what.scenario_ids,
            data.what.acceptance_scenario_ids,
            data.what.scenarios_map,
        )
    if stage == "how":
        return how_stage_checks(
            data.how.flow_ids,
            data.how.flows_with_steps,
            data.how.flows_map,
            data.what.actor_ids,
            data.how.steps,
            data.how.step_actor_map,
            data.how.step_input_object_map,
            data.how.step_output_object_map,
            data.how.business_object_ids,
            data.how.business_objects,
        )
    return scope_stage_checks(
        data.what.leaf_features,
        data.scoped_feature_ids,
        data.project.kano_status,
    )


def _stage_not_started(stage: str, data: StageProgressData) -> bool:
    return {
        "what": not data.what.actor_ids,
        "how": (
            not data.how.flow_ids
            and not data.how.business_objects
        ),
        "scope": not data.scoped_feature_ids,
    }[stage]


def _build_stage(
    stage: str,
    public_project_id: str,
    data: StageProgressData,
    gate_findings: list,
) -> dict:
    unlocked = _is_stage_unlocked(stage, data.unlocked_stages)
    failed_checks = _stage_failed_checks(stage, data)
    content_complete = not failed_checks
    latest_job = data.latest_jobs.get(stage)
    analysis_running = (
        latest_job is not None
        and latest_job.status in ("running", "pending")
    )
    status_code = stage_status(
        unlocked,
        stage in data.unlocked_stages,
        bool(gate_findings),
        content_complete,
        analysis_running,
        _stage_not_started(stage, data),
    )
    return {
        "stage": stage,
        "status_code": status_code,
        "status_label": f"stageProgress.status.{status_code}",
        "content_complete": content_complete,
        "unlocked": unlocked,
        "transition_available": status_code == "ready_to_advance",
        "next_action": stage_next_action(
            stage,
            status_code,
            public_project_id,
        ),
        "failed_checks": failed_checks,
        "blocking_findings": gate_findings,
        "analysis_status": stage_analysis_status(
            latest_job,
            analysis_running,
        ),
    }


async def _load_gate_findings(
    project_id: int,
    session,
) -> dict[str, list]:
    finding_service = FindingService()
    return {
        "what": await finding_service.list_findings(
            project_id=project_id,
            stage="what",
            view="gate",
            action="enter_how",
            session=session,
        ),
        "how": await finding_service.list_findings(
            project_id=project_id,
            stage="how",
            view="gate",
            action="enter_scope",
            session=session,
        ),
        "scope": await finding_service.list_findings(
            project_id=project_id,
            stage="scope",
            view="gate",
            action="generate_preview",
            session=session,
        ),
    }


async def get_stage_progress(
    project_id: int,
    public_project_id: str,
    session,
) -> dict:
    data = await load_stage_progress_data(project_id, session)
    findings_by_stage = await _load_gate_findings(project_id, session)
    return {
        "project_id": public_project_id,
        "stages": [
            _build_stage(
                stage,
                public_project_id,
                data,
                findings_by_stage[stage],
            )
            for stage in STAGES_ORDER
        ],
    }
