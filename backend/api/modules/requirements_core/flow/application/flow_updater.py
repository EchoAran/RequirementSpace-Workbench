from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.database.model import FeatureModel, FlowModel, FlowStepModel


async def load_flow_for_update(session, project_id: int, flow_id: int):
    result = await session.execute(
        select(FlowModel)
        .where(
            FlowModel.project_id == project_id,
            FlowModel.id == flow_id,
        )
        .options(
            selectinload(FlowModel.features),
            selectinload(FlowModel.steps).selectinload(FlowStepModel.actors),
            selectinload(FlowModel.steps).selectinload(
                FlowStepModel.input_business_objects
            ),
            selectinload(FlowModel.steps).selectinload(
                FlowStepModel.output_business_objects
            ),
            selectinload(FlowModel.transitions),
        )
    )
    flow = result.scalar_one_or_none()
    if flow is None:
        raise ValueError("flow_not_found")
    return flow


def capture_flow_state(flow) -> dict:
    return {
        "name": flow.name,
        "description": flow.description,
        "feature_ids": [feature.id for feature in flow.features],
    }


async def apply_flow_updates(
    session,
    *,
    project_id: int,
    flow,
    request,
) -> None:
    if request.name is not None:
        flow.name = request.name
    if request.description is not None:
        flow.description = request.description
    if request.feature_ids is None:
        return
    if not request.feature_ids:
        flow.features = []
        return

    result = await session.execute(
        select(FeatureModel).where(
            FeatureModel.project_id == project_id,
            FeatureModel.id.in_(request.feature_ids),
        )
    )
    features = result.scalars().all()
    if len(features) != len(request.feature_ids):
        raise ValueError("invalid_feature_ids")
    flow.features = features


def build_flow_update_diff(before: dict, flow) -> dict:
    after = capture_flow_state(flow)
    return {
        field: {"before": before[field], "after": value}
        for field, value in after.items()
        if before[field] != value
    }
