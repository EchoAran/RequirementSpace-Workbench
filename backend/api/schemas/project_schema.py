from datetime import datetime
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )

class ProjectListItemResponse(CamelModel):
    id: str
    project_id: int
    name: str
    idea: str
    description: str
    updated_at: datetime
    status: str
    issue_count: int
    node_count: int

class ProjectDeleteResponse(CamelModel):
    project_id: int
    message: str = "project_deleted"

class ProjectUpdateRequest(CamelModel):
    name: str
    description: str

class ProjectUpdateResponse(CamelModel):
    project_id: int
    name: str
    description: str
    message: str = "project_updated"

# ----------------- Aggregated requirement space details -----------------

class PerceptionSlotDetail(CamelModel):
    kind: str = "perception_slot"
    perception_slot_id: int
    perception_kind: str
    perception_description: str

class ActorDetail(CamelModel):
    kind: str = "actor"
    actor_id: int
    actor_name: str
    actor_description: str

class ScopeDetail(CamelModel):
    kind: str = "scope"
    scope_id: int
    scope_status: str
    reason: str
    positive_summary: str | None = None
    negative_summary: str | None = None
    positive_picture_base64: str | None = None
    negative_picture_base64: str | None = None

class AcceptanceCriterionDetail(CamelModel):
    kind: str = "acceptance_criterion"
    criterion_id: int
    criterion_content: str

class ScenarioDetail(CamelModel):
    kind: str = "scenario"
    scenario_id: int
    scenario_name: str
    scenario_content: str
    feature_id: int
    actor_id: int
    acceptance_criteria: list[AcceptanceCriterionDetail] = []

class FeatureDetail(CamelModel):
    kind: str = "feature"
    feature_id: int
    feature_name: str
    feature_description: str
    actor_ids: list[int] = []
    parent_id: int | None = None
    children_ids: list[int] = []
    scenarios: list[ScenarioDetail] = []
    scope: ScopeDetail | None = None

class BusinessObjectAttributeDetail(CamelModel):
    kind: str = "business_object_attribute"
    business_object_attribute_id: int
    business_object_attribute_name: str
    business_object_attribute_description: str
    business_object_attribute_type: str
    business_object_attribute_example: str

class BusinessObjectDetail(CamelModel):
    kind: str = "business_object"
    business_object_id: int
    business_object_name: str
    business_object_description: str
    business_object_attributes: list[BusinessObjectAttributeDetail] = []

class FlowStepDetail(CamelModel):
    kind: str = "flow_step"
    step_id: int
    step_name: str
    step_description: str
    step_type: str
    actor_ids: list[int] = []
    input_business_object_ids: list[int] = []
    output_business_object_ids: list[int] = []
    next_step_ids: list[int] = []

class FlowDetail(CamelModel):
    kind: str = "flow"
    flow_id: int
    flow_name: str
    flow_description: str
    feature_ids: list[int] = []
    flow_steps: list[FlowStepDetail] = []

class ProjectDetailResponse(CamelModel):
    kind: str = "requirement_space"
    project_id: int
    project_name: str
    project_description: str
    user_requirements: str
    perception_slot: PerceptionSlotDetail | None = None
    actors: list[ActorDetail] = []
    features: list[FeatureDetail] = []
    business_objects: list[BusinessObjectDetail] = []
    flows: list[FlowDetail] = []

class ScopeImpactPreviewRequest(CamelModel):
    feature_id: int
    next_status: str

class ScopeImpactPreviewResponse(CamelModel):
    affected_scenarios: list[str] = []
    affected_flows: list[str] = []
    affected_business_objects: list[str] = []
    summary: str
