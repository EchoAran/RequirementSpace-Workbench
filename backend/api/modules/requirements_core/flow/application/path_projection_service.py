"""Application service for computing path projections of a flow.

This module coordinates loading steps and transitions for a given flow and
invoking the pure domain PathProjectionEngine to produce deterministic,
bounded, read-only path projections.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.path_projection import (
    PathProjectionEngine,
    PathStepNode,
    PathTransitionEdge,
)
from backend.api.modules.requirements_core.flow.schemas import (
    PathProjectionItem,
    PathProjectionResponse,
)
from backend.core.logging.events import (
    PATH_PROJECTION_AMBIGUOUS,
    PATH_PROJECTION_COMPLETE,
    PATH_PROJECTION_CYCLE,
    PATH_PROJECTION_TRUNCATED,
)
from backend.core.observability import emit_how_lifecycle_event
from backend.database.model import FlowModel, FlowStepModel, FlowTransitionModel


class PathProjectionService:
    """Service providing path projections for a flow."""

    async def get_path_projections(
        self,
        project_id: int,
        flow_id: int,
        session: AsyncSession,
        workspace_id: int,
    ) -> PathProjectionResponse:
        """Compute path projections for a given flow.

        Args:
            project_id: Owning project ID.
            flow_id: Target flow ID.
            session: Database session.
            workspace_id: Optional branch workspace ID.

        Returns:
            PathProjectionResponse containing list of projected paths.

        Raises:
            HTTPException: 404 if flow is not found.
        """
        # Ensure flow exists in project and workspace
        flow_stmt = select(FlowModel).where(
            FlowModel.id == flow_id,
            FlowModel.project_id == project_id,
            FlowModel.workspace_id == workspace_id,
        )
        flow_res = await session.execute(flow_stmt)
        flow = flow_res.scalar_one_or_none()
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")

        # Load steps
        steps_stmt = (
            select(FlowStepModel)
            .where(
                FlowStepModel.flow_id == flow_id,
                FlowStepModel.workspace_id == workspace_id,
            )
            .order_by(FlowStepModel.position, FlowStepModel.id)
        )
        steps_res = await session.execute(steps_stmt)
        db_steps = steps_res.scalars().all()

        # Load transitions
        trans_stmt = (
            select(FlowTransitionModel)
            .where(
                FlowTransitionModel.flow_id == flow_id,
                FlowTransitionModel.workspace_id == workspace_id,
            )
            .order_by(FlowTransitionModel.position, FlowTransitionModel.id)
        )
        trans_res = await session.execute(trans_stmt)
        db_transitions = trans_res.scalars().all()

        # Map to domain structures
        domain_steps = [
            PathStepNode(
                id=s.id,
                logical_uuid=s.logical_uuid,
                position=s.position,
                name=s.name,
            )
            for s in db_steps
        ]
        domain_transitions = [
            PathTransitionEdge(
                id=t.id,
                logical_uuid=t.logical_uuid,
                source_step_id=t.source_step_id,
                target_step_id=t.target_step_id,
                label=t.label,
                condition_text=t.condition_text,
                is_default=t.is_default,
                position=t.position,
            )
            for t in db_transitions
        ]

        engine = PathProjectionEngine(domain_steps, domain_transitions)
        projected_paths = engine.compute_projections()

        emit_how_lifecycle_event(
            PATH_PROJECTION_COMPLETE,
            capability="path_projection",
            project_id=project_id,
            workspace_id=workspace_id,
            flow_logical_uuid=flow.logical_uuid,
            path_count=len(projected_paths),
        )
        status_events = {
            "ambiguous": PATH_PROJECTION_AMBIGUOUS,
            "cycle": PATH_PROJECTION_CYCLE,
            "truncated": PATH_PROJECTION_TRUNCATED,
        }
        observed_statuses = {
            str(path.status).lower()
            for path in projected_paths
        }
        for status, event_name in status_events.items():
            if any(status in value for value in observed_statuses):
                emit_how_lifecycle_event(
                    event_name,
                    capability="path_projection",
                    project_id=project_id,
                    workspace_id=workspace_id,
                    flow_logical_uuid=flow.logical_uuid,
                    affected_path_count=sum(
                        status in str(path.status).lower()
                        for path in projected_paths
                    ),
                )

        response_items = [
            PathProjectionItem(
                path_id=p.path_id,
                name=p.name,
                is_main=p.is_main,
                status=p.status,
                step_ids=p.step_ids,
                step_logical_uuids=p.step_logical_uuids,
                transition_ids=p.transition_ids,
                transition_logical_uuids=p.transition_logical_uuids,
                summary=p.summary,
            )
            for p in projected_paths
        ]

        return PathProjectionResponse(flow_id=flow_id, paths=response_items)
