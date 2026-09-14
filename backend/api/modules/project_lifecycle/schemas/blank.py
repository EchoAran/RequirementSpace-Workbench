from pydantic import BaseModel, Field
from backend.api.base_schema import CamelModel


class BlankProjectCreateRequest(BaseModel):
    user_requirements: str = Field(min_length=1)
    project_name: str | None = None
    project_description: str | None = None
    knowledge_workspace_id: str | None = None


class BlankProjectCreateResponse(CamelModel):
    project_id: str
    project_name: str
    project_description: str
    message: str = "project_created"
