from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.api.base_schema import CamelModel


# CRUD Models
class FlowStepCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    step_type: str = Field(..., pattern="^(actorAction|systemAction|judgment)$")
    actor_ids: list[int] = Field(default_factory=list)
    input_business_object_ids: list[int] = Field(default_factory=list)
    output_business_object_ids: list[int] = Field(default_factory=list)


class FlowStepUpdateRequest(CamelModel):
    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    step_type: str | None = Field(default=None, pattern="^(actorAction|systemAction|judgment)$")
    actor_ids: list[int] | None = Field(default=None)
    input_business_object_ids: list[int] | None = Field(default=None)
    output_business_object_ids: list[int] | None = Field(default=None)
    last_seen_updated_at: datetime | None = Field(default=None)


class FlowStepResponse(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: int
    flow_id: int
    position: int
    name: str
    description: str
    step_type: str
    actor_ids: list[int] = []
    input_business_object_ids: list[int] = []
    output_business_object_ids: list[int] = []
    confirmation_status: str | None = None


class FlowTransitionCreateRequest(CamelModel):
    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    source_step_id: int
    target_step_id: int
    label: str = Field(default="", max_length=255)
    condition_text: str = Field(default="")
    is_default: bool = Field(default=False)
    position: int | None = Field(default=None, ge=0)
    semantic_tags: list[str] = Field(default_factory=list)
    rule_ids: list[int] = Field(default_factory=list)
    origin: str = Field(default="manual")
    confirmation_status: str = Field(default="confirmed")


class FlowTransitionUpdateRequest(CamelModel):
    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    label: str | None = Field(default=None, max_length=255)
    condition_text: str | None = Field(default=None)
    is_default: bool | None = Field(default=None)
    position: int | None = Field(default=None, ge=0)
    semantic_tags: list[str] | None = Field(default=None)
    rule_ids: list[int] | None = Field(default=None)
    confirmation_status: str | None = Field(default=None)
    last_seen_updated_at: datetime | None = Field(default=None)


class FlowTransitionResponse(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    logical_uuid: str
    project_id: int
    workspace_id: int
    flow_id: int
    source_step_id: int
    target_step_id: int
    label: str = ""
    condition_text: str = ""
    is_default: bool = False
    position: int = 0
    semantic_tags: list[str] = []
    origin: str = "manual"
    confirmation_status: str = "confirmed"
    rule_ids: list[int] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PathProjectionItem(CamelModel):
    path_id: str
    name: str
    is_main: bool
    status: str
    step_ids: list[int] = []
    step_logical_uuids: list[str] = []
    transition_ids: list[int] = []
    transition_logical_uuids: list[str] = []
    summary: str = ""


class PathProjectionResponse(CamelModel):
    flow_id: int
    paths: list[PathProjectionItem] = []


class ObjectUsageAttributeItem(CamelModel):
    id: int
    name: str
    data_type: str
    description: str = ""
    example: str = ""


class ObjectUsageProjectionItem(CamelModel):
    business_object_id: int
    logical_uuid: str
    name: str
    description: str = ""
    confirmation_status: str = "confirmed"
    attributes: list[ObjectUsageAttributeItem] = []
    used_by_step_ids: list[int] = []
    input_at_step_ids: list[int] = []
    output_at_step_ids: list[int] = []
    other_flows_count: int = 0
    other_flow_names: list[str] = []


class FlowObjectUsageResponse(CamelModel):
    flow_id: int
    objects: list[ObjectUsageProjectionItem] = []


class FlowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    feature_ids: list[int] = Field(default_factory=list)


class FlowUpdateRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    feature_ids: list[int] | None = Field(default=None)
    last_seen_updated_at: datetime | None = Field(default=None)


class FlowStepsReorderRequest(BaseModel):
    step_ids: list[int] = Field(..., min_length=1)


class FlowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    flow_id: int
    name: str
    description: str
    feature_ids: list[int] = []
    steps: list[FlowStepResponse] = []
    transitions: list[FlowTransitionResponse] = []
    confirmation_status: str | None = None


# Generation Models
class FlowGenerationDraftCreateRequest(BaseModel):
    project_id: str


class GeneratedBusinessObjectAttributePreview(CamelModel):
    business_object_attribute_name: str
    business_object_attribute_description: str
    business_object_attribute_type: str
    business_object_attribute_example: str


class GeneratedBusinessObjectPreview(CamelModel):
    business_object_name: str
    business_object_description: str
    business_object_attributes: list[GeneratedBusinessObjectAttributePreview] = []


class GeneratedFlowStepPreview(CamelModel):
    step_name: str
    step_description: str
    step_type: str
    rule_refs: list[str] = Field(default_factory=list)
    actor_names: list[str] = []
    input_business_object_names: list[str] = []
    output_business_object_names: list[str] = []


class GeneratedFlowTransitionPreview(CamelModel):
    source_step_name: str
    target_step_name: str
    label: str = ""
    condition_text: str = ""
    is_default: bool = False
    position: int = 0
    semantic_tags: list[str] = []
    rule_refs: list[str] = Field(default_factory=list)


class GeneratedFlowPreview(CamelModel):
    flow_name: str
    flow_description: str
    rule_refs: list[str] = Field(default_factory=list)
    feature_names: list[str] = []
    flow_steps: list[GeneratedFlowStepPreview] = []
    flow_transitions: list[GeneratedFlowTransitionPreview] = []


class FlowGenerationDraftResponse(CamelModel):
    draft_id: str
    project_id: str
    generation_mode: str
    leaf_feature_count: int
    business_objects: list[GeneratedBusinessObjectPreview]
    flows: list[GeneratedFlowPreview]


class FlowGenerationConfirmResponse(CamelModel):
    project_id: str
    business_object_count: int
    flow_count: int
    flow_step_count: int
    message: str = "flows_created"


class FlowGenerationDraftDiscardResponse(CamelModel):
    draft_id: str
    message: str = "draft_discarded"
