from sqlalchemy import select

from backend.database.model import ProjectModel
from backend.schemas import (
    BlockingScope,
    Finding,
    FindingType,
    IssueSeverity,
    IssueStage,
    IssueTarget,
)


def normalize_finding_filters(
    stage: str | None,
    view: str,
) -> tuple[str, str]:
    stage_clean = (stage or "all").strip().lower()
    if stage_clean not in {
        "what",
        "how",
        "scope",
        "preview",
        "all",
    }:
        raise ValueError("invalid_stage")
    view_clean = (view or "issues").strip().lower()
    if view_clean not in {
        "issues",
        "next_action",
        "gate",
        "health",
    }:
        raise ValueError("invalid_view")
    return stage_clean, view_clean


def policy_stages(stage: str, policies: dict) -> list[str]:
    if stage == "all":
        return ["what", "how", "scope"]
    return [stage] if stage in policies else []


def filter_gates_by_action(
    gate_findings: list[Finding],
    action: str | None,
) -> list[Finding]:
    if not action:
        return gate_findings
    action_clean = action.strip().lower()
    filtered_gates = []
    for finding in gate_findings:
        is_blocking = False
        if action_clean == "enter_how":
            is_blocking = (
                finding.stage == IssueStage.WHAT
                and finding.blockingScope
                == BlockingScope.STAGE_TRANSITION
            )
        elif action_clean == "enter_scope":
            is_blocking = (
                finding.stage == IssueStage.HOW
                and finding.blockingScope
                == BlockingScope.STAGE_TRANSITION
            )
        elif action_clean == "generate_preview":
            is_blocking = (
                finding.blockingScope == BlockingScope.PREVIEW
                or (
                    finding.stage == IssueStage.SCOPE
                    and finding.blockingScope
                    == BlockingScope.STAGE_TRANSITION
                )
            )
        elif action_clean == "export":
            is_blocking = (
                finding.blockingScope == BlockingScope.EXPORT
            )
        elif action_clean == "save_checkpoint":
            is_blocking = (
                finding.blockingScope == BlockingScope.CHECKPOINT
            )
        if is_blocking:
            filtered_gates.append(finding)
    return filtered_gates


async def suggestion_stages(
    project_id: int,
    stage: str,
    session,
    workspace_id: int | None = None,
) -> list[str]:
    if stage != "all":
        return [stage] if stage in {"what", "how", "scope"} else []
    unlocked_text = None
    if workspace_id is not None:
        from backend.database.model import BranchWorkspaceModel
        ws_res = await session.execute(
            select(BranchWorkspaceModel.unlocked_stages).where(
                BranchWorkspaceModel.id == workspace_id
            )
        )
        unlocked_text = ws_res.scalar_one_or_none()

    if unlocked_text is None:
        result = await session.execute(
            select(ProjectModel.unlocked_stages).where(
                ProjectModel.id == project_id
            )
        )
        unlocked_text = result.scalar_one_or_none() or ""
    unlocked = {
        item.strip()
        for item in (unlocked_text or "").split(",")
        if item.strip()
    }
    stages = ["what"]
    if "what" in unlocked:
        stages.append("how")
    if "how" in unlocked:
        stages.append("scope")
    return stages


def build_next_suggestion_finding(
    stage: str,
    suggestion: dict,
) -> Finding | None:
    if (
        not suggestion
        or suggestion.get("code")
        in {"PREVIEW_READY", "STAGE_LOCKED"}
    ):
        return None
    target_dict = suggestion.get("target")
    target_node = None
    if target_dict:
        target_node = IssueTarget(
            targetType=target_dict.get("type", "project"),
            targetId=target_dict.get("id"),
        )
    return Finding(
        findingId=f"{stage}:{suggestion['code']}:suggest",
        type=FindingType.NEXT_SUGGESTION,
        stage=IssueStage(stage),
        code=suggestion["code"],
        severity=IssueSeverity.INFO,
        title=suggestion["title"],
        description=suggestion["description"],
        target=target_node,
        blockingScope=BlockingScope.NONE,
        actionCode=(
            suggestion["action"].get("kind") or "navigate"
        ),
        metadata={
            "action": suggestion.get("action") or {},
            "target": suggestion.get("target"),
            "source_type": suggestion.get("source_type"),
            "status": suggestion.get("status"),
        },
    )
