import logging
import time

from fastapi import BackgroundTasks
from sqlalchemy import select

from backend.api.modules.diagnosis_quality.next_suggestion.application.next_suggestion_service import (
    NextSuggestionService,
)
from backend.core.findings.how_finding_policy import HowFindingPolicy
from backend.core.findings.scope_finding_policy import ScopeFindingPolicy
from backend.core.findings.what_finding_policy import WhatFindingPolicy
from backend.core.issue_capabilities import (
    get_issue_capability,
)
from backend.core.logging import get_logger, log_event, sanitize_message
from backend.core.logging.events import (
    FINDING_DETECTION_COMPLETED,
    FINDING_DETECTION_FAILED,
    FINDING_DETECTION_STARTED,
)
from backend.schemas import (
    BlockingScope,
    Finding,
    FindingType,
)

from .finding_list_helpers import (
    build_next_suggestion_finding,
    filter_gates_by_action,
    normalize_finding_filters,
    policy_stages,
    suggestion_stages,
)

logger = get_logger(__name__)

class FindingService:
    def __init__(self):
        self._policies = {
            "what": WhatFindingPolicy(),
            "how": HowFindingPolicy(),
            "scope": ScopeFindingPolicy(),
        }
        self._next_suggestion_service = NextSuggestionService()

    async def list_findings(
        self,
        project_id: int,
        stage: str | None,
        view: str,
        action: str | None,
        session,
        workspace_id: int,
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> list[Finding]:
        stage_clean, view_clean = normalize_finding_filters(
            stage,
            view,
        )

        findings: list[Finding] = []
        if view_clean in {"issues", "gate", "health"}:
            findings = await self._collect_structural_findings(
                project_id,
                stage_clean,
                view_clean,
                session,
                workspace_id=workspace_id,
            )
            overrides = await self._load_overrides(project_id, session, workspace_id=workspace_id)
            if overrides:
                findings = [f for f in findings if f.findingId not in overrides]

        # 2. Process views
        if view_clean == "issues":
            result = [f for f in findings if f.type == FindingType.ISSUE]
            self._attach_capability(result)
            return result

        elif view_clean == "health":
            result = [f for f in findings if f.type == FindingType.QUALITY_HINT]
            self._attach_capability(result)
            return result

        elif view_clean == "gate":
            gate_findings = [f for f in findings if f.type == FindingType.GATE_CONDITION or f.blockingScope != BlockingScope.NONE]
            self._attach_capability(gate_findings)
            return filter_gates_by_action(gate_findings, action)

        elif view_clean == "next_action":
            stages_to_suggest = await suggestion_stages(
                stage_clean,
                session,
                workspace_id=workspace_id,
            )

            next_findings = []
            for s in stages_to_suggest:
                try:
                    res = await self._next_suggestion_service.get_next_suggestion(
                        project_id=project_id,
                        stage=s,
                        session=session,
                        background_tasks=background_tasks,
                        public_project_id=public_project_id,
                        workspace_id=workspace_id,
                    )
                    sugg = res.get("suggestion")
                    finding = build_next_suggestion_finding(s, sugg)
                    if finding:
                        next_findings.append(finding)
                except Exception as e:
                    logger.exception(f"Error loading next suggestions for stage {s}: {e}")

            # NextSuggestion 不附加 capability（NEXT_SUGGESTION 不允许 AI 处理）
            return next_findings

        return []

    async def list_all_findings_views(
        self,
        project_id: int,
        session,
        workspace_id: int,
        stage: str = "all",
        action: str | None = None,
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> dict[str, list[Finding]]:
        """Collect and partition findings into all 4 views (issues, health, gate, next_action) in a single pass."""
        stage_clean, _ = normalize_finding_filters(stage, "issues")

        findings = await self._collect_structural_findings(
            project_id,
            stage_clean,
            "issues",
            session,
            workspace_id=workspace_id,
        )
        overrides = await self._load_overrides(project_id, session, workspace_id=workspace_id)
        if overrides:
            findings = [f for f in findings if f.findingId not in overrides]

        issues = [f for f in findings if f.type == FindingType.ISSUE]
        self._attach_capability(issues)

        health = [f for f in findings if f.type == FindingType.QUALITY_HINT]
        self._attach_capability(health)

        gate = [f for f in findings if f.type == FindingType.GATE_CONDITION or f.blockingScope != BlockingScope.NONE]
        self._attach_capability(gate)
        gate_filtered = filter_gates_by_action(gate, action)

        stages_to_suggest = await suggestion_stages(
            stage_clean,
            session,
            workspace_id=workspace_id,
        )
        next_findings = []
        for s in stages_to_suggest:
            try:
                res = await self._next_suggestion_service.get_next_suggestion(
                    project_id=project_id,
                    stage=s,
                    session=session,
                    background_tasks=background_tasks,
                    public_project_id=public_project_id,
                    workspace_id=workspace_id,
                )
                sugg = res.get("suggestion")
                finding = build_next_suggestion_finding(s, sugg)
                if finding:
                    next_findings.append(finding)
            except Exception as e:
                logger.exception(f"Error loading next suggestions for stage {s}: {e}")

        return {
            "issues": issues,
            "health": health,
            "gate": gate_filtered,
            "next_action": next_findings,
        }

    async def _collect_structural_findings(
        self,
        project_id: int,
        stage: str,
        view: str,
        session,
        workspace_id: int,
    ) -> list[Finding]:
        findings: list[Finding] = []
        for current_stage in policy_stages(stage, self._policies):
            policy = self._policies[current_stage]
            policy_start = time.perf_counter()
            log_event(
                logger,
                logging.INFO,
                "domain",
                FINDING_DETECTION_STARTED,
                "Finding detection started",
                project_id=project_id,
                stage=current_stage,
                view=view,
            )
            try:
                stage_findings = await policy.get_findings(
                    project_id,
                    session,
                    workspace_id=workspace_id,
                )
                findings.extend(stage_findings)
            except Exception as error:
                log_event(
                    logger,
                    logging.WARNING,
                    "domain",
                    FINDING_DETECTION_FAILED,
                    "Finding detection failed",
                    project_id=project_id,
                    stage=current_stage,
                    view=view,
                    error_type=type(error).__name__,
                    error_message=sanitize_message(str(error)),
                    duration_ms=int(
                        (time.perf_counter() - policy_start) * 1000
                    ),
                )
            else:
                log_event(
                    logger,
                    logging.INFO,
                    "domain",
                    FINDING_DETECTION_COMPLETED,
                    "Finding detection completed",
                    project_id=project_id,
                    stage=current_stage,
                    view=view,
                    finding_count=len(stage_findings),
                    duration_ms=int(
                        (time.perf_counter() - policy_start) * 1000
                    ),
                )
        overrides = await self._load_overrides(project_id, session, workspace_id=workspace_id)
        return [
            finding
            for finding in findings
            if finding.findingId not in overrides
        ]

    async def set_finding_status(
        self,
        project_id: int,
        finding_id: str,
        status: str,
        session,
        workspace_id: int,
    ) -> dict:
        from backend.database.model import FindingOverrideModel, ProjectModel

        status_clean = (status or "").strip().lower()
        if status_clean not in {"open", "ignored", "resolved"}:
            raise ValueError("invalid_finding_status")

        # Verify project exists
        stmt_p = select(ProjectModel.id).where(ProjectModel.id == project_id)
        project_result = await session.execute(stmt_p)
        if project_result.scalar_one_or_none() is None:
            raise ValueError("project_not_found")

        # Identify the true finding type by re-detecting.
        parts = finding_id.split(":", 2)
        stage_val = parts[0] if len(parts) > 0 else None

        finding_type_val = await self._find_finding_type(
            project_id=project_id,
            finding_id=finding_id,
            stage_val=stage_val,
            session=session,
            workspace_id=workspace_id,
        )

        # Restrict ignored/resolved based on finding type
        if status_clean == "ignored":
            if finding_type_val not in {"issue", "quality_hint"}:
                raise ValueError("invalid_finding_status")
        elif status_clean == "resolved":
            if finding_type_val != "issue":
                raise ValueError("invalid_finding_status")

        # Query existing override
        stmt_e = select(FindingOverrideModel).where(
            FindingOverrideModel.project_id == project_id,
            FindingOverrideModel.finding_id == finding_id,
            FindingOverrideModel.workspace_id == workspace_id,
        )

        existing_result = await session.execute(stmt_e)
        existing = existing_result.scalar_one_or_none()

        if status_clean == "open":
            if existing is not None:
                await session.delete(existing)
        else:
            parts = finding_id.split(":", 2)
            code_val = parts[1] if len(parts) > 1 else None
            if existing is None:
                session.add(
                    FindingOverrideModel(
                        project_id=project_id,
                        workspace_id=workspace_id,
                        finding_id=finding_id,
                        finding_type=finding_type_val,
                        status=status_clean,
                        stage=stage_val,
                        code=code_val,
                    )
                )
            else:
                existing.status = status_clean
                existing.finding_type = finding_type_val

        await session.flush()
        return {
            "project_id": project_id,
            "finding_id": finding_id,
            "status": status_clean,
        }

    async def _find_finding_type(
        self,
        project_id: int,
        finding_id: str,
        stage_val: str | None,
        session,
        workspace_id: int,
    ) -> str:
        """通过 finding_id 前缀与重新检测确定 finding 的真实类型。

        常见 stage 级 issue/quality_hint 直接归类，避免为每次状态写回都全量重新检测；
        但聚合 gate（{stage}:{CODE}:aggregate）不是 issue，必须走重新检测判定真实类型，
        否则 gate 会被错误地允许 ignored/resolved。
        """
        if stage_val in {"what", "how", "scope"}:
            id_parts = (finding_id or "").split(":")
            if not (len(id_parts) >= 3 and id_parts[-1] == "aggregate"):
                return "issue"

        # Phase 1: structural findings (policies bypass overrides)
        findings = []
        stages_to_run = []
        if stage_val in self._policies:
            stages_to_run = [stage_val]
        else:
            stages_to_run = ["what", "how", "scope"]

        for s in stages_to_run:
            policy = self._policies[s]
            try:
                s_findings = await policy.get_findings(project_id, session, workspace_id=workspace_id)
                findings.extend(s_findings)
            except Exception as e:
                logger.warning(f"Error re-detecting findings for stage {s}: {e}")

        match = next((f for f in findings if f.findingId == finding_id), None)
        if match:
            return match.type.value

        # Phase 2: suggestion findings
        try:
            suggestions = await self.list_findings(
                project_id=project_id,
                stage=stage_val if stage_val in {"what", "how", "scope"} else "all",
                view="next_action",
                action=None,
                session=session,
                workspace_id=workspace_id,
            )
            match = next((f for f in suggestions if f.findingId == finding_id), None)
            if match:
                return match.type.value
        except Exception as e:
            logger.warning(f"Error re-detecting suggestions: {e}")

        return "unknown"

    @staticmethod
    def _attach_capability(findings: list[Finding]) -> None:
        """为 findings 附加处理能力信息。

        NEXT_SUGGESTION 不附加 capability（不允许 AI 处理）。
        ISSUE / GATE_CONDITION / QUALITY_HINT 从能力注册表获取对应 capability。
        """
        for f in findings:
            if f.type == FindingType.NEXT_SUGGESTION:
                f.capability = None
                continue
            cap = get_issue_capability(f.code)
            f.capability = {
                "kind": cap.kind.value,
                "action_label": cap.action_label,
                "enabled": cap.enabled,
            }

    async def _load_overrides(self, project_id: int, session, workspace_id: int) -> set[str]:
        from backend.database.model import FindingOverrideModel
        stmt = select(FindingOverrideModel.finding_id).where(
            FindingOverrideModel.project_id == project_id,
            FindingOverrideModel.status.in_({"ignored", "resolved"}),
            FindingOverrideModel.workspace_id == workspace_id,
        )

        res = await session.execute(stmt)
        return {finding_id for finding_id in res.scalars().all() if finding_id}
