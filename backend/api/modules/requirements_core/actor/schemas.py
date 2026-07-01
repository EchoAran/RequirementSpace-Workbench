from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from backend.api.base_schema import CamelModel

# CRUD Models
class ActorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")


class ActorUpdateRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    last_seen_updated_at: datetime | None = Field(default=None)


class ActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_id: int
    name: str
    description: str
    confirmation_status: str | None = None


# Generation Models
class ActorGenerationDraftCreateRequest(BaseModel):
    project_id: str


class GeneratedActorPreview(BaseModel):
    actor_name: str
    actor_description: str


class ActorGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: str
    actors: list[GeneratedActorPreview]


class ActorGenerationConfirmResponse(BaseModel):
    project_id: str
    actor_count: int
    message: str = "actors_created"


class ActorGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"
