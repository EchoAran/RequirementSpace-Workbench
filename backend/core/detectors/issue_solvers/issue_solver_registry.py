from backend.core.detectors.issue_solvers.base_issue_solver import (
    BaseIssueSolver,
)
from backend.core.detectors.issue_solvers.generation_draft_issue_solver import (
    GenerationDraftIssueSolver,
)
from backend.core.detectors.issue_solvers.open_panel_issue_solver import (
    OpenPanelIssueSolver,
)
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
        solver = self._solvers.get(issue_code)

        if solver is None:
            raise ValueError("unsupported_issue_code")

        return await solver.resolve(
            project_id=project_id,
            issue_code=issue_code,
            target=target,
            metadata=metadata,
            session=session,
        )
