from backend.database.model import BranchWorkspaceModel

from .issue_context import (
    AcceptanceCriterionIssueItem as AcceptanceCriterionIssueItem,
    ActorIssueItem as ActorIssueItem,
    BusinessObjectIssueItem as BusinessObjectIssueItem,
    DomainRuleIssueItem as DomainRuleIssueItem,
    FeatureIssueItem as FeatureIssueItem,
    FlowIssueItem as FlowIssueItem,
    FlowStepIssueItem as FlowStepIssueItem,
    IssueProjectContext,
    RuleLinkIssueItem as RuleLinkIssueItem,
    ScenarioIssueItem as ScenarioIssueItem,
    ScopeIssueItem as ScopeIssueItem,
    load_issue_actors,
    load_issue_business_objects,
    load_issue_domain_rules,
    load_issue_features,
    load_issue_flows,
    load_issue_project,
    load_issue_rule_links,
    load_issue_scenarios,
    load_issue_scopes,
)


async def load_issue_project_context(
    project_id: int,
    session,
    workspace_id: int,
) -> IssueProjectContext:
    project = await load_issue_project(project_id, session)
    ws = await session.get(BranchWorkspaceModel, workspace_id)
    if ws is None or ws.project_id != project_id:
        raise ValueError("workspace_not_found")
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
    domain_rules = await load_issue_domain_rules(
        project_id,
        session,
        workspace_id=workspace_id,
    )
    rule_links = await load_issue_rule_links(
        project_id,
        session,
        workspace_id=workspace_id,
    )

    return IssueProjectContext(
        project_id=project.id,
        user_requirements=ws.user_requirements,
        actors=actors,
        features=features,
        scenarios=scenarios,
        flows=flows,
        business_objects=business_objects,
        scopes=scopes,
        domain_rules=domain_rules,
        rule_links=rule_links,
    )
