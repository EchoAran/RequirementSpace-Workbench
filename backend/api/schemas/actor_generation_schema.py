from pydantic import BaseModel, Field


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
