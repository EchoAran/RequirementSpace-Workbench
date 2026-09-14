"""Pydantic schemas for bounded flow refinement HTTP APIs and candidate payloads."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FlowRefinementRequest(BaseModel):
    """Request payload for initiating flow refinement."""
    model_config = ConfigDict(extra="forbid")

    target_kind: Literal["flow", "flow_step"]
    target_id: int
    focus_text: str | None = None
    source_finding_id: str | int | None = None
    candidate_count: int = Field(default=3, ge=1, le=5)


class RefinedStepItem(BaseModel):
    """Incrementally proposed step in refinement."""
    model_config = ConfigDict(extra="forbid")

    temp_id: str
    name: str
    description: str
    step_type: Literal["actorAction", "systemAction"] = "actorAction"
    actor_ids: list[int] = Field(default_factory=list)
    input_business_object_numbers: list[str] = Field(default_factory=list)
    output_business_object_numbers: list[str] = Field(default_factory=list)


class RefinedTransitionItem(BaseModel):
    """Incrementally proposed transition in refinement."""
    model_config = ConfigDict(extra="forbid")

    temp_id: str
    source_step_ref: str | int
    target_step_ref: str | int
    label: str
    condition_text: str = ""
    is_default: bool = False
    semantic_tags: list[str] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)


class RefinedTransitionUpdateItem(BaseModel):
    """Proposed condition update on an existing transition."""
    model_config = ConfigDict(extra="forbid")

    logical_uuid: str
    label: str | None = None
    condition_text: str | None = None
    semantic_tags: list[str] | None = None
    rule_refs: list[str] | None = None


class RefinedRuleItem(BaseModel):
    """Elaborated domain rule anchored to existing rules or WHAT evidence."""
    model_config = ConfigDict(extra="forbid")

    temp_id: str
    title: str
    statement: str
    parent_rule_ref: str | None = None
    confirmation_status: Literal["ai_assumption"] = "ai_assumption"
    source_links: list[dict[str, Any]] = Field(default_factory=list)


class RefinedRuleLinkItem(BaseModel):
    """Link connecting rule to transition or step."""
    model_config = ConfigDict(extra="forbid")

    rule_ref: str
    target_kind: Literal["flow", "flow_transition", "flow_step", "feature", "scenario", "knowledge"]
    target_ref: str
    link_purpose: str = "applies_to"
    context_text: str | None = None


class BusinessObjectAttributeItem(BaseModel):
    """Attribute on newly proposed business object."""
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    data_type: str = "string"
    example: str = ""


class RefinedBusinessObjectItem(BaseModel):
    """Incrementally proposed business object in refinement."""
    model_config = ConfigDict(extra="forbid")

    business_object_number: str
    business_object_name: str
    business_object_description: str = ""
    business_object_attributes: list[BusinessObjectAttributeItem] = Field(default_factory=list)


class FlowRefinementCandidatePayload(BaseModel):
    """Persisted candidate payload for ChoiceGroup storage."""
    model_config = ConfigDict(extra="forbid")

    project_id: int
    workspace_id: int
    target_flow_id: int
    target_flow_logical_uuid: str = ""
    target_kind: str = "flow"
    target_id: int | None = None
    source_finding_id: str | int | None = None
    expected_workspace_version: str | None = None
    context_hash: str | None = None
    rationale: str = ""
    steps_added: list[dict[str, Any]] = Field(default_factory=list)
    transitions_added: list[dict[str, Any]] = Field(default_factory=list)
    transitions_updated: list[dict[str, Any]] = Field(default_factory=list)
    rules_added: list[dict[str, Any]] = Field(default_factory=list)
    rule_links_added: list[dict[str, Any]] = Field(default_factory=list)
    business_objects_added: list[RefinedBusinessObjectItem] = Field(default_factory=list)
    step_object_links_added: list[dict[str, Any]] = Field(default_factory=list)
    done_empty: bool = False


class FlowRefinementPreviewResponse(BaseModel):
    """Response payload for choice group preview."""
    model_config = ConfigDict(extra="ignore")

    target_flow_id: int
    target_flow_name: str
    expected_workspace_version: str
    steps_added_count: int
    transitions_added_count: int
    transitions_updated_count: int
    rules_added_count: int
    steps_added: list[dict[str, Any]]
    transitions_added: list[dict[str, Any]]
    transitions_updated: list[dict[str, Any]]
    rules_added: list[dict[str, Any]]
    assumptions: list[str]
    rule_links_added: list[dict[str, Any]] = Field(default_factory=list)
    business_objects_added: list[dict[str, Any]] = Field(default_factory=list)
    step_object_links_added: list[dict[str, Any]] = Field(default_factory=list)
    done_empty: bool = False
