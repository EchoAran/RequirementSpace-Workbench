from pydantic import BaseModel, ConfigDict, Field

# CRUD Models
class FeatureCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    parent_id: int | None = Field(default=None)


class FeatureUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    actor_ids: list[int] | None = Field(default=None)


class FeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature_id: int
    name: str
    description: str
    parent_id: int | None = None
    child_ids: list[int] = []
    actor_ids: list[int] = []
    confirmation_status: str | None = None


# Generation Models
class FeatureGenerationDraftCreateRequest(BaseModel):
    project_id: str


class GeneratedFeaturePreview(BaseModel):
    feature_name: str
    feature_description: str
    actor_names: list[str] = []


class FeatureGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: str
    features: list[GeneratedFeaturePreview]


class FeatureGenerationConfirmResponse(BaseModel):
    project_id: str
    feature_count: int
    message: str = "features_created"


class FeatureGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"
