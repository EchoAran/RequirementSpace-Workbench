import logging
from sqlalchemy import select
from fastapi import BackgroundTasks

from backend.schemas import (
    Finding,
    FindingType,
    BlockingScope,
    IssueStage,
    IssueSeverity,
    IssueTarget,
)
from backend.core.findings.what_finding_policy import WhatFindingPolicy
from backend.core.findings.how_finding_policy import HowFindingPolicy
from backend.core.findings.scope_finding_policy import ScopeFindingPolicy
from backend.core.issue_capabilities import (
    get_issue_capability,
)
from backend.api.services.next_suggestion_service import NextSuggestionService

logger = logging.getLogger(__name__)

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
        background_tasks: BackgroundTasks | None = None,
        public_project_id: str | None = None,
    ) -> list[Finding]:
        # Normalize stage
        stage_clean = (stage or "all").strip().lower()
        if stage_clean not in {"what", "how", "scope", "preview", "all"}:
            raise ValueError("invalid_stage")

        # Normalize view
        view_clean = (view or "issues").strip().lower()
        if view_clean not in {"issues", "next_action", "gate", "health"}:
            raise ValueError("invalid_view")

        # 1. Fetch structural findings if view requires them
        findings: list[Finding] = []
        if view_clean in {"issues", "gate", "health"}:
            stages_to_run = []
            if stage_clean == "all":
                stages_to_run = ["what", "how", "scope"]
            elif stage_clean in self._policies:
                stages_to_run = [stage_clean]

            for s in stages_to_run:
                policy = self._policies[s]
                try:
                    s_findings = await policy.get_findings(project_id, session)
                    findings.extend(s_findings)
                except Exception as e:
                    logger.exception(f"Error executing finding policy for stage {s}: {e}")

            # Apply overrides filter (ignored or resolved findings)
            overrides = await self._load_overrides(project_id, session)
            findings = [
                f for f in findings
                if f.findingId not in overrides
            ]

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
            if not action:
                return gate_findings

            action_clean = action.strip().lower()
            filtered_gates = []
            for gf in gate_findings:
                is_blocking = False
                if action_clean == "enter_how":
                    is_blocking = (gf.stage == IssueStage.WHAT and gf.blockingScope == BlockingScope.STAGE_TRANSITION)
                elif action_clean == "enter_scope":
                    is_blocking = (gf.stage == IssueStage.HOW and gf.blockingScope == BlockingScope.STAGE_TRANSITION)
                elif action_clean == "generate_preview":
                    is_blocking = (gf.blockingScope == BlockingScope.PREVIEW or (gf.stage == IssueStage.SCOPE and gf.blockingScope == BlockingScope.STAGE_TRANSITION))
                elif action_clean == "export":
                    is_blocking = (gf.blockingScope == BlockingScope.EXPORT)
                elif action_clean == "save_checkpoint":
                    is_blocking = (gf.blockingScope == BlockingScope.CHECKPOINT)

                if is_blocking:
                    filtered_gates.append(gf)
            return filtered_gates

        elif view_clean == "next_action":
            # Call next suggestion service
            stages_to_suggest = []
            if stage_clean == "all":
                # Check which stages are visible/unlocked
                from backend.database.model import ProjectModel
                proj_result = await session.execute(
                    select(ProjectModel.unlocked_stages).where(ProjectModel.id == project_id)
                )
                unlocked_text = proj_result.scalar_one_or_none() or ""
                unlocked = {item.strip() for item in unlocked_text.split(",") if item.strip()}

                stages_to_suggest.append("what")
                if "what" in unlocked:
                    stages_to_suggest.append("how")
                if "how" in unlocked:
                    stages_to_suggest.append("scope")
            elif stage_clean in {"what", "how", "scope"}:
                stages_to_suggest = [stage_clean]

            next_findings = []
            for s in stages_to_suggest:
                try:
                    res = await self._next_suggestion_service.get_next_suggestion(
                        project_id=project_id,
                        stage=s,
                        session=session,
                        background_tasks=background_tasks,
                        public_project_id=public_project_id,
                    )
                    sugg = res.get("suggestion")
                    if sugg and sugg.get("code") not in {"PREVIEW_READY", "STAGE_LOCKED"}:
                        target_dict = sugg.get("target")
                        target_node = None
                        if target_dict:
                            target_node = IssueTarget(
                                targetType=target_dict.get("type", "project"),
                                targetId=target_dict.get("id"),
                            )

                        next_findings.append(
                            Finding(
                                findingId=f"{s}:{sugg['code']}:suggest",
                                type=FindingType.NEXT_SUGGESTION,
                                stage=IssueStage(s),
                                code=sugg["code"],
                                severity=IssueSeverity.INFO,
                                title=sugg["title"],
                                description=sugg["description"],
                                target=target_node,
                                blockingScope=BlockingScope.NONE,
                                actionCode=sugg["action"].get("kind") or "navigate",
                                metadata={
                                    "action": sugg.get("action") or {},
                                    "target": sugg.get("target"),
                                    "source_type": sugg.get("source_type"),
                                    "status": sugg.get("status"),
                                },
                            )
                        )
                except Exception as e:
                    logger.exception(f"Error loading next suggestions for stage {s}: {e}")

            # NextSuggestion 不附加 capability（NEXT_SUGGESTION 不允许 AI 处理）
            return next_findings

        return []

    async def set_finding_status(
        self,
        project_id: int,
        finding_id: str,
        status: str,
        session,
    ) -> dict:
        from backend.database.model import FindingOverrideModel, ProjectModel

        status_clean = (status or "").strip().lower()
        if status_clean not in {"open", "ignored", "resolved"}:
            raise ValueError("invalid_finding_status")

        # Verify project exists
        project_result = await session.execute(
            select(ProjectModel.id).where(ProjectModel.id == project_id)
        )
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
        )

        # Restrict ignored/resolved based on finding type
        if status_clean == "ignored":
            if finding_type_val not in {"issue", "quality_hint"}:
                raise ValueError("invalid_finding_status")
        elif status_clean == "resolved":
            if finding_type_val != "issue":
                raise ValueError("invalid_finding_status")

        # Query existing override
        existing_result = await session.execute(
            select(FindingOverrideModel).where(
                FindingOverrideModel.project_id == project_id,
                FindingOverrideModel.finding_id == finding_id,
            )
        )
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
    ) -> str:
        """通过重新检测确定 finding 的真实类型。

        优先通过 policy 重新检测结构 finding。
        再检查 suggestion finding。
        仍找不到时返回 "unknown"，此时调用者只允许 `open` 状态写回。
        """
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
                s_findings = await policy.get_findings(project_id, session)
                findings.extend(s_findings)
            except Exception as e:
                logger.exception(f"Error re-detecting findings for stage {s}: {e}")
                raise

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
            )
            match = next((f for f in suggestions if f.findingId == finding_id), None)
            if match:
                return match.type.value
        except Exception as e:
            logger.exception(f"Error re-detecting suggestions: {e}")
            raise

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

    async def _load_overrides(self, project_id: int, session) -> set[str]:
        from backend.database.model import FindingOverrideModel
        result = await session.execute(
            select(FindingOverrideModel.finding_id).where(
                FindingOverrideModel.project_id == project_id,
                FindingOverrideModel.status.in_({"ignored", "resolved"}),
            )
        )
        return {finding_id for finding_id in result.scalars().all() if finding_id}
