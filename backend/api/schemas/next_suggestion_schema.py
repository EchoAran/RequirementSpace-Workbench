from pydantic import BaseModel, Field


class NextSuggestionResponseItem(BaseModel):
    source_type: str
    code: str
    title: str
    description: str
    status: str
    target: dict | None = None
    action: dict = Field(default_factory=dict)


class NextSuggestionResponse(BaseModel):
    project_id: int
    stage: str
    suggestion: NextSuggestionResponseItem


class NextSuggestionStartRequest(BaseModel):
    stage: str
    suggestion_code: str
    target: dict | None = None
    query: str | None = None


class NextSuggestionStartResponse(BaseModel):
    project_id: int
    stage: str
    suggestion_code: str
    action_type: str
    action: dict
