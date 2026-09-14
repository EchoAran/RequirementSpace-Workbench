from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import (
    DomainRuleModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
)

from .common import _CommitIdMaps, _resolve_id


async def _load_scoped_entity(
    model,
    entity_id: int,
    project_id: int,
    workspace_id: int,
    session: AsyncSession,
):
    entity = (
        await session.execute(
            select(model).where(
                model.id == entity_id,
                model.project_id == project_id,
                model.workspace_id == workspace_id,
            )
        )
    ).scalars().first()
    if entity is None:
        raise ValueError(f"shadow_commit_target_not_found:{model.__tablename__}:{entity_id}")
    return entity


async def apply_how_removals(
    project_id: int,
    workspace_id: int,
    patch: dict,
    session: AsyncSession,
) -> None:
    for reference in patch.get("rule_links_removed", []):
        link = await _load_scoped_entity(
            RuleLinkModel,
            _resolve_id(reference, {}),
            project_id,
            workspace_id,
            session,
        )
        await session.delete(link)
    await session.flush()

    for reference in patch.get("flow_transitions_removed", []):
        transition = await _load_scoped_entity(
            FlowTransitionModel,
            _resolve_id(reference, {}),
            project_id,
            workspace_id,
            session,
        )
        linked = (
            await session.execute(
                select(RuleLinkModel.id).where(
                    RuleLinkModel.project_id == project_id,
                    RuleLinkModel.workspace_id == workspace_id,
                    RuleLinkModel.target_kind == "flow_transition",
                    RuleLinkModel.target_logical_uuid == transition.logical_uuid,
                )
            )
        ).first()
        if linked is not None:
            raise ValueError("shadow_transition_has_rule_links")
        await session.delete(transition)
    await session.flush()

    for reference in patch.get("domain_rules_removed", []):
        rule = await _load_scoped_entity(
            DomainRuleModel,
            _resolve_id(reference, {}),
            project_id,
            workspace_id,
            session,
        )
        linked = (
            await session.execute(
                select(RuleLinkModel.id).where(
                    RuleLinkModel.rule_id == rule.id,
                    RuleLinkModel.workspace_id == workspace_id,
                )
            )
        ).first()
        child = (
            await session.execute(
                select(DomainRuleModel.id).where(
                    DomainRuleModel.parent_rule_id == rule.id,
                    DomainRuleModel.workspace_id == workspace_id,
                )
            )
        ).first()
        if linked is not None:
            raise ValueError("shadow_rule_has_links")
        if child is not None:
            raise ValueError("shadow_rule_has_children")
        await session.delete(rule)
    await session.flush()


async def apply_how_updates(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    resolve_target_logical_uuid,
    session: AsyncSession,
) -> None:
    for update in patch.get("domain_rules_updated", []):
        rule = await _load_scoped_entity(
            DomainRuleModel,
            id_maps.resolve_domain_rule(update["rule_ref"]),
            project_id,
            workspace_id,
            session,
        )
        for field_name in ("title", "statement", "origin", "confirmation_status"):
            if field_name in update:
                setattr(rule, field_name, update[field_name])
        if "parent_ref" in update:
            rule.parent_rule_id = (
                id_maps.resolve_domain_rule(update["parent_ref"])
                if update["parent_ref"] is not None
                else None
            )

    for update in patch.get("rule_links_updated", []):
        link = await _load_scoped_entity(
            RuleLinkModel,
            _resolve_id(update["rule_link_ref"], {}),
            project_id,
            workspace_id,
            session,
        )
        if "rule_ref" in update:
            link.rule_id = id_maps.resolve_domain_rule(update["rule_ref"])
        if "target_kind" in update:
            link.target_kind = update["target_kind"]
            link.target_logical_uuid = await resolve_target_logical_uuid(
                update["target_kind"],
                update["target_ref"],
                id_maps,
                session,
            )
        for field_name in ("link_purpose", "context_text"):
            if field_name in update:
                setattr(link, field_name, update[field_name])

    for update in patch.get("flow_transitions_updated", []):
        transition = await _load_scoped_entity(
            FlowTransitionModel,
            id_maps.resolve_transition(update["transition_ref"]),
            project_id,
            workspace_id,
            session,
        )
        for field_name, target_name in (
            ("source_step_ref", "source_step_id"),
            ("target_step_ref", "target_step_id"),
        ):
            if field_name in update:
                step_id = id_maps.resolve_step(update[field_name])
                step = await _load_scoped_entity(
                    FlowStepModel,
                    step_id,
                    project_id,
                    workspace_id,
                    session,
                )
                if step.flow_id != transition.flow_id:
                    raise ValueError("shadow_transition_step_outside_flow")
                setattr(transition, target_name, step_id)
        for field_name in (
            "label",
            "condition_text",
            "is_default",
            "position",
            "origin",
            "confirmation_status",
        ):
            if field_name in update:
                setattr(transition, field_name, update[field_name])
        if "semantic_tags" in update:
            transition.semantic_tags = sorted(set(update["semantic_tags"]))
    await session.flush()
