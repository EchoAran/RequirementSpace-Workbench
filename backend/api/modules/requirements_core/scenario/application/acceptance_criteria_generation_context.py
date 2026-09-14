from sqlalchemy import select

from backend.api.modules.requirements_core.generation_context import (
    build_actor_nodes,
    load_generation_project,
)
from backend.database.model import (
    ActorModel,
    FeatureModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
)
from backend.schemas import FeatureNode, ScenarioNode


def build_scenario_statement(
    project_id: int,
    scenario_ids: list[int] | None,
    workspace_id: int,
):
    statement = select(ScenarioModel).where(
        ScenarioModel.project_id == project_id,
        ScenarioModel.workspace_id == workspace_id,
    )
    if scenario_ids is None:
        return statement
    scenario_id_set = set(scenario_ids)
    if not scenario_id_set:
        raise ValueError("empty_scenarios")
    if len(scenario_id_set) != len(scenario_ids):
        raise ValueError("duplicate_scenario_id")
    return statement.where(ScenarioModel.id.in_(scenario_id_set))


async def load_target_scenarios(
    session,
    project_id: int,
    scenario_ids: list[int] | None,
    workspace_id: int,
) -> list:
    result = await session.execute(
        build_scenario_statement(project_id, scenario_ids, workspace_id)
    )
    scenarios = result.scalars().all()
    if not scenarios:
        error = (
            "no_scenarios_found"
            if scenario_ids is None
            else "scenario_not_found"
        )
        raise ValueError(error)
    if scenario_ids is not None and len(scenarios) != len(scenario_ids):
        raise ValueError("scenario_not_found")
    return scenarios


async def ensure_acceptance_criteria_absent(
    session,
    scenario_ids: list[int],
    workspace_id: int,
) -> None:
    result = await session.execute(
        select(ScenarioAcceptanceCriterionModel).where(
            ScenarioAcceptanceCriterionModel.scenario_id.in_(scenario_ids),
            ScenarioAcceptanceCriterionModel.workspace_id == workspace_id,
        )
    )
    if result.scalars().all():
        raise ValueError("acceptance_criteria_already_exist")


async def load_scenario_reference_nodes(
    session,
    project_id: int,
    scenarios: list,
    workspace_id: int,
) -> tuple[dict, dict]:
    actor_ids = {scenario.actor_id for scenario in scenarios}
    feature_ids = {scenario.feature_id for scenario in scenarios}
    actor_result = await session.execute(
        select(ActorModel).where(
            ActorModel.id.in_(actor_ids),
            ActorModel.project_id == project_id,
            ActorModel.workspace_id == workspace_id,
        )
    )
    feature_result = await session.execute(
        select(FeatureModel).where(
            FeatureModel.id.in_(feature_ids),
            FeatureModel.project_id == project_id,
            FeatureModel.workspace_id == workspace_id,
        )
    )
    actors_by_id = {
        node.actorId: node
        for node in build_actor_nodes(actor_result.scalars().all())
    }
    features_by_id = {
        feature.id: FeatureNode(
            featureId=feature.id,
            featureName=feature.name,
            featureDescription=feature.description,
        )
        for feature in feature_result.scalars().all()
    }
    if set(actors_by_id) != actor_ids:
        raise ValueError("invalid_scenario_actor_reference")
    if set(features_by_id) != feature_ids:
        raise ValueError("invalid_scenario_feature_reference")
    return actors_by_id, features_by_id


def build_scenario_nodes(scenarios: list) -> list[ScenarioNode]:
    return [
        ScenarioNode(
            scenarioId=scenario.id,
            scenarioName=scenario.name,
            scenarioContent=scenario.content,
            featureId=scenario.feature_id,
            actorId=scenario.actor_id,
            acceptanceCriteria=[],
        )
        for scenario in scenarios
    ]


async def load_acceptance_criteria_generation_context(
    project_id: int,
    scenario_ids: list[int] | None,
    session,
    workspace_id: int,
):
    from backend.database.model import BranchWorkspaceModel

    workspace = await session.get(BranchWorkspaceModel, workspace_id)
    if workspace is None or workspace.project_id != project_id:
        raise ValueError("project_not_found")
    scenarios = await load_target_scenarios(
        session,
        project_id,
        scenario_ids,
        workspace_id,
    )
    await ensure_acceptance_criteria_absent(
        session,
        [scenario.id for scenario in scenarios],
        workspace_id,
    )
    actor_nodes, feature_nodes = await load_scenario_reference_nodes(
        session,
        project_id,
        scenarios,
        workspace_id,
    )
    return (
        workspace.user_requirements,
        actor_nodes,
        feature_nodes,
        build_scenario_nodes(scenarios),
    )
