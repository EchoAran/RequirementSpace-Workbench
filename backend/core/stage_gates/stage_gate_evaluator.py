"""Stage gate evaluator orchestrating deterministic gate criteria evaluations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.detectors import (
    HowIssueDetector,
    ScopeIssueDetector,
    WhatIssueDetector,
)
from backend.core.stage_gates.stage_gate_context import (
    load_how_gate_context,
    load_scoped_feature_ids,
    load_what_gate_context,
)
from backend.core.stage_gates.stage_gate_criteria import (
    evaluate_how_gate,
    evaluate_scope_gate,
    evaluate_what_gate,
)
from backend.database.model import BranchWorkspaceModel, ProjectModel


class StageGateEvaluator:
    """Evaluates project stage gates (WHAT, HOW, SCOPE) against deterministic criteria."""

    def __init__(self) -> None:
        self.what_detector = WhatIssueDetector()
        self.how_detector = HowIssueDetector()
        self.scope_detector = ScopeIssueDetector()

    async def evaluate_gates(
        self,
        project_id: int,
        session: AsyncSession,
        workspace_id: int,
    ) -> dict[str, bool]:
        """Evaluate gate progression for the specified project workspace."""
        project = await session.get(ProjectModel, project_id)
        if not project:
            return {"what": False, "how": False, "scope": False}

        workspace = await session.get(BranchWorkspaceModel, workspace_id)
        if workspace is None or workspace.project_id != project_id:
            raise ValueError("workspace_not_found")

        what_issues = await self.what_detector.detect(
            project_id,
            session,
            workspace_id=workspace_id,
        )
        how_issues = await self.how_detector.detect(
            project_id,
            session,
            workspace_id=workspace_id,
        )
        scope_issues = await self.scope_detector.detect(
            project_id,
            session,
            workspace_id=workspace_id,
        )

        what_context = await load_what_gate_context(
            project_id,
            session,
            workspace_id=workspace_id,
        )
        what_passed = evaluate_what_gate(
            what_context,
            what_issues,
        )
        how_context = await load_how_gate_context(
            project_id,
            session,
            workspace_id=workspace_id,
        )
        how_passed = evaluate_how_gate(
            what_passed,
            what_context,
            how_context,
            how_issues,
        )
        scoped_feature_ids = await load_scoped_feature_ids(
            project_id,
            session,
            workspace_id=workspace_id,
        )
        scope_passed = evaluate_scope_gate(
            what_passed,
            how_passed,
            what_context.leaf_feature_ids,
            scoped_feature_ids,
            workspace.kano_status,
            scope_issues,
        )
        return {
            "what": bool(what_passed),
            "how": bool(how_passed),
            "scope": bool(scope_passed),
        }
