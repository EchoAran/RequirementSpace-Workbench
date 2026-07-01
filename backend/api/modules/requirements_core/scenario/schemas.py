from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from backend.api.base_schema import CamelModel

# CRUD Models
class AcceptanceCriterionCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    position: int | None = Field(default=None)


class AcceptanceCriterionUpdateRequest(CamelModel):
    content: str = Field(..., min_length=1)
    last_seen_updated_at: datetime | None = Field(default=None)


class AcceptanceCriterionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    criterion_id: int
    scenario_id: int
    content: str
    position: int
    confirmation_status: str | None = None


class ScenarioCreateRequest(BaseModel):
    feature_id: int
    actor_id: int
    name: str = Field(..., min_length=1, max_length=255)
    content: str = Field(default="")


class ScenarioUpdateRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None)
    last_seen_updated_at: datetime | None = Field(default=None)


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: int
    feature_id: int
    actor_id: int
    name: str
    content: str
    acceptance_criteria: list[AcceptanceCriterionResponse] = []
    confirmation_status: str | None = None


# Generation Models - Scenario
class ScenarioGenerationFullDraftCreateRequest(BaseModel):
    project_id: str


class ScenarioGenerationSingleDraftCreateRequest(BaseModel):
    project_id: str
    feature_id: int = Field(gt=0)


class GeneratedScenarioPreview(BaseModel):
    feature_id: int
    feature_name: str
    actor_id: int
    actor_name: str
    scenario_name: str
    scenario_content: str
    acceptance_criteria: list[str] = []


class ScenarioGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: str
    generation_mode: str
    feature_id: int | None = None
    scenarios: list[GeneratedScenarioPreview]


class ScenarioGenerationConfirmRequest(BaseModel):
    generate_acceptance_criteria: bool = False


class ScenarioGenerationConfirmResponse(BaseModel):
    project_id: str
    scenario_count: int
    acceptance_criterion_count: int = 0
    message: str = "scenarios_created"


class ScenarioGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"


# Generation Models - AC
class AcceptanceCriteriaGenerationFullDraftCreateRequest(BaseModel):
    project_id: str


class AcceptanceCriteriaGenerationSingleDraftCreateRequest(BaseModel):
    project_id: str
    scenario_id: int = Field(gt=0)


class AcceptanceCriteriaGenerationBatchDraftCreateRequest(BaseModel):
    project_id: str
    scenario_ids: list[int]


class GeneratedAcceptanceCriteriaPreview(BaseModel):
    scenario_id: int
    scenario_name: str
    acceptance_criteria: list[str]


class AcceptanceCriteriaGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: str
    scenario_acceptance_criteria: list[GeneratedAcceptanceCriteriaPreview]


class AcceptanceCriteriaGenerationConfirmResponse(BaseModel):
    project_id: str
    acceptance_criterion_count: int
    message: str = "acceptance_criteria_created"


class AcceptanceCriteriaGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"


# Legacy compatibility aliases
ACCreateRequest = AcceptanceCriterionCreateRequest
ACUpdateRequest = AcceptanceCriterionUpdateRequest
ACResponse = AcceptanceCriterionResponse
