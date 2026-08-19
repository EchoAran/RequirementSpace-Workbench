from .issue_context import (
    load_issue_business_objects,
    load_issue_scopes,
    load_issue_flows,
    AcceptanceCriterionIssueItem,
    ActorIssueItem,
    BusinessObjectIssueItem,
    FeatureIssueItem,
    FlowIssueItem,
    FlowStepIssueItem,
    IssueProjectContext,
    ScenarioIssueItem,
    ScopeIssueItem,
    load_issue_actors,
    load_issue_features,
    load_issue_project,
    load_issue_scenarios,
)


async def load_issue_project_context(
    project_id: int,
    session,
    workspace_id: int | None = None,
) -> IssueProjectContext:
    project = await load_issue_project(project_id, session)
    actors = await load_issue_actors(project_id, session, workspace_id=workspace_id)
    features, feature_ids = await load_issue_features(project_id, session, workspace_id=workspace_id)
    scenarios = await load_issue_scenarios(project_id, session, workspace_id=workspace_id)
    flows = await load_issue_flows(project_id, session, workspace_id=workspace_id)
    business_objects = await load_issue_business_objects(
        project_id,
        session,
        workspace_id=workspace_id,
    )
    scopes = await load_issue_scopes(feature_ids, session)

    user_reqs = project.user_requirements
    if workspace_id is not None:
        from backend.database.model import BranchWorkspaceModel
        ws = await session.get(BranchWorkspaceModel, workspace_id)
        if ws and ws.user_requirements:
            user_reqs = ws.user_requirements

    return IssueProjectContext(
        project_id=project.id,
        user_requirements=user_reqs,
        actors=actors,
        features=features,
        scenarios=scenarios,
        flows=flows,
        business_objects=business_objects,
        scopes=scopes,
    )
