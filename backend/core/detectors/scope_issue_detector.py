from backend.core.detectors.base_issue_detector import BaseIssueDetector
from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)
from backend.schemas import (
    Issue,
    IssueSeverity,
    IssueStage,
    IssueTarget,
)


class ScopeIssueDetector(BaseIssueDetector):
    async def detect(self, project_id: int, session) -> list[Issue]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )

        issues: list[Issue] = []
        issues.extend(self._detect_leaf_feature_without_scope(context))
        issues.extend(self._detect_scope_without_reason(context))

        return issues

    @staticmethod
    def _detect_leaf_feature_without_scope(
        context: IssueProjectContext,
    ) -> list[Issue]:
        # Non-equilibrium: if scopes are completely empty, let ScopeSuggestionPolicy recommend GENERATE_SCOPE.
        if not context.scopes:
            return []

        scoped_feature_ids = {
            scope.feature_id
            for scope in context.scopes
        }

        return [
            Issue(
                code="LEAF_FEATURE_WITHOUT_SCOPE",
                stage=IssueStage.SCOPE,
                severity=IssueSeverity.WARNING,
                title="叶子功能缺少范围结论",
                description=f"叶子功能“{feature.name}”还没有范围结论。",
                target=IssueTarget(
                    targetType="feature",
                    targetId=feature.feature_id,
                ),
                actionCode="create_scope_generation_draft",
            )
            for feature in context.leaf_features
            if feature.feature_id not in scoped_feature_ids
        ]

    @staticmethod
    def _detect_scope_without_reason(
        context: IssueProjectContext,
    ) -> list[Issue]:
        return [
            Issue(
                code="SCOPE_WITHOUT_REASON",
                stage=IssueStage.SCOPE,
                severity=IssueSeverity.WARNING,
                title="范围结论缺少理由",
                description=f"范围结论 {scope.scope_id} 缺少说明理由。",
                target=IssueTarget(
                    targetType="scope",
                    targetId=scope.scope_id,
                ),
                actionCode="open_scope_reason_panel",
            )
            for scope in context.scopes
            if not scope.reason.strip()
        ]
