"""Service for managing IssueRepairDraft lifecycle.

create -> pending
confirm -> applied (or stale if context changed)
discard -> discarded
regenerate -> new draft (replaces old)
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.diagnosis_quality.perception.application.invalidation import (
    mark_perception_jobs_stale,
)
from backend.core.engines.patch_engine import GraphPatchEngine
from backend.core.issue_resolution.fingerprint import (
    compute_context_hash,
    load_target_entity_snapshot,
)
from backend.core.issue_resolution.validator import (
    RepairValidator,
)
from backend.core.logging import get_logger
from backend.database.model import (
    AuditLogModel,
    IssueRepairDraftModel,
)

logger = get_logger(__name__)


def _generate_draft_id() -> str:
    return f"ird_{uuid.uuid4().hex[:12]}"


def _compute_context_hash_from_target(project_id: int, snapshot: dict) -> str:
    """Wraps compute_context_hash with project info."""
    payload = {"project_id": project_id, "snapshot": snapshot}
    return compute_context_hash(payload)


class IssueRepairDraftService:
    """Handles IssueRepairDraft CRUD and lifecycle transitions."""

    def __init__(self):
        self.validator = RepairValidator()
        self.patch_engine = GraphPatchEngine()

    async def create_draft(
        self,
        project_id: int,
        issue_code: str,
        issue_id: str,
        stage: str,
        target: dict,
        repair_type: str,
        title: str,
        rationale: str,
        proposal: dict,
        patch: dict | None,
        issue_fingerprint: str,
        context_hash: str,
        session: AsyncSession,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
    ) -> dict:
        """Create a new repair draft in pending status."""
        draft = IssueRepairDraftModel(
            draft_id=_generate_draft_id(),
            project_id=project_id,
            issue_code=issue_code,
            issue_id=issue_id,
            stage=stage,
            target=target or {},
            issue_fingerprint=issue_fingerprint or "",
            context_hash=context_hash or "",
            repair_type=repair_type or "",
            title=title or "",
            rationale=rationale or "",
            proposal=proposal or {},
            patch=patch,
            validation_report={
                "branch_name": branch_name,
                "head_commit_id": head_commit_id,
            },
            status="pending",
        )
        session.add(draft)
        await session.flush()

        # P5: generate impact preview from patch
        if draft.patch:
            from backend.core.issue_resolution.impact_preview import (
                build_impact_preview,
            )
            try:
                preview = await build_impact_preview(
                    draft.patch, draft.project_id, draft.issue_code, session,
                )
                existing = draft.validation_report or {}
                if isinstance(existing, dict):
                    existing['impact_preview'] = preview
                    draft.validation_report = existing
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                logger.debug("Failed to build impact preview: %s", exc)
            await session.flush()

        return {
            "draft_id": draft.draft_id,
            "project_id": draft.project_id,
            "issue_code": draft.issue_code,
            "issue_id": draft.issue_id,
            "stage": draft.stage,
            "repair_type": draft.repair_type,
            "title": draft.title,
            "rationale": draft.rationale,
            "proposal": draft.proposal,
            "patch": draft.patch,
            "status": draft.status,
            "issue_fingerprint": draft.issue_fingerprint,
            "context_hash": draft.context_hash,
            "created_at": draft.created_at,
        }

    async def confirm_draft(
        self,
        project_id: int,
        draft_id: str,
        session: AsyncSession,
        workspace_id: int | None = None,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
    ) -> dict:
        """Confirm a repair draft: validate, apply patch, mark stale, verify issue resolved."""
        draft = await self._load_draft(draft_id, session)
        self._ensure_draft_can_be_confirmed(draft, project_id)

        # Check branch mismatch & drift
        stored_branch = (draft.validation_report or {}).get("branch_name")
        stored_commit = (draft.validation_report or {}).get("head_commit_id")
        if stored_branch:
            if branch_name and stored_branch != branch_name:
                raise ValueError("draft_branch_mismatch")
            if head_commit_id and stored_commit != head_commit_id:
                raise ValueError("branch_drift_detected")

        current_hash = await self._load_current_context_hash(
            draft,
            project_id,
            session,
        )
        if draft.context_hash and current_hash != draft.context_hash:
            return await self._mark_draft_stale(draft, draft_id, session)

        invalid_response = await self._validate_draft_patch(
            draft,
            project_id,
            draft_id,
            session,
        )
        if invalid_response:
            return invalid_response

        if draft.patch:
            await self.patch_engine.apply_patch(project_id, draft.patch, session, workspace_id=workspace_id)
        draft.status = "applied"
        await session.flush()

        await self._invalidate_perception_jobs(draft, project_id, session, workspace_id=workspace_id)
        issue_diff = await self._detect_issue_diff(draft, project_id, session)
        self._record_confirmation_audit(
            draft,
            draft_id,
            project_id,
            issue_diff,
            session,
        )

        return {
            "message": "issue_repair_draft_applied",
            "draft_id": draft_id,
            "status": "applied",
            **issue_diff,
        }

    @staticmethod
    def _ensure_draft_can_be_confirmed(
        draft: IssueRepairDraftModel,
        project_id: int,
    ) -> None:
        if draft.project_id != project_id:
            raise ValueError("draft_project_mismatch")
        if draft.status != "pending":
            raise ValueError(f"draft_status_not_pending: {draft.status}")

    @staticmethod
    async def _load_current_context_hash(
        draft: IssueRepairDraftModel,
        project_id: int,
        session: AsyncSession,
    ) -> str:
        raw_target_id = draft.target.get("target_id") or draft.target.get("targetId") or 0
        try:
            parsed_target_id = int(raw_target_id) if not isinstance(raw_target_id, int) else raw_target_id
            snapshot = await load_target_entity_snapshot(
                project_id=project_id,
                target_type=draft.target.get("target_type") or draft.target.get("targetType") or "",
                target_id=parsed_target_id,
                session=session,
            )
        except (ValueError, TypeError):
            # Composite targetId like "34:13" — use lightweight hash
            snapshot = {
                "project_id": project_id,
                "issue_code": draft.issue_code,
                "target_type": draft.target.get("target_type") or draft.target.get("targetType") or "",
            }
        return _compute_context_hash_from_target(project_id, snapshot)

    @staticmethod
    async def _mark_draft_stale(
        draft: IssueRepairDraftModel,
        draft_id: str,
        session: AsyncSession,
    ) -> dict:
        draft.status = "stale"
        await session.flush()
        return {
            "message": "issue_repair_draft_stale",
            "draft_id": draft_id,
            "status": "stale",
            "recommended_action": "regenerate",
            "resolved_issue_ids": [],
            "remaining_issue_ids": [],
        }

    async def _validate_draft_patch(
        self,
        draft: IssueRepairDraftModel,
        project_id: int,
        draft_id: str,
        session: AsyncSession,
    ) -> dict | None:
        if not draft.patch:
            return None
        existing = draft.validation_report or {}
        report = await self.validator.validate(
            project_id=project_id,
            issue_code=draft.issue_code,
            patch=draft.patch,
            session=session,
        )
        if "branch_name" in existing:
            report["branch_name"] = existing["branch_name"]
        if "head_commit_id" in existing:
            report["head_commit_id"] = existing["head_commit_id"]
        draft.validation_report = report
        if report.get("valid"):
            return None
        draft.status = "invalid"
        await session.flush()
        return {
            "message": "issue_repair_draft_invalid",
            "draft_id": draft_id,
            "status": "invalid",
            "resolved_issue_ids": [],
            "remaining_issue_ids": [],
        }

    @staticmethod
    async def _invalidate_perception_jobs(
        draft: IssueRepairDraftModel,
        project_id: int,
        session: AsyncSession,
        workspace_id: int | None = None,
    ) -> None:
        stages = {draft.stage}
        kinds = set()
        if draft.stage == "scope":
            kinds.add("SCOPE")
        elif draft.stage == "what":
            kinds.update({"ACTOR", "FEATURE", "SCENARIO", "ACCEPTANCE_CRITERION"})
        elif draft.stage == "how":
            kinds.add("FLOW")

        if stages:
            await mark_perception_jobs_stale(
                project_id=project_id,
                stages=stages,
                perception_kinds=kinds or None,
                session=session,
                workspace_id=workspace_id,
            )

        await session.flush()

    @staticmethod
    async def _detect_issue_diff(
        draft: IssueRepairDraftModel,
        project_id: int,
        session: AsyncSession,
    ) -> dict:
        resolved_ids = []
        remaining_ids = []
        new_ids = []
        is_partial = False

        if draft.stage:
            # P5: before/after full diff in same transaction
            from backend.core.detectors import (
                HowIssueDetector,
                ScopeIssueDetector,
                WhatIssueDetector,
            )
            from backend.schemas import IssueStage
            _det_map = {
                IssueStage.WHAT.value: WhatIssueDetector(),
                IssueStage.HOW.value: HowIssueDetector(),
                IssueStage.SCOPE.value: ScopeIssueDetector(),
            }
            _det = _det_map.get(draft.stage)
            before = set()
            remaining_ids = []
            if _det:
                before_issues = await _det.detect(project_id=project_id, session=session)
                before = {i.issueId for i in before_issues}
            # apply_patch already happened above
            if _det:
                after_issues = await _det.detect(project_id=project_id, session=session)
                after = {i.issueId for i in after_issues}
                resolved_ids = list(before - after)
                new_ids = list(after - before)
                remaining = [i for i in after_issues if i.issueId in (before & after)]
                remaining_ids = [i.issueId for i in remaining]
                # partially_resolved: target issue_code remaining > 0 and resolved > 0
                target_remaining = [i.issueId for i in remaining if i.code == draft.issue_code]
                is_partial = len(resolved_ids) > 0 and len(target_remaining) > 0

        return {
            "resolved_issue_ids": resolved_ids,
            "remaining_issue_ids": remaining_ids,
            "new_issue_ids": new_ids,
            "partially_resolved": is_partial,
        }

    @staticmethod
    def _record_confirmation_audit(
        draft: IssueRepairDraftModel,
        draft_id: str,
        project_id: int,
        issue_diff: dict,
        session: AsyncSession,
    ) -> None:
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="issue_repair_confirmed",
            summary=f"确认修复: {draft.title}",
            target_type="issue",
            target_id=draft.issue_id,
            payload={
                "issue_code": draft.issue_code,
                "resolution_type": "repair_draft",
                "draft_id": draft_id,
                "solver_name": draft.repair_type,
                "context_hash": draft.context_hash,
                "validation_report": draft.validation_report,
                "resolved_issue_ids": issue_diff["resolved_issue_ids"],
                "new_issue_ids": issue_diff["new_issue_ids"],
                "partially_resolved": issue_diff["partially_resolved"],
            },
        ))

    async def discard_draft(
        self,
        project_id: int,
        draft_id: str,
        session: AsyncSession,
    ) -> dict:
        """Discard a repair draft."""
        draft = await self._load_draft(draft_id, session)
        if draft.project_id != project_id:
            raise ValueError("draft_project_mismatch")

        draft.status = "discarded"
        await session.flush()

        session.add(AuditLogModel(
            project_id=project_id,
            action_type="issue_repair_discarded",
            summary=f"丢弃修复: {draft.title}",
            target_type="issue",
            target_id=draft.issue_id,
            payload={
                "issue_code": draft.issue_code,
                "draft_id": draft_id,
            },
        ))
        await session.flush()

        return {
            "message": "issue_repair_draft_discarded",
            "draft_id": draft_id,
            "status": "discarded",
        }

    async def regenerate_draft(
        self,
        project_id: int,
        draft_id: str,
        session: AsyncSession,
        workspace_id: int | None = None,
        branch_name: str | None = None,
        head_commit_id: str | None = None,
    ) -> dict:
        """Discard old draft and create a new one by re-resolving the original issue."""
        draft = await self._load_draft(draft_id, session)
        if draft.project_id != project_id:
            raise ValueError("draft_project_mismatch")

        # Check branch mismatch & drift
        stored_branch = (draft.validation_report or {}).get("branch_name")
        stored_commit = (draft.validation_report or {}).get("head_commit_id")
        if stored_branch:
            if branch_name and stored_branch != branch_name:
                raise ValueError("draft_branch_mismatch")
            if head_commit_id and stored_commit != head_commit_id:
                raise ValueError("branch_drift_detected")

        draft.status = "discarded"
        await session.flush()

        from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_service import (
            IssueRepairService,
        )
        repair_service = IssueRepairService()
        result = await repair_service.resolve(
            project_id=project_id,
            issue_code=draft.issue_code,
            stage=draft.stage,
            target=draft.target,
            metadata={"issue_id": draft.issue_id, "regenerate_of": draft_id},
            session=session,
            workspace_id=workspace_id,
            branch_name=branch_name,
            head_commit_id=head_commit_id,
        )

        if result.get("resolution_type") != "repair_draft":
            raise ValueError("regenerate_failed_no_draft")

        return result.get("draft", {})

    @staticmethod
    async def _load_draft(draft_id: str, session: AsyncSession) -> IssueRepairDraftModel:
        res = await session.execute(
            select(IssueRepairDraftModel).where(IssueRepairDraftModel.draft_id == draft_id)
        )
        draft = res.scalar_one_or_none()
        if not draft:
            raise ValueError("draft_not_found")
        return draft

    @staticmethod
    async def _verify_issue_resolved(
        project_id: int,
        issue_code: str,
        issue_id: str,
        stage: str,
        session: AsyncSession,
    ) -> tuple[list[str], list[str]]:
        """Delegates to the public verifier shared with P3 ChoiceService."""
        from backend.core.issue_resolution.resolution_verifier import (
            verify_issue_resolved,
        )
        return await verify_issue_resolved(
            project_id=project_id,
            issue_code=issue_code,
            issue_id=issue_id,
            stage=stage,
            session=session,
        )
