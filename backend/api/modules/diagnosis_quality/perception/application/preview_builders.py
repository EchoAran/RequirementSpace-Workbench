from sqlalchemy import select

from backend.api.modules.diagnosis_quality.perception.application.normalizers import (
    PerceptionDraftNormalizer,
)
from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)
from backend.core.perceptrons.slot_fillers.acceptance_criteria_filler import (
    AcceptanceCriteriaFillerInput,
)
from backend.core.perceptrons.slot_fillers.actors_filler import (
    ActorsFillerInput,
)
from backend.core.perceptrons.slot_fillers.features_filler import (
    FeaturesFillerInput,
)
from backend.core.perceptrons.slot_fillers.flows_filler import (
    FlowsFillerInput,
)
from backend.core.perceptrons.slot_fillers.scenarios_filler import (
    ScenariosFillerInput,
)
from backend.schemas import (
    AcceptanceCriterionNode,
    ActorNode,
    BusinessObjectAttributeNode,
    BusinessObjectNode,
    FeatureNode,
    FlowNode,
    FlowStepNode,
    FlowStepType,
    FlowTransitionNode,
    PerceptionJobStatus,
    PerceptionKindType,
    PerceptionSlot,
    ScenarioNode,
)


class PerceptionPreviewBuilder:
    @staticmethod
    async def generate_actor_preview(
        creator,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
        workspace_id: int,
    ) -> tuple[dict, dict]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )
        _job, perception_slot = await PerceptionPreviewBuilder._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={"ACTOR"},
            session=session,
            workspace_id=workspace_id,
        )

        raw = await creator._actors_filler.fill(
            ActorsFillerInput(
                user_requirements=context.user_requirements,
                actors=PerceptionPreviewBuilder._build_actor_nodes(context),
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        actors = PerceptionDraftNormalizer.normalize_filled_actors(raw)

        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "actor",
            "actors": actors,
        }

        return draft_payload, PerceptionPreviewBuilder._build_response_payload(draft_payload)

    @staticmethod
    async def generate_feature_preview(
        creator,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
        workspace_id: int,
    ) -> tuple[dict, dict]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )
        _job, perception_slot = await PerceptionPreviewBuilder._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={
                "FEATURE_BRANCH",
                "FEATURE_LEAF",
            },
            session=session,
            workspace_id=workspace_id,
        )

        raw = await creator._features_filler.fill(
            FeaturesFillerInput(
                user_requirements=context.user_requirements,
                features=PerceptionPreviewBuilder._build_feature_nodes(context),
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        features = PerceptionDraftNormalizer.normalize_filled_features(
            raw=raw,
            context=context,
        )

        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "feature",
            "features": features,
        }

        return draft_payload, PerceptionPreviewBuilder._build_response_payload(draft_payload)

    @staticmethod
    async def generate_scenario_preview(
        creator,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
        workspace_id: int,
    ) -> tuple[dict, dict]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )
        job, perception_slot = await PerceptionPreviewBuilder._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={"SCENARIO"},
            session=session,
            workspace_id=workspace_id,
        )
        actor, feature, scenarios = PerceptionPreviewBuilder._load_pair_nodes(
            target_id=job.target_id,
            context=context,
        )

        raw = await creator._scenarios_filler.fill(
            ScenariosFillerInput(
                user_requirements=context.user_requirements,
                actor=actor,
                feature=feature,
                scenarios=scenarios,
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        filled_scenarios = PerceptionDraftNormalizer.normalize_filled_scenarios(
            raw=raw,
            actor=actor,
            feature=feature,
        )

        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "scenario",
            "scenarios": filled_scenarios,
        }

        return draft_payload, PerceptionPreviewBuilder._build_response_payload(draft_payload)

    @staticmethod
    async def generate_acceptance_criteria_preview(
        creator,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
        workspace_id: int,
    ) -> tuple[dict, dict]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )
        job, perception_slot = await PerceptionPreviewBuilder._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
        )

        try:
            scenario_id = int(job.target_id)
        except (TypeError, ValueError) as error:
            raise ValueError("invalid_scenario_reference") from error

        from backend.database.model import ScenarioModel
        scenario_stmt = select(ScenarioModel).where(
            ScenarioModel.id == scenario_id,
            ScenarioModel.project_id == project_id,
            ScenarioModel.workspace_id == workspace_id,
        )

        scenario_result = await session.execute(scenario_stmt)
        scenario_model = scenario_result.scalar_one_or_none()

        if scenario_model is None:
            raise ValueError("invalid_scenario_reference")

        from backend.database.model import ScenarioAcceptanceCriterionModel
        ac_stmt = select(ScenarioAcceptanceCriterionModel).where(
            ScenarioAcceptanceCriterionModel.scenario_id == scenario_id,
            ScenarioAcceptanceCriterionModel.workspace_id == workspace_id,
        )

        ac_result = await session.execute(ac_stmt)
        existing_ac = ac_result.scalars().all()

        scenarios_input = [
            ScenarioNode(
                scenarioId=scenario_model.id,
                scenarioName=scenario_model.name,
                scenarioContent=scenario_model.content,
                acceptanceCriteria=[
                    AcceptanceCriterionNode(
                        acceptanceCriterionId=ac.id,
                        position=ac.position,
                        content=ac.content,
                    )
                    for ac in existing_ac
                ],
            )
        ]

        raw = await creator._acceptance_criteria_filler.fill(
            AcceptanceCriteriaFillerInput(
                user_requirements=context.user_requirements,
                scenarios=scenarios_input,
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        filled_ac = PerceptionDraftNormalizer.normalize_filled_acceptance_criteria(
            raw=raw,
            scenarios=scenarios_input,
        )

        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "acceptance_criteria",
            "scenario_acceptance_criteria": filled_ac,
        }

        return draft_payload, PerceptionPreviewBuilder._build_response_payload(draft_payload)

    @staticmethod
    async def generate_flow_preview(
        creator,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
        workspace_id: int,
    ) -> tuple[dict, dict]:
        context, business_object_nodes = await PerceptionPreviewBuilder._load_flow_filling_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )
        _job, perception_slot = await PerceptionPreviewBuilder._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={"FLOW"},
            session=session,
            workspace_id=workspace_id,
        )

        raw = await creator._flows_filler.fill(
            FlowsFillerInput(
                user_requirements=context.user_requirements,
                flows=PerceptionPreviewBuilder._build_flow_nodes(context),
                business_objects=business_object_nodes,
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "flow",
            **PerceptionDraftNormalizer.normalize_filled_flow_payload(
                raw=raw,
                context=context,
                business_object_nodes=business_object_nodes,
            ),
        }

        return (
            draft_payload,
            PerceptionPreviewBuilder._build_flow_response_payload(
                draft_payload=draft_payload,
                context=context,
                business_object_nodes=business_object_nodes,
            ),
        )

    @staticmethod
    async def _load_perception_job_and_slot(
        project_id: int,
        perception_job_id: int,
        expected_kinds: set[str],
        session,
        workspace_id: int,
    ) -> tuple[object, PerceptionSlot]:
        from backend.database.model import PerceptionJobModel

        stmt = select(PerceptionJobModel).where(
            PerceptionJobModel.id == perception_job_id,
            PerceptionJobModel.project_id == project_id,
            PerceptionJobModel.workspace_id == workspace_id,
        )

        result = await session.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            raise ValueError("perception_job_not_found")

        if (
            job.status != PerceptionJobStatus.DONE_WITH_SLOT.value
            or not job.result_slot_payload
        ):
            raise ValueError("perception_slot_not_ready")

        payload = job.result_slot_payload
        perception_kind_code = payload.get(
            "perception_kind_code",
            job.perception_kind,
        )

        if perception_kind_code not in expected_kinds:
            raise ValueError("invalid_perception_kind")

        return (
            job,
            PerceptionSlot(
                perceptionSlotId=job.id,
                perceptionKind=PerceptionKindType[perception_kind_code],
                perceptionDescription=payload.get(
                    "perception_description",
                    "",
                ),
            ),
        )

    @staticmethod
    async def _load_flow_filling_context(
        project_id: int,
        session,
        workspace_id: int,
    ) -> tuple[IssueProjectContext, list[BusinessObjectNode]]:
        from backend.database.model import (
            BusinessObjectAttributeModel,
            BusinessObjectModel,
        )

        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
            workspace_id=workspace_id,
        )
        bo_stmt = select(BusinessObjectModel).where(
            BusinessObjectModel.project_id == project_id,
            BusinessObjectModel.workspace_id == workspace_id,
        )

        business_object_result = await session.execute(bo_stmt)
        business_object_models = business_object_result.scalars().all()
        business_object_ids = [
            business_object.id
            for business_object in business_object_models
        ]

        attributes_map: dict[int, list[BusinessObjectAttributeNode]] = {}

        if business_object_ids:
            attr_stmt = select(BusinessObjectAttributeModel).where(
                BusinessObjectAttributeModel.business_object_id.in_(
                    business_object_ids
                ),
                BusinessObjectAttributeModel.workspace_id == workspace_id,
            )

            attribute_result = await session.execute(attr_stmt)

            for attribute in attribute_result.scalars().all():
                attributes_map.setdefault(
                    attribute.business_object_id,
                    [],
                ).append(
                    BusinessObjectAttributeNode(
                        businessObjectAttributeId=attribute.id,
                        businessObjectAttributeName=attribute.name,
                        businessObjectAttributeDescription=(
                            attribute.description
                        ),
                        businessObjectAttributeType=attribute.data_type,
                        businessObjectAttributeExample=attribute.example,
                    )
                )

        return (
            context,
            [
                BusinessObjectNode(
                    businessObjectId=business_object.id,
                    businessObjectName=business_object.name,
                    businessObjectDescription=business_object.description,
                    businessObjectAttributes=attributes_map.get(
                        business_object.id,
                        [],
                    ),
                )
                for business_object in business_object_models
            ],
        )

    @staticmethod
    def _build_actor_nodes(context: IssueProjectContext) -> list[ActorNode]:
        return [
            ActorNode(
                actorId=actor.actor_id,
                actorName=actor.name,
                actorDescription=actor.description,
            )
            for actor in context.actors
        ]

    @staticmethod
    def _build_feature_nodes(context: IssueProjectContext) -> list[FeatureNode]:
        return [
            FeatureNode(
                featureId=feature.feature_id,
                featureName=feature.name,
                featureDescription=feature.description,
            )
            for feature in context.features
        ]

    @staticmethod
    def _build_flow_nodes(context: IssueProjectContext) -> list[FlowNode]:
        return [
            FlowNode(
                flowId=flow.flow_id,
                flowName=flow.name,
                flowDescription=flow.description,
                featureIds=[feature.feature_id for feature in flow.features],
                flowSteps=[
                    FlowStepNode(
                        flowStepId=step.step_id,
                        position=step.position,
                        stepName=step.name,
                        stepDescription=step.description,
                        stepType=(
                            FlowStepType[step.step_type]
                            if step.step_type in FlowStepType.__members__
                            else FlowStepType.SYSTEM_ACTION
                        ),
                        actorIds=step.actor_ids,
                        inputBusinessObjectIds=step.input_business_object_ids,
                        outputBusinessObjectIds=step.output_business_object_ids,
                    )
                    for step in flow.steps
                ],
                transitions=[
                    FlowTransitionNode(
                        transitionId=t.transition_id,
                        sourceStepId=t.source_step_id,
                        targetStepId=t.target_step_id,
                        label=t.label or "",
                        conditionText=t.condition_text or "",
                        isDefault=t.is_default,
                        position=t.position,
                    )
                    for t in flow.transitions
                ],
            )
            for flow in context.flows
        ]

    @staticmethod
    def _load_pair_nodes(
        target_id: str,
        context: IssueProjectContext,
    ) -> tuple[ActorNode, FeatureNode, list[ScenarioNode]]:
        try:
            actor_id, feature_id = PerceptionPreviewBuilder._parse_pair_target_id(target_id)
        except ValueError as error:
            raise ValueError("invalid_scenario_pair_reference") from error

        actor_model = next(
            (actor for actor in context.actors if actor.actor_id == actor_id),
            None,
        )
        feature_model = next(
            (
                feature
                for feature in context.features
                if feature.feature_id == feature_id
            ),
            None,
        )

        if actor_model is None or feature_model is None:
            raise ValueError("invalid_scenario_pair_reference")

        actor_node = ActorNode(
            actorId=actor_model.actor_id,
            actorName=actor_model.name,
            actorDescription=actor_model.description,
        )
        feature_node = FeatureNode(
            featureId=feature_model.feature_id,
            featureName=feature_model.name,
            featureDescription=feature_model.description,
        )

        from backend.schemas import ScenarioAcceptanceCriterionNode

        scenario_nodes = [
            ScenarioNode(
                scenarioId=scenario.scenario_id,
                scenarioName=scenario.name,
                scenarioContent=scenario.content,
                acceptanceCriteria=[
                    ScenarioAcceptanceCriterionNode(
                        acceptanceCriterionId=ac.id,
                        position=ac.position,
                        content=ac.content,
                    )
                    for ac in scenario.acceptance_criteria
                ],
            )
            for scenario in context.scenarios
            if (
                scenario.actor_id == actor_id
                and scenario.feature_id == feature_id
            )
        ]

        return actor_node, feature_node, scenario_nodes

    @staticmethod
    def _parse_pair_target_id(target_id: str) -> tuple[int, int]:
        parts = target_id.split(":")
        if len(parts) != 2:
            raise ValueError("invalid_format")

        return int(parts[0]), int(parts[1])

    @staticmethod
    def _build_response_payload(draft_payload: dict) -> dict:
        return {
            "project_id": draft_payload["project_id"],
            "perception_job_id": draft_payload["perception_job_id"],
            "filler_kind": draft_payload["filler_kind"],
            "actors": draft_payload.get("actors", []),
            "features": draft_payload.get("features", []),
            "scenarios": draft_payload.get("scenarios", []),
            "scenario_acceptance_criteria": draft_payload.get(
                "scenario_acceptance_criteria",
                [],
            ),
            "business_objects": draft_payload.get("business_objects", []),
            "flows": draft_payload.get("flows", []),
        }

    @staticmethod
    def _build_flow_step_preview(
        step: dict,
        actor_names: dict[int, str],
        business_object_names: dict[int, str],
        step_names: dict[str, str],
    ) -> dict:
        return {
            "step_number": step["step_number"],
            "step_name": step["step_name"],
            "step_description": step["step_description"],
            "step_type": step["step_type"],
            "actor_names": [
                actor_names[actor_id]
                for actor_id in step.get("actor_ids", [])
            ],
            "input_business_object_names": [
                business_object_names[business_object_id]
                for business_object_id in step.get(
                    "input_business_object_ids",
                    [],
                )
            ],
            "output_business_object_names": [
                business_object_names[business_object_id]
                for business_object_id in step.get(
                    "output_business_object_ids",
                    [],
                )
            ],
        }

    @staticmethod
    def _build_flow_preview(
        flow: dict,
        actor_names: dict[int, str],
        feature_names: dict[int, str],
        business_object_names: dict[int, str],
    ) -> dict:
        steps = flow.get("flow_steps", [])
        step_names = {
            step["step_number"]: step["step_name"]
            for step in steps
        }
        return {
            "flow_name": flow["flow_name"],
            "flow_description": flow["flow_description"],
            "feature_ids": flow.get("feature_ids", []),
            "feature_names": [
                feature_names[feature_id]
                for feature_id in flow.get("feature_ids", [])
            ],
            "flow_steps": [
                PerceptionPreviewBuilder._build_flow_step_preview(
                    step,
                    actor_names,
                    business_object_names,
                    step_names,
                )
                for step in steps
            ],
            "transitions": [
                {
                    "source_step_name": step_names.get(
                        t.get("source_step_number"),
                        t.get("source_step_number"),
                    ),
                    "target_step_name": step_names.get(
                        t.get("target_step_number"),
                        t.get("target_step_number"),
                    ),
                    "label": t.get("label", ""),
                    "condition_text": t.get("condition_text", ""),
                    "is_default": t.get("is_default", False),
                    "position": t.get("position", 0),
                    "semantic_tags": t.get("semantic_tags", []),
                }
                for t in flow.get("transitions", [])
            ],
        }

    @staticmethod
    def _build_flow_response_payload(
        draft_payload: dict,
        context: IssueProjectContext,
        business_object_nodes: list[BusinessObjectNode],
    ) -> dict:
        actor_name_map = {
            actor.actor_id: actor.name
            for actor in context.actors
        }
        feature_name_map = {
            feature.feature_id: feature.name
            for feature in context.features
        }
        business_object_name_map = {
            item.businessObjectId: item.businessObjectName
            for item in business_object_nodes
        }

        for item in draft_payload["business_objects"]:
            business_object_name_map[item["business_object_id"]] = item[
                "business_object_name"
            ]

        flows_preview = [
            PerceptionPreviewBuilder._build_flow_preview(
                flow,
                actor_name_map,
                feature_name_map,
                business_object_name_map,
            )
            for flow in draft_payload["flows"]
        ]

        return {
            **PerceptionPreviewBuilder._build_response_payload(
                draft_payload
            ),
            "business_objects": draft_payload["business_objects"],
            "flows": flows_preview,
        }
