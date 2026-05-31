from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from backend.database.model import (
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    FeatureModel,
    ActorModel,
    AuditLogModel,
    ConfirmationStatus,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.api.schemas.crud_schema import (
    ScenarioCreateRequest,
    ScenarioUpdateRequest,
    ScenarioResponse,
    ACCreateRequest,
    ACUpdateRequest,
    ACResponse,
)


class ScenarioService:
    async def create_scenario(
        self,
        project_id: int,
        req: ScenarioCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
    ) -> ScenarioResponse:
        # Verify feature exists in the project
        feature_res = await session.execute(
            select(FeatureModel).where(
                FeatureModel.project_id == project_id,
                FeatureModel.id == req.feature_id,
            )
        )
        if feature_res.scalar_one_or_none() is None:
            raise ValueError("feature_not_found")

        # Verify actor exists in the project
        actor_res = await session.execute(
            select(ActorModel).where(
                ActorModel.project_id == project_id,
                ActorModel.id == req.actor_id,
            )
        )
        if actor_res.scalar_one_or_none() is None:
            raise ValueError("actor_not_found")

        scenario = ScenarioModel(
            project_id=project_id,
            feature_id=req.feature_id,
            actor_id=req.actor_id,
            name=req.name,
            content=req.content,
            confirmation_status=confirmation_status,
        )
        session.add(scenario)
        await session.flush()

        # 审计日志: 新增场景
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="create_scenario",
            summary=f"手动新增场景: {scenario.name}",
            target_type="scenario",
            target_id=str(scenario.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
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
    ) -> ScenarioResponse:
        result = await session.execute(
            select(ScenarioModel)
            .where(
                ScenarioModel.project_id == project_id,
                ScenarioModel.id == scenario_id,
            )
            .options(selectinload(ScenarioModel.acceptance_criteria))
        )
        scenario = result.scalar_one_or_none()

        if scenario is None:
            raise ValueError("scenario_not_found")

        if req.name is not None:
            scenario.name = req.name
        if req.content is not None:
            scenario.content = req.content

        await session.flush()

        # 审计日志: 更新场景
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_scenario",
            summary=f"手动更新场景: {scenario.name}",
            target_type="scenario",
            target_id=str(scenario.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return ScenarioResponse(
            scenario_id=scenario.id,
            feature_id=scenario.feature_id,
            actor_id=scenario.actor_id,
            name=scenario.name,
            content=scenario.content,
            acceptance_criteria=[
                ACResponse(
                    criterion_id=ac.id,
                    scenario_id=ac.scenario_id,
                    content=ac.content,
                    position=ac.position,
                )
                for ac in scenario.acceptance_criteria
            ],
        )

    async def delete_scenario(
        self,
        project_id: int,
        scenario_id: int,
        session,
    ) -> dict:
        result = await session.execute(
            select(ScenarioModel).where(
                ScenarioModel.project_id == project_id,
                ScenarioModel.id == scenario_id,
            )
        )
        scenario = result.scalar_one_or_none()

        if scenario is None:
            raise ValueError("scenario_not_found")

        scenario_name = scenario.name
        await session.delete(scenario)
        await session.flush()

        # 审计日志: 删除场景
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="delete_scenario",
            summary=f"手动删除场景: {scenario_name}",
            target_type="scenario",
            target_id=str(scenario_id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return {
            "scenario_id": scenario_id,
            "message": "scenario_deleted",
        }

    async def create_ac(
        self,
        project_id: int,
        scenario_id: int,
        req: ACCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
    ) -> ACResponse:
        # Verify scenario exists and belongs to project
        scenario_res = await session.execute(
            select(ScenarioModel).where(
                ScenarioModel.project_id == project_id,
                ScenarioModel.id == scenario_id,
            )
        )
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
            scenario_id=scenario_id,
            position=position,
            content=req.content,
            confirmation_status=confirmation_status,
        )
        session.add(ac)
        await session.flush()

        # 审计日志: 新增验收标准
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="create_ac",
            summary=f"手动新增验收标准: {ac.content[:50]}...",
            target_type="acceptance_criterion",
            target_id=str(ac.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
        )

        return ACResponse(
            criterion_id=ac.id,
            scenario_id=ac.scenario_id,
            content=ac.content,
            position=ac.position,
        )

    async def update_ac(
        self,
        project_id: int,
        scenario_id: int,
        ac_id: int,
        req: ACUpdateRequest,
        session,
    ) -> ACResponse:
        # Verify scenario belongs to project
        scenario_res = await session.execute(
            select(ScenarioModel).where(
                ScenarioModel.project_id == project_id,
                ScenarioModel.id == scenario_id,
            )
        )
        if scenario_res.scalar_one_or_none() is None:
            raise ValueError("scenario_not_found")

        ac_res = await session.execute(
            select(ScenarioAcceptanceCriterionModel).where(
                ScenarioAcceptanceCriterionModel.scenario_id == scenario_id,
                ScenarioAcceptanceCriterionModel.id == ac_id,
            )
        )
        ac = ac_res.scalar_one_or_none()

        if ac is None:
            raise ValueError("acceptance_criterion_not_found")

        ac.content = req.content
        await session.flush()

        # 审计日志: 更新验收标准
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_ac",
            summary=f"手动更新验收标准: {ac.content[:50]}...",
            target_type="acceptance_criterion",
            target_id=str(ac.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
        )

        return ACResponse(
            criterion_id=ac.id,
            scenario_id=ac.scenario_id,
            content=ac.content,
            position=ac.position,
        )

    async def delete_ac(
        self,
        project_id: int,
        scenario_id: int,
        ac_id: int,
        session,
    ) -> dict:
        # Verify scenario belongs to project
        scenario_res = await session.execute(
            select(ScenarioModel).where(
                ScenarioModel.project_id == project_id,
                ScenarioModel.id == scenario_id,
            )
        )
        if scenario_res.scalar_one_or_none() is None:
            raise ValueError("scenario_not_found")

        ac_res = await session.execute(
            select(ScenarioAcceptanceCriterionModel).where(
                ScenarioAcceptanceCriterionModel.scenario_id == scenario_id,
                ScenarioAcceptanceCriterionModel.id == ac_id,
            )
        )
        ac = ac_res.scalar_one_or_none()

        if ac is None:
            raise ValueError("acceptance_criterion_not_found")

        await session.delete(ac)
        await session.flush()

        # 审计日志: 删除验收标准
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="delete_ac",
            summary=f"手动删除验收标准: ID {ac_id}",
            target_type="acceptance_criterion",
            target_id=str(ac_id),
            payload={},
        ))

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

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
        )

        return {
            "acceptance_criterion_id": ac_id,
            "message": "acceptance_criterion_deleted",
        }
