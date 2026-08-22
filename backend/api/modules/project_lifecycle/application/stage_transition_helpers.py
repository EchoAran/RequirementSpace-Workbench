from dataclasses import dataclass

from backend.database.model import AuditLogModel

STAGES_ORDER = ("what", "how", "scope")


@dataclass(frozen=True)
class StageTransitionConfig:
    gate_action: str
    gate_stage: str
    unlock_stage: str
    target_stage: str
    target_route: str


def get_stage_transition_config(
    action: str,
    public_project_id: str,
) -> StageTransitionConfig:
    configs = {
        "enter_how": StageTransitionConfig(
            gate_action="enter_how",
            gate_stage="what",
            unlock_stage="what",
            target_stage="how",
            target_route=f"/projects/{public_project_id}/flow",
        ),
        "enter_scope": StageTransitionConfig(
            gate_action="enter_scope",
            gate_stage="how",
            unlock_stage="how",
            target_stage="scope",
            target_route=f"/projects/{public_project_id}/scope",
        ),
        "enter_preview": StageTransitionConfig(
            gate_action="generate_preview",
            gate_stage="scope",
            unlock_stage="scope",
            target_stage="preview",
            target_route=f"/projects/{public_project_id}/preview",
        ),
    }
    config = configs.get(action)
    if config is None:
        raise ValueError("invalid_stage_transition")
    return config


def parse_unlocked_stages(
    unlocked_stages: str,
) -> tuple[set[str], list[str]]:
    unlocked = (
        {
            stage.strip().lower()
            for stage in unlocked_stages.split(",")
            if stage.strip()
        }
        if unlocked_stages
        else set()
    )
    ordered = [
        stage
        for stage in STAGES_ORDER
        if stage in unlocked
    ]
    return unlocked, ordered


def build_blocked_transition_result(
    action: str,
    unlocked_stages: list[str],
    findings: list,
) -> dict:
    return {
        "status": "blocked",
        "action": action,
        "unlocked_stage": None,
        "target_route": None,
        "unlocked_stages": unlocked_stages,
        "blocking_findings": findings,
    }


def get_source_stage_state(
    stage_progress: dict,
    gate_stage: str,
) -> tuple[str | None, bool]:
    source_progress = next(
        (
            stage
            for stage in stage_progress["stages"]
            if stage["stage"] == gate_stage
        ),
        None,
    )
    if source_progress is None:
        return None, False
    return (
        source_progress.get("status_code"),
        bool(source_progress.get("content_complete")),
    )


def build_stage_transition_audit(
    *,
    project_id: int,
    public_project_id: str,
    action: str,
    config: StageTransitionConfig,
    force: bool,
    findings: list,
    operator_id: int | None,
) -> AuditLogModel:
    is_forced_transition = bool(findings and force)
    audit_action = (
        "stage_transition_forced"
        if is_forced_transition
        else "stage_transition_unlocked"
    )
    audit_summary = (
        f"强制推进阶段: {action} "
        f"(跳过了 {len(findings)} 个阻塞项)"
        if is_forced_transition
        else (
            f"解锁阶段: {action} "
            f"(前置 {config.unlock_stage} 已满足)"
        )
    )
    return AuditLogModel(
        project_id=project_id,
        action_type=audit_action,
        summary=audit_summary,
        target_type="project",
        target_id=public_project_id,
        actor_user_id=operator_id,
        payload={
            "action": action,
            "unlock_stage": config.unlock_stage,
            "force": force,
            "is_forced_transition": is_forced_transition,
            "from_stage": config.gate_stage,
            "target_stage": config.target_stage,
            "blocking_finding_ids": [
                finding.findingId
                for finding in findings
            ] if findings else [],
            "operator_id": operator_id,
            "bypass_findings_count": (
                len(findings)
                if findings
                else 0
            ),
        },
    )
