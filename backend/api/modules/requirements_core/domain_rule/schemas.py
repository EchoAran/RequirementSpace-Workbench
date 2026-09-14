from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.api.base_schema import CamelModel


class RuleLinkCreateRequest(CamelModel):
    """Payload for creating a link between a rule and a target entity."""

    target_kind: str = Field(..., description="Kind of target entity, e.g. feature, scenario, flow.")
    target_logical_uuid: str = Field(..., description="Logical UUID of the linked target entity.")
    link_purpose: str = Field(default="applies_to", description="Purpose: source or applies_to.")
    context_text: str = Field(default="", description="Optional context or excerpt explaining the link.")


class TargetRuleLinksUpdateRequest(CamelModel):
    """Replace only the rules applying directly to a flow entity."""

    target_kind: Literal["flow", "flow_step", "flow_transition"]
    target_logical_uuid: str = Field(min_length=1)
    rule_ids: list[int]


class RuleLinkUpdateRequest(CamelModel):
    """Payload for updating a rule link under optimistic concurrency control."""

    target_kind: str | None = None
    target_logical_uuid: str | None = None
    link_purpose: str | None = None
    context_text: str | None = None
    last_seen_updated_at: datetime | None = None


class RuleLinkResponse(CamelModel):
    """Serialized representation of a rule link."""

    id: int
    logical_uuid: str
    project_id: int
    workspace_id: int
    rule_id: int
    target_kind: str
    target_logical_uuid: str
    link_purpose: str
    context_text: str
    created_at: datetime
    updated_at: datetime


class DomainRuleCreateRequest(CamelModel):
    """Payload for creating a new domain rule."""

    title: str = Field(..., description="Short title of the rule.")
    statement: str = Field(..., description="Full declarative statement of the business rule.")
    origin: str = Field(default="manual", description="Origin: manual, ai_generated, flow_refinement.")
    confirmation_status: str = Field(default="needs_confirmation", description="Confirmation status.")
    parent_rule_id: int | None = Field(default=None, description="Optional parent rule ID if refined.")


class DomainRuleUpdateRequest(CamelModel):
    """Payload for updating an existing domain rule."""

    title: str | None = Field(default=None, description="Updated title.")
    statement: str | None = Field(default=None, description="Updated statement.")
    origin: str | None = Field(default=None, description="Updated origin.")
    confirmation_status: str | None = Field(default=None, description="Updated confirmation status.")
    parent_rule_id: int | None = Field(default=None, description="Updated parent rule ID.")
    last_seen_updated_at: datetime | None = Field(default=None, description="Timestamp for optimistic lock checking.")


class DomainRuleResponse(CamelModel):
    """Serialized representation of a domain rule with attached links and child identifiers."""

    id: int
    logical_uuid: str
    project_id: int
    workspace_id: int
    parent_rule_id: int | None = None
    title: str
    statement: str
    origin: str
    confirmation_status: str
    links: list[RuleLinkResponse] = Field(default_factory=list)
    child_rule_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DomainRuleListResponse(CamelModel):
    """Collection of domain rules with count metadata."""

    rules: list[DomainRuleResponse]
    total: int
