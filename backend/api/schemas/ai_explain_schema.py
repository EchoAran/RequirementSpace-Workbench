"""Schemas for AI-powered Q&A explanation endpoint."""

from pydantic import BaseModel, Field


class ExplainScope(BaseModel):
    kind: str = Field(..., pattern="^(node|projection|workspace)$")
    target_type: str | None = None
    target_id: int | None = None
    stage: str | None = None


class ExplainRequest(BaseModel):
    project_id: int = Field(gt=0)
    scope: ExplainScope
    question: str = Field(..., min_length=1)


class ExplainContextSummary(BaseModel):
    scope_label: str = ""
    objects_loaded: list[str] = Field(default_factory=list)


class ExplainResponse(BaseModel):
    answer: str
    context_summary: ExplainContextSummary = Field(default_factory=ExplainContextSummary)
