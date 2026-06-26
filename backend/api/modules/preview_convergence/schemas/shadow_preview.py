from backend.api.base_schema import CamelModel


from backend.api.modules.preview_convergence.schemas.prototype import PrototypePreviewResponse


class PreviewShadowDraftResponse(CamelModel):
    source: str  # "real_project" | "shadow_project"
    draft_id: str | None = None
    status: str  # "generating" | "ready" | "failed" | "committed" | "discarded" | "stale"
    unready_gates: list[str] = []
    shadow_summary: dict[str, int] = {}
    prototype_preview: PrototypePreviewResponse | None = None
    shadow_snapshot_json: dict | None = None
    error_message: str | None = None
    current_progress: int | None = None
    current_step_label: str | None = None


class PreviewShadowRegenerateRequest(CamelModel):
    user_feedback: str | None = None
