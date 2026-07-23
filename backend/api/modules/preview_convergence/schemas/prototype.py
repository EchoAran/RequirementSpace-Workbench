from datetime import datetime

from backend.api.base_schema import CamelModel




class PrototypePreviewGenerateRequest(CamelModel):
    force_regenerate: bool = True


class PrototypePageResponse(CamelModel):
    page_id: str
    role_id: int
    role_name: str
    feature_id: int
    feature_name: str
    html: str
    javascript: str
    css: str
    source: str
    status: str = "ready"


class PrototypePreviewResponse(CamelModel):
    prototype_id: int
    project_id: str
    html: str
    javascript: str
    css: str
    pages: list[PrototypePageResponse] = []
    source: str
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    shadow_draft_id: str | None = None


class PrototypePreviewNotFoundResponse(CamelModel):
    project_id: str
    message: str = "prototype_preview_not_found"
