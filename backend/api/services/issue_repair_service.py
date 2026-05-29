"""Issue Repair Service — unified resolve entry point.

Replaces IssueService.resolve_issue() as the orchestrator:
  1. Re-detect current issues for the stage
  2. Match the issue by code + target; return already_resolved if gone
  3. Build fingerprint and context hash
  4. Dispatch to strategy (registry or AI solver)
  5. Return unified response

P2 AI solver dispatch:
  - SCOPE_WITHOUT_REASON → ScopeReasonSolver → repair_draft
  - LEAF_FEATURE_WITHOUT_ACTOR → ActorFeatureCoverageSolver → repair_draft or manual_action
  - Other codes → registry (manual_action / generation_draft / unsupported)
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.detectors import (
    HowIssueDetector,
    ScopeIssueDetector,
    WhatIssueDetector,
)
from backend.core.detectors.issue_solvers import IssueSolverRegistry
from backend.core.detectors.issue_solvers.ai_issue_solver import (
    RepairProposal,
    RepairResult,
)
from backend.core.detectors.issue_solvers.draft_factory import (
    IssueResolutionDraftFactory,
)
from backend.core.detectors.issue_solvers.repair_fingerprint import (
    build_issue_fingerprint,
    compute_context_hash,
    load_target_entity_snapshot,
)
from backend.core.detectors.issue_solvers.repair_validator import (
    RepairValidator,
)
from backend.core.detectors.issue_solvers.strategies.scope_reason_solver import (
    ScopeReasonSolver,
)
from backend.core.detectors.issue_solvers.strategies.actor_feature_coverage_solver import (
    ActorFeatureCoverageSolver,
)
from backend.core.detectors.issue_solvers.strategies.business_object_attribute_solver import (
    BusinessObjectAttributeSolver,
)
from backend.core.detectors.issue_solvers.strategies.flow_feature_coverage_solver import (
    FlowFeatureCoverageSolver,
)
from backend.core.detectors.issue_solvers.strategies.scenario_coverage_solver import (
    ScenarioCoverageSolver,
)
from backend.schemas import Issue, IssueStage, IssueTarget


# Map stage names to detector instances
_STAGE_DETECTORS = {
    IssueStage.WHAT.value: WhatIssueDetector(),
    IssueStage.HOW.value: HowIssueDetector(),
    IssueStage.SCOPE.value: ScopeIssueDetector(),
}

# Map issue codes to their likely stage (fallback when no stage is provided)
_ISSUE_CODE_TO_STAGE: dict[str, str] = {
    # What stage
    "ACTOR_WITHOUT_FEATURE": "what",
    "LEAF_FEATURE_WITHOUT_ACTOR": "what",
    "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO": "what",
    "SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS": "what",
    "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA": "what",
    "DUPLICATE_SCENARIO_NAME": "what",
    # How stage
    "LEAF_FEATURE_WITHOUT_FLOW": "how",
    "FLOW_WITHOUT_FEATURE": "how",
    "FLOW_WITHOUT_STEPS": "how",
    "ACTOR_ACTION_STEP_WITHOUT_ACTOR": "how",
    "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES": "how",
    "UNREACHABLE_FLOW_STEP": "how",
    "BUSINESS_OBJECT_WITHOUT_USAGE": "how",
    "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES": "how",
    # Scope stage
    "LEAF_FEATURE_WITHOUT_SCOPE": "scope",
    "SCOPE_WITHOUT_REASON": "scope",
}


# AI solvers registered by issue code
_AI_SOLVERS: dict[str, object] = {
    "SCOPE_WITHOUT_REASON": ScopeReasonSolver(),
    "LEAF_FEATURE_WITHOUT_ACTOR": ActorFeatureCoverageSolver(),
    "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES": BusinessObjectAttributeSolver(),
    "LEAF_FEATURE_WITHOUT_FLOW": FlowFeatureCoverageSolver(),
    "FLOW_WITHOUT_FEATURE": FlowFeatureCoverageSolver(),
    "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO": ScenarioCoverageSolver(),
}


class IssueRepairService:
    """Coordinates issue resolution end-to-end."""

    def __init__(self):
        self._solver_registry = IssueSolverRegistry()
        self._draft_factory = IssueResolutionDraftFactory()
        self._validator = RepairValidator()

    async def resolve(
        self,
        project_id: int,
        issue_code: str,
        stage: str | None,
        target: dict | None,
        metadata: dict,
        session: AsyncSession,
    ) -> dict:
        """Main resolve entry point.

        Returns a dict matching IssueResolutionResponse schema.
        """
        # 1. Validate project
        await self._ensure_project_exists(project_id, session)

        # 2. Resolve stage
        resolved_stage = self._resolve_stage(stage, issue_code)

        # 3. Re-detect issues for the stage
        current_issues = await self._detect_stage_issues(project_id, resolved_stage, session)

        # 4. Build IssueTarget for matching
        issue_target = self._build_target(target)
        issue_target_dict = self._target_to_dict(target)

        # 4a. Validate target for issue codes that require one
        self._validate_target_for_code(issue_code, target)

        # 5. Match current issue
        matched_issue = self._find_matching_issue(current_issues, issue_code, issue_target)

        # 6. If issue no longer exists → check if code is known or truly unsupported
        if matched_issue is None:
            is_known = self._is_known_code(issue_code)
            if not is_known:
                return {
                    "project_id": project_id,
                    "issue_code": issue_code,
                    "resolution_type": "unsupported",
                    "title": "暂不支持自动处理",
                    "description": f"当前系统暂不支持自动处理「{issue_code}」类型的问题。",
                    "action": {"kind": "manual_action", "payload": {}},
                    "draft_id": None,
                    "draft": {},
                    "patch": None,
                    "issue_fingerprint": None,
                    "context_hash": None,
                }
            return {
                "project_id": project_id,
                "issue_code": issue_code,
                "resolution_type": "already_resolved",
                "title": "该问题已解决",
                "description": "当前项目中已经找不到这个问题。",
                "action": {"kind": "refresh_issues"},
                "draft_id": None,
                "draft": {},
                "patch": None,
                "issue_fingerprint": None,
                "context_hash": None,
            }

        # 7. Build fingerprint and context hash
        issue_fp = self._build_fingerprint(resolved_stage, issue_code, matched_issue.target)
        context_hash = await self._build_context_hash(project_id, matched_issue, session)

        # 8. Check if this issue code has an AI solver (P2)
        ai_solver = _AI_SOLVERS.get(issue_code)

        if ai_solver is not None:
            # P2: AI solver path
            return await self._resolve_with_ai(
                project_id=project_id,
                issue_code=issue_code,
                issue_id=matched_issue.issueId,
                target=issue_target_dict,
                issue_target=issue_target,
                stage=resolved_stage,
                matched_issue=matched_issue,
                issue_fp=issue_fp,
                context_hash=context_hash,
                ai_solver=ai_solver,
                metadata=metadata or {},
                session=session,
            )

        # 9. Fallback to registry (manual_action / generation_draft / unsupported)
        resolution = await self._solver_registry.resolve(
            project_id=project_id,
            issue_code=issue_code,
            target=issue_target,
            metadata=metadata or {},
            session=session,
        )

        # 10. If generation_draft, create the actual draft
        if resolution.resolutionType == "generation_draft":
            resolution = await self._draft_factory.create_draft(
                project_id=project_id,
                resolution=resolution,
                session=session,
            )

        # 11. Build unified response dict
        result = resolution.to_dict()
        result["project_id"] = project_id
        result["issue_fingerprint"] = issue_fp
        result["context_hash"] = context_hash
        return result

    async def _resolve_with_ai(
        self,
        project_id: int,
        issue_code: str,
        issue_id: str,
        target: dict | None,
        issue_target: IssueTarget | None,
        stage: str,
        matched_issue: Issue,
        issue_fp: str,
        context_hash: str,
        ai_solver,
        metadata: dict,
        session: AsyncSession,
    ) -> dict:
        """AI solver path: call solver, validate, create draft, return response."""
        from backend.api.services.issue_repair_draft_service import (
            IssueRepairDraftService,
        )

        result: RepairResult = await ai_solver.solve(
            project_id=project_id,
            issue_code=issue_code,
            target=target,
            session=session,
        )

        # P4: fallback_to_registry — solver wants generation_draft path
        if result.fallback_to_registry:
            resolution = await self._solver_registry.resolve(
                project_id=project_id,
                issue_code=issue_code,
                target=issue_target,
                metadata=metadata,
                session=session,
            )
            if resolution.resolutionType == "generation_draft":
                resolution = await self._draft_factory.create_draft(
                    project_id=project_id, resolution=resolution, session=session,
                )
            response = resolution.to_dict()
            response["project_id"] = project_id
            response["issue_fingerprint"] = issue_fp
            response["context_hash"] = context_hash
            return response

        # Branch: choice_group (multiple candidates)
        if result.result_type == "choice_group" and len(result.candidates) > 1:
            return await self._handle_choice_group(
                project_id=project_id, issue_code=issue_code,
                issue_id=issue_id, stage=stage, target=target,
                issue_fp=issue_fp, context_hash=context_hash,
                result=result, session=session,
            )

        # If no candidates, return manual_action fallback
        if not result.candidates:
            return {
                "project_id": project_id,
                "issue_code": issue_code,
                "resolution_type": "manual_action",
                "title": "无法自动修复",
                "description": result.fallback_reason or "AI 无法确定修复方案，请手动处理。",
                "action": {
                    "kind": "open_panel",
                    "payload": {"target": target},
                },
                "draft_id": None,
                "draft": {},
                "patch": None,
                "issue_fingerprint": issue_fp,
                "context_hash": context_hash,
            }

        # Single candidate: take the highest confidence
        candidate = result.candidates[0]

        # Validate the patch
        if candidate.patch:
            report = await self._validator.validate(
                project_id=project_id,
                issue_code=issue_code,
                patch=candidate.patch,
                session=session,
            )
            if not report.get("valid"):
                return {
                    "project_id": project_id,
                    "issue_code": issue_code,
                    "resolution_type": "manual_action",
                    "title": "修复方案校验未通过",
                    "description": "; ".join(report.get("errors", [])),
                    "action": {
                        "kind": "open_panel",
                        "payload": {"target": target},
                    },
                    "draft_id": None,
                    "draft": {},
                    "patch": None,
                    "issue_fingerprint": issue_fp,
                    "context_hash": context_hash,
                }

        # Create repair draft
        draft_service = IssueRepairDraftService()
        draft = await draft_service.create_draft(
            project_id=project_id,
            issue_code=issue_code,
            issue_id=issue_id,
            stage=stage,
            target=target or {},
            repair_type=candidate.repair_type,
            title=candidate.title,
            rationale=candidate.rationale,
            proposal={"candidates": [candidate.__dict__]},
            patch=candidate.patch,
            issue_fingerprint=issue_fp,
            context_hash=context_hash,
            session=session,
        )

        return {
            "project_id": project_id,
            "issue_code": issue_code,
            "resolution_type": "repair_draft",
            "title": candidate.title,
            "description": candidate.rationale,
            "action": {
                "kind": "show_repair_draft",
                "draft_id": draft["draft_id"],
                "payload": draft,
            },
            "draft_id": draft["draft_id"],
            "draft": draft,
            "patch": candidate.patch,
            "issue_fingerprint": issue_fp,
            "context_hash": context_hash,
        }

    async def _handle_choice_group(
        self,
        project_id: int,
        issue_code: str,
        issue_id: str,
        stage: str,
        target: dict | None,
        issue_fp: str,
        context_hash: str,
        result: RepairResult,
        session: AsyncSession,
    ) -> dict:
        """Validate multiple AI candidates and create a ChoiceGroup."""
        from backend.api.services.choice_service import ChoiceService

        valid_candidates = []
        for c in result.candidates:
            if c.patch:
                report = await self._validator.validate(
                    project_id=project_id, issue_code=issue_code,
                    patch=c.patch, session=session,
                )
                if report.get("valid"):
                    valid_candidates.append(c)

        if len(valid_candidates) >= 2:
            choice_service = ChoiceService()
            choice_group = await choice_service.create_choice_group(
                project_id=project_id,
                source_type="issue_repair",
                source_id=issue_fp,
                issue_code=issue_code,
                issue_id=issue_id,
                stage=stage,
                target=target,
                context_hash=context_hash,
                candidates=valid_candidates,
                session=session,
            )
            return {
                "project_id": project_id,
                "issue_code": issue_code,
                "resolution_type": "choice_group",
                "title": "选择处理方案",
                "description": f"AI 找到 {len(valid_candidates)} 个可行方案，请选择。",
                "action": {
                    "kind": "open_choice_group",
                    "choice_group_id": choice_group["id"],
                    "payload": {"choice_group": choice_group},
                },
                "draft_id": None,
                "draft": {},
                "patch": None,
                "issue_fingerprint": issue_fp,
                "context_hash": context_hash,
            }

        return {
            "project_id": project_id,
            "issue_code": issue_code,
            "resolution_type": "manual_action",
            "title": "候选方案均未通过校验",
            "description": "AI 生成的候选方案未通过系统校验，请手动处理。",
            "action": {"kind": "open_panel", "payload": {"target": target}},
            "draft_id": None, "draft": {}, "patch": None,
            "issue_fingerprint": issue_fp, "context_hash": context_hash,
        }

    # ---- helpers (unchanged from P1) ----

    @staticmethod
    async def _ensure_project_exists(project_id: int, session: AsyncSession) -> None:
        from backend.database.model import ProjectModel

        project_result = await session.execute(
            select(ProjectModel.id).where(ProjectModel.id == project_id)
        )
        if project_result.scalar_one_or_none() is None:
            raise ValueError("project_not_found")

    @staticmethod
    def _resolve_stage(stage: str | None, issue_code: str) -> str:
        if stage and stage.strip().lower() in {"what", "how", "scope", "preview"}:
            return stage.strip().lower()
        mapped = _ISSUE_CODE_TO_STAGE.get(issue_code)
        if mapped:
            return mapped
        raise ValueError("invalid_stage")

    @staticmethod
    async def _detect_stage_issues(
        project_id: int,
        stage: str,
        session: AsyncSession,
    ) -> list[Issue]:
        detector = _STAGE_DETECTORS.get(stage)
        if detector is None:
            return []
        return await detector.detect(project_id=project_id, session=session)

    @staticmethod
    def _build_target(target: dict | None) -> IssueTarget | None:
        if target is None:
            return None
        return IssueTarget(
            targetType=target.get("target_type") or target.get("targetType") or "",
            targetId=target.get("target_id") or target.get("targetId"),
            parentType=target.get("parent_type") or target.get("parentType"),
            parentId=target.get("parent_id") or target.get("parentId"),
        )

    @staticmethod
    def _target_to_dict(target: dict | None) -> dict | None:
        if target is None:
            return None
        return {
            "target_type": target.get("target_type") or target.get("targetType") or "",
            "target_id": target.get("target_id") or target.get("targetId"),
            "parent_type": target.get("parent_type") or target.get("parentType"),
            "parent_id": target.get("parent_id") or target.get("parentId"),
        }

    @staticmethod
    def _find_matching_issue(
        issues: list[Issue],
        issue_code: str,
        target: IssueTarget | None,
    ) -> Issue | None:
        target_key = target.key() if target is not None else "project"
        candidates = [i for i in issues if i.code == issue_code]
        if not candidates:
            return None
        for issue in candidates:
            if issue.issueId.endswith(target_key):
                return issue
        for issue in candidates:
            if target is not None and issue.target is not None:
                if issue.target.key() == target_key:
                    return issue
        if target is not None and target.targetId is not None:
            for issue in candidates:
                if issue.target is not None:
                    if issue.target.targetType == target.targetType:
                        if str(issue.target.targetId) == str(target.targetId):
                            return issue
        return candidates[0]

    @staticmethod
    def _build_fingerprint(
        stage: str,
        issue_code: str,
        target: IssueTarget | None,
    ) -> str:
        if target is None:
            return build_issue_fingerprint(stage, issue_code, None, None)
        return build_issue_fingerprint(
            stage=stage,
            issue_code=issue_code,
            target_type=target.targetType,
            target_id=target.targetId,
            parent_type=target.parentType,
            parent_id=target.parentId,
        )

    @staticmethod
    def _is_known_code(issue_code: str) -> bool:
        """Check if an issue code is known to any solver (registry or AI)."""
        from backend.core.detectors.issue_solvers.issue_solver_registry import (
            KNOWN_ISSUE_CODES,
        )
        return issue_code in _AI_SOLVERS or issue_code in KNOWN_ISSUE_CODES

    @staticmethod
    def _validate_target_for_code(issue_code: str, target: dict | None) -> None:
        """Validate target has required fields for issue codes that need them.

        Raises ValueError (→ 400) if the target is malformed.
        """
        _requires_target = {
            "LEAF_FEATURE_WITHOUT_ACTOR", "ACTOR_WITHOUT_FEATURE",
            "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO", "SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS",
            "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA", "DUPLICATE_SCENARIO_NAME",
            "LEAF_FEATURE_WITHOUT_FLOW", "FLOW_WITHOUT_FEATURE", "FLOW_WITHOUT_STEPS",
            "ACTOR_ACTION_STEP_WITHOUT_ACTOR", "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES",
            "UNREACHABLE_FLOW_STEP", "BUSINESS_OBJECT_WITHOUT_USAGE",
            "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES", "SCOPE_WITHOUT_REASON",
        }
        if issue_code not in _requires_target:
            return
        if not target or not isinstance(target, dict):
            raise ValueError("invalid_resolution_payload")
        tid = target.get("target_id") or target.get("targetId")
        ttype = target.get("target_type") or target.get("targetType")
        if not tid or not ttype:
            raise ValueError("invalid_resolution_payload")

    @staticmethod
    async def _build_context_hash(
        project_id: int,
        issue: Issue,
        session: AsyncSession,
    ) -> str:
        if issue.target is None or issue.target.targetId is None:
            snapshot = {"project_id": project_id, "issue_code": issue.code}
        else:
            # targetId may be composite like "29:12" — skip snapshot if not a plain int
            raw = issue.target.targetId
            try:
                parsed_id = int(raw) if not isinstance(raw, int) else raw
            except (ValueError, TypeError):
                snapshot = {"project_id": project_id, "issue_code": issue.code, "target_type": issue.target.targetType}
            else:
                snapshot = await load_target_entity_snapshot(
                    project_id=project_id,
                    target_type=issue.target.targetType,
                    target_id=parsed_id,
                    session=session,
                )
        # Must match the format used in IssueRepairDraftService.confirm_draft()
        return compute_context_hash({"project_id": project_id, "snapshot": snapshot})
