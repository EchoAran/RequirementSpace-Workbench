"""Base class for Issue AI solvers.

Each concrete solver handles one or more issue codes and produces
structured repair proposals. The base class provides the LLM calling
pattern with JSON output validation and fallback to manual_action.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from backend.core.llm_protected_inputs import collect_protected_texts
from backend.core.localized_messages import localized_message
from backend.services.llm_handler_service import LLMHandler


@dataclass
class RepairProposal:
    """Single repair proposal from an AI solver."""
    repair_type: str
    title: str
    rationale: str
    confidence: float = 0.0
    patch: dict | None = None
    risks: list[str] = field(default_factory=list)
    requires_user_decision: bool = False


@dataclass
class RepairResult:
    """Result from an AI solver, containing either proposals or a fallback."""
    candidates: list[RepairProposal] = field(default_factory=list)
    result_type: str = "repair_draft"  # "repair_draft" | "choice_group" | "manual_action"
    fallback_reason: str = ""
    error: str | None = None
    # P4: when True, _resolve_with_ai() should fall back to IssueSolverRegistry
    fallback_to_registry: bool = False
    # Deprecated: use result_type instead
    fallback_kind: str = "manual_action"


class BaseIssueAISolver(ABC):
    """Base class for issue-specific AI solvers.

    Subclasses must implement:
    - build_prompt_context() — prepare the LLM input
    - parse_response() — convert LLM output to RepairResult
    - repair_type() — the repair type identifier
    """

    def __init__(self):
        self._llm_handler = LLMHandler()

    @property
    @abstractmethod
    def supported_issue_codes(self) -> list[str]:
        """Issue codes this solver handles."""
        ...

    @abstractmethod
    async def build_prompt_context(
        self,
        project_id: int,
        issue_code: str,
        target: dict | None,
        session,
    ) -> dict:
        """Build the context dict for the LLM prompt."""
        ...

    @abstractmethod
    def repair_type(self) -> str:
        """The repair_type value for proposals from this solver."""
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """The system prompt template."""
        ...

    @abstractmethod
    def get_user_prompt(self, context: dict) -> str:
        """The user prompt template, filled with context."""
        ...

    def parse_response(self, raw_json: dict) -> RepairResult:
        """Parse LLM JSON response into a RepairResult.

        Override in subclasses for custom parsing.
        Default implementation:
        - 0 candidates: manual_action
        - 1 candidate: repair_draft
        - 2+ candidates: choice_group
        """
        try:
            candidates_raw = raw_json.get("candidates", [raw_json])
            candidates = []
            for c in candidates_raw:
                candidates.append(RepairProposal(
                    repair_type=c.get("repair_type", self.repair_type()),
                    title=c.get("title", ""),
                    rationale=c.get("rationale", ""),
                    confidence=c.get("confidence", 0.0),
                    patch=c.get("patch"),
                    risks=c.get("risks", []),
                    requires_user_decision=c.get("requires_user_decision", False),
                ))
            fallback = raw_json.get("fallback", {})

            # Determine result_type based on candidate count
            if not candidates:
                result_type = "manual_action"
            elif len(candidates) == 1:
                result_type = "repair_draft"
            else:
                result_type = "choice_group"

            return RepairResult(
                candidates=candidates,
                result_type=result_type,
                fallback_kind=fallback.get("kind", "manual_action"),
                fallback_reason=fallback.get("reason", ""),
            )
        except (ValueError, TypeError, KeyError) as e:
            return RepairResult(
                result_type="manual_action",
                fallback_kind="manual_action",
                fallback_reason=f"解析 AI 输出失败: {e}",
                error=str(e),
            )

    def fallback_result(self, reason: str | None = None) -> RepairResult:
        """Return a fallback result when AI cannot process."""
        return RepairResult(
            fallback_kind="manual_action",
            fallback_reason=reason or localized_message("issue_unavailable"),
        )

    async def solve(
        self,
        project_id: int,
        issue_code: str,
        target: dict | None,
        session,
    ) -> RepairResult:
        """Main entry point: build context, call LLM, parse result."""
        try:
            context = await self.build_prompt_context(project_id, issue_code, target, session)
        except Exception:
            return self.fallback_result(localized_message("issue_context_failed"))

        system_prompt = self.get_system_prompt()
        user_prompt = self.get_user_prompt(context)

        try:
            response = await self._llm_handler.call_llm(
                prompt=system_prompt,
                query=user_prompt,
                print_log=True,
                response_format={"type": "json_object"},
                protected_inputs=collect_protected_texts(context, target),
            )
        except Exception:
            return self.fallback_result(localized_message("issue_call_failed"))

        if not response:
            return self.fallback_result(localized_message("issue_empty_response"))

        try:
            import json
            raw = json.loads(response)
        except json.JSONDecodeError:
            return self.fallback_result(localized_message("issue_invalid_response"))

        result = self.parse_response(raw)

        # P4: if solver signals registry fallback, short-circuit no-candidates check
        if result.fallback_to_registry:
            return result

        # Filter: if no valid candidates, fallback
        if not result.candidates:
            return self.fallback_result(
                result.fallback_reason or localized_message("issue_no_solution")
            )

        return result
