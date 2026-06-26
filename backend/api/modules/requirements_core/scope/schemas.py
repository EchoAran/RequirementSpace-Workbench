from pydantic import BaseModel, ConfigDict, Field

# CRUD Schemas
class ScopeUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(current|postponed|exclude)$")
    reason: str = Field(default="")
    positive_summary: str | None = Field(default=None)
    negative_summary: str | None = Field(default=None)


class ScopeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope_id: int
    feature_id: int
    status: str
    reason: str
    positive_summary: str | None = None
    negative_summary: str | None = None
    positive_picture_base64: str | None = None
    negative_picture_base64: str | None = None
    kano_category: str | None = None
    kano_category_name: str | None = None
    confirmation_status: str | None = None


# Generation Schemas
class ScopeGenerationDraftCreateRequest(BaseModel):
    project_id: str


class GeneratedScopePreview(BaseModel):
    feature_id: int
    feature_name: str
    scope_status: str
    reason: str
    positive_summary: str | None = None
    negative_summary: str | None = None
    positive_picture_base64: str | None = None
    negative_picture_base64: str | None = None
    kano_category: str | None = None
    kano_category_name: str | None = None


class ScopeGenerationDraftResponse(BaseModel):
    draft_id: str
    project_id: str
    scopes: list[GeneratedScopePreview]


class ScopeGenerationConfirmResponse(BaseModel):
    project_id: str
    scope_count: int
    message: str = "scopes_created"


class ScopeGenerationDraftDiscardResponse(BaseModel):
    draft_id: str
    message: str = "draft_discarded"
