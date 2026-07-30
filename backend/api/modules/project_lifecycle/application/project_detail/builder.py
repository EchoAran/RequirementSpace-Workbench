from backend.api.modules.project_lifecycle.schemas.project import (
    AcceptanceCriterionDetail,
    ActorDetail,
    BusinessObjectAttributeDetail,
    BusinessObjectDetail,
    FeatureDetail,
    FlowDetail,
    FlowStepDetail,
    ProjectDetailResponse,
    ScenarioDetail,
    ScopeDetail,
)
from backend.services.binary_conversion_service import (
    BinaryConversionService,
)


def _build_actor(actor) -> ActorDetail:
    return ActorDetail(
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
        criterion_id=criterion.id,
        criterion_content=criterion.content,
        confirmation_status=criterion.confirmation_status,
        updated_at=criterion.updated_at,
    )


def _build_scenario(scenario) -> ScenarioDetail:
    return ScenarioDetail(
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


def _build_flow_step(step) -> FlowStepDetail:
    return FlowStepDetail(
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
        next_step_ids=[next_step.id for next_step in step.next_steps],
        confirmation_status=step.confirmation_status,
        updated_at=step.updated_at,
    )


def _build_flow(flow) -> FlowDetail:
    return FlowDetail(
        flow_id=flow.id,
        flow_name=flow.name,
        flow_description=flow.description,
        feature_ids=[feature.id for feature in flow.features],
        flow_steps=[_build_flow_step(step) for step in flow.steps],
        confirmation_status=flow.confirmation_status,
        updated_at=flow.updated_at,
    )


def build_project_detail_response(
    project,
    perception_slot,
    issue_count: int,
    status_code: str,
    status: str,
    unresolved_gates: list,
) -> ProjectDetailResponse:
    unlocked_stages = (
        [
            stage.strip()
            for stage in project.unlocked_stages.split(",")
            if stage.strip()
        ]
        if project.unlocked_stages
        else []
    )
    return ProjectDetailResponse(
        project_id=project.public_id,
        project_name=project.name,
        project_description=project.description,
        user_requirements=project.user_requirements,
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
        flows=[_build_flow(flow) for flow in project.flows],
        kano_status=project.kano_status,
        unlocked_stages=unlocked_stages,
        unresolved_gates=unresolved_gates,
        status_code=status_code,
        status=status,
        issue_count=issue_count,
    )
