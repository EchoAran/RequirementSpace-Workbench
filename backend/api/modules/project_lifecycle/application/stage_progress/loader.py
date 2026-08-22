from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    BusinessObjectModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    PerceptionJobModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)


@dataclass
class WhatProgressData:
    actor_ids: list[int]
    leaf_features: list
    feature_actor_map: dict[int, list[int]]
    feature_scenario_map: dict[int, list[int]]
    scenario_ids: list[int]
    acceptance_scenario_ids: set[int]
    scenarios_map: dict[int, object]


@dataclass
class HowProgressData:
    flow_ids: list[int]
    flows_with_steps: set[int]
    flows_map: dict[int, object]
    steps: list
    step_actor_map: dict[int, list[int]]
    step_input_object_map: dict[int, list[int]]
    step_output_object_map: dict[int, list[int]]
    business_object_ids: set[int]
    business_objects: list


@dataclass
class StageProgressData:
    project: ProjectModel
    unlocked_stages: set[str]
    what: WhatProgressData
    how: HowProgressData
    scoped_feature_ids: set[int]
    latest_jobs: dict[str, PerceptionJobModel] = field(default_factory=dict)
    kano_status: str = "missing"


def _append_value(mapping: dict[int, list[int]], key: int, value: int) -> None:
    mapping.setdefault(key, []).append(value)


async def _load_project(project_id: int, session) -> ProjectModel:
    result = await session.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ValueError("project_not_found")
    return project


async def _load_feature_data(project_id: int, session, workspace_id: int | None = None):
    stmt = select(FeatureModel).where(FeatureModel.project_id == project_id)
    if workspace_id is not None:
        stmt = stmt.where(FeatureModel.workspace_id == workspace_id)
    features = (await session.execute(stmt)).scalars().all()
    feature_ids = [feature.id for feature in features]
    parent_ids = set()
    if feature_ids:
        parent_ids = set(
            (
                await session.execute(
                    select(FeatureRelationModel.parent_feature_id).where(
                        FeatureRelationModel.parent_feature_id.in_(
                            feature_ids
                        ),
                        FeatureRelationModel.child_feature_id.in_(
                            feature_ids
                        ),
                    )
                )
            ).scalars().all()
        )
    leaf_features = [
        feature for feature in features if feature.id not in parent_ids
    ]
    actor_rows = (
        await session.execute(
            select(
                feature_actor_table.c.feature_id,
                feature_actor_table.c.actor_id,
            )
            .join(
                FeatureModel,
                FeatureModel.id == feature_actor_table.c.feature_id,
            )
            .where(
                FeatureModel.project_id == project_id,
                *([FeatureModel.workspace_id == workspace_id] if workspace_id is not None else []),
            )
        )
    ).all()
    feature_actor_map: dict[int, list[int]] = {}
    for feature_id, actor_id in actor_rows:
        _append_value(feature_actor_map, feature_id, actor_id)
    return feature_ids, leaf_features, feature_actor_map


async def _load_scenario_data(project_id: int, session, workspace_id: int | None = None):
    stmt = (
        select(ScenarioModel)
        .join(FeatureModel, FeatureModel.id == ScenarioModel.feature_id)
        .where(
            FeatureModel.project_id == project_id,
            *([FeatureModel.workspace_id == workspace_id] if workspace_id is not None else []),
        )
    )
    result = await session.execute(stmt)
    scenarios = result.scalars().all()
    scenario_ids = [scenario.id for scenario in scenarios]
    feature_scenario_map: dict[int, list[int]] = {}
    for scenario in scenarios:
        _append_value(
            feature_scenario_map,
            scenario.feature_id,
            scenario.id,
        )
    acceptance_scenario_ids = set()
    if scenario_ids:
        acceptance_scenario_ids = set(
            (
                await session.execute(
                    select(
                        ScenarioAcceptanceCriterionModel.scenario_id
                    ).where(
                        ScenarioAcceptanceCriterionModel.scenario_id.in_(
                            scenario_ids
                        )
                    )
                )
            ).scalars().all()
        )
    return (
        scenario_ids,
        {scenario.id: scenario for scenario in scenarios},
        feature_scenario_map,
        acceptance_scenario_ids,
    )


async def _load_what_data(
    project_id: int,
    session,
    workspace_id: int | None = None,
) -> tuple[WhatProgressData, list[int]]:
    actor_stmt = select(ActorModel.id).where(ActorModel.project_id == project_id)
    if workspace_id is not None:
        actor_stmt = actor_stmt.where(ActorModel.workspace_id == workspace_id)
    actor_ids = (await session.execute(actor_stmt)).scalars().all()
    feature_ids, leaf_features, feature_actor_map = (
        await _load_feature_data(project_id, session, workspace_id)
    )
    (
        scenario_ids,
        scenarios_map,
        feature_scenario_map,
        acceptance_scenario_ids,
    ) = await _load_scenario_data(project_id, session, workspace_id)
    return (
        WhatProgressData(
            actor_ids=actor_ids,
            leaf_features=leaf_features,
            feature_actor_map=feature_actor_map,
            feature_scenario_map=feature_scenario_map,
            scenario_ids=scenario_ids,
            acceptance_scenario_ids=acceptance_scenario_ids,
            scenarios_map=scenarios_map,
        ),
        feature_ids,
    )


