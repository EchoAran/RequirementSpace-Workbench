from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from backend.api.base_schema import CamelModel

# CRUD Models
class FlowStepCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    step_type: str = Field(..., pattern="^(actorAction|systemAction|judgment)$")
    actor_ids: list[int] = Field(default_factory=list)
    input_business_object_ids: list[int] = Field(default_factory=list)
    output_business_object_ids: list[int] = Field(default_factory=list)
    next_step_ids: list[int] = Field(default_factory=list)


class FlowStepUpdateRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    step_type: str | None = Field(default=None, pattern="^(actorAction|systemAction|judgment)$")
    actor_ids: list[int] | None = Field(default=None)
    input_business_object_ids: list[int] | None = Field(default=None)
    output_business_object_ids: list[int] | None = Field(default=None)
    next_step_ids: list[int] | None = Field(default=None)
    last_seen_updated_at: datetime | None = Field(default=None)


class FlowStepResponse(BaseModel):
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
    next_step_ids: list[int] = []
    confirmation_status: str | None = None


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
    confirmation_status: str | None = None


# Generation Models
class FlowGenerationDraftCreateRequest(BaseModel):
    project_id: str


class GeneratedBusinessObjectAttributePreview(BaseModel):
    business_object_attribute_name: str
    business_object_attribute_description: str
    business_object_attribute_type: str
    business_object_attribute_example: str


class GeneratedBusinessObjectPreview(BaseModel):
    business_object_name: str
    business_object_description: str
    business_object_attributes: list[GeneratedBusinessObjectAttributePreview] = []


class GeneratedFlowStepPreview(BaseModel):
    step_name: str
    step_description: str
    step_type: str
    actor_names: list[str] = []
    input_business_object_names: list[str] = []
    output_business_object_names: list[str] = []
    next_step_names: list[str] = []


class GeneratedFlowPreview(BaseModel):
    flow_name: str
    flow_description: str
    feature_names: list[str] = []
    flow_steps: list[GeneratedFlowStepPreview] = []


class FlowGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: str
    generation_mode: str
    leaf_feature_count: int
    business_objects: list[GeneratedBusinessObjectPreview]
    flows: list[GeneratedFlowPreview]


class FlowGenerationConfirmResponse(BaseModel):
    project_id: str
    business_object_count: int
    flow_count: int
    flow_step_count: int
    message: str = "flows_created"


class FlowGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"
