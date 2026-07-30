from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defaultload, selectinload

from backend.api.modules.project_lifecycle.schemas.project import (
    PerceptionSlotDetail,
    UnresolvedGateResponse,
)
from backend.database.model import (
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
):
    statement = (
        select(ProjectModel)
        .where(ProjectModel.id == project_id)
        .options(
            selectinload(ProjectModel.perception_slot),
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
) -> PerceptionSlotDetail | None:
    if not project.perception_slot:
        return None

    slot_job = await session.get(
        PerceptionJobModel,
        project.perception_slot.id,
    )
    slot_stage = slot_job.stage if slot_job is not None else None
    if not is_stage_visible(
        stage=slot_stage,
        unlocked_stages=project.unlocked_stages,
    ):
        return None

    return PerceptionSlotDetail(
        perception_slot_id=project.perception_slot.id,
        perception_kind=project.perception_slot.perception_kind,
        perception_description=project.perception_slot.description,
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
