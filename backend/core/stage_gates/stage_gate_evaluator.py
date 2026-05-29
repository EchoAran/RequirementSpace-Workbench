from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.detectors import WhatIssueDetector, HowIssueDetector, ScopeIssueDetector
from backend.database.model import (
    ProjectModel,
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    FlowModel,
    BusinessObjectModel,
    ScopeModel,
)
from backend.schemas import IssueSeverity


class StageGateEvaluator:
    def __init__(self) -> None:
        self.what_detector = WhatIssueDetector()
        self.how_detector = HowIssueDetector()
        self.scope_detector = ScopeIssueDetector()

    async def evaluate_gates(self, project_id: int, session: AsyncSession) -> dict[str, bool]:
        """
        Evaluate absolute What/How/Scope gate readiness states in Python.
        Returns a dict e.g. {"what": True, "how": False, "scope": False}.
        """
        project = await session.get(ProjectModel, project_id)
        if not project:
            return {"what": False, "how": False, "scope": False}

        # 1. Detect issues for each stage using existing detectors
        what_issues = await self.what_detector.detect(project_id, session)
        how_issues = await self.how_detector.detect(project_id, session)
        scope_issues = await self.scope_detector.detect(project_id, session)

        # 2. Query structural models count and properties
        actors_result = await session.execute(
            select(ActorModel.id).where(ActorModel.project_id == project_id)
        )
        actors_count = len(actors_result.scalars().all())

        features_result = await session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        )
        features = features_result.scalars().all()

        # Find leaf features (features that are not parents of any other feature)
        # Query FeatureRelationModel directly to avoid ORM lazy-loading MissingGreenlet errors
        relations_result = await session.execute(
            select(FeatureRelationModel.parent_feature_id)
        )
        parent_ids = set(relations_result.scalars().all())
        leaf_features = [f for f in features if f.id not in parent_ids]

        # 3. Evaluate What Stage Gate
        # What stage passes if:
        # - Has at least 1 actor and at least 1 leaf feature.
        # - Has no BLOCKING issues.
        what_has_blocking = any(
            issue.severity == IssueSeverity.BLOCKING for issue in what_issues
        )
        what_passed = (
            actors_count > 0
            and len(leaf_features) > 0
            and not what_has_blocking
        )

        # 4. Evaluate How Stage Gate
        # How stage passes if:
        # - What stage has passed.
        # - Has at least 1 flow.
        # - Has no BLOCKING issues.
        flows_result = await session.execute(
            select(FlowModel.id).where(FlowModel.project_id == project_id)
        )
        flows_count = len(flows_result.scalars().all())

        how_has_blocking = any(
            issue.severity == IssueSeverity.BLOCKING for issue in how_issues
        )
        how_passed = (
            what_passed
            and flows_count > 0
            and not how_has_blocking
        )

        # 5. Evaluate Scope Stage Gate
        # Scope stage passes if:
        # - What and How stages have passed.
        # - Kano status is 'generated' or 'skipped'.
        # - Every leaf feature has a scope status decision.
        # - Has no BLOCKING issues.
        scopes_result = await session.execute(
            select(ScopeModel)
            .join(FeatureModel)
            .where(FeatureModel.project_id == project_id)
        )
        scopes = scopes_result.scalars().all()
        scoped_feature_ids = {s.feature_id for s in scopes if s.status}

        all_leaf_features_scoped = len(leaf_features) > 0 and all(
            lf.id in scoped_feature_ids for lf in leaf_features
        )
        kano_ready = project.kano_status in ("generated", "skipped")

        scope_has_blocking = any(
            issue.severity == IssueSeverity.BLOCKING for issue in scope_issues
        )

        scope_passed = (
            what_passed
            and how_passed
            and all_leaf_features_scoped
            and kano_ready
            and not scope_has_blocking
        )

        return {
            "what": bool(what_passed),
            "how": bool(how_passed),
            "scope": bool(scope_passed),
        }
