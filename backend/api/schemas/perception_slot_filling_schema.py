from pydantic import BaseModel, Field
from backend.api.schemas.project_schema import CamelModel


class PerceptionSlotFillingDraftCreateRequest(CamelModel):
    project_id: int = Field(gt=0)
    perception_job_id: int = Field(gt=0)


class PerceptionSlotFilledActorPreview(CamelModel):
    actor_name: str
    actor_description: str


class PerceptionSlotFilledFeaturePreview(CamelModel):
    temporary_feature_id: int
    feature_name: str
    feature_description: str
    parent_temporary_feature_id: int | None = None
    parent_feature_id: int | None = None


class PerceptionSlotFilledScenarioPreview(CamelModel):
    feature_id: int
    feature_name: str
    actor_id: int
    actor_name: str
    scenario_name: str
    scenario_content: str


class PerceptionSlotFilledAcceptanceCriteriaPreview(CamelModel):
    scenario_id: int
    scenario_name: str
    acceptance_criteria: list[str]


class PerceptionSlotFilledBusinessObjectAttributePreview(CamelModel):
    business_object_attribute_name: str
    business_object_attribute_description: str
    business_object_attribute_type: str
    business_object_attribute_example: str


class PerceptionSlotFilledBusinessObjectPreview(CamelModel):
    business_object_id: int
    business_object_name: str
    business_object_description: str
    is_existing: bool = False
    business_object_attributes: list[
        PerceptionSlotFilledBusinessObjectAttributePreview
    ] = []


class PerceptionSlotFilledFlowStepPreview(CamelModel):
    step_name: str
    step_description: str
    step_type: str
    actor_names: list[str] = []
    input_business_object_names: list[str] = []
    output_business_object_names: list[str] = []
    next_step_names: list[str] = []


class PerceptionSlotFilledFlowPreview(CamelModel):
    flow_name: str
    flow_description: str
    feature_names: list[str] = []
    flow_steps: list[PerceptionSlotFilledFlowStepPreview] = []


class PerceptionSlotFillingDraftResponse(CamelModel):
    draft_id: str
    project_id: int
    perception_job_id: int
    filler_kind: str
    actors: list[PerceptionSlotFilledActorPreview] = []
    features: list[PerceptionSlotFilledFeaturePreview] = []
    scenarios: list[PerceptionSlotFilledScenarioPreview] = []
    scenario_acceptance_criteria: list[
        PerceptionSlotFilledAcceptanceCriteriaPreview
    ] = []
    business_objects: list[PerceptionSlotFilledBusinessObjectPreview] = []
    flows: list[PerceptionSlotFilledFlowPreview] = []


class PerceptionSlotFillingConfirmResponse(CamelModel):
    project_id: int
    filler_kind: str
    created_count: int = 0
    scenario_count: int = 0
    acceptance_criterion_count: int = 0
    business_object_count: int = 0
    flow_count: int = 0
    flow_step_count: int = 0
    message: str = "perception_slot_filled"


class PerceptionSlotFillingDraftDiscardResponse(CamelModel):
    draft_id: str
    message: str = "draft_discarded"
