from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkspaceBootstrapRequest(BaseModel):
    prompt: str = Field(min_length=1)


class PromptAnalyzeRequest(BaseModel):
    prompt: str = Field(min_length=1)


class PromptAnalyzeResponse(BaseModel):
    taskType: str
    goals: list[str]
    actors: list[str]
    flows: list[str]
    objects: list[str]
    questions: list[str]


class NodeUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    scopeStatus: str | None = None
    confidence: float | None = None
    source: dict[str, Any] | None = None
    extra: dict[str, Any] | None = None


class StatusUpdateRequest(BaseModel):
    status: str


class ScopeUpdateRequest(BaseModel):
    scopeStatus: str


class IssueStatusRequest(BaseModel):
    status: str


class IssueUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    category: str | None = None
    relatedNodeIds: list[str] | None = None
    suggestedProjection: str | None = None
    suggestedAction: str | None = None
    status: str | None = None
    source: dict[str, Any] | None = None


class DiagnoseRequest(BaseModel):
    scope: dict[str, Any] | None = None


class GraphPatch(BaseModel):
    addNodes: list[dict[str, Any]] | None = None
    updateNodes: list[dict[str, Any]] | None = None
    removeNodeIds: list[str] | None = None
    addLinks: list[dict[str, Any]] | None = None
    removeLinkIds: list[str] | None = None
    updateSlots: list[dict[str, Any]] | None = None
    resolveIssueIds: list[str] | None = None


class CreateIssueRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    severity: str = "medium"
    category: str = "missing"
    relatedNodeIds: list[str] = Field(default_factory=list)
    suggestedProjection: str = "goal"
    suggestedAction: str = ""
    source: dict[str, Any] = Field(default_factory=lambda: {"type": "system"})


class AddChoiceRequest(BaseModel):
    title: str = Field(min_length=1)
    rationale: str = ""
    proposedNodeIds: list[str] = Field(default_factory=list)
    proposedLinkIds: list[str] = Field(default_factory=list)
    impactPreview: dict[str, Any] = Field(default_factory=dict)


class ChoiceUpdateRequest(BaseModel):
    title: str | None = None
    rationale: str | None = None
    status: str | None = None


class WorkspaceListItem(BaseModel):
    id: str
    name: str
    idea: str
    updatedAt: str
    status: str
    issueCount: int
    nodeCount: int
