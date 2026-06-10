from pydantic import BaseModel, Field


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
