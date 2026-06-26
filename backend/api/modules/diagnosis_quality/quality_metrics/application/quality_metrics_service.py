"""Quality metrics for issue AI repairs.

Read-only queries against existing models — no new tables.
"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.model import (
    ChoiceModel,
    ChoiceGroupModel,
    IssueRepairDraftModel,
)


async def get_repair_metrics(project_id: int, session: AsyncSession) -> dict:
    """Aggregate repair and choice metrics for a project."""
    # Repair draft counts by status
    draft_counts = {}
    for status in ("pending", "applied", "discarded", "stale", "invalid"):
        res = await session.execute(
            select(func.count(IssueRepairDraftModel.id)).where(
                IssueRepairDraftModel.project_id == project_id,
                IssueRepairDraftModel.status == status,
            )
        )
        draft_counts[status] = res.scalar() or 0

    # Choice counts by status
    choice_counts = {}
    for status in ("candidate", "accepted", "rejected"):
        res = await session.execute(
            select(func.count(ChoiceModel.id))
            .select_from(ChoiceModel)
            .join(ChoiceGroupModel, ChoiceModel.choice_group_id == ChoiceGroupModel.id)
            .where(
                ChoiceGroupModel.project_id == project_id,
                ChoiceModel.status == status,
            )
        )
        choice_counts[status] = res.scalar() or 0

    # Per issue code breakdown
    codes_res = await session.execute(
        select(
            IssueRepairDraftModel.issue_code,
            IssueRepairDraftModel.status,
            func.count(IssueRepairDraftModel.id),
        )
        .where(IssueRepairDraftModel.project_id == project_id)
        .group_by(IssueRepairDraftModel.issue_code, IssueRepairDraftModel.status)
    )
    by_code = {}
    for row in codes_res.fetchall():
        code, status, count = row
        if code not in by_code:
            by_code[code] = {"generated": 0, "applied": 0, "discarded": 0, "stale": 0, "invalid": 0}
        key = "generated" if status == "pending" else status
        if key in by_code[code]:
            by_code[code][key] = count

    return {
        "repair_generated": draft_counts.get("pending", 0),
        "repair_confirmed": draft_counts.get("applied", 0),
        "repair_discarded": draft_counts.get("discarded", 0),
        "repair_stale": draft_counts.get("stale", 0),
        "repair_invalid": draft_counts.get("invalid", 0),
        "choice_generated": choice_counts.get("candidate", 0),
        "choice_accepted": choice_counts.get("accepted", 0),
        "choice_rejected": choice_counts.get("rejected", 0),
        "by_issue_code": by_code,
    }
