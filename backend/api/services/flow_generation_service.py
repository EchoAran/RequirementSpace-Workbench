import re
from uuid import uuid4
from sqlalchemy import insert, select

from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.core.generators.flows_generator import (
    FlowsGenerator,
    FlowsGeneratorInput,
)
from backend.schemas import ActorNode, FeatureNode


class FlowGenerationService:
    # Below 8 leaves, one-shot generation keeps fewer LLM calls and enough context.
    _three_step_leaf_feature_threshold = 8
    _business_object_number_pattern = re.compile(
        r"^B-\d{3}$"
    )
    _step_number_pattern = re.compile(
        r"^S-\d{3}$"
    )
    _valid_step_types = {
        "actorAction",
        "systemAction",
        "judgment",
    }

    def __init__(self):
        self._flows_generator = FlowsGenerator()

    async def create_draft(self, project_id: int, owner_user_id: int, session) -> dict:
        draft_id = uuid4().hex
        draft_payload, response_payload = await self._generate_preview(
            project_id=project_id,
            user_feedback=None,
            session=session,
        )
        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=project_id,
            draft_id=draft_id,
            draft_type="flow",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def regenerate_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        user_feedback: str | None,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        draft_payload, response_payload = await self._generate_preview(
            project_id=draft["project_id"],
            user_feedback=user_feedback,
            session=session,
        )

        draft_payload["draft_id"] = draft_id
        response_payload["draft_id"] = draft_id

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.save_draft(
            project_id=draft["project_id"],
            draft_id=draft_id,
            draft_type="flow",
            payload=draft_payload,
            owner_user_id=owner_user_id,
            session=session,
        )

        return response_payload

    async def confirm_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        result = await self._persist_flow_generation_draft(
            draft=draft,
            session=session,
        )
        await mark_perception_jobs_stale(
            project_id=draft["project_id"],
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)

        return result

    async def discard_draft(
        self,
        draft_id: str,
        owner_user_id: int,
    ) -> dict:
        from backend.api.services.draft_store import GenerativeDraftStore
        await GenerativeDraftStore.discard_draft_locally(draft_id, owner_user_id)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }

    async def _get_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.api.services.draft_store import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, owner_user_id, session)

    async def _generate_preview(
        self,
        project_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        (
            user_requirements,
            actor_nodes,
            feature_nodes,
            leaf_feature_count,
        ) = await self._load_project_context(
            project_id=project_id,
            session=session,
        )
        use_three_step_generation = (
            leaf_feature_count >= self._three_step_leaf_feature_threshold
        )

        raw = await self._flows_generator.generate(
            FlowsGeneratorInput(
                user_requirements=user_requirements,
                actors=actor_nodes,
                features=feature_nodes,
                user_feedback=user_feedback,
            ),
            use_old_prompt=not use_three_step_generation,
        )
        self._validate_generated_flows(
            raw=raw,
            actor_nodes=actor_nodes,
            feature_nodes=feature_nodes,
        )

        draft_payload = {
            "project_id": project_id,
            "generation_mode": (
                "three_step"
                if use_three_step_generation
                else "single_step"
            ),
            "leaf_feature_count": leaf_feature_count,
            "business_objects": raw["business_objects"],
            "flows": raw["flows"],
        }

        response_payload = self._build_response_payload(
            project_id=project_id,
            draft_payload=draft_payload,
            actor_nodes=actor_nodes,
            feature_nodes=feature_nodes,
        )

        return draft_payload, response_payload

    @staticmethod
    async def _load_project_context(
            project_id: int,
        session,
    ) -> tuple[str, list[ActorNode], list[FeatureNode], int]:
        from backend.database.model import (
            ActorModel,
            FeatureModel,
            FeatureRelationModel,
            ProjectModel,
            feature_actor_table,
        )

        project_result = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
            )
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        actor_result = await session.execute(
            select(ActorModel).where(
                ActorModel.project_id == project_id,
            )
        )
        actor_models = actor_result.scalars().all()

        if not actor_models:
            raise ValueError("empty_actors")

        feature_result = await session.execute(
            select(FeatureModel).where(
                FeatureModel.project_id == project_id,
            )
        )
        feature_models = feature_result.scalars().all()

        if not feature_models:
            raise ValueError("empty_features")

        feature_id_set = {
            feature.id
            for feature in feature_models
        }

        relation_result = await session.execute(
            select(FeatureRelationModel).where(
                FeatureRelationModel.parent_feature_id.in_(
                    feature_id_set
                )
            )
        )
        relation_models = relation_result.scalars().all()

        feature_actor_result = await session.execute(
            select(
                feature_actor_table.c.feature_id,
                feature_actor_table.c.actor_id,
            ).where(
                feature_actor_table.c.feature_id.in_(
                    feature_id_set
                )
            )
        )
        feature_actor_rows = feature_actor_result.all()

        children_map: dict[int, list[int]] = {}
        parent_map: dict[int, int] = {}

        for relation in relation_models:
            children_map.setdefault(
                relation.parent_feature_id,
                [],
            ).append(relation.child_feature_id)

            parent_map[
                relation.child_feature_id
            ] = relation.parent_feature_id

        actor_ids_map: dict[int, list[int]] = {}

        for feature_id, actor_id in feature_actor_rows:
            actor_ids_map.setdefault(
                feature_id,
                [],
            ).append(actor_id)

        actor_nodes = [
            ActorNode(
                actorId=actor.id,
                actorName=actor.name,
                actorDescription=actor.description,
            )
            for actor in actor_models
        ]

        feature_nodes = [
            FeatureNode(
                featureId=feature.id,
                featureName=feature.name,
                featureDescription=feature.description,
                actorIds=actor_ids_map.get(feature.id, []),
                parentId=parent_map.get(feature.id),
                childrenIds=children_map.get(feature.id, []),
            )
            for feature in feature_models
        ]

        leaf_features = [
            feature
            for feature in feature_nodes
            if len(feature.childrenIds) == 0
        ]

        if not leaf_features:
            raise ValueError("empty_leaf_features")

        return (
            project.user_requirements,
            actor_nodes,
            feature_nodes,
            len(leaf_features),
        )

    def _validate_generated_flows(
        self,
        raw: dict,
        actor_nodes: list[ActorNode],
        feature_nodes: list[FeatureNode],
    ) -> None:
        business_objects = raw.get("business_objects", [])
        flows = raw.get("flows", [])

        if not business_objects:
            raise ValueError("empty_business_objects")

        if not flows:
            raise ValueError("empty_flows")

        actor_id_set = {
            actor.actorId
            for actor in actor_nodes
        }

        feature_id_set = {
            feature.featureId
            for feature in feature_nodes
        }

        business_object_numbers = [
            item["business_object_number"]
            for item in business_objects
        ]

        business_object_number_set = set(
            business_object_numbers
        )

        if len(business_object_number_set) != len(
            business_object_numbers
        ):
            raise ValueError("duplicate_business_object_number")

        for number in business_object_numbers:
            if self._business_object_number_pattern.match(number) is None:
                raise ValueError("invalid_business_object_number_format")

        for flow in flows:
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
                step["step_number"]
                for step in flow_steps
            ]

            step_number_set = set(step_numbers)

            if len(step_number_set) != len(step_numbers):
                raise ValueError("duplicate_step_number")

            for step_number in step_numbers:
                if self._step_number_pattern.match(step_number) is None:
                    raise ValueError("invalid_step_number_format")

            for step in flow_steps:
                step_type = step.get("step_type")

                if step_type not in self._valid_step_types:
                    raise ValueError("invalid_step_type")

                for actor_id in step.get("actor_ids", []):
                    if actor_id not in actor_id_set:
                        raise ValueError("invalid_actor_reference")

                for number in step.get(
                    "input_business_object_numbers",
                    [],
                ):
                    if number not in business_object_number_set:
                        raise ValueError(
                            "invalid_business_object_reference"
                        )

                for number in step.get(
                    "output_business_object_numbers",
                    [],
                ):
                    if number not in business_object_number_set:
                        raise ValueError(
                            "invalid_business_object_reference"
                        )

                for next_step_number in step.get("next_steps", []):
                    if next_step_number not in step_number_set:
                        raise ValueError("invalid_next_step_reference")

    @staticmethod
    def _build_response_payload(
            project_id: int,
        draft_payload: dict,
        actor_nodes: list[ActorNode],
        feature_nodes: list[FeatureNode],
    ) -> dict:
        actor_name_map = {
            actor.actorId: actor.actorName
            for actor in actor_nodes
        }

        feature_name_map = {
            feature.featureId: feature.featureName
            for feature in feature_nodes
        }

        business_object_name_map = {
            item["business_object_number"]: item["business_object_name"]
            for item in draft_payload["business_objects"]
        }

        business_objects_preview = []

        for item in draft_payload["business_objects"]:
           business_objects_preview.append(
                {
                    "business_object_name": item["business_object_name"],
                    "business_object_description": item[
                        "business_object_description"
                    ],
                    "business_object_attributes": item.get(
                        "business_object_attributes",
                        [],
                    ),
                }
            )

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
                        "step_name": step["step_name"],
                        "step_description": step["step_description"],
                        "step_type": step["step_type"],
                        "actor_names": [
                            actor_name_map[actor_id]
                            for actor_id in step.get(
                                "actor_ids",
                                [],
                            )
                        ],
                        "input_business_object_names": [
                            business_object_name_map[number]
                            for number in step.get(
                                "input_business_object_numbers",
                                [],
                            )
                        ],
                        "output_business_object_names": [
                            business_object_name_map[number]
                            for number in step.get(
                                "output_business_object_numbers",
                                [],
                            )
                        ],
                        "next_step_names": [
                            step_name_map[number]
                            for number in step.get(
                                "next_steps",
                                [],
                            )
                        ],
                    }
                )

            flows_preview.append(
                {
                    "flow_name": flow["flow_name"],
                    "flow_description": flow["flow_description"],
                    "feature_names": [
                        feature_name_map[feature_id]
                        for feature_id in flow.get("feature_ids", [])
                    ],
                    "flow_steps": flow_steps_preview,
                }
            )

        return {
            "project_id": project_id,
            "generation_mode": draft_payload["generation_mode"],
            "leaf_feature_count": draft_payload["leaf_feature_count"],
            "business_objects": business_objects_preview,
            "flows": flows_preview,
        }

    @staticmethod
    async def _persist_flow_generation_draft(
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

        business_object_number_to_model = {}

        for item in draft["business_objects"]:
            model = BusinessObjectModel(
                project_id=project_id,
                name=item["business_object_name"],
                description=item[
                    "business_object_description"
                ],
                confirmation_status='ai_assumption',
            )
            session.add(model)
            business_object_number_to_model[
                item["business_object_number"]
            ] = model

        await session.flush()

        for item in draft["business_objects"]:
            business_object_model = business_object_number_to_model[
                item["business_object_number"]
            ]

            for attribute in item.get(
                    "business_object_attributes",
                    [],
            ):
                example_value = attribute.get(
                    "business_object_attribute_example",
                    "",
                )

                if example_value is None:
                    example_value = ""

                session.add(
                    BusinessObjectAttributeModel(
                        business_object_id=business_object_model.id,
                        name=attribute[
                            "business_object_attribute_name"
                        ],
                        description=attribute[
                            "business_object_attribute_description"
                        ],
                        data_type=attribute[
                            "business_object_attribute_type"
                        ],
                        example=str(example_value),
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
                confirmation_status='ai_assumption',
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
                step_number_to_model[
                    step["step_number"]
                ] = step_model

            await session.flush()

            flow_step_count += len(step_number_to_model)

            for step in flow.get("flow_steps", []):
                step_model = step_number_to_model[
                    step["step_number"]
                ]

                for actor_id in step.get("actor_ids", []):
                    flow_step_actor_rows.append(
                        {
                            "flow_step_id": step_model.id,
                            "actor_id": actor_id,
                        }
                    )

                for number in step.get(
                    "input_business_object_numbers",
                    [],
                ):
                    business_object_model = business_object_number_to_model[
                        number
                    ]

                    flow_step_input_business_object_rows.append(
                        {
                            "flow_step_id": step_model.id,
                            "business_object_id": business_object_model.id,
                        }
                    )

                for number in step.get(
                    "output_business_object_numbers",
                    [],
                ):
                    business_object_model = business_object_number_to_model[
                        number
                    ]

                    flow_step_output_business_object_rows.append(
                        {
                            "flow_step_id": step_model.id,
                            "business_object_id": business_object_model.id,
                        }
                    )

                for next_step_number in step.get(
                    "next_steps",
                    [],
                ):
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
            await session.execute(
                insert(flow_feature_table),
                flow_feature_rows,
            )

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
            "business_object_count": len(
                draft["business_objects"]
            ),
            "flow_count": flow_count,
            "flow_step_count": flow_step_count,
            "message": "flows_created",
        }
