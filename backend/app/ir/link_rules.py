from __future__ import annotations

from typing import Final

from .schema import LinkType, NodeKind


LINK_RULES: Final[dict[LinkType, set[tuple[NodeKind, NodeKind]]]] = {
    LinkType.REALIZES: {
        (NodeKind.CAPABILITY, NodeKind.GOAL),
        (NodeKind.FLOW, NodeKind.TASK),
    },
    LinkType.SUPPORTS: {
        (NodeKind.TASK, NodeKind.CAPABILITY),
        (NodeKind.FLOW_STEP, NodeKind.TASK),
    },
    LinkType.PERFORMED_BY: {
        (NodeKind.TASK, NodeKind.ACTOR),
        (NodeKind.FLOW_STEP, NodeKind.ACTOR),
    },
    LinkType.OWNS: {
        (NodeKind.ACTOR, NodeKind.BUSINESS_OBJECT),
    },
    LinkType.PRECEDES: {
        (NodeKind.FLOW_STEP, NodeKind.FLOW_STEP),
    },
    LinkType.BRANCHES_TO: {
        (NodeKind.FLOW_STEP, NodeKind.FLOW_STEP),
    },
    LinkType.GUARDS: {
        (NodeKind.RULE, NodeKind.FLOW_STEP),
        (NodeKind.RULE, NodeKind.STATE_TRANSITION),
    },
    LinkType.READS: {
        (NodeKind.FLOW_STEP, NodeKind.BUSINESS_OBJECT),
        (NodeKind.SCREEN, NodeKind.BUSINESS_OBJECT),
    },
    LinkType.WRITES: {
        (NodeKind.FLOW_STEP, NodeKind.BUSINESS_OBJECT),
        (NodeKind.SCREEN, NodeKind.BUSINESS_OBJECT),
    },
    LinkType.CHANGES_STATE: {
        (NodeKind.FLOW_STEP, NodeKind.STATE_TRANSITION),
    },
    LinkType.CONTAINS: {
        (NodeKind.GOAL, NodeKind.CAPABILITY),
        (NodeKind.CAPABILITY, NodeKind.CAPABILITY),
        (NodeKind.BUSINESS_OBJECT, NodeKind.FIELD),
        (NodeKind.BUSINESS_OBJECT, NodeKind.STATE_MACHINE),
        (NodeKind.STATE_MACHINE, NodeKind.OBJECT_STATE),
        (NodeKind.STATE_MACHINE, NodeKind.STATE_TRANSITION),
        (NodeKind.SCREEN, NodeKind.UI_COMPONENT),
        (NodeKind.UI_COMPONENT, NodeKind.UI_COMPONENT),
    },
    LinkType.ACCESSIBLE_BY: {
        (NodeKind.SCREEN, NodeKind.ACTOR),
    },
    LinkType.BINDS_FIELD: {
        (NodeKind.UI_COMPONENT, NodeKind.FIELD),
    },
    LinkType.INVOKES_STEP: {
        (NodeKind.UI_COMPONENT, NodeKind.FLOW_STEP),
    },
    LinkType.DEPENDS_ON: {
        (NodeKind.CAPABILITY, NodeKind.CAPABILITY),
        (NodeKind.TASK, NodeKind.TASK),
        (NodeKind.TASK, NodeKind.CAPABILITY),
        (NodeKind.FLOW_STEP, NodeKind.FLOW_STEP),
    },
    LinkType.DIAGNOSES: set(),
}


def is_link_allowed(link_type: LinkType | str, source_kind: NodeKind | str, target_kind: NodeKind | str) -> bool:
    link = link_type if isinstance(link_type, LinkType) else LinkType(link_type)
    source = source_kind if isinstance(source_kind, NodeKind) else NodeKind(source_kind)
    target = target_kind if isinstance(target_kind, NodeKind) else NodeKind(target_kind)
    return (source, target) in LINK_RULES.get(link, set())
