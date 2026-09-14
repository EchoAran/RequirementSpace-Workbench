from backend.api.modules.project_lifecycle.schemas.project import (
    AcceptanceCriterionDetail,
    ActorDetail,
    BusinessObjectAttributeDetail,
    BusinessObjectDetail,
    DomainRuleDetail,
    FeatureDetail,
    FlowDetail,
    FlowStepDetail,
    FlowTransitionDetail,
    ProjectDetailResponse,
    RuleLinkDetail,
    ScenarioDetail,
    ScopeDetail,
)
from backend.services.binary_conversion_service import (
    BinaryConversionService,
)


def _build_actor(actor) -> ActorDetail:
    return ActorDetail(
        logical_uuid=actor.logical_uuid,
        actor_id=actor.id,
        actor_name=actor.name,
        actor_description=actor.description,
        confirmation_status=actor.confirmation_status,
        updated_at=actor.updated_at,
    )


def _build_scope(scope) -> ScopeDetail | None:
    if not scope:
        return None
    return ScopeDetail(
        logical_uuid=scope.logical_uuid,
        scope_id=scope.id,
        scope_status=scope.status,
        reason=scope.reason,
        positive_summary=scope.positive_summary,
        negative_summary=scope.negative_summary,
        positive_picture_base64=(
            BinaryConversionService.bytes_to_base64(
                scope.positive_picture
            )
            if scope.positive_picture is not None
            else None
        ),
        negative_picture_base64=(
            BinaryConversionService.bytes_to_base64(
                scope.negative_picture
            )
            if scope.negative_picture is not None
            else None
        ),
        kano_category=scope.kano_category,
        kano_category_name=scope.kano_category_name,
        confirmation_status=scope.confirmation_status,
        updated_at=scope.updated_at,
    )


def _build_acceptance_criterion(
    criterion,
) -> AcceptanceCriterionDetail:
    return AcceptanceCriterionDetail(
        logical_uuid=criterion.logical_uuid,
        criterion_id=criterion.id,
        criterion_content=criterion.content,
        confirmation_status=criterion.confirmation_status,
        updated_at=criterion.updated_at,
    )


def _build_scenario(scenario) -> ScenarioDetail:
    return ScenarioDetail(
        logical_uuid=scenario.logical_uuid,
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        scenario_content=scenario.content,
        feature_id=scenario.feature_id,
        actor_id=scenario.actor_id,
        acceptance_criteria=[
            _build_acceptance_criterion(criterion)
            for criterion in scenario.acceptance_criteria
        ],
        confirmation_status=scenario.confirmation_status,
        updated_at=scenario.updated_at,
    )


def _build_feature(feature) -> FeatureDetail:
    return FeatureDetail(
        logical_uuid=feature.logical_uuid,
        feature_id=feature.id,
        feature_name=feature.name,
        feature_description=feature.description,
        actor_ids=[actor.id for actor in feature.actors],
        parent_id=(
            feature.parent_relation.parent_feature_id
            if feature.parent_relation
            else None
        ),
        children_ids=[
            relation.child_feature_id
            for relation in feature.child_relations
        ],
        scenarios=[
            _build_scenario(scenario)
            for scenario in feature.scenarios
        ],
        scope=_build_scope(feature.scope),
        confirmation_status=feature.confirmation_status,
        updated_at=feature.updated_at,
    )


def _build_business_object_attribute(
    attribute,
) -> BusinessObjectAttributeDetail:
    return BusinessObjectAttributeDetail(
        logical_uuid=attribute.logical_uuid,
        business_object_attribute_id=attribute.id,
        business_object_attribute_name=attribute.name,
        business_object_attribute_description=attribute.description,
        business_object_attribute_type=attribute.data_type,
        business_object_attribute_example=attribute.example,
        confirmation_status=attribute.confirmation_status,
        updated_at=attribute.updated_at,
    )


def _build_business_object(business_object) -> BusinessObjectDetail:
    return BusinessObjectDetail(
        logical_uuid=business_object.logical_uuid,
        business_object_id=business_object.id,
        business_object_name=business_object.name,
        business_object_description=business_object.description,
        business_object_attributes=[
            _build_business_object_attribute(attribute)
            for attribute in business_object.attributes
        ],
        confirmation_status=business_object.confirmation_status,
        updated_at=business_object.updated_at,
    )


