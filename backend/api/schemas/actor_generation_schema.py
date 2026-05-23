from pydantic import BaseModel, Field


class ActorGenerationDraftCreateRequest(BaseModel):
    project_id: int = Field(gt=0)


class GeneratedActorPreview(BaseModel):
    actor_name: str
    actor_description: str


class ActorGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: int
    actors: list[GeneratedActorPreview]


class ActorGenerationConfirmResponse(BaseModel):
    project_id: int
    actor_count: int
    message: str = "actors_created"


class ActorGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"
