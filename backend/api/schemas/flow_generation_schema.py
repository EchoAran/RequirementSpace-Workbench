from pydantic import BaseModel, Field


class FlowGenerationDraftCreateRequest(BaseModel):
    project_id: int = Field(gt=0)

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
    project_id: int
    generation_mode: str
    leaf_feature_count: int
    business_objects: list[GeneratedBusinessObjectPreview]
    flows: list[GeneratedFlowPreview]

class FlowGenerationConfirmResponse(BaseModel):
    project_id: int
    business_object_count: int
    flow_count: int
    flow_step_count: int
    message: str = "flows_created"

class FlowGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"
