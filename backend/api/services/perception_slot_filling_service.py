import re
from uuid import uuid4

from sqlalchemy import insert, select

from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)
from backend.core.perceptrons.slot_fillers.acceptance_criteria_filler import (
    AcceptanceCriteriaFiller,
    AcceptanceCriteriaFillerInput,
)
from backend.core.perceptrons.slot_fillers.actors_filler import (
    ActorsFiller,
    ActorsFillerInput,
)
from backend.core.perceptrons.slot_fillers.features_filler import (
    FeaturesFiller,
    FeaturesFillerInput,
)
from backend.core.perceptrons.slot_fillers.flows_filler import (
    FlowsFiller,
    FlowsFillerInput,
)
from backend.core.perceptrons.slot_fillers.scenarios_filler import (
    ScenariosFiller,
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
    PerceptionJobStatus,
    PerceptionKindType,
    PerceptionSlot,
    ScenarioNode,
)


class PerceptionSlotFillingService:
    _step_number_pattern = re.compile(r"^S-\d{3}$")
    _valid_step_types = {
        "actorAction",
        "systemAction",
        "judgment",
    }

    def __init__(self):
        self._actors_filler = ActorsFiller()
        self._features_filler = FeaturesFiller()
        self._scenarios_filler = ScenariosFiller()
        self._acceptance_criteria_filler = AcceptanceCriteriaFiller()
        self._flows_filler = FlowsFiller()

    async def create_actor_draft(
        self,
        project_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            perception_job_id=perception_job_id,
            filler_kind="actor",
            session=session,
        )

    async def create_feature_draft(
        self,
        project_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            perception_job_id=perception_job_id,
            filler_kind="feature",
            session=session,
        )

    async def create_scenario_draft(
        self,
        project_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            perception_job_id=perception_job_id,
            filler_kind="scenario",
            session=session,
        )

    async def create_acceptance_criteria_draft(
        self,
        project_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            perception_job_id=perception_job_id,
            filler_kind="acceptance_criteria",
            session=session,
        )

    async def create_flow_draft(
        self,
        project_id: int,
        perception_job_id: int,
        session,
    ) -> dict:
        return await self._create_draft(
            project_id=project_id,
            perception_job_id=perception_job_id,
            filler_kind="flow",
            session=session,
        )

    async def _create_draft(
        self,
        project_id: int,
        perception_job_id: int,
        filler_kind: str,
        session,
    ) -> dict:
        draft_id = uuid4().hex
        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            perception_job_id=perception_job_id,
            filler_kind=filler_kind,
            user_feedback=None,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="perception_slot_filling",
            payload=draft_payload,
            session=session,
        )

        return response_payload

    async def regenerate_draft(
        self,
        draft_id: str,
        user_feedback: str | None,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, session)

        draft_payload, response_payload = await self._generate_preview(
            project_id=draft["project_id"],
            perception_job_id=draft["perception_job_id"],
            filler_kind=draft["filler_kind"],
            user_feedback=user_feedback,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=draft["project_id"],
            draft_id=draft_id,
            draft_type="perception_slot_filling",
            payload=draft_payload,
            session=session,
        )

        return response_payload

    async def confirm_draft(
        self,
        draft_id: str,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, session)

        if draft["filler_kind"] == "actor":
            result = await self._persist_actor_draft(
                draft=draft,
                session=session,
            )
            stale_stages = {"what", "how"}
            stale_kinds = {"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"}
        elif draft["filler_kind"] == "feature":
            result = await self._persist_feature_draft(
                draft=draft,
                session=session,
            )
            stale_stages = {"what", "how", "scope"}
            stale_kinds = {
                "FEATURE",
                "SCENARIO",
                "ACCEPTANCE_CRITERION",
                "FLOW",
            }
        elif draft["filler_kind"] == "scenario":
            result = await self._persist_scenario_draft(
                draft=draft,
                session=session,
            )
            stale_stages = {"what"}
            stale_kinds = {"SCENARIO", "ACCEPTANCE_CRITERION"}
        elif draft["filler_kind"] == "acceptance_criteria":
            result = await self._persist_acceptance_criteria_draft(
                draft=draft,
                session=session,
            )
            stale_stages = {"what"}
            stale_kinds = {"ACCEPTANCE_CRITERION"}
        elif draft["filler_kind"] == "flow":
            result = await self._persist_flow_draft(
                draft=draft,
                session=session,
            )
            stale_stages = {"how"}
            stale_kinds = {"FLOW"}
        else:
            raise ValueError("unsupported_filler_kind")

        await mark_perception_jobs_stale(
            project_id=draft["project_id"],
            stages=stale_stages,
            perception_kinds=stale_kinds,
            session=session,
        )

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, session)
        return result

    async def discard_draft(
        self,
        draft_id: str,
    ) -> dict:
        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.discard_draft_locally(draft_id)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }

    async def _get_draft(
        self,
        draft_id: str,
        session,
    ) -> dict:
        from backend.api.services.draft_store import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, session)

    async def _generate_preview(
        self,
        project_id: int,
        perception_job_id: int,
        filler_kind: str,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        if filler_kind == "actor":
            return await self._generate_actor_preview(
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        if filler_kind == "feature":
            return await self._generate_feature_preview(
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        if filler_kind == "scenario":
            return await self._generate_scenario_preview(
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        if filler_kind == "acceptance_criteria":
            return await self._generate_acceptance_criteria_preview(
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        if filler_kind == "flow":
            return await self._generate_flow_preview(
                project_id=project_id,
                perception_job_id=perception_job_id,
                user_feedback=user_feedback,
                session=session,
            )

        raise ValueError("unsupported_filler_kind")

    async def _generate_actor_preview(
        self,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )
        _job, perception_slot = await self._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={"ACTOR"},
            session=session,
        )

        raw = await self._actors_filler.fill(
            ActorsFillerInput(
                user_requirements=context.user_requirements,
                actors=self._build_actor_nodes(context),
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        actors = self._normalize_filled_actors(raw)

        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "actor",
            "actors": actors,
        }

        return draft_payload, self._build_response_payload(draft_payload)

    async def _generate_feature_preview(
        self,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )
        _job, perception_slot = await self._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={
                "FEATURE_BRANCH",
                "FEATURE_LEAF",
            },
            session=session,
        )

        raw = await self._features_filler.fill(
            FeaturesFillerInput(
                user_requirements=context.user_requirements,
                features=self._build_feature_nodes(context),
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        features = self._normalize_filled_features(
            raw=raw,
            context=context,
        )

        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "feature",
            "features": features,
        }

        return draft_payload, self._build_response_payload(draft_payload)

    async def _generate_scenario_preview(
        self,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )
        job, perception_slot = await self._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={"SCENARIO"},
            session=session,
        )
        actor, feature, scenarios = self._load_pair_nodes(
            target_id=job.target_id,
            context=context,
        )

        raw = await self._scenarios_filler.fill(
            ScenariosFillerInput(
                user_requirements=context.user_requirements,
                actor=actor,
                feature=feature,
                scenarios=scenarios,
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        filled_scenarios = self._normalize_filled_scenarios(
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

        return draft_payload, self._build_response_payload(draft_payload)

    async def _generate_acceptance_criteria_preview(
        self,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )
        job, perception_slot = await self._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
        )
        actor, feature, scenarios = self._load_pair_nodes(
            target_id=job.target_id,
            context=context,
        )

        raw = await self._acceptance_criteria_filler.fill(
            AcceptanceCriteriaFillerInput(
                user_requirements=context.user_requirements,
                actor=actor,
                feature=feature,
                scenarios=scenarios,
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        scenario_acceptance_criteria = (
            self._normalize_filled_acceptance_criteria(
                raw=raw,
                scenarios=scenarios,
            )
        )

        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "acceptance_criteria",
            "scenario_acceptance_criteria": (
                scenario_acceptance_criteria
            ),
        }

        return draft_payload, self._build_response_payload(draft_payload)

    async def _generate_flow_preview(
        self,
        project_id: int,
        perception_job_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        (
            context,
            business_object_nodes,
        ) = await self._load_flow_filling_context(
            project_id=project_id,
            session=session,
        )
        _job, perception_slot = await self._load_perception_job_and_slot(
            project_id=project_id,
            perception_job_id=perception_job_id,
            expected_kinds={"FLOW"},
            session=session,
        )

        raw = await self._flows_filler.fill(
            FlowsFillerInput(
                user_requirements=context.user_requirements,
                actors=self._build_actor_nodes(context),
                features=self._build_feature_nodes(context),
                business_objects=business_object_nodes,
                flows=self._build_flow_nodes(context),
                perception_description=perception_slot,
                user_feedback=user_feedback,
            )
        )
        flow_payload = self._normalize_filled_flow_payload(
            raw=raw,
            context=context,
            business_object_nodes=business_object_nodes,
        )

        draft_payload = {
            "project_id": project_id,
            "perception_job_id": perception_job_id,
            "filler_kind": "flow",
            **flow_payload,
        }

        return draft_payload, self._build_flow_response_payload(
            draft_payload=draft_payload,
            context=context,
            business_object_nodes=business_object_nodes,
        )

    @staticmethod
    async def _load_perception_job_and_slot(
        project_id: int,
        perception_job_id: int,
        expected_kinds: set[str],
        session,
    ) -> tuple[object, PerceptionSlot]:
        from backend.database.model import PerceptionJobModel

        result = await session.execute(
            select(PerceptionJobModel).where(
                PerceptionJobModel.id == perception_job_id,
                PerceptionJobModel.project_id == project_id,
            )
        )
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
    ) -> tuple[IssueProjectContext, list[BusinessObjectNode]]:
        from backend.database.model import (
            BusinessObjectAttributeModel,
            BusinessObjectModel,
        )

        context = await load_issue_project_context(
            project_id=project_id,
            session=session,
        )
        business_object_result = await session.execute(
            select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id
            )
        )
        business_object_models = business_object_result.scalars().all()
        business_object_ids = [
            business_object.id
            for business_object in business_object_models
        ]

        attributes_map: dict[int, list[BusinessObjectAttributeNode]] = {}

        if business_object_ids:
            attribute_result = await session.execute(
                select(BusinessObjectAttributeModel).where(
                    BusinessObjectAttributeModel.business_object_id.in_(
                        business_object_ids
                    )
                )
            )

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
                actorIds=feature.actor_ids,
                parentId=feature.parent_id,
                childrenIds=feature.child_ids,
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
                featureIds=flow.feature_ids,
                flowSteps=[
                    FlowStepNode(
                        stepId=step.step_id,
                        stepName=step.name,
                        stepDescription=step.description,
                        stepType=(
                            FlowStepType(step.step_type)
                            if step.step_type in FlowStepType._value2member_map_
                            else FlowStepType.SYSTEM_ACTION
                        ),
                        actorIds=step.actor_ids,
                        inputBusinessObjectIds=(
                            step.input_business_object_ids
                        ),
                        outputBusinessObjectIds=(
                            step.output_business_object_ids
                        ),
                        nextStepIds=step.next_step_ids,
                    )
                    for step in flow.steps
                ],
            )
            for flow in context.flows
        ]

    def _load_pair_nodes(
        self,
        target_id: str,
        context: IssueProjectContext,
    ) -> tuple[ActorNode, FeatureNode, list[ScenarioNode]]:
        feature_id, actor_id = self._parse_pair_target_id(target_id)
        actor_node_map = {
            actor.actorId: actor
            for actor in self._build_actor_nodes(context)
        }
        feature_node_map = {
            feature.featureId: feature
            for feature in self._build_feature_nodes(context)
        }

        actor = actor_node_map.get(actor_id)
        feature = feature_node_map.get(feature_id)

        if actor is None or feature is None:
            raise ValueError("invalid_perception_target")

        scenarios = [
            ScenarioNode(
                scenarioId=scenario.scenario_id,
                scenarioName=scenario.name,
                scenarioContent=scenario.content,
                featureId=scenario.feature_id,
                actorId=scenario.actor_id,
                acceptanceCriteria=[
                    AcceptanceCriterionNode(
                        criterionId=criterion.criterion_id,
                        criterionContent=criterion.content,
                    )
                    for criterion in scenario.acceptance_criteria
                ],
            )
            for scenario in context.scenarios
            if (
                scenario.feature_id == feature_id
                and scenario.actor_id == actor_id
            )
        ]

        if not scenarios:
            raise ValueError("empty_scenarios")

        return actor, feature, scenarios

    @staticmethod
    def _parse_pair_target_id(target_id: str) -> tuple[int, int]:
        try:
            feature_id_text, actor_id_text = target_id.split(":", 1)
            return int(feature_id_text), int(actor_id_text)
        except (ValueError, TypeError) as error:
            raise ValueError("invalid_perception_target") from error

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
    def _normalize_filled_actors(raw: dict | None) -> list[dict]:
        if raw is None:
            raise ValueError("empty_filler_response")

        raw_actors = raw.get("actors", [])

        if not raw_actors:
            raise ValueError("empty_actors")

        actors = []

        for item in raw_actors:
            actor_name = item.get("actor_name")
            actor_description = item.get("actor_description")

            if not actor_name or not actor_description:
                raise ValueError("invalid_actor_payload")

            actors.append(
                {
                    "actor_name": actor_name,
                    "actor_description": actor_description,
                }
            )

        return actors

    @staticmethod
    def _normalize_filled_features(
        raw: dict | None,
        context: IssueProjectContext,
    ) -> list[dict]:
        if raw is None:
            raise ValueError("empty_filler_response")

        raw_features = raw.get("features", [])

        if not raw_features:
            raise ValueError("empty_features")

        existing_feature_ids = {
            feature.feature_id
            for feature in context.features
        }
        temporary_feature_ids = set()
        features = []

        for item in raw_features:
            temporary_feature_id = item.get("feature_id")
            feature_name = item.get("feature_name")
            feature_description = item.get("feature_description")
            parent_id = item.get("parent_id")

            if temporary_feature_id is None:
                raise ValueError("invalid_feature_payload")

            try:
                temporary_feature_id = int(temporary_feature_id)
            except (TypeError, ValueError) as error:
                raise ValueError("invalid_feature_payload") from error

            if temporary_feature_id in temporary_feature_ids:
                raise ValueError("duplicate_feature_id")

            if not feature_name or not feature_description:
                raise ValueError("invalid_feature_payload")

            if parent_id is None:
                raise ValueError("missing_parent_feature")

            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError) as error:
                raise ValueError("missing_parent_feature") from error

            temporary_feature_ids.add(temporary_feature_id)
            features.append(
                {
                    "temporary_feature_id": temporary_feature_id,
                    "feature_name": feature_name,
                    "feature_description": feature_description,
                    "parent_temporary_feature_id": (
                        parent_id
                        if parent_id not in existing_feature_ids
                        else None
                    ),
                    "parent_feature_id": (
                        parent_id
                        if parent_id in existing_feature_ids
                        else None
                    ),
                }
            )

        # Generated parent references are allowed, but they must point to a
        # feature in the same draft so confirm can build relations
        # deterministically.
        for item in features:
            parent_temporary_feature_id = item["parent_temporary_feature_id"]

            if (
                parent_temporary_feature_id is not None
                and parent_temporary_feature_id not in temporary_feature_ids
            ):
                raise ValueError("missing_parent_feature")

        return features

    @staticmethod
    def _normalize_filled_scenarios(
        raw: dict | None,
        actor: ActorNode,
        feature: FeatureNode,
    ) -> list[dict]:
        if raw is None:
            raise ValueError("empty_filler_response")

        raw_scenarios = raw.get("scenarios", [])

        if not raw_scenarios:
            raise ValueError("empty_scenarios")

        scenarios = []

        for item in raw_scenarios:
            scenario_name = item.get("scenario_name", "")
            scenario_content = item.get("scenario_content", "")

            if not scenario_name or not scenario_content:
                raise ValueError("invalid_scenario_payload")

            scenarios.append(
                {
                    "feature_id": feature.featureId,
                    "feature_name": feature.featureName,
                    "actor_id": actor.actorId,
                    "actor_name": actor.actorName,
                    "scenario_name": scenario_name,
                    "scenario_content": scenario_content,
                }
            )

        return scenarios

    @staticmethod
    def _normalize_filled_acceptance_criteria(
        raw: dict | None,
        scenarios: list[ScenarioNode],
    ) -> list[dict]:
        if raw is None:
            raise ValueError("empty_filler_response")

        raw_items = raw.get("scenario_acceptance_criteria", [])

        if not raw_items:
            raise ValueError("empty_acceptance_criteria")

        scenario_name_map = {
            scenario.scenarioId: scenario.scenarioName
            for scenario in scenarios
        }
        seen_scenario_ids = set()
        result = []

        for item in raw_items:
            try:
                scenario_id = int(item.get("scenario_id"))
            except (TypeError, ValueError) as error:
                raise ValueError("invalid_scenario_reference") from error

            if scenario_id not in scenario_name_map:
                raise ValueError("invalid_scenario_reference")

            if scenario_id in seen_scenario_ids:
                raise ValueError("duplicate_scenario_id")

            seen_scenario_ids.add(scenario_id)
            raw_criteria = item.get("acceptance_criteria", [])

            if not isinstance(raw_criteria, list) or not raw_criteria:
                raise ValueError("empty_acceptance_criteria")

            acceptance_criteria = []

            for criterion in raw_criteria:
                if not isinstance(criterion, str):
                    raise ValueError("invalid_acceptance_criteria_payload")

                criterion = criterion.strip()

                if not criterion:
                    raise ValueError("invalid_acceptance_criteria_payload")

                acceptance_criteria.append(criterion)

            result.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_name_map[scenario_id],
                    "acceptance_criteria": acceptance_criteria,
                }
            )

        return result

    def _normalize_filled_flow_payload(
        self,
        raw: dict | None,
        context: IssueProjectContext,
        business_object_nodes: list[BusinessObjectNode],
    ) -> dict:
        if raw is None:
            raise ValueError("empty_filler_response")

        (
            business_objects,
            business_object_ref_map,
        ) = self._normalize_filled_business_objects(
            raw.get("business_objects", []),
            business_object_nodes,
        )
        flows = self._normalize_filled_flows(
            raw.get("flows", []),
            business_object_ref_map,
        )

        self._validate_filled_flows(
            flows=flows,
            business_objects=business_objects,
            context=context,
            business_object_nodes=business_object_nodes,
        )

        return {
            "business_objects": business_objects,
            "flows": flows,
        }

    def _normalize_filled_flows(
        self,
        raw_flows: list[dict],
        business_object_ref_map: dict[object, int],
    ) -> list[dict]:
        if not isinstance(raw_flows, list) or not raw_flows:
            raise ValueError("empty_flows")

        flows = []

        for flow in raw_flows:
            if not isinstance(flow, dict):
                raise ValueError("invalid_flow_payload")

            raw_steps = flow.get("flow_steps", [])

            if not isinstance(raw_steps, list) or not raw_steps:
                raise ValueError("empty_flow_steps")

            step_aliases: dict[object, str] = {}
            used_step_numbers: set[str] = set()
            normalized_steps = []

            for index, step in enumerate(raw_steps, start=1):
                if not isinstance(step, dict):
                    raise ValueError("invalid_flow_step_payload")

                raw_step_number = step.get("step_number")
                step_number = self._normalize_step_number(
                    raw_step_number,
                    index,
                )

                if step_number in used_step_numbers:
                    step_number = self._next_available_step_number(
                        index,
                        used_step_numbers,
                    )

                used_step_numbers.add(step_number)

                for alias in {
                    raw_step_number,
                    "" if raw_step_number is None else str(raw_step_number),
                    step_number,
                }:
                    if alias != "":
                        step_aliases[alias] = step_number

                normalized_steps.append(
                    {
                        **step,
                        "step_number": step_number,
                    }
                )

            for step in normalized_steps:
                step["step_type"] = self._normalize_step_type(
                    step.get("step_type")
                )
                step["actor_ids"] = self._dedupe_int_values(
                    step.get("actor_ids", [])
                )
                step["input_business_object_ids"] = (
                    self._dedupe_business_object_refs(
                        self._coerce_list(
                            step.get("input_business_object_ids", [])
                        )
                        + self._coerce_list(
                            step.get("input_business_object_numbers", [])
                        ),
                        business_object_ref_map,
                    )
                )
                step["output_business_object_ids"] = (
                    self._dedupe_business_object_refs(
                        self._coerce_list(
                            step.get("output_business_object_ids", [])
                        )
                        + self._coerce_list(
                            step.get("output_business_object_numbers", [])
                        ),
                        business_object_ref_map,
                    )
                )
                step["next_steps"] = self._normalize_next_steps(
                    step.get("next_steps", []),
                    step_aliases,
                    used_step_numbers,
                )

            flows.append(
                {
                    **flow,
                    "feature_ids": self._dedupe_int_values(
                        flow.get("feature_ids", [])
                    ),
                    "flow_steps": normalized_steps,
                }
            )

        return flows

    @classmethod
    def _normalize_step_number(
        cls,
        value: object,
        fallback_index: int,
    ) -> str:
        if isinstance(value, str):
            stripped = value.strip().upper()
            if cls._step_number_pattern.match(stripped) is not None:
                return stripped

            match = re.match(r"^S-?(\d+)$", stripped)
            if match:
                return f"S-{int(match.group(1)):03d}"

            if stripped.isdigit():
                return f"S-{int(stripped):03d}"

        if isinstance(value, int):
            return f"S-{value:03d}"

        return f"S-{fallback_index:03d}"

    @classmethod
    def _next_available_step_number(
        cls,
        preferred_index: int,
        used_step_numbers: set[str],
    ) -> str:
        index = preferred_index

        while True:
            step_number = f"S-{index:03d}"

            if step_number not in used_step_numbers:
                return step_number

            index += 1

    @staticmethod
    def _normalize_step_type(value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized = re.sub(r"[^a-z]", "", value.lower())
        aliases = {
            "actoraction": "actorAction",
            "actor": "actorAction",
            "useraction": "actorAction",
            "systemaction": "systemAction",
            "system": "systemAction",
            "judgment": "judgment",
            "decision": "judgment",
            "condition": "judgment",
        }

        return aliases.get(normalized, value)

    @staticmethod
    def _coerce_list(value: object) -> list:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    @classmethod
    def _dedupe_int_values(cls, values: object) -> list[int]:
        result = []
        seen = set()

        for value in cls._coerce_list(values):
            try:
                int_value = int(value)
            except (TypeError, ValueError):
                continue

            if int_value in seen:
                continue

            seen.add(int_value)
            result.append(int_value)

        return result

    @classmethod
    def _dedupe_business_object_refs(
        cls,
        values: object,
        business_object_ref_map: dict[object, int],
    ) -> list[int]:
        result = []
        seen = set()

        for value in cls._coerce_list(values):
            business_object_id = (
                business_object_ref_map.get(value)
                or business_object_ref_map.get(str(value))
            )

            if business_object_id is None:
                try:
                    business_object_id = int(value)
                except (TypeError, ValueError):
                    continue

            if business_object_id in seen:
                continue

            seen.add(business_object_id)
            result.append(business_object_id)

        return result

    @classmethod
    def _normalize_next_steps(
        cls,
        values: object,
        step_aliases: dict[object, str],
        step_number_set: set[str],
    ) -> list[str]:
        result = []
        seen = set()

        for value in cls._coerce_list(values):
            step_number = (
                step_aliases.get(value)
                or step_aliases.get(str(value))
                or cls._normalize_step_number(value, 0)
            )

            if step_number not in step_number_set or step_number in seen:
                continue

            seen.add(step_number)
            result.append(step_number)

        return result

    @staticmethod
    def _normalize_filled_business_objects(
        raw_items: list[dict],
        business_object_nodes: list[BusinessObjectNode],
    ) -> tuple[list[dict], dict[object, int]]:
        if not isinstance(raw_items, list):
            raise ValueError("invalid_business_object_payload")

        existing_business_object_ids = {
            item.businessObjectId
            for item in business_object_nodes
        }
        business_object_ref_map: dict[object, int] = {}

        for business_object_id in existing_business_object_ids:
            business_object_ref_map[business_object_id] = business_object_id
            business_object_ref_map[str(business_object_id)] = (
                business_object_id
            )

        seen_business_object_ids = set()
        business_objects = []
        next_temporary_business_object_id = -1

        for item in raw_items:
            if not isinstance(item, dict):
                raise ValueError("invalid_business_object_payload")

            business_object_ref = (
                item.get("business_object_id")
                if item.get("business_object_id") is not None
                else item.get("business_object_number")
            )

            if business_object_ref is None:
                raise ValueError("invalid_business_object_payload")

            try:
                business_object_id = int(business_object_ref)
            except (TypeError, ValueError):
                while (
                    next_temporary_business_object_id
                    in seen_business_object_ids
                ):
                    next_temporary_business_object_id -= 1

                business_object_id = next_temporary_business_object_id
                next_temporary_business_object_id -= 1

            if business_object_id in seen_business_object_ids:
                raise ValueError("duplicate_business_object_id")

            seen_business_object_ids.add(business_object_id)
            business_object_ref_map[business_object_ref] = business_object_id
            business_object_ref_map[str(business_object_ref)] = (
                business_object_id
            )

            business_object_number = item.get("business_object_number")

            if business_object_number is not None:
                business_object_ref_map[business_object_number] = (
                    business_object_id
                )
                business_object_ref_map[str(business_object_number)] = (
                    business_object_id
                )

            business_object_name = item.get("business_object_name", "")
            business_object_description = item.get(
                "business_object_description",
                "",
            )

            if not business_object_name or not business_object_description:
                raise ValueError("invalid_business_object_payload")

            attributes = []

            attributes_payload = item.get(
                "business_object_attributes",
                [],
            )

            if attributes_payload is None:
                attributes_payload = []

            if not isinstance(attributes_payload, list):
                raise ValueError("invalid_business_object_payload")

            for attribute in attributes_payload:
                if not isinstance(attribute, dict):
                    raise ValueError("invalid_business_object_payload")

                attribute_name = attribute.get(
                    "business_object_attribute_name",
                    "",
                )
                attribute_description = attribute.get(
                    "business_object_attribute_description",
                    "",
                )
                attribute_type = attribute.get(
                    "business_object_attribute_type",
                    "",
                )
                attribute_example = attribute.get(
                    "business_object_attribute_example",
                    "",
                )

                if (
                    not attribute_name
                    or not attribute_description
                    or not attribute_type
                ):
                    raise ValueError("invalid_business_object_payload")

                attributes.append(
                    {
                        "business_object_attribute_name": attribute_name,
                        "business_object_attribute_description": (
                            attribute_description
                        ),
                        "business_object_attribute_type": attribute_type,
                        "business_object_attribute_example": (
                            ""
                            if attribute_example is None
                            else str(attribute_example)
                        ),
                    }
                )

            business_objects.append(
                {
                    "business_object_id": business_object_id,
                    "business_object_name": business_object_name,
                    "business_object_description": (
                        business_object_description
                    ),
                    "is_existing": (
                        business_object_id in existing_business_object_ids
                    ),
                    "business_object_attributes": attributes,
                }
            )

        return business_objects, business_object_ref_map

    def _validate_filled_flows(
        self,
        flows: list[dict],
        business_objects: list[dict],
        context: IssueProjectContext,
        business_object_nodes: list[BusinessObjectNode],
    ) -> None:
        actor_id_set = {
            actor.actor_id
            for actor in context.actors
        }
        feature_id_set = {
            feature.feature_id
            for feature in context.features
        }
        business_object_id_set = {
            item.businessObjectId
            for item in business_object_nodes
        } | {
            item["business_object_id"]
            for item in business_objects
        }

        for flow in flows:
            if not isinstance(flow, dict):
                raise ValueError("invalid_flow_payload")

            if not flow.get("flow_name") or not flow.get(
                "flow_description"
            ):
                raise ValueError("invalid_flow_payload")

            feature_ids = flow.get("feature_ids", [])

            if not feature_ids:
                raise ValueError("invalid_feature_reference")

            for feature_id in feature_ids:
                if feature_id not in feature_id_set:
                    raise ValueError("invalid_feature_reference")

            flow_steps = flow.get("flow_steps", [])

            if not flow_steps:
                raise ValueError("empty_flow_steps")

            step_numbers = [
                step.get("step_number")
                for step in flow_steps
            ]
            step_number_set = set(step_numbers)

            if len(step_number_set) != len(step_numbers):
                raise ValueError("duplicate_step_number")

            for step_number in step_numbers:
                if (
                    not isinstance(step_number, str)
                    or self._step_number_pattern.match(step_number) is None
                ):
                    raise ValueError("invalid_step_number_format")

            for step in flow_steps:
                step_type = step.get("step_type")

                if step_type not in self._valid_step_types:
                    raise ValueError("invalid_step_type")

                if not step.get("step_name") or not step.get(
                    "step_description"
                ):
                    raise ValueError("invalid_flow_step_payload")

                for actor_id in step.get("actor_ids", []):
                    if actor_id not in actor_id_set:
                        raise ValueError("invalid_actor_reference")

                for business_object_id in step.get(
                    "input_business_object_ids",
                    [],
                ):
                    if business_object_id not in business_object_id_set:
                        raise ValueError(
                            "invalid_business_object_reference"
                        )

                for business_object_id in step.get(
                    "output_business_object_ids",
                    [],
                ):
                    if business_object_id not in business_object_id_set:
                        raise ValueError(
                            "invalid_business_object_reference"
                        )

                for next_step_number in step.get("next_steps", []):
                    if next_step_number not in step_number_set:
                        raise ValueError("invalid_next_step_reference")

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

        flows_preview = []

        for flow in draft_payload["flows"]:
            step_name_map = {
                step["step_number"]: step["step_name"]
                for step in flow.get("flow_steps", [])
            }
            flow_steps_preview = []

            for step in flow.get("flow_steps", []):
                flow_steps_preview.append(
                    {
                        "step_number": step["step_number"],
                        "step_name": step["step_name"],
                        "step_description": step["step_description"],
                        "step_type": step["step_type"],
                        "actor_names": [
                            actor_name_map[actor_id]
                            for actor_id in step.get("actor_ids", [])
                        ],
                        "input_business_object_names": [
                            business_object_name_map[business_object_id]
                            for business_object_id in step.get(
                                "input_business_object_ids",
                                [],
                            )
                        ],
                        "output_business_object_names": [
                            business_object_name_map[business_object_id]
                            for business_object_id in step.get(
                                "output_business_object_ids",
                                [],
                            )
                        ],
                        "next_step_names": [
                            step_name_map[step_number]
                            for step_number in step.get("next_steps", [])
                        ],
                        "next_steps": step.get("next_steps", []),
                    }
                )

            flows_preview.append(
                {
                    "flow_name": flow["flow_name"],
                    "flow_description": flow["flow_description"],
                    "feature_ids": flow.get("feature_ids", []),
                    "feature_names": [
                        feature_name_map[feature_id]
                        for feature_id in flow.get("feature_ids", [])
                    ],
                    "flow_steps": flow_steps_preview,
                }
            )

        return {
            **PerceptionSlotFillingService._build_response_payload(
                draft_payload
            ),
            "business_objects": draft_payload["business_objects"],
            "flows": flows_preview,
        }

    @staticmethod
    async def _persist_actor_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import ActorModel

        for item in draft["actors"]:
            session.add(
                ActorModel(
                    project_id=draft["project_id"],
                    name=item["actor_name"],
                    description=item["actor_description"],
                )
            )

        await session.flush()

        return {
            "project_id": draft["project_id"],
            "filler_kind": "actor",
            "created_count": len(draft["actors"]),
            "message": "perception_slot_filled",
        }

    @staticmethod
    async def _persist_feature_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import (
            FeatureModel,
            FeatureRelationModel,
        )

        temporary_id_to_model = {}

        for item in draft["features"]:
            model = FeatureModel(
                project_id=draft["project_id"],
                name=item["feature_name"],
                description=item["feature_description"],
            )
            session.add(model)
            temporary_id_to_model[item["temporary_feature_id"]] = model

        await session.flush()

        parent_position_map: dict[int, int] = {}

        for item in draft["features"]:
            child_model = temporary_id_to_model[item["temporary_feature_id"]]
            parent_feature_id = item["parent_feature_id"]

            if parent_feature_id is None:
                parent_model = temporary_id_to_model[
                    item["parent_temporary_feature_id"]
                ]
                parent_feature_id = parent_model.id

            if parent_feature_id not in parent_position_map:
                existing_position_result = await session.execute(
                    select(FeatureRelationModel.position).where(
                        FeatureRelationModel.parent_feature_id
                        == parent_feature_id
                    )
                )
                existing_positions = existing_position_result.scalars().all()
                parent_position_map[parent_feature_id] = (
                    max(existing_positions)
                    if existing_positions
                    else 0
                )

            parent_position_map[parent_feature_id] += 1

            session.add(
                FeatureRelationModel(
                    parent_feature_id=parent_feature_id,
                    child_feature_id=child_model.id,
                    position=parent_position_map[parent_feature_id],
                )
            )

        await session.flush()

        return {
            "project_id": draft["project_id"],
            "filler_kind": "feature",
            "created_count": len(draft["features"]),
            "message": "perception_slot_filled",
        }

    @staticmethod
    async def _persist_scenario_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import ScenarioModel

        for item in draft["scenarios"]:
            session.add(
                ScenarioModel(
                    project_id=draft["project_id"],
                    feature_id=item["feature_id"],
                    actor_id=item["actor_id"],
                    name=item["scenario_name"],
                    content=item["scenario_content"],
                )
            )

        await session.flush()

        return {
            "project_id": draft["project_id"],
            "filler_kind": "scenario",
            "created_count": len(draft["scenarios"]),
            "scenario_count": len(draft["scenarios"]),
            "message": "perception_slot_filled",
        }

    @staticmethod
    async def _persist_acceptance_criteria_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import ScenarioAcceptanceCriterionModel

        scenario_ids = [
            item["scenario_id"]
            for item in draft["scenario_acceptance_criteria"]
        ]
        existing_position_result = await session.execute(
            select(
                ScenarioAcceptanceCriterionModel.scenario_id,
                ScenarioAcceptanceCriterionModel.position,
            ).where(
                ScenarioAcceptanceCriterionModel.scenario_id.in_(
                    scenario_ids
                )
            )
        )
        max_position_map: dict[int, int] = {}

        for scenario_id, position in existing_position_result.all():
            max_position_map[scenario_id] = max(
                max_position_map.get(scenario_id, 0),
                position,
            )

        acceptance_criterion_count = 0

        for item in draft["scenario_acceptance_criteria"]:
            scenario_id = item["scenario_id"]
            next_position = max_position_map.get(scenario_id, 0)

            for criterion in item["acceptance_criteria"]:
                next_position += 1
                session.add(
                    ScenarioAcceptanceCriterionModel(
                        scenario_id=scenario_id,
                        position=next_position,
                        content=criterion,
                    )
                )
                acceptance_criterion_count += 1

            max_position_map[scenario_id] = next_position

        await session.flush()

        return {
            "project_id": draft["project_id"],
            "filler_kind": "acceptance_criteria",
            "created_count": acceptance_criterion_count,
            "acceptance_criterion_count": acceptance_criterion_count,
            "message": "perception_slot_filled",
        }

    @staticmethod
    async def _persist_flow_draft(
        draft: dict,
        session,
    ) -> dict:
        from backend.database.model import (
            BusinessObjectAttributeModel,
            BusinessObjectModel,
            FlowModel,
            FlowStepModel,
            flow_feature_table,
            flow_step_actor_table,
            flow_step_input_business_object_table,
            flow_step_next_table,
            flow_step_output_business_object_table,
        )

        project_id = draft["project_id"]
        business_object_id_to_model_id = {}
        business_object_count = 0

        for item in draft["business_objects"]:
            if item["is_existing"]:
                business_object_id_to_model_id[
                    item["business_object_id"]
                ] = item["business_object_id"]
                continue

            model = BusinessObjectModel(
                project_id=project_id,
                name=item["business_object_name"],
                description=item["business_object_description"],
            )
            session.add(model)
            await session.flush()

            business_object_count += 1
            business_object_id_to_model_id[item["business_object_id"]] = (
                model.id
            )

            for attribute in item.get("business_object_attributes", []):
                session.add(
                    BusinessObjectAttributeModel(
                        business_object_id=model.id,
                        name=attribute[
                            "business_object_attribute_name"
                        ],
                        description=attribute[
                            "business_object_attribute_description"
                        ],
                        data_type=attribute[
                            "business_object_attribute_type"
                        ],
                        example=attribute[
                            "business_object_attribute_example"
                        ],
                    )
                )

        await session.flush()

        flow_count = 0
        flow_step_count = 0
        flow_feature_rows = []
        flow_step_actor_rows = []
        flow_step_input_business_object_rows = []
        flow_step_output_business_object_rows = []
        flow_step_next_rows = []

        for flow in draft["flows"]:
            flow_model = FlowModel(
                project_id=project_id,
                name=flow["flow_name"],
                description=flow["flow_description"],
            )
            session.add(flow_model)
            await session.flush()

            flow_count += 1

            for feature_id in flow.get("feature_ids", []):
                flow_feature_rows.append(
                    {
                        "flow_id": flow_model.id,
                        "feature_id": feature_id,
                    }
                )

            step_number_to_model = {}

            for position, step in enumerate(
                flow.get("flow_steps", []),
                start=1,
            ):
                step_model = FlowStepModel(
                    flow_id=flow_model.id,
                    position=position,
                    name=step["step_name"],
                    description=step["step_description"],
                    step_type=step["step_type"],
                )
                session.add(step_model)
                step_number_to_model[step["step_number"]] = step_model

            await session.flush()
            flow_step_count += len(step_number_to_model)

            for step in flow.get("flow_steps", []):
                step_model = step_number_to_model[step["step_number"]]

                for actor_id in step.get("actor_ids", []):
                    flow_step_actor_rows.append(
                        {
                            "flow_step_id": step_model.id,
                            "actor_id": actor_id,
                        }
                    )

                for business_object_id in step.get(
                    "input_business_object_ids",
                    [],
                ):
                    flow_step_input_business_object_rows.append(
                        {
                            "flow_step_id": step_model.id,
                            "business_object_id": (
                                business_object_id_to_model_id.get(
                                    business_object_id,
                                    business_object_id,
                                )
                            ),
                        }
                    )

                for business_object_id in step.get(
                    "output_business_object_ids",
                    [],
                ):
                    flow_step_output_business_object_rows.append(
                        {
                            "flow_step_id": step_model.id,
                            "business_object_id": (
                                business_object_id_to_model_id.get(
                                    business_object_id,
                                    business_object_id,
                                )
                            ),
                        }
                    )

                for next_step_number in step.get("next_steps", []):
                    target_step_model = step_number_to_model[
                        next_step_number
                    ]
                    flow_step_next_rows.append(
                        {
                            "source_step_id": step_model.id,
                            "target_step_id": target_step_model.id,
                        }
                    )

        if flow_feature_rows:
            await session.execute(insert(flow_feature_table), flow_feature_rows)

        if flow_step_actor_rows:
            await session.execute(
                insert(flow_step_actor_table),
                flow_step_actor_rows,
            )

        if flow_step_input_business_object_rows:
            await session.execute(
                insert(flow_step_input_business_object_table),
                flow_step_input_business_object_rows,
            )

        if flow_step_output_business_object_rows:
            await session.execute(
                insert(flow_step_output_business_object_table),
                flow_step_output_business_object_rows,
            )

        if flow_step_next_rows:
            await session.execute(
                insert(flow_step_next_table),
                flow_step_next_rows,
            )

        await session.flush()

        return {
            "project_id": project_id,
            "filler_kind": "flow",
            "created_count": flow_count + business_object_count,
            "business_object_count": business_object_count,
            "flow_count": flow_count,
            "flow_step_count": flow_step_count,
            "message": "perception_slot_filled",
        }
