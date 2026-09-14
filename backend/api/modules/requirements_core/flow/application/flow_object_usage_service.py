"""Application service for computing business object usage projection of a flow."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.modules.requirements_core.flow.schemas import (
    FlowObjectUsageResponse,
    ObjectUsageAttributeItem,
    ObjectUsageProjectionItem,
)
from backend.database.model import (
    BusinessObjectModel,
    FlowModel,
    FlowStepModel,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)


class FlowObjectUsageService:
    """Service providing business object usage projection for a flow."""

    async def get_flow_object_usage(
        self,
        project_id: int,
        flow_id: int,
        session: AsyncSession,
        workspace_id: int,
    ) -> FlowObjectUsageResponse:
        """Compute business object usage projection for a given flow.

        Args:
            project_id: Owning project ID.
            flow_id: Target flow ID.
            session: Database session.
            workspace_id: Optional branch workspace ID.

        Returns:
            FlowObjectUsageResponse containing the projection items.

        Raises:
            HTTPException: 404 if flow is not found.
        """
        flow_stmt = select(FlowModel).where(
            FlowModel.id == flow_id,
            FlowModel.project_id == project_id,
            FlowModel.workspace_id == workspace_id,
        )
        flow_res = await session.execute(flow_stmt)
        if not flow_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Flow not found")

        steps_stmt = (
            select(FlowStepModel)
            .where(
                FlowStepModel.flow_id == flow_id,
                FlowStepModel.workspace_id == workspace_id,
            )
            .options(
                selectinload(FlowStepModel.input_business_objects).selectinload(BusinessObjectModel.attributes),
                selectinload(FlowStepModel.output_business_objects).selectinload(BusinessObjectModel.attributes),
            )
            .order_by(FlowStepModel.position, FlowStepModel.id)
        )
        steps_res = await session.execute(steps_stmt)
        db_steps = steps_res.scalars().all()

        bo_map: dict[int, BusinessObjectModel] = {}
        input_map: dict[int, set[int]] = {}
        output_map: dict[int, set[int]] = {}

        for step in db_steps:
            for bo in step.input_business_objects:
                bo_map[bo.id] = bo
                input_map.setdefault(bo.id, set()).add(step.id)

            for bo in step.output_business_objects:
                bo_map[bo.id] = bo
                output_map.setdefault(bo.id, set()).add(step.id)

        if not bo_map:
            return FlowObjectUsageResponse(flow_id=flow_id, objects=[])

        target_bo_ids = list(bo_map.keys())
        other_flow_names_map: dict[int, set[str]] = {bo_id: set() for bo_id in target_bo_ids}

        other_input_stmt = (
            select(FlowModel.name, flow_step_input_business_object_table.c.business_object_id)
            .join(FlowStepModel, FlowStepModel.id == flow_step_input_business_object_table.c.flow_step_id)
            .join(FlowModel, FlowModel.id == FlowStepModel.flow_id)
            .where(
                FlowStepModel.flow_id != flow_id,
                FlowStepModel.workspace_id == workspace_id,
                flow_step_input_business_object_table.c.business_object_id.in_(target_bo_ids),
            )
        )
        other_input_res = await session.execute(other_input_stmt)
        for flow_name, bo_id in other_input_res.all():
            other_flow_names_map[bo_id].add(flow_name)

        other_output_stmt = (
            select(FlowModel.name, flow_step_output_business_object_table.c.business_object_id)
            .join(FlowStepModel, FlowStepModel.id == flow_step_output_business_object_table.c.flow_step_id)
            .join(FlowModel, FlowModel.id == FlowStepModel.flow_id)
            .where(
                FlowStepModel.flow_id != flow_id,
                FlowStepModel.workspace_id == workspace_id,
                flow_step_output_business_object_table.c.business_object_id.in_(target_bo_ids),
            )
        )
        other_output_res = await session.execute(other_output_stmt)
        for flow_name, bo_id in other_output_res.all():
            other_flow_names_map[bo_id].add(flow_name)

        items: list[ObjectUsageProjectionItem] = []
        for bo_id in sorted(bo_map.keys()):
            bo = bo_map[bo_id]
            inputs = sorted(input_map.get(bo_id, set()))
            outputs = sorted(output_map.get(bo_id, set()))
            used_by = sorted(set(inputs + outputs))

            attributes = [
                ObjectUsageAttributeItem(
                    id=attr.id,
                    name=attr.name,
                    data_type=attr.data_type,
                    description=attr.description or "",
                    example=attr.example or "",
                )
                for attr in sorted(bo.attributes or [], key=lambda a: a.id)
            ]

            other_names = sorted(other_flow_names_map.get(bo_id, set()))

            items.append(
                ObjectUsageProjectionItem(
                    business_object_id=bo.id,
                    logical_uuid=bo.logical_uuid,
                    name=bo.name,
                    description=bo.description or "",
                    confirmation_status=bo.confirmation_status,
                    attributes=attributes,
                    used_by_step_ids=used_by,
                    input_at_step_ids=inputs,
                    output_at_step_ids=outputs,
                    other_flows_count=len(other_names),
                    other_flow_names=other_names,
                )
            )

        return FlowObjectUsageResponse(flow_id=flow_id, objects=items)
