from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defaultload, selectinload

from backend.api.modules.project_lifecycle.schemas.project import (
    PerceptionSlotDetail,
    UnresolvedGateResponse,
)
from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    PerceptionJobModel,
    ProjectModel,
    ScenarioModel,
)


async def load_project_detail_model(
    project_id: int,
    session: AsyncSession,
    workspace_id: int | None = None,
):
    if workspace_id is not None:
        project_stmt = (
            select(ProjectModel)
            .where(ProjectModel.id == project_id)
            .options(
                selectinload(ProjectModel.perception_slots),
            )
        )
        result = await session.execute(project_stmt)
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError("project_not_found")

        actors_res = await session.execute(
            select(ActorModel).where(
                ActorModel.project_id == project_id,
                ActorModel.workspace_id == workspace_id,
            ).order_by(ActorModel.id.asc())
        )
        features_res = await session.execute(
            select(FeatureModel)
            .where(
                FeatureModel.project_id == project_id,
                FeatureModel.workspace_id == workspace_id,
            )
            .options(
                selectinload(FeatureModel.child_relations),
                selectinload(FeatureModel.parent_relation),
                selectinload(FeatureModel.actors),
                selectinload(FeatureModel.scope),
                selectinload(FeatureModel.scenarios).selectinload(ScenarioModel.acceptance_criteria),
            )
            .order_by(FeatureModel.id.asc())
        )
        bo_res = await session.execute(
            select(BusinessObjectModel)
            .where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.workspace_id == workspace_id,
            )
            .options(
                selectinload(BusinessObjectModel.attributes),
            )
            .order_by(BusinessObjectModel.id.asc())
        )
        flows_res = await session.execute(
            select(FlowModel)
            .where(
                FlowModel.project_id == project_id,
                FlowModel.workspace_id == workspace_id,
            )
            .options(
                selectinload(FlowModel.features),
                selectinload(FlowModel.steps).selectinload(FlowStepModel.actors),
                defaultload(FlowModel.steps).selectinload(FlowStepModel.input_business_objects),
                defaultload(FlowModel.steps).selectinload(FlowStepModel.output_business_objects),
                defaultload(FlowModel.steps).selectinload(FlowStepModel.next_steps),
            )
            .order_by(FlowModel.id.asc())
        )

        from sqlalchemy.orm.attributes import set_committed_value

        actors = list(actors_res.scalars().all())
        features = list(features_res.scalars().all())
        bos = list(bo_res.scalars().all())
        flows = list(flows_res.scalars().all())
        scenarios = [s for f in features for s in getattr(f, "scenarios", [])]

        set_committed_value(project, "actors", actors)
        set_committed_value(project, "features", features)
        set_committed_value(project, "business_objects", bos)
        set_committed_value(project, "flows", flows)
        set_committed_value(project, "scenarios", scenarios)
        return project

    statement = (
        select(ProjectModel)
        .where(ProjectModel.id == project_id)
        .options(
            selectinload(ProjectModel.perception_slots),
            selectinload(ProjectModel.actors),
            selectinload(ProjectModel.scenarios),
            selectinload(ProjectModel.features).selectinload(
                FeatureModel.child_relations
            ),
            defaultload(ProjectModel.features).selectinload(
                FeatureModel.parent_relation
            ),
            defaultload(ProjectModel.features).selectinload(
                FeatureModel.actors
            ),
            defaultload(ProjectModel.features).selectinload(
                FeatureModel.scope
            ),
            defaultload(ProjectModel.features)
            .selectinload(FeatureModel.scenarios)
            .selectinload(ScenarioModel.acceptance_criteria),
            selectinload(ProjectModel.business_objects).selectinload(
                BusinessObjectModel.attributes
            ),
            selectinload(ProjectModel.flows).selectinload(
                FlowModel.features
            ),
            defaultload(ProjectModel.flows)
            .selectinload(FlowModel.steps)
            .selectinload(FlowStepModel.actors),
            defaultload(ProjectModel.flows)
            .defaultload(FlowModel.steps)
            .selectinload(FlowStepModel.input_business_objects),
            defaultload(ProjectModel.flows)
            .defaultload(FlowModel.steps)
            .selectinload(FlowStepModel.output_business_objects),
            defaultload(ProjectModel.flows)
            .defaultload(FlowModel.steps)
            .selectinload(FlowStepModel.next_steps),
        )
    )
    result = await session.execute(statement)
    project = result.scalar_one_or_none()
    if project is None:
        raise ValueError("project_not_found")
    return project


async def build_visible_perception_slot(
    project,
    session: AsyncSession,
    is_stage_visible: Callable[..., bool],
    workspace_id: int | None = None,
    unlocked_stages: str | None = None,
) -> PerceptionSlotDetail | None:
    from backend.database.model import PerceptionSlotModel

    slot_stmt = select(PerceptionSlotModel).where(
        PerceptionSlotModel.project_id == project.id,
    )
    if workspace_id is not None:
        slot_stmt = slot_stmt.where(PerceptionSlotModel.workspace_id == workspace_id)
    else:
        slot_stmt = slot_stmt.where(PerceptionSlotModel.workspace_id.is_(None))

    result = await session.execute(slot_stmt)
    if hasattr(result, "scalars"):
        scalars_obj = result.scalars()
        slot = scalars_obj.first() if hasattr(scalars_obj, "first") else getattr(result, "first", lambda: None)()
    elif hasattr(result, "scalar_one_or_none"):
        slot = result.scalar_one_or_none()
    elif hasattr(result, "first"):
        slot = result.first()
    else:
        slot = None
    if hasattr(slot, "perception_slot") and not hasattr(slot, "perception_kind"):
        slot = slot.perception_slot
    if not slot:
        return None

    slot_job = await session.get(
        PerceptionJobModel,
        slot.id,
    )
    slot_stage = slot_job.stage if slot_job is not None else None
    stages = unlocked_stages if unlocked_stages is not None else project.unlocked_stages
    if not is_stage_visible(
        stage=slot_stage,
        unlocked_stages=stages,
    ):
        return None

    return PerceptionSlotDetail(
        perception_slot_id=slot.id,
        perception_kind=slot.perception_kind,
        perception_description=slot.description,
        stage=slot_stage,
    )


async def load_unresolved_export_gates(
    project_id: int,
    session: AsyncSession,
) -> list[UnresolvedGateResponse]:
    from backend.api.modules.diagnosis_quality.public import FindingService

    gate_findings = await FindingService().list_findings(
        project_id=project_id,
        stage="all",
        view="gate",
        action="export",
        session=session,
    )
    return [
        UnresolvedGateResponse(
            finding_id=finding.findingId,
            title=finding.title,
            description=finding.description,
            stage=finding.stage.value,
            code=finding.code,
        )
        for finding in gate_findings
    ]
