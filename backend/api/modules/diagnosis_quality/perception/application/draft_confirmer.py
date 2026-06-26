from sqlalchemy import insert, select

from backend.api.modules.diagnosis_quality.perception.application.invalidation import (
    mark_perception_jobs_stale,
)


class PerceptionDraftConfirmer:
    async def confirm_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

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

        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, session)
        return result

    async def _get_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        return await GenerativeDraftStore.get_draft(draft_id, owner_user_id, session)

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
                    confirmation_status='ai_assumption',
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
                confirmation_status='ai_assumption',
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
                    confirmation_status='ai_assumption',
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
                        confirmation_status='ai_assumption',
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
                confirmation_status='ai_assumption',
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
