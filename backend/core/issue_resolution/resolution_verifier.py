"""Public issue resolution verifier.

Reused by:
  - IssueRepairDraftService.confirm_draft() (P2)
  - ChoiceService.accept_choice() (P3)
"""


async def verify_issue_resolved(
    project_id: int,
    issue_code: str,
    issue_id: str,
    stage: str,
    session,
) -> tuple[list[str], list[str]]:
    """Re-run detector for the stage and check if the target issue is gone.

    Returns (resolved_issue_ids, remaining_issue_ids):
    - resolved: the specific issue_id that was acted upon (now gone)
    - remaining: all other open issues of the same code that still exist
    """
    from backend.core.detectors import (
        HowIssueDetector,
        ScopeIssueDetector,
        WhatIssueDetector,
    )
    from backend.schemas import IssueStage

    detector_map = {
        IssueStage.WHAT.value: WhatIssueDetector(),
        IssueStage.HOW.value: HowIssueDetector(),
        IssueStage.SCOPE.value: ScopeIssueDetector(),
    }

    detector = detector_map.get(stage)
    if not detector:
        return [], []

    remaining = await detector.detect(project_id=project_id, session=session)
    still_open = [i.issueId for i in remaining if i.issueId == issue_id]
    same_code_remaining = [
        i.issueId for i in remaining
        if i.code == issue_code and i.issueId != issue_id
    ]

    if still_open:
        return [], [issue_id] + same_code_remaining
    else:
        return [issue_id], same_code_remaining
