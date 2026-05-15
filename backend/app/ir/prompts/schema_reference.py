from __future__ import annotations

import json

from ..schema import (
    AuditInfo,
    ChoiceGroupStatus,
    ChoiceStatus,
    GraphPatch,
    IssueCategory,
    IssueStatus,
    LinkStatus,
    LinkType,
    Meta,
    NodeKind,
    NodeStatus,
    ProjectionKind,
    ProjectionState,
    ProposalStatus,
    ScopeStatus,
    SlotArity,
    SlotStatus,
)


def _enum_values(enum_cls) -> str:
    return " / ".join(f"`{item.value}`" for item in enum_cls)


def _json_template(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


NODE_KIND_ENUM = _enum_values(NodeKind)
NODE_STATUS_ENUM = _enum_values(NodeStatus)
SCOPE_STATUS_ENUM = _enum_values(ScopeStatus)
LINK_TYPE_ENUM = _enum_values(LinkType)
LINK_STATUS_ENUM = _enum_values(LinkStatus)
PROJECTION_ENUM = _enum_values(ProjectionKind)
SLOT_ARITY_ENUM = _enum_values(SlotArity)
SLOT_STATUS_ENUM = _enum_values(SlotStatus)
CHOICE_GROUP_STATUS_ENUM = _enum_values(ChoiceGroupStatus)
CHOICE_STATUS_ENUM = _enum_values(ChoiceStatus)
ISSUE_CATEGORY_ENUM = _enum_values(IssueCategory)
ISSUE_STATUS_ENUM = _enum_values(IssueStatus)
PROPOSAL_STATUS_ENUM = _enum_values(ProposalStatus)

GRAPH_PATCH_FIELDS = tuple(GraphPatch.model_fields.keys())
GRAPH_PATCH_FIELDS_BULLETS = "\n".join(f"- {field}" for field in GRAPH_PATCH_FIELDS)

META_TEMPLATE = _json_template(Meta().model_dump(mode="json"))
PROJECTION_STATE_TEMPLATE = _json_template(ProjectionState().model_dump(mode="json"))
AUDIT_TEMPLATE = _json_template(AuditInfo().model_dump(mode="json"))
