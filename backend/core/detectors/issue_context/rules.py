"""Issue context loaders for domain rules and rule links."""

from __future__ import annotations

from sqlalchemy import select

from backend.database.model import (
    DomainRuleModel,
    RuleLinkModel,
)

from .types import (
    DomainRuleIssueItem,
    RuleLinkIssueItem,
)


async def load_issue_domain_rules(
    project_id: int,
    session,
    workspace_id: int,
) -> list[DomainRuleIssueItem]:
    """Load domain rules for issue detection context."""
    stmt = select(DomainRuleModel).where(
        DomainRuleModel.project_id == project_id,
        DomainRuleModel.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    rules = result.scalars().all()
    return [
        DomainRuleIssueItem(
            rule_id=rule.id,
            logical_uuid=rule.logical_uuid,
            title=rule.title,
            statement=rule.statement,
            origin=rule.origin,
            confirmation_status=rule.confirmation_status,
            parent_rule_id=rule.parent_rule_id,
        )
        for rule in rules
    ]


async def load_issue_rule_links(
    project_id: int,
    session,
    workspace_id: int,
) -> list[RuleLinkIssueItem]:
    """Load rule links for issue detection context."""
    stmt = select(RuleLinkModel).where(
        RuleLinkModel.project_id == project_id,
        RuleLinkModel.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    links = result.scalars().all()
    return [
        RuleLinkIssueItem(
            link_id=link.id,
            logical_uuid=link.logical_uuid,
            rule_id=link.rule_id,
            target_kind=link.target_kind,
            target_logical_uuid=link.target_logical_uuid,
            link_purpose=link.link_purpose,
        )
        for link in links
    ]
