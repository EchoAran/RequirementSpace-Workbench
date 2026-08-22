from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.database.model import (
    ActorModel,
    ConfirmationStatus,
    FeatureModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
)
from backend.services.audit_service import AuditService

audit_service = AuditService()
from backend.api.modules.requirements_core.scenario.schemas import (
    AcceptanceCriterionCreateRequest,
    AcceptanceCriterionResponse,
    AcceptanceCriterionUpdateRequest,
    ScenarioCreateRequest,
    ScenarioResponse,
    ScenarioUpdateRequest,
)
from backend.core.notifier import get_notifier


class ScenarioService:
    async def create_scenario(
        self,
        project_id: int,
        req: ScenarioCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
        workspace_id: int | None = None,
    ) -> ScenarioResponse:
        # Verify feature exists in the project and workspace
        stmt_f = select(FeatureModel).where(
            FeatureModel.project_id == project_id,
            FeatureModel.id == req.feature_id,
        )
        if workspace_id is not None:
            stmt_f = stmt_f.where(FeatureModel.workspace_id == workspace_id)
        feature_res = session.execute(stmt_f)
        feat_obj = (await feature_res if hasattr(feature_res, "__await__") else feature_res).scalar_one_or_none()
        if feat_obj is None:
            raise ValueError("Cross-workspace entity reference rejected: feature_not_found_in_workspace")

        # Verify actor exists in the project and workspace
        stmt_a = select(ActorModel).where(
            ActorModel.project_id == project_id,
            ActorModel.id == req.actor_id,
        )
        if workspace_id is not None:
            stmt_a = stmt_a.where(ActorModel.workspace_id == workspace_id)
        actor_res = session.execute(stmt_a)
        actor_obj = (await actor_res if hasattr(actor_res, "__await__") else actor_res).scalar_one_or_none()
        if actor_obj is None:
            raise ValueError("Cross-workspace entity reference rejected: actor_not_found_in_workspace")

        scenario = ScenarioModel(
            project_id=project_id,
            workspace_id=workspace_id,
            feature_id=req.feature_id,
            actor_id=req.actor_id,
            name=req.name,
            content=req.content,
            confirmation_status=confirmation_status,
        )
        session.add(scenario)
        flush_res = session.flush()
        if hasattr(flush_res, "__await__"):
            await flush_res

        # 审计日志: 新增场景
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="create_scenario",
            summary=f"手动新增场景: {scenario.name}",
            target_type="scenario",
            target_id=scenario.id,
            diff={"name": scenario.name, "content": scenario.content, "confirmation_status": confirmation_status},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
        )

        return ScenarioResponse(
            scenario_id=scenario.id,
            feature_id=scenario.feature_id,
            actor_id=scenario.actor_id,
            name=scenario.name,
            content=scenario.content,
            acceptance_criteria=[],
            confirmation_status=scenario.confirmation_status,
        )

    async def update_scenario(
        self,
        project_id: int,
        scenario_id: int,
        req: ScenarioUpdateRequest,
        session,
        workspace_id: int | None = None,
    ) -> ScenarioResponse:
        stmt = (
            select(ScenarioModel)
            .where(
                ScenarioModel.project_id == project_id,
                ScenarioModel.id == scenario_id,
            )
            .options(selectinload(ScenarioModel.acceptance_criteria))
        )
        if workspace_id is not None:
            stmt = stmt.where(ScenarioModel.workspace_id == workspace_id)
        exec_res = session.execute(stmt)
        scenario = (await exec_res if hasattr(exec_res, "__await__") else exec_res).scalar_one_or_none()

        if scenario is None:
            raise ValueError("scenario_not_found_in_workspace")

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "scenario", scenario, req.last_seen_updated_at)

        old_name = scenario.name
        old_content = scenario.content

        if req.name is not None:
            scenario.name = req.name
        if req.content is not None:
            scenario.content = req.content

        flush_res = session.flush()
        if hasattr(flush_res, "__await__"):
            await flush_res

        # 审计日志: 更新场景
        diff = {}
        if old_name != scenario.name:
            diff["name"] = {"before": old_name, "after": scenario.name}
        if old_content != scenario.content:
            diff["content"] = {"before": old_content, "after": scenario.content}

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_scenario",
            summary=f"手动更新场景: {scenario.name}",
            target_type="scenario",
            target_id=scenario.id,
            diff=diff,
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
        )

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "scenario", scenario)

        return ScenarioResponse(
            scenario_id=scenario.id,
            feature_id=scenario.feature_id,
            actor_id=scenario.actor_id,
            name=scenario.name,
            content=scenario.content,
            acceptance_criteria=[
                AcceptanceCriterionResponse(
                    criterion_id=ac.id,
                    scenario_id=ac.scenario_id,
                    content=ac.content,
                    position=ac.position,
                )
                for ac in scenario.acceptance_criteria
            ],
            confirmation_status=scenario.confirmation_status,
        )

    async def delete_scenario(
        self,
        project_id: int,
        scenario_id: int,
        session,
        workspace_id: int | None = None,
    ) -> dict:
        stmt = select(ScenarioModel).where(
            ScenarioModel.project_id == project_id,
            ScenarioModel.id == scenario_id,
        )
        if workspace_id is not None:
            stmt = stmt.where(ScenarioModel.workspace_id == workspace_id)
        exec_res = session.execute(stmt)
        scenario = (await exec_res if hasattr(exec_res, "__await__") else exec_res).scalar_one_or_none()

        if scenario is None:
            raise ValueError("scenario_not_found_in_workspace")

        scenario_name = scenario.name
        await session.delete(scenario)
        await session.flush()

        # 审计日志: 删除场景
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="delete_scenario",
            summary=f"手动删除场景: {scenario_name}",
            target_type="scenario",
            target_id=scenario_id,
            diff={"status": "deleted"},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
        )

        return {
            "scenario_id": scenario_id,
            "message": "scenario_deleted",
        }

    async def create_acceptance_criterion(
        self,
        project_id: int,
        scenario_id: int,
        req: AcceptanceCriterionCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
        workspace_id: int | None = None,
    ) -> AcceptanceCriterionResponse:
        # Verify scenario exists and belongs to project and workspace
        sc_stmt = select(ScenarioModel).where(
            ScenarioModel.project_id == project_id,
            ScenarioModel.id == scenario_id,
        )
        if workspace_id is not None:
            sc_stmt = sc_stmt.where(ScenarioModel.workspace_id == workspace_id)
        scenario_res = await session.execute(sc_stmt)
        if scenario_res.scalar_one_or_none() is None:
            raise ValueError("scenario_not_found")

        if req.position is not None:
            position = req.position
        else:
            pos_result = await session.execute(
                select(func.max(ScenarioAcceptanceCriterionModel.position)).where(
                    ScenarioAcceptanceCriterionModel.scenario_id == scenario_id
                )
            )
            max_pos = pos_result.scalar()
            position = 0 if max_pos is None else max_pos + 1

        ac = ScenarioAcceptanceCriterionModel(
            workspace_id=workspace_id,
            scenario_id=scenario_id,
            position=position,
            content=req.content,
            confirmation_status=confirmation_status,
        )
        session.add(ac)
        await session.flush()

        # 审计日志: 新增验收标准
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="create_ac",
            summary=f"手动新增验收标准: {ac.content[:50]}...",
            target_type="acceptance_criterion",
            target_id=ac.id,
            diff={"content": ac.content, "position": ac.position, "confirmation_status": confirmation_status},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
        )

        return AcceptanceCriterionResponse(
            criterion_id=ac.id,
            scenario_id=ac.scenario_id,
            content=ac.content,
            position=ac.position,
        )

    async def update_acceptance_criterion(
        self,
        project_id: int,
        scenario_id: int,
        ac_id: int,
        req: AcceptanceCriterionUpdateRequest,
        session,
        workspace_id: int | None = None,
    ) -> AcceptanceCriterionResponse:
        # Verify scenario belongs to project and workspace
        sc_stmt = select(ScenarioModel).where(
            ScenarioModel.project_id == project_id,
            ScenarioModel.id == scenario_id,
        )
        if workspace_id is not None:
            sc_stmt = sc_stmt.where(ScenarioModel.workspace_id == workspace_id)
        scenario_res = await session.execute(sc_stmt)
        if scenario_res.scalar_one_or_none() is None:
            raise ValueError("scenario_not_found")

        ac_stmt = select(ScenarioAcceptanceCriterionModel).where(
            ScenarioAcceptanceCriterionModel.scenario_id == scenario_id,
            ScenarioAcceptanceCriterionModel.id == ac_id,
        )
        if workspace_id is not None:
            ac_stmt = ac_stmt.where(ScenarioAcceptanceCriterionModel.workspace_id == workspace_id)
        ac_res = await session.execute(ac_stmt)
        ac = ac_res.scalar_one_or_none()

        if ac is None:
            raise ValueError("acceptance_criterion_not_found")

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "acceptance_criterion", ac, req.last_seen_updated_at)

        old_content = ac.content

        ac.content = req.content
        await session.flush()

        # 审计日志: 更新验收标准
        diff = {}
        if old_content != ac.content:
            diff["content"] = {"before": old_content, "after": ac.content}

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_ac",
            summary=f"手动更新验收标准: {ac.content[:50]}...",
            target_type="acceptance_criterion",
            target_id=ac.id,
            diff=diff,
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
        )

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "acceptance_criterion", ac)

        return AcceptanceCriterionResponse(
            criterion_id=ac.id,
            scenario_id=ac.scenario_id,
            content=ac.content,
            position=ac.position,
        )

    async def delete_acceptance_criterion(
        self,
        project_id: int,
        scenario_id: int,
        ac_id: int,
        session,
        workspace_id: int | None = None,
    ) -> dict:
        # Verify scenario belongs to project and workspace
        sc_stmt = select(ScenarioModel).where(
            ScenarioModel.project_id == project_id,
            ScenarioModel.id == scenario_id,
        )
        if workspace_id is not None:
            sc_stmt = sc_stmt.where(ScenarioModel.workspace_id == workspace_id)
        scenario_res = await session.execute(sc_stmt)
        if scenario_res.scalar_one_or_none() is None:
            raise ValueError("scenario_not_found")

        ac_stmt = select(ScenarioAcceptanceCriterionModel).where(
            ScenarioAcceptanceCriterionModel.scenario_id == scenario_id,
            ScenarioAcceptanceCriterionModel.id == ac_id,
        )
        if workspace_id is not None:
            ac_stmt = ac_stmt.where(ScenarioAcceptanceCriterionModel.workspace_id == workspace_id)
        ac_res = await session.execute(ac_stmt)
        ac = ac_res.scalar_one_or_none()

        if ac is None:
            raise ValueError("acceptance_criterion_not_found")

        await session.delete(ac)
        await session.flush()

        # 审计日志: 删除验收标准
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="delete_ac",
            summary=f"手动删除验收标准: ID {ac_id}",
            target_type="acceptance_criterion",
            target_id=ac_id,
            diff={"status": "deleted"},
        )

        # Re-index remaining criteria position to prevent unique constraint failures
        list_res = await session.execute(
            select(ScenarioAcceptanceCriterionModel)
            .where(ScenarioAcceptanceCriterionModel.scenario_id == scenario_id)
            .order_by(ScenarioAcceptanceCriterionModel.position.asc())
        )
        ac_list = list_res.scalars().all()
        for idx, item in enumerate(ac_list):
            item.position = idx

        await session.flush()

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
            workspace_id=workspace_id,
        )

        return {
            "acceptance_criterion_id": ac_id,
            "message": "acceptance_criterion_deleted",
        }

    # Backward-compatible shims for Acceptance Criterion operations
    async def create_ac(self, project_id: int, scenario_id: int, req, session, confirmation_status=None) -> AcceptanceCriterionResponse:
        status = confirmation_status or ConfirmationStatus.NEEDS_CONFIRMATION.value
        return await self.create_acceptance_criterion(project_id, scenario_id, req, session, status)

    async def update_ac(self, project_id: int, scenario_id: int, ac_id: int, req, session) -> AcceptanceCriterionResponse:
        return await self.update_acceptance_criterion(project_id, scenario_id, ac_id, req, session)

    async def delete_ac(self, project_id: int, scenario_id: int, ac_id: int, session) -> dict:
        return await self.delete_acceptance_criterion(project_id, scenario_id, ac_id, session)
