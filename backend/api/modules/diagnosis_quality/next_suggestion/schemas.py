from pydantic import BaseModel, Field
from backend.api.base_schema import CamelModel




class NextSuggestionResponseItem(CamelModel):
    source_type: str
    code: str
    title: str
    description: str
    status: str
    target: dict | None = None
    action: dict = Field(default_factory=dict)


class NextSuggestionResponse(CamelModel):
    project_id: str
    stage: str
    suggestion: NextSuggestionResponseItem | None


class NextSuggestionRediagnoseRequest(CamelModel):
    stage: str
