from sqlalchemy import select

from backend.api.services.issue_repair_service import IssueRepairService
from backend.core.detectors import (
    HowIssueDetector,
    ScopeIssueDetector,
    WhatIssueDetector,
)
from backend.schemas import Issue, IssueStage, IssueTarget


class IssueService:
    def __init__(self):
        self._detectors = {
            IssueStage.WHAT.value: WhatIssueDetector(),
            IssueStage.HOW.value: HowIssueDetector(),
            IssueStage.SCOPE.value: ScopeIssueDetector(),
        }
        self._repair_service = IssueRepairService()

    async def list_issues(
        self,
        project_id: int,
        stage: str,
        session,
    ) -> dict:
        stage = self._normalize_stage(stage)

        if not await self._is_stage_visible(project_id, stage, session):
            return {
                "project_id": project_id,
                "stage": stage,
                "issues": [],
            }

        detector = self._detectors.get(stage)

        if detector is None:
            await self._ensure_project_exists(project_id, session)
            issues = []
        else:
            issues = await detector.detect(
                project_id=project_id,
                session=session,
            )

        hidden_issue_ids = await self._load_hidden_issue_ids(project_id, session)
        issues = [
            issue
            for issue in issues
            if issue.issueId not in hidden_issue_ids
        ]

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
        issue_id: str | None,
        issue_code: str,
        stage: str | None,
        target: dict | None,
        metadata: dict,
        session,
    ) -> dict:
        """Resolve an issue by delegating to IssueRepairService.

        IssueRepairService handles re-detection, fingerprint/context hash,
        strategy dispatch, and generation draft creation.
        """
        # Load metadata from the request, with issue_id for tracing
        merged_metadata = {**(metadata or {})}
        if issue_id:
            merged_metadata["issue_id"] = issue_id

        return await self._repair_service.resolve(
            project_id=project_id,
            issue_code=issue_code,
            stage=stage,
            target=target,
            metadata=merged_metadata,
            session=session,
        )

    async def set_issue_status(
        self,
        project_id: int,
        issue_id: str,
        status: str,
        session,
    ) -> dict:
        from backend.database.model import IssueOverrideModel

        normalized_status = (status or "").strip().lower()
        if normalized_status not in {"open", "ignored", "resolved"}:
            raise ValueError("invalid_issue_status")

        await self._ensure_project_exists(project_id, session)

        existing_result = await session.execute(
            select(IssueOverrideModel).where(
                IssueOverrideModel.project_id == project_id,
                IssueOverrideModel.issue_id == issue_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if normalized_status == "open":
            if existing is not None:
                await session.delete(existing)
        else:
            if existing is None:
                session.add(
                    IssueOverrideModel(
                        project_id=project_id,
                        issue_id=issue_id,
                        status=normalized_status,
                    )
                )
            else:
                existing.status = normalized_status

        await session.flush()

        return {
            "project_id": project_id,
            "issue_id": issue_id,
            "status": normalized_status,
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

    @classmethod
    async def _is_stage_visible(
        cls,
        project_id: int,
        stage: str,
        session,
    ) -> bool:
        from backend.database.model import ProjectModel

        project_result = await session.execute(
            select(ProjectModel.unlocked_stages).where(
                ProjectModel.id == project_id,
            )
        )
        unlocked_text = project_result.scalar_one_or_none()

        if unlocked_text is None:
            raise ValueError("project_not_found")

        return cls._is_stage_unlocked_for_detection(
            stage=stage,
            unlocked_stages=unlocked_text,
        )

    @staticmethod
    def _is_stage_unlocked_for_detection(
        stage: str,
        unlocked_stages: str,
    ) -> bool:
        unlocked = {
            item.strip()
            for item in (unlocked_stages or "").split(",")
            if item.strip()
        }

        if stage == "what":
            return True
        if stage == "how":
            return "what" in unlocked
        if stage == "scope":
            return "how" in unlocked
        if stage == "preview":
            return "scope" in unlocked

        return False

    @staticmethod
    async def _load_hidden_issue_ids(project_id: int, session) -> set[str]:
        from backend.database.model import IssueOverrideModel

        result = await session.execute(
            select(IssueOverrideModel.issue_id).where(
                IssueOverrideModel.project_id == project_id,
                IssueOverrideModel.status.in_(("ignored", "resolved")),
            )
        )
        return {issue_id for issue_id in result.scalars().all() if issue_id}

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
