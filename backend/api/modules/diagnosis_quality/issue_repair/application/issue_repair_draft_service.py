"""Service for managing IssueRepairDraft lifecycle.

create -> pending
confirm -> applied (or stale if context changed)
discard -> discarded
regenerate -> new draft (replaces old)
"""

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.modules.diagnosis_quality.perception.application.invalidation import (
    mark_perception_jobs_stale,
)
from backend.core.issue_resolution.fingerprint import (
    build_issue_fingerprint,
    compute_context_hash,
    load_target_entity_snapshot,
)
from backend.core.issue_resolution.validator import (
    RepairValidator,
)
from backend.core.engines.patch_engine import GraphPatchEngine
from backend.database.model import (
    AuditLogModel,
    IssueRepairDraftModel,
    ProjectModel,
)


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
            validation_report={},
            status="pending",
        )
        session.add(draft)
        await session.flush()

        # P5: generate impact preview from patch
        if draft.patch:
            from backend.core.issue_resolution.impact_preview import build_impact_preview
            try:
                preview = await build_impact_preview(
                    draft.patch, draft.project_id, draft.issue_code, session,
                )
                existing = draft.validation_report or {}
                if isinstance(existing, dict):
                    existing['impact_preview'] = preview
                    draft.validation_report = existing
            except Exception:
                pass
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
    ) -> dict:
        """Confirm a repair draft: validate, apply patch, mark stale, verify issue resolved."""
        # 1. Load draft
        draft = await self._load_draft(draft_id, session)
        if draft.project_id != project_id:
            raise ValueError("draft_project_mismatch")
        if draft.status != "pending":
            raise ValueError(f"draft_status_not_pending: {draft.status}")

        # 2. Recompute context hash and check staleness
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
        current_hash = _compute_context_hash_from_target(project_id, snapshot)

        if draft.context_hash and current_hash != draft.context_hash:
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

        # 3. Validate patch again (entities may have been deleted)
        if draft.patch:
            report = await self.validator.validate(
                project_id=project_id,
                issue_code=draft.issue_code,
                patch=draft.patch,
                session=session,
            )
            draft.validation_report = report
            if not report.get("valid"):
                draft.status = "invalid"
                await session.flush()
                return {
                    "message": "issue_repair_draft_invalid",
                    "draft_id": draft_id,
                    "status": "invalid",
                    "resolved_issue_ids": [],
                    "remaining_issue_ids": [],
                }

        # 4. Apply patch
        if draft.patch:
            await self.patch_engine.apply_patch(project_id, draft.patch, session)

        # 5. Mark applied
        draft.status = "applied"
        await session.flush()


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
            )

        await session.flush()

        # 8. Re-detect to verify issue resolved
        resolved_ids = []
        remaining_ids = []
        new_ids = []
        is_partial = False

        if draft.stage:
            # P5: before/after full diff in same transaction
            from backend.core.detectors import (
                HowIssueDetector, ScopeIssueDetector, WhatIssueDetector,
            )
            from backend.schemas import IssueStage
            _det_map = {
                IssueStage.WHAT.value: WhatIssueDetector(),
                IssueStage.HOW.value: HowIssueDetector(),
                IssueStage.SCOPE.value: ScopeIssueDetector(),
            }
            _det = _det_map.get(draft.stage)
            before = set()
            after_ids = []
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

        # Audit log (after before/after diff so variables are defined)
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
                "resolved_issue_ids": resolved_ids,
                "new_issue_ids": new_ids,
                "partially_resolved": is_partial,
            },
        ))

        return {
            "message": "issue_repair_draft_applied",
            "draft_id": draft_id,
            "status": "applied",
            "resolved_issue_ids": resolved_ids,
            "remaining_issue_ids": remaining_ids,
            "new_issue_ids": new_ids,
            "partially_resolved": is_partial,
        }

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
    ) -> dict:
        """Discard old draft and create a new one by re-resolving the original issue."""
        draft = await self._load_draft(draft_id, session)
        if draft.project_id != project_id:
            raise ValueError("draft_project_mismatch")

        draft.status = "discarded"
        await session.flush()

        from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_service import IssueRepairService
        repair_service = IssueRepairService()
        result = await repair_service.resolve(
            project_id=project_id,
            issue_code=draft.issue_code,
            stage=draft.stage,
            target=draft.target,
            metadata={"issue_id": draft.issue_id, "regenerate_of": draft_id},
            session=session,
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
