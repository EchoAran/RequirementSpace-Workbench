from pydantic import BaseModel, Field
from backend.api.base_schema import CamelModel


class ProjectCreationDraftCreateRequest(BaseModel):
    user_requirements: str = Field(min_length=1)
    project_name: str | None = None
    project_description: str | None = None
    knowledge_workspace_id: str | None = None

class ProjectPreview(CamelModel):
    project_name: str
    project_description: str

class GeneratedActorPreview(CamelModel):
    actor_name: str
    actor_description: str

class GeneratedFeaturePreview(CamelModel):
    feature_number: str | None = None
    feature_name: str
    feature_description: str
    actor_names: list[str] = []

class ProjectCreationDraftResponse(CamelModel):
    draft_id: str
    user_requirements: str
    project_preview: ProjectPreview
    actors: list[GeneratedActorPreview]
    features: list[GeneratedFeaturePreview]

class ProjectCreationConfirmResponse(CamelModel):
    project_id: str
    project_name: str
    project_description: str
    message: str = "project_created"

class ProjectCreationDraftDiscardResponse(CamelModel):
    draft_id: str
    message: str = "draft_discarded"
