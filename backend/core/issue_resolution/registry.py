from backend.core.issue_resolution.base_solver import (
    BaseIssueSolver,
)
from backend.core.issue_resolution.generation_draft_solver import (
    GenerationDraftIssueSolver,
)
from backend.core.issue_resolution.open_panel_solver import (
    OpenPanelIssueSolver,
)
from backend.core.issue_capabilities import KNOWN_ISSUE_CODES
from backend.schemas import IssueResolution, IssueTarget


class IssueSolverRegistry:
    def __init__(self):
        open_panel_solver = OpenPanelIssueSolver()
        generation_draft_solver = GenerationDraftIssueSolver()

        self._solvers: dict[str, BaseIssueSolver] = {
            "ACTOR_WITHOUT_FEATURE": open_panel_solver,
            "LEAF_FEATURE_WITHOUT_ACTOR": open_panel_solver,
            "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO": generation_draft_solver,
            "SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS": open_panel_solver,
            "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA": (
                generation_draft_solver
            ),
            "DUPLICATE_SCENARIO_NAME": open_panel_solver,
            "LEAF_FEATURE_WITHOUT_FLOW": open_panel_solver,
            "FLOW_WITHOUT_FEATURE": open_panel_solver,
            "FLOW_WITHOUT_STEPS": open_panel_solver,
            "ACTOR_ACTION_STEP_WITHOUT_ACTOR": open_panel_solver,
            "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES": open_panel_solver,
            "UNREACHABLE_FLOW_STEP": open_panel_solver,
            "BUSINESS_OBJECT_WITHOUT_USAGE": open_panel_solver,
            "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES": open_panel_solver,
            "LEAF_FEATURE_WITHOUT_SCOPE": generation_draft_solver,
            "SCOPE_WITHOUT_REASON": open_panel_solver,
        }

    async def resolve(
        self,
        project_id: int,
        issue_code: str,
        target: IssueTarget | None,
        metadata: dict,
        session,
    ) -> IssueResolution:
        """Resolve an issue by dispatching to the registered solver.

        Returns an IssueResolution. For unknown issue codes, returns an
        unsupported resolution instead of raising.
        """
        solver = self._solvers.get(issue_code)

        if solver is None:
            return IssueResolution(
                issueCode=issue_code,
                resolutionType="unsupported",
                title="暂不支持自动处理",
                description=f"当前系统暂不支持自动处理「{issue_code}」类型的问题。",
                action={
                    "kind": "manual_action",
                    "payload": {},
                },
            )

        return await solver.resolve(
            project_id=project_id,
            issue_code=issue_code,
            target=target,
            metadata=metadata,
            session=session,
        )

    def get_stage_for_code(self, issue_code: str) -> str | None:
        """Infer the stage for a given issue code.

        Returns None if the code is unknown.
        """
        solver = self._solvers.get(issue_code)
        if solver is None:
            return None

        if isinstance(solver, GenerationDraftIssueSolver):
            draft_type = solver.get_draft_type(issue_code)
            return {
                "scenario_generation": "what",
                "acceptance_criteria_generation": "what",
                "scope_generation": "scope",
            }.get(draft_type)

        return None
