from sqlalchemy import select

from backend.api.services.service_registry import (
    acceptance_criteria_generation_service,
    scenario_generation_service,
    scope_generation_service,
)
from backend.core.detectors import (
    HowIssueDetector,
    ScopeIssueDetector,
    WhatIssueDetector,
)
from backend.core.detectors.issue_solvers import IssueSolverRegistry
from backend.schemas import Issue, IssueStage, IssueTarget


class IssueService:
    def __init__(self):
        self._detectors = {
            IssueStage.WHAT.value: WhatIssueDetector(),
            IssueStage.HOW.value: HowIssueDetector(),
            IssueStage.SCOPE.value: ScopeIssueDetector(),
        }
        self._solver_registry = IssueSolverRegistry()

    async def list_issues(
        self,
        project_id: int,
        stage: str,
        session,
    ) -> dict:
        stage = self._normalize_stage(stage)

        detector = self._detectors.get(stage)

        if detector is None:
            await self._ensure_project_exists(project_id, session)
            issues = []
        else:
            issues = await detector.detect(
                project_id=project_id,
                session=session,
            )

        return {
            "project_id": project_id,
            "stage": stage,
            "issues": [
                self._serialize_issue(issue)
                for issue in issues
            ],
        }

    async def resolve_issue(
        self,
        project_id: int,
        issue_code: str,
        target: dict | None,
        metadata: dict,
        session,
    ) -> dict:
        await self._ensure_project_exists(project_id, session)

        resolution = await self._solver_registry.resolve(
            project_id=project_id,
            issue_code=issue_code,
            target=self._build_issue_target(target),
            metadata=metadata or {},
            session=session,
        )

        if resolution.resolutionType == "generation_draft":
            resolution = await self._create_resolution_draft(
                project_id=project_id,
                resolution=resolution,
                session=session,
            )

        return {
            "project_id": project_id,
            **resolution.to_dict(),
        }

    @staticmethod
    def _normalize_stage(stage: str) -> str:
        normalized_stage = stage.strip().lower()

        if normalized_stage not in {
            "what",
            "how",
            "scope",
            "preview",
        }:
            raise ValueError("invalid_stage")

        return normalized_stage

    @staticmethod
    async def _ensure_project_exists(project_id: int, session) -> None:
        from backend.database.model import ProjectModel

        project_result = await session.execute(
            select(ProjectModel.id).where(ProjectModel.id == project_id)
        )

        if project_result.scalar_one_or_none() is None:
            raise ValueError("project_not_found")

    @staticmethod
    def _build_issue_target(target: dict | None) -> IssueTarget | None:
        if target is None:
            return None

        return IssueTarget(
            targetType=target.get("target_type"),
            targetId=target.get("target_id"),
            parentType=target.get("parent_type"),
            parentId=target.get("parent_id"),
        )

    @staticmethod
    def _serialize_issue(issue: Issue) -> dict:
        return {
            "issue_id": issue.issueId,
            "code": issue.code,
            "stage": issue.stage.value,
            "severity": issue.severity.value,
            "title": issue.title,
            "description": issue.description,
            "target": (
                {
                    "target_type": issue.target.targetType,
                    "target_id": issue.target.targetId,
                    "parent_type": issue.target.parentType,
                    "parent_id": issue.target.parentId,
                }
                if issue.target is not None
                else None
            ),
            "resolver_code": issue.resolverCode,
            "metadata": issue.metadata,
        }

    async def _create_resolution_draft(
        self,
        project_id: int,
        resolution,
        session,
    ):
        draft_type = resolution.action.get("draft_type")
        payload = resolution.action.get("payload", {})

        if draft_type == "scenario_generation":
            feature_id = payload.get("feature_id")
            actor_id = payload.get("actor_id")

            if feature_id is None or actor_id is None:
                raise ValueError("invalid_resolution_payload")

            draft = await scenario_generation_service.create_pair_draft(
                project_id=project_id,
                feature_id=int(feature_id),
                actor_id=int(actor_id),
                session=session,
            )

        elif draft_type == "acceptance_criteria_generation":
            scenario_id = payload.get("scenario_id")

            if scenario_id is None:
                raise ValueError("invalid_resolution_payload")

            draft = await acceptance_criteria_generation_service.create_single_draft(
                project_id=project_id,
                scenario_id=int(scenario_id),
                session=session,
            )

        elif draft_type == "scope_generation":
            draft = await scope_generation_service.create_draft(
                project_id=project_id,
                session=session,
            )

        else:
            raise ValueError("unsupported_resolution_draft")

        resolution.draftId = draft["draft_id"]
        resolution.draft = draft
        resolution.action["endpoint"] = resolution.action[
            "endpoint"
        ].format(draft_id=draft["draft_id"])
        resolution.action["payload"] = {
            **payload,
            "draft_id": draft["draft_id"],
        }

        return resolution
