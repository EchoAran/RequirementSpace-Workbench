"""Deterministic graph traversal and path projection engine.

This module provides pure domain logic to analyze flow steps and transitions,
projecting execution paths with cycle protection and bounded traversal.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from backend.core.path_projection.models import (
    PathProjectionSummary,
    PathStepNode,
    PathTransitionEdge,
    ProjectedPath,
)


class PathProjectionEngine:
    """Deterministic path projection engine with bounded traversal and cycle protection."""

    MAX_TRAVERSAL_DEPTH = 50

    def __init__(
        self,
        steps: Sequence[PathStepNode],
        transitions: Sequence[PathTransitionEdge],
    ) -> None:
        self.step_by_id = {s.id: s for s in steps}
        self.steps = sorted(steps, key=lambda s: (s.position, s.logical_uuid))
        self.transitions = list(transitions)

        self.outgoing_by_source: dict[int, list[PathTransitionEdge]] = {}
        self.incoming_by_target: dict[int, list[PathTransitionEdge]] = {}
        for t in transitions:
            self.outgoing_by_source.setdefault(t.source_step_id, []).append(t)
            self.incoming_by_target.setdefault(t.target_step_id, []).append(t)

        for edges in self.outgoing_by_source.values():
            edges.sort(key=lambda e: (0 if e.is_default else 1, e.position, e.id))

    def _generate_path_id(self, entry_uuid: str, edge_uuids: list[str]) -> str:
        """Compute stable hash for path identity based on entry and transition sequence."""
        hasher = hashlib.sha256()
        hasher.update(entry_uuid.encode("utf-8"))
        for edge_uuid in edge_uuids:
            hasher.update(b":")
            hasher.update(edge_uuid.encode("utf-8"))
        return hasher.hexdigest()[:16]

    def _find_entry_steps(self) -> list[PathStepNode]:
        """Identify entry steps with in-degree zero."""
        return [
            s for s in self.steps
            if not self.incoming_by_target.get(s.id)
        ]

    def compute_projections(self) -> list[ProjectedPath]:
        """Execute deterministic path projections across the flow graph."""
        if not self.steps:
            return []

        entries = self._find_entry_steps()
        projections: list[ProjectedPath] = []
        global_visited_transition_ids: set[int] = set()
        global_visited_step_ids: set[int] = set()
        pending_branches: list[PathTransitionEdge] = []
        branch_index = 1

        if len(entries) == 1:
            main_entry = entries[0]
            main_path, branch_edges = self._traverse_path(
                start_step=main_entry,
                is_main=True,
                name="Main Path",
            )
            projections.append(main_path)
            global_visited_transition_ids.update(main_path.transition_ids)
            global_visited_step_ids.update(main_path.step_ids)
            pending_branches.extend(branch_edges)
        elif len(entries) > 1:
            for idx, entry in enumerate(entries, 1):
                path, branch_edges = self._traverse_path(
                    start_step=entry,
                    is_main=(idx == 1),
                    name=f"Alternative Path {idx} (Entry: {entry.name})",
                )
                if path.status == "complete":
                    path.status = "ambiguous"
                path.summary = f"Multiple flow entries detected: starting from {entry.name}"
                projections.append(path)
                global_visited_transition_ids.update(path.transition_ids)
                global_visited_step_ids.update(path.step_ids)
                pending_branches.extend(branch_edges)

        branch_index = self._process_pending_branches(
            pending_branches,
            projections,
            global_visited_transition_ids,
            global_visited_step_ids,
            branch_index,
        )

        self._sweep_unvisited_components(
            projections,
            global_visited_transition_ids,
            global_visited_step_ids,
            branch_index,
        )

        self._sweep_isolated_steps(
            projections,
            global_visited_step_ids,
        )

        return projections

    def _process_pending_branches(
        self,
        pending_branches: list[PathTransitionEdge],
        projections: list[ProjectedPath],
        global_visited_transition_ids: set[int],
        global_visited_step_ids: set[int],
        branch_index: int,
    ) -> int:
        """Traverse and append branches from the pending work queue."""
        while pending_branches:
            branch_edge = pending_branches.pop(0)
            if branch_edge.id in global_visited_transition_ids:
                continue
            branch_path, nested_branches = self._traverse_branch(branch_edge, branch_index)
            projections.append(branch_path)
            global_visited_transition_ids.update(branch_path.transition_ids)
            global_visited_step_ids.update(branch_path.step_ids)
            pending_branches.extend(nested_branches)
            branch_index += 1
        return branch_index

    def _sweep_unvisited_components(
        self,
        projections: list[ProjectedPath],
        global_visited_transition_ids: set[int],
        global_visited_step_ids: set[int],
        branch_index: int,
    ) -> None:
        """Sweep unvisited transitions to detect cycles and disconnected subgraphs."""
        while True:
            unvisited = [e for e in self.transitions if e.id not in global_visited_transition_ids]
            if not unvisited:
                break

            unvisited_targets = {e.target_step_id for e in unvisited}
            pseudo_entries = [e for e in unvisited if e.source_step_id not in unvisited_targets]

            if pseudo_entries:
                start_edge = min(
                    pseudo_entries,
                    key=lambda e: (self.step_by_id[e.source_step_id].position if e.source_step_id in self.step_by_id else 0, e.position),
                )
                is_pure_cycle = False
            else:
                start_edge = min(
                    unvisited,
                    key=lambda e: (self.step_by_id[e.source_step_id].position if e.source_step_id in self.step_by_id else 0, e.position),
                )
                is_pure_cycle = True

            comp_path, comp_nested = self._traverse_branch(start_edge, branch_index)
            if is_pure_cycle:
                comp_path.status = "cycle"
                if not projections:
                    comp_path.is_main = True
                    comp_path.name = "Cycle Analysis Path"
                    comp_path.summary = "No entry step with zero in-degree; flow forms a closed loop"
                else:
                    comp_path.summary = f"Disconnected cycle path ({len(comp_path.step_ids)} steps)"
            elif comp_path.status == "complete":
                comp_path.status = "ambiguous"
                comp_path.summary = f"Disconnected component path with {len(comp_path.step_ids)} steps"

            projections.append(comp_path)
            global_visited_transition_ids.update(comp_path.transition_ids)
            global_visited_step_ids.update(comp_path.step_ids)
            branch_index += 1

            branch_index = self._process_pending_branches(
                comp_nested,
                projections,
                global_visited_transition_ids,
                global_visited_step_ids,
                branch_index,
            )

    def _sweep_isolated_steps(
        self,
        projections: list[ProjectedPath],
        global_visited_step_ids: set[int],
    ) -> None:
        """Create single-node paths for steps that have no incident transitions."""
        for step in self.steps:
            if step.id not in global_visited_step_ids:
                path_id = self._generate_path_id(step.logical_uuid, [])
                projections.append(
                    ProjectedPath(
                        path_id=path_id,
                        name=f"Isolated Step: {step.name}",
                        is_main=(len(projections) == 0),
                        status="complete",
                        step_ids=[step.id],
                        step_logical_uuids=[step.logical_uuid],
                        transition_ids=[],
                        transition_logical_uuids=[],
                        summary=f"Single isolated step: {step.name}",
                    )
                )
                global_visited_step_ids.add(step.id)

    def _select_next_edge(
        self,
        outgoing: list[PathTransitionEdge],
        branches_to_visit: list[PathTransitionEdge],
    ) -> tuple[PathTransitionEdge | None, str]:
        """Select the next edge according to default preference and single outgoing rules."""
        default_edges = [e for e in outgoing if e.is_default]
        if default_edges:
            chosen = default_edges[0]
            for edge in outgoing:
                if edge.id != chosen.id:
                    branches_to_visit.append(edge)
            return chosen, "complete"
        if len(outgoing) == 1:
            return outgoing[0], "complete"
        for edge in outgoing:
            branches_to_visit.append(edge)
        return None, "ambiguous"

    def _traverse_path(
        self,
        start_step: PathStepNode,
        is_main: bool,
        name: str,
    ) -> tuple[ProjectedPath, list[PathTransitionEdge]]:
        """Traverse step transitions starting from an entry step."""
        current_step: PathStepNode | None = start_step
        visited_step_ids: set[int] = set()
        visited_transition_ids: set[int] = set()

        step_ids: list[int] = []
        step_uuids: list[str] = []
        transition_ids: list[int] = []
        transition_uuids: list[str] = []
        branches_to_visit: list[PathTransitionEdge] = []
        status = "complete"

        while current_step is not None:
            if current_step.id in visited_step_ids:
                status = "cycle"
                break
            if len(step_ids) >= self.MAX_TRAVERSAL_DEPTH:
                status = "truncated"
                break

            visited_step_ids.add(current_step.id)
            step_ids.append(current_step.id)
            step_uuids.append(current_step.logical_uuid)

            outgoing = self.outgoing_by_source.get(current_step.id, [])
            if not outgoing:
                status = "complete"
                break

            chosen_edge, edge_status = self._select_next_edge(outgoing, branches_to_visit)
            if chosen_edge is None:
                status = edge_status
                break

            if chosen_edge.id in visited_transition_ids:
                status = "cycle"
                break

            visited_transition_ids.add(chosen_edge.id)
            transition_ids.append(chosen_edge.id)
            transition_uuids.append(chosen_edge.logical_uuid)

            current_step = self.step_by_id.get(chosen_edge.target_step_id)
            if current_step is None:
                status = "ambiguous"
                break

        path_id = self._generate_path_id(start_step.logical_uuid, transition_uuids)
        summary = f"Path with {len(step_ids)} steps and {len(transition_ids)} transitions ({status})"
        projected = ProjectedPath(
            path_id=path_id,
            name=name,
            is_main=is_main,
            status=status,
            step_ids=step_ids,
            step_logical_uuids=step_uuids,
            transition_ids=transition_ids,
            transition_logical_uuids=transition_uuids,
            summary=summary,
        )
        return projected, branches_to_visit

    def _traverse_branch(
        self,
        branch_edge: PathTransitionEdge,
        index: int,
    ) -> tuple[ProjectedPath, list[PathTransitionEdge]]:
        """Traverse a branch starting with a divergent transition edge."""
        start_step = self.step_by_id.get(branch_edge.source_step_id)
        entry_uuid = start_step.logical_uuid if start_step else "unknown"

        step_ids: list[int] = [branch_edge.source_step_id]
        step_uuids: list[str] = [entry_uuid]
        transition_ids: list[int] = [branch_edge.id]
        transition_uuids: list[str] = [branch_edge.logical_uuid]

        visited_step_ids: set[int] = {branch_edge.source_step_id}
        visited_transition_ids: set[int] = {branch_edge.id}
        nested_branches: list[PathTransitionEdge] = []

        current_step = self.step_by_id.get(branch_edge.target_step_id)
        status = "complete"

        while current_step is not None:
            if current_step.id in visited_step_ids:
                status = "cycle"
                break
            if len(step_ids) >= self.MAX_TRAVERSAL_DEPTH:
                status = "truncated"
                break

            visited_step_ids.add(current_step.id)
            step_ids.append(current_step.id)
            step_uuids.append(current_step.logical_uuid)

            outgoing = self.outgoing_by_source.get(current_step.id, [])
            if not outgoing:
                status = "complete"
                break

            chosen_edge, edge_status = self._select_next_edge(outgoing, nested_branches)
            if chosen_edge is None:
                status = edge_status
                break

            if chosen_edge.id in visited_transition_ids:
                status = "cycle"
                break

            visited_transition_ids.add(chosen_edge.id)
            transition_ids.append(chosen_edge.id)
            transition_uuids.append(chosen_edge.logical_uuid)

            current_step = self.step_by_id.get(chosen_edge.target_step_id)

        branch_name = (
            f"Branch {index} ({branch_edge.label})"
            if branch_edge.label
            else f"Branch {index}"
        )
        path_id = self._generate_path_id(entry_uuid, transition_uuids)
        summary = f"Branch path with {len(step_ids)} steps ({status})"

        projected = ProjectedPath(
            path_id=path_id,
            name=branch_name,
            is_main=False,
            status=status,
            step_ids=step_ids,
            step_logical_uuids=step_uuids,
            transition_ids=transition_ids,
            transition_logical_uuids=transition_uuids,
            summary=summary,
        )
        return projected, nested_branches


def project_flow_paths(
    flow_id: int,
    steps: Sequence[Any],
    transitions: Sequence[Any],
) -> PathProjectionSummary:
    """Project paths for a flow and return an immutable summary."""
    step_nodes = [
        PathStepNode(
            id=getattr(s, "id", getattr(s, "step_id", 0)),
            logical_uuid=getattr(s, "logical_uuid", str(getattr(s, "id", getattr(s, "step_id", 0)))),
            position=getattr(s, "position", 0),
            name=getattr(s, "name", ""),
        )
        for s in steps
    ]
    transition_edges = [
        PathTransitionEdge(
            id=getattr(t, "id", getattr(t, "transition_id", 0)),
            logical_uuid=getattr(t, "logical_uuid", str(getattr(t, "id", getattr(t, "transition_id", 0)))),
            source_step_id=getattr(t, "source_step_id", 0),
            target_step_id=getattr(t, "target_step_id", 0),
            label=getattr(t, "label", "") or "",
                condition_text=t.condition_text or "",
            is_default=bool(getattr(t, "is_default", False)),
            position=getattr(t, "position", 0),
        )
        for t in transitions
    ]
    engine = PathProjectionEngine(step_nodes, transition_edges)
    paths = engine.compute_projections()
    is_truncated = any(p.status == "truncated" for p in paths)
    cycles_detected = any(p.status == "cycle" for p in paths)
    return PathProjectionSummary(
        flow_id=flow_id,
        total_paths=len(paths),
        paths=paths,
        is_truncated=is_truncated,
        cycles_detected=cycles_detected,
    )
