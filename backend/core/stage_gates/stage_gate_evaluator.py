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
from backend.core.stage_gates.stage_gate_rules import (
    evaluate_how_gate,
    evaluate_scope_gate,
    evaluate_what_gate,
)
from backend.database.model import ProjectModel


class StageGateEvaluator:
    def __init__(self) -> None:
        self.what_detector = WhatIssueDetector()
        self.how_detector = HowIssueDetector()
        self.scope_detector = ScopeIssueDetector()

    async def evaluate_gates(
        self,
        project_id: int,
        session: AsyncSession,
    ) -> dict[str, bool]:
        project = await session.get(ProjectModel, project_id)
        if not project:
            return {"what": False, "how": False, "scope": False}

        what_issues = await self.what_detector.detect(
            project_id,
            session,
        )
        how_issues = await self.how_detector.detect(
            project_id,
            session,
        )
        scope_issues = await self.scope_detector.detect(
            project_id,
            session,
        )

        what_context = await load_what_gate_context(
            project_id,
            session,
        )
        what_passed = evaluate_what_gate(
            what_context,
            what_issues,
        )
        how_context = await load_how_gate_context(
            project_id,
            session,
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
        )
        scope_passed = evaluate_scope_gate(
            what_passed,
            how_passed,
            what_context.leaf_feature_ids,
            scoped_feature_ids,
            project.kano_status,
            scope_issues,
        )
        return {
            "what": bool(what_passed),
            "how": bool(how_passed),
            "scope": bool(scope_passed),
        }