def _build_flow_transition(transition, rule_ids: list[int] | None = None) -> FlowTransitionDetail:
    return FlowTransitionDetail(
        logical_uuid=transition.logical_uuid,
        transition_id=transition.id,
        source_step_id=transition.source_step_id,
        target_step_id=transition.target_step_id,
        label=transition.label,
        condition_text=transition.condition_text,
        is_default=transition.is_default,
        position=transition.position,
        semantic_tags=transition.semantic_tags or [],
        rule_ids=rule_ids or [],
        origin=transition.origin,
        confirmation_status=transition.confirmation_status,
        updated_at=transition.updated_at,
    )


def _build_flow_step(step) -> FlowStepDetail:
    return FlowStepDetail(
        logical_uuid=step.logical_uuid,
        step_id=step.id,
        step_name=step.name,
        step_description=step.description,
        step_type=step.step_type,
        position=step.position,
        actor_ids=[actor.id for actor in step.actors],
        input_business_object_ids=[
            business_object.id
            for business_object in step.input_business_objects
        ],
        output_business_object_ids=[
            business_object.id
            for business_object in step.output_business_objects
        ],
        confirmation_status=step.confirmation_status,
        updated_at=step.updated_at,
    )


def _build_flow(flow, transition_rule_ids: dict[str, list[int]] | None = None) -> FlowDetail:
    return FlowDetail(
        logical_uuid=flow.logical_uuid,
        flow_id=flow.id,
        flow_name=flow.name,
        flow_description=flow.description,
        feature_ids=[feature.id for feature in flow.features],
        flow_steps=[_build_flow_step(step) for step in flow.steps],
        transitions=[_build_flow_transition(t, (transition_rule_ids or {}).get(t.logical_uuid, []))
                     for t in flow.transitions],
        confirmation_status=flow.confirmation_status,
        updated_at=flow.updated_at,
    )


def _build_rule_link(link) -> RuleLinkDetail:
    return RuleLinkDetail(
        id=link.id,
        logical_uuid=link.logical_uuid,
        rule_id=link.rule_id,
        target_kind=link.target_kind,
        target_logical_uuid=link.target_logical_uuid,
        link_purpose=link.link_purpose,
        context_text=link.context_text or "",
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def _build_domain_rule(rule) -> DomainRuleDetail:
    links = [_build_rule_link(link) for link in rule.links]
    child_ids = [c.id for c in rule.child_rules]
    return DomainRuleDetail(
        logical_uuid=rule.logical_uuid,
        rule_id=rule.id,
        id=rule.id,
        parent_rule_id=rule.parent_rule_id,
        title=rule.title,
        statement=rule.statement,
        origin=rule.origin,
        confirmation_status=rule.confirmation_status,
        links=links,
        child_rule_ids=child_ids,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def build_project_detail_response(
    project,
    workspace,
    perception_slot,
    issue_count: int,
    status_code: str,
    status: str,
    unresolved_gates: list,
) -> ProjectDetailResponse:
    unlocked_stages = (
        [
            stage.strip()
            for stage in workspace.unlocked_stages.split(",")
            if stage.strip()
        ]
        if workspace.unlocked_stages
        else []
    )
    domain_rules = [
        _build_domain_rule(rule)
        for rule in project.domain_rules
    ]
    transition_rule_ids: dict[str, list[int]] = {}
    for rule in domain_rules:
        for link in rule.links:
            if link.target_kind == "flow_transition" and link.link_purpose == "applies_to":
                transition_rule_ids.setdefault(link.target_logical_uuid, []).append(rule.id)
    return ProjectDetailResponse(
        project_id=project.public_id,
        project_name=project.name,
        project_description=project.description,
        user_requirements=workspace.user_requirements,
        perception_slot=perception_slot,
        actors=[_build_actor(actor) for actor in project.actors],
        features=[
            _build_feature(feature)
            for feature in project.features
        ],
        business_objects=[
            _build_business_object(business_object)
            for business_object in project.business_objects
        ],
        flows=[_build_flow(flow, transition_rule_ids) for flow in project.flows],
        domain_rules=domain_rules,
        kano_status=workspace.kano_status,
        unlocked_stages=unlocked_stages,
        unresolved_gates=unresolved_gates,
        status_code=status_code,
        status=status,
        issue_count=issue_count,
    )
