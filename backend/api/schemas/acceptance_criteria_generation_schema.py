from pydantic import BaseModel, Field


class AcceptanceCriteriaGenerationDraftCreateRequest(BaseModel):
    project_id: int = Field(gt=0)
    scenario_ids: list[int] | None = None


class GeneratedAcceptanceCriteriaPreview(BaseModel):
    scenario_id: int
    scenario_name: str
    acceptance_criteria: list[str]


class AcceptanceCriteriaGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: int
    scenario_acceptance_criteria: list[GeneratedAcceptanceCriteriaPreview]


class AcceptanceCriteriaGenerationConfirmResponse(BaseModel):
    project_id: int
    acceptance_criterion_count: int
    message: str = "acceptance_criteria_created"


class AcceptanceCriteriaGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"
