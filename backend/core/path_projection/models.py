"""Pure domain models for graph traversal and path projection."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PathStepNode:
    """Immutable representation of a step node in the path engine."""

    id: int
    logical_uuid: str
    position: int
    name: str


@dataclass(frozen=True)
class PathTransitionEdge:
    """Immutable representation of a directed transition edge in the path engine."""

    id: int
    logical_uuid: str
    source_step_id: int
    target_step_id: int
    label: str
    condition_text: str
    is_default: bool
    position: int


@dataclass
class ProjectedPath:
    """Represents a computed path projection across flow steps and transitions."""

    path_id: str
    name: str
    is_main: bool
    status: str  # "complete", "ambiguous", "cycle", "truncated"
    step_ids: list[int] = field(default_factory=list)
    step_logical_uuids: list[str] = field(default_factory=list)
    transition_ids: list[int] = field(default_factory=list)
    transition_logical_uuids: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass(frozen=True)
class PathProjectionSummary:
    """Summary of deterministic path projection analysis for a flow graph."""

    flow_id: int
    total_paths: int
    paths: list[ProjectedPath]
    is_truncated: bool
    cycles_detected: bool