async def _load_step_maps(step_ids: list[int], session):
    actor_map: dict[int, list[int]] = {}
    input_map: dict[int, list[int]] = {}
    output_map: dict[int, list[int]] = {}
    if not step_ids:
        return actor_map, input_map, output_map
    actor_rows = (
        await session.execute(
            select(
                flow_step_actor_table.c.flow_step_id,
                flow_step_actor_table.c.actor_id,
            ).where(flow_step_actor_table.c.flow_step_id.in_(step_ids))
        )
    ).all()
    for step_id, actor_id in actor_rows:
        _append_value(actor_map, step_id, actor_id)
    input_rows = (
        await session.execute(
            select(
                flow_step_input_business_object_table.c.flow_step_id,
                flow_step_input_business_object_table.c.business_object_id,
            ).where(
                flow_step_input_business_object_table.c.flow_step_id.in_(
                    step_ids
                )
            )
        )
    ).all()
    for step_id, object_id in input_rows:
        _append_value(input_map, step_id, object_id)
    output_rows = (
        await session.execute(
            select(
                flow_step_output_business_object_table.c.flow_step_id,
                flow_step_output_business_object_table.c.business_object_id,
            ).where(
                flow_step_output_business_object_table.c.flow_step_id.in_(
                    step_ids
                )
            )
        )
    ).all()
    for step_id, object_id in output_rows:
        _append_value(output_map, step_id, object_id)
    return actor_map, input_map, output_map


async def _load_how_data(
    project_id: int,
    session,
    workspace_id: int | None = None,
) -> HowProgressData:
    flow_stmt = select(FlowModel).where(FlowModel.project_id == project_id)
    if workspace_id is not None:
        flow_stmt = flow_stmt.where(FlowModel.workspace_id == workspace_id)
    flows = (await session.execute(flow_stmt)).scalars().all()
    flow_ids = [flow.id for flow in flows]
    steps = []
    if flow_ids:
        steps = (
            await session.execute(
                select(FlowStepModel).where(
                    FlowStepModel.flow_id.in_(flow_ids)
                )
            )
        ).scalars().all()
    actor_map, input_map, output_map = await _load_step_maps(
        [step.id for step in steps],
        session,
    )
    bo_stmt = (
        select(BusinessObjectModel)
        .options(selectinload(BusinessObjectModel.attributes))
        .where(BusinessObjectModel.project_id == project_id)
    )
    if workspace_id is not None:
        bo_stmt = bo_stmt.where(BusinessObjectModel.workspace_id == workspace_id)
    object_result = await session.execute(bo_stmt)
    business_objects = object_result.scalars().all()
    return HowProgressData(
        flow_ids=flow_ids,
        flows_with_steps={step.flow_id for step in steps},
        flows_map={flow.id: flow for flow in flows},
        steps=steps,
        step_actor_map=actor_map,
        step_input_object_map=input_map,
        step_output_object_map=output_map,
        business_object_ids={item.id for item in business_objects},
        business_objects=business_objects,
    )


async def _load_scoped_feature_ids(
    project_id: int,
    session,
    workspace_id: int | None = None,
) -> set[int]:
    stmt = (
        select(ScopeModel.feature_id)
        .join(FeatureModel, FeatureModel.id == ScopeModel.feature_id)
        .where(
            FeatureModel.project_id == project_id,
            ScopeModel.status != None,
            *([FeatureModel.workspace_id == workspace_id] if workspace_id is not None else []),
        )
    )
    rows = (await session.execute(stmt)).scalars().all()
    return set(rows)


async def _load_latest_jobs(
    project_id: int,
    session,
    workspace_id: int | None = None,
) -> dict:
    stmt = (
        select(PerceptionJobModel)
        .where(PerceptionJobModel.project_id == project_id)
    )
    if workspace_id is not None:
        stmt = stmt.where(PerceptionJobModel.workspace_id == workspace_id)
    else:
        stmt = stmt.where(PerceptionJobModel.workspace_id.is_(None))
    stmt = stmt.order_by(PerceptionJobModel.id.desc())
    jobs = (await session.execute(stmt)).scalars().all()
    latest_jobs = {}
    for job in jobs:
        if job.stage not in latest_jobs:
            latest_jobs[job.stage] = job
    return latest_jobs


async def load_stage_progress_data(
    project_id: int,
    session,
    workspace_id: int | None = None,
) -> StageProgressData:
    project = await _load_project(project_id, session)
    what, _feature_ids = await _load_what_data(project_id, session, workspace_id)
    how = await _load_how_data(project_id, session, workspace_id)
    scoped_feature_ids = await _load_scoped_feature_ids(
        project_id,
        session,
        workspace_id,
    )
    latest_jobs = await _load_latest_jobs(project_id, session, workspace_id)
    raw_unlocked = project.unlocked_stages
    kano_status = project.kano_status or "missing"
    if workspace_id is not None:
        ws_row = (await session.execute(
            select(BranchWorkspaceModel).where(
                BranchWorkspaceModel.id == workspace_id
            )
        )).scalar_one_or_none()
        if ws_row is not None:
            raw_unlocked = ws_row.unlocked_stages or ""
            kano_status = ws_row.kano_status or "missing"

    unlocked_stages = (
        {
            stage.strip().lower()
            for stage in raw_unlocked.split(",")
            if stage.strip()
        }
        if raw_unlocked
        else set()
    )
    return StageProgressData(
        project=project,
        unlocked_stages=unlocked_stages,
        what=what,
        how=how,
        scoped_feature_ids=scoped_feature_ids,
        latest_jobs=latest_jobs,
        kano_status=kano_status,
    )
