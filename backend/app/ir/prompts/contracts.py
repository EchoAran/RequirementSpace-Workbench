from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InitializeWorkspaceInput(BaseModel):
    idea: str = Field(min_length=1)
    schemaVersion: str = "0.2"
    templateHints: list[str] = Field(default_factory=list)


class InitializeWorkspaceOutput(BaseModel):
    ir: dict[str, Any]


class ExpandSlotInput(BaseModel):
    slot: dict[str, Any]
    ownerNode: dict[str, Any]
    relatedNodes: list[dict[str, Any]] = Field(default_factory=list)
    relatedLinks: list[dict[str, Any]] = Field(default_factory=list)
    projectionContext: str = "system"


class ExpandSlotOutput(BaseModel):
    choiceGroup: dict[str, Any]


class RewriteInput(BaseModel):
    workspaceId: str
    scope: dict[str, Any] = Field(default_factory=dict)
    instruction: str = Field(min_length=1)
    irSlice: dict[str, Any] = Field(default_factory=dict)


class RewriteOutput(BaseModel):
    proposal: dict[str, Any]
