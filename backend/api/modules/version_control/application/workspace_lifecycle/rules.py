"""Restore and copy rule aggregates within a branch workspace."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.model_invariants.rule_invariants import (
    validate_rule_confirmation_status,
    validate_rule_link_purpose,
    validate_rule_link_target,
    validate_rule_origin,
    validate_rule_parent_graph,
    validate_rule_text,
)
from backend.database.model import (
    DomainRuleModel,
    RuleLinkModel,
)


def restore_rule_aggregate(
    db: Session,
    project_id: int,
    workspace_id: int,
    state: dict[str, Any],
) -> None:
    """Restore rules, their hierarchy and links from canonical workspace state."""
    rules_by_uuid: dict[str, DomainRuleModel] = {}
    validate_rule_parent_graph({
        item["logical_uuid"]: item.get("parent_rule_logical_uuid")
        for item in state.get("domain_rules", [])
    })
    for item in state.get("domain_rules", []):
        validate_rule_text(item["title"], item["statement"])
        validate_rule_origin(item["origin"])
        validate_rule_confirmation_status(item["confirmation_status"])
        rule = DomainRuleModel(
            project_id=project_id,
            workspace_id=workspace_id,
            logical_uuid=item["logical_uuid"],
            title=item["title"],
            statement=item["statement"],
            origin=item["origin"],
            confirmation_status=item["confirmation_status"],
        )
        db.add(rule)
        rules_by_uuid[item["logical_uuid"]] = rule
    db.flush()

    for item in state.get("domain_rules", []):
        parent_uuid = item.get("parent_rule_logical_uuid")
        if parent_uuid is None:
            continue
        parent = rules_by_uuid.get(parent_uuid)
        if parent is None:
            raise ValueError(
                f"Domain rule '{item['logical_uuid']}' refers to missing parent '{parent_uuid}'"
            )
        rules_by_uuid[item["logical_uuid"]].parent_rule_id = parent.id
    db.flush()

    for item in state.get("rule_links", []):
        rule = rules_by_uuid.get(item["rule_logical_uuid"])
        if rule is None:
            raise ValueError(
                f"Rule link '{item['logical_uuid']}' refers to missing rule "
                f"'{item['rule_logical_uuid']}'"
            )
        validate_rule_link_target(
            item["target_kind"],
            item["target_logical_uuid"],
        )
        validate_rule_link_purpose(item["link_purpose"])
        db.add(
            RuleLinkModel(
                project_id=project_id,
                workspace_id=workspace_id,
                logical_uuid=item["logical_uuid"],
                rule_id=rule.id,
                target_kind=item["target_kind"],
                target_logical_uuid=item["target_logical_uuid"],
                link_purpose=item["link_purpose"],
                context_text=item.get("context_text", ""),
            )
        )

    db.flush()


def copy_rule_aggregate(
    db: Session,
    project_id: int,
    source_workspace_id: int,
    target_workspace_id: int,
) -> None:
    """Copy rule aggregates while preserving logical identities."""
    source_rules = db.scalars(
        select(DomainRuleModel).where(
            DomainRuleModel.workspace_id == source_workspace_id
        )
    ).all()
    copied_by_source_id: dict[int, DomainRuleModel] = {}
    for source in source_rules:
        copied = DomainRuleModel(
            project_id=project_id,
            workspace_id=target_workspace_id,
            logical_uuid=source.logical_uuid,
            title=source.title,
            statement=source.statement,
            origin=source.origin,
            confirmation_status=source.confirmation_status,
        )
        db.add(copied)
        copied_by_source_id[source.id] = copied
    db.flush()

    for source in source_rules:
        if source.parent_rule_id is not None:
            copied_by_source_id[source.id].parent_rule_id = copied_by_source_id[
                source.parent_rule_id
            ].id
    db.flush()

    source_links = db.scalars(
        select(RuleLinkModel).where(
            RuleLinkModel.workspace_id == source_workspace_id
        )
    ).all()
    for source in source_links:
        copied_rule = copied_by_source_id.get(source.rule_id)
        if copied_rule is None:
            raise ValueError(
                f"Rule link '{source.logical_uuid}' refers to a rule outside the source workspace"
            )
        db.add(
            RuleLinkModel(
                project_id=project_id,
                workspace_id=target_workspace_id,
                logical_uuid=source.logical_uuid,
                rule_id=copied_rule.id,
                target_kind=source.target_kind,
                target_logical_uuid=source.target_logical_uuid,
                link_purpose=source.link_purpose,
                context_text=source.context_text,
            )
        )

    db.flush()
