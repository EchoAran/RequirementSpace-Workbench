from sqlalchemy import select

from backend.api.modules.diagnosis_quality.perception.application.invalidation import (
    mark_perception_jobs_stale,
)

from .flow_draft_persistence import persist_flow_draft


async def _exec(value):
    """兼容同步与异步 Session：execute/flush 的返回若可 await 则 await。"""
    if hasattr(value, "__await__"):
        return await value
    return value


class PerceptionDraftConfirmer:
    async def confirm_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session,
        branch_name: str | None = None,
        head_commit_id: int | None = None,
        workspace_id: int | None = None,
    ) -> dict:
        draft = await self._get_draft(draft_id, owner_user_id, session)

        # 分支/Head 漂移校验：草稿创建时的分支上下文必须与当前确认上下文一致，
        # 防止把旧分支的草稿确认写入当前分支工作区。
        self._check_branch_context(draft, branch_name, head_commit_id)

        if draft["filler_kind"] == "actor":
            result = await self._persist_actor_draft(
                draft=draft,
                session=session,
                workspace_id=workspace_id,
            )
            stale_stages = {"what", "how"}
            stale_kinds = {"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"}
        elif draft["filler_kind"] == "feature":
            result = await self._persist_feature_draft(
                draft=draft,
                session=session,
                workspace_id=workspace_id,
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
                workspace_id=workspace_id,
            )
            stale_stages = {"what"}
            stale_kinds = {"SCENARIO", "ACCEPTANCE_CRITERION"}
        elif draft["filler_kind"] == "acceptance_criteria":
            result = await self._persist_acceptance_criteria_draft(
                draft=draft,
                session=session,
                workspace_id=workspace_id,
            )
            stale_stages = {"what"}
            stale_kinds = {"ACCEPTANCE_CRITERION"}
        elif draft["filler_kind"] == "flow":
            result = await self._persist_flow_draft(
                draft=draft,
                session=session,
                workspace_id=workspace_id,
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
            workspace_id=workspace_id,
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
    def _check_branch_context(
        draft: dict,
        branch_name: str | None,
        head_commit_id: int | None,
    ) -> None:
        """校验草稿创建时的分支/Head 与当前确认上下文一致，防止跨分支误确认。"""
        stored_branch = draft.get("branch_name")
        stored_head = draft.get("head_commit_id")
        if stored_branch and branch_name and stored_branch != branch_name:
            raise ValueError("draft_branch_mismatch")
        if stored_head and head_commit_id and stored_head != head_commit_id:
            raise ValueError("branch_drift_detected")

    @staticmethod
    async def _persist_actor_draft(
        draft: dict,
        session,
        workspace_id: int | None = None,
    ) -> dict:
        from backend.database.model import ActorModel

        for item in draft["actors"]:
            session.add(
                ActorModel(
                    project_id=draft["project_id"],
                    workspace_id=workspace_id,
                    name=item["actor_name"],
                    description=item["actor_description"],
                    confirmation_status='ai_assumption',
                )
            )

        await _exec(session.flush())

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
        workspace_id: int | None = None,
    ) -> dict:
        from backend.database.model import (
            FeatureModel,
            FeatureRelationModel,
        )

        temporary_id_to_model = {}

        for item in draft["features"]:
            model = FeatureModel(
                project_id=draft["project_id"],
                workspace_id=workspace_id,
                name=item["feature_name"],
                description=item["feature_description"],
                confirmation_status='ai_assumption',
            )
            session.add(model)
            temporary_id_to_model[item["temporary_feature_id"]] = model

        await _exec(session.flush())

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
                existing_position_result = await _exec(session.execute(
                    select(FeatureRelationModel.position).where(
                        FeatureRelationModel.parent_feature_id
                        == parent_feature_id
                    )
                ))
                existing_positions = existing_position_result.scalars().all()
                parent_position_map[parent_feature_id] = (
                    max(existing_positions)
                    if existing_positions
                    else 0
                )

            parent_position_map[parent_feature_id] += 1

            session.add(
                FeatureRelationModel(
                    workspace_id=workspace_id,
                    parent_feature_id=parent_feature_id,
                    child_feature_id=child_model.id,
                    position=parent_position_map[parent_feature_id],
                )
            )

        await _exec(session.flush())

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
        workspace_id: int | None = None,
    ) -> dict:
        from backend.database.model import ScenarioModel

        for item in draft["scenarios"]:
            session.add(
                ScenarioModel(
                    project_id=draft["project_id"],
                    workspace_id=workspace_id,
                    feature_id=item["feature_id"],
                    actor_id=item["actor_id"],
                    name=item["scenario_name"],
                    content=item["scenario_content"],
                    confirmation_status='ai_assumption',
                )
            )

        await _exec(session.flush())

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
        workspace_id: int | None = None,
    ) -> dict:
        from backend.database.model import ScenarioAcceptanceCriterionModel

        scenario_ids = [
            item["scenario_id"]
            for item in draft["scenario_acceptance_criteria"]
        ]
        existing_position_result = await _exec(session.execute(
            select(
                ScenarioAcceptanceCriterionModel.scenario_id,
                ScenarioAcceptanceCriterionModel.position,
            ).where(
                ScenarioAcceptanceCriterionModel.scenario_id.in_(
                    scenario_ids
                )
            )
        ))
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
                        workspace_id=workspace_id,
                        scenario_id=scenario_id,
                        position=next_position,
                        content=criterion,
                        confirmation_status='ai_assumption',
                    )
                )
                acceptance_criterion_count += 1

            max_position_map[scenario_id] = next_position

        await _exec(session.flush())

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
        workspace_id: int | None = None,
    ) -> dict:
        return await persist_flow_draft(draft, session, workspace_id=workspace_id)
