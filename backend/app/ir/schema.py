from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RequirementSpaceIR(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    idea: str

    meta: dict[str, Any] = Field(default_factory=dict)

    nodes: dict[str, dict[str, Any]] = Field(default_factory=dict)
    links: list[dict[str, Any]] = Field(default_factory=list)

    slots: dict[str, dict[str, Any]] = Field(default_factory=dict)
    choiceGroups: dict[str, dict[str, Any]] = Field(default_factory=dict)
    proposals: dict[str, dict[str, Any]] = Field(default_factory=dict)
    issues: dict[str, dict[str, Any]] = Field(default_factory=dict)

    projections: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}
