from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .ir.schema import (
    ChoiceStatus,
    GraphPatch,
    IssueCategory,
    IssueStatus,
    NodeKind,
    NodeStatus,
    ProjectionKind,
    ScopeStatus,
    Severity,
    SlotArity,
    SlotStatus,
)


class WorkspaceBootstrapRequest(BaseModel):
    prompt: str = Field(min_length=1)


class NodeUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: NodeStatus | None = None
    scopeStatus: ScopeStatus | None = None
    confidence: float | None = None
    source: dict[str, Any] | None = None


class StatusUpdateRequest(BaseModel):
    status: NodeStatus


class ScopeUpdateRequest(BaseModel):
    scopeStatus: ScopeStatus


class IssueStatusRequest(BaseModel):
    status: IssueStatus


class IssueUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: Severity | None = None
    category: IssueCategory | None = None
    relatedNodeIds: list[str] | None = None
    suggestedProjection: ProjectionKind | None = None
    suggestedAction: str | None = None
    status: IssueStatus | None = None
    source: dict[str, Any] | None = None


class DiagnoseRequest(BaseModel):
    scope: dict[str, Any] | None = None


class CreateIssueRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    severity: Severity = Severity.MEDIUM
    category: IssueCategory = IssueCategory.MISSING
    relatedNodeIds: list[str] = Field(default_factory=list)
    suggestedProjection: ProjectionKind = ProjectionKind.GOAL
    suggestedAction: str = ""
    source: dict[str, Any] = Field(default_factory=lambda: {"type": "system"})


class AddChoiceRequest(BaseModel):
    title: str = Field(min_length=1)
    rationale: str = ""
    patch: dict[str, Any] = Field(default_factory=dict)
    impactPreview: dict[str, Any] = Field(default_factory=dict)
    status: ChoiceStatus | None = None


class ChoiceUpdateRequest(BaseModel):
    title: str | None = None
    rationale: str | None = None
    patch: dict[str, Any] | None = None
    status: ChoiceStatus | None = None


class CreateSlotRequest(BaseModel):
    ownerNodeId: str = Field(min_length=1)
    ownerProjection: ProjectionKind = ProjectionKind.GOAL
    name: str = Field(min_length=1)
    description: str = ""
    expectedKinds: list[NodeKind] = Field(default_factory=list)
    arity: SlotArity = SlotArity.MANY
    status: SlotStatus = SlotStatus.EMPTY
    context: dict[str, Any] = Field(default_factory=dict)


class SlotUpdateRequest(BaseModel):
    ownerNodeId: str | None = None
    ownerProjection: ProjectionKind | None = None
    name: str | None = None
    description: str | None = None
    expectedKinds: list[NodeKind] | None = None
    arity: SlotArity | None = None
    status: SlotStatus | None = None
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
