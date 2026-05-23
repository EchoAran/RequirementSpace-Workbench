from pydantic import BaseModel, Field


class FeatureGenerationDraftCreateRequest(BaseModel):
    project_id: int = Field(gt=0)


class GeneratedFeaturePreview(BaseModel):
    feature_name: str
    feature_description: str
    actor_names: list[str] = []


class FeatureGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: int
    features: list[GeneratedFeaturePreview]


class FeatureGenerationConfirmResponse(BaseModel):
    project_id: int
    feature_count: int
    message: str = "features_created"


class FeatureGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"
