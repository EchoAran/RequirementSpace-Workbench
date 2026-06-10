from pydantic import BaseModel, Field


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
