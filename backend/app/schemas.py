from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkspaceBootstrapRequest(BaseModel):
    prompt: str = Field(min_length=1)


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
    addSlots: list[dict[str, Any]] | None = None
    updateSlots: list[dict[str, Any]] | None = None
    removeSlotIds: list[str] | None = None
    addIssues: list[dict[str, Any]] | None = None
    updateIssues: list[dict[str, Any]] | None = None
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
    patch: dict[str, Any] = Field(default_factory=dict)
    proposedNodeIds: list[str] = Field(default_factory=list)
    proposedLinkIds: list[str] = Field(default_factory=list)
    impactPreview: dict[str, Any] = Field(default_factory=dict)


class ChoiceUpdateRequest(BaseModel):
    title: str | None = None
    rationale: str | None = None
    patch: dict[str, Any] | None = None
    status: str | None = None


class CreateSlotRequest(BaseModel):
    ownerNodeId: str = Field(min_length=1)
    ownerProjection: str = "goal"
    name: str = Field(min_length=1)
    description: str = ""
    expectedKinds: list[str] = Field(default_factory=list)
    arity: str = "many"
    status: str = "empty"
    context: dict[str, Any] = Field(default_factory=dict)


class SlotUpdateRequest(BaseModel):
    ownerProjection: str | None = None
    name: str | None = None
    description: str | None = None
    expectedKinds: list[str] | None = None
    arity: str | None = None
    status: str | None = None
    choiceGroupId: str | None = None
    context: dict[str, Any] | None = None


class RewriteRequest(BaseModel):
    scope: dict[str, Any] = Field(default_factory=dict)
    instruction: str = Field(min_length=1)


class ImpactPreviewRequest(BaseModel):
    patch: dict[str, Any] | None = None
    choiceId: str | None = None


class WorkspaceListItem(BaseModel):
    id: str
    name: str
    idea: str
    updatedAt: str
    status: str
    issueCount: int
    nodeCount: int
