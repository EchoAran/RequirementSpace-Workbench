import sqlalchemy as sa

from backend.database.model import (
    ActorModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    CollaborationTaskModel,
    ConfirmationStatus,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    UserModel,
)


def _project_node_count(model, project_id: int):
    return sa.select(sa.func.count(model.id)).where(
        model.project_id == project_id,
        model.confirmation_status == ConfirmationStatus.AI_ASSUMPTION.value,
    )


def _child_node_count(model, relation, project_id: int):
    parent_model = relation.property.mapper.class_
    return sa.select(sa.func.count(model.id)).join(relation).where(
        parent_model.project_id == project_id,
        model.confirmation_status == ConfirmationStatus.AI_ASSUMPTION.value,
    )


async def _count_ai_assumptions(session, project_id: int) -> int:
    statements = [
        _project_node_count(ActorModel, project_id),
        _project_node_count(FeatureModel, project_id),
        _project_node_count(ScenarioModel, project_id),
        _child_node_count(
            ScenarioAcceptanceCriterionModel,
            ScenarioAcceptanceCriterionModel.scenario,
            project_id,
        ),
        _project_node_count(BusinessObjectModel, project_id),
        _child_node_count(
            BusinessObjectAttributeModel,
            BusinessObjectAttributeModel.business_object,
            project_id,
        ),
        _project_node_count(FlowModel, project_id),
        _child_node_count(
            FlowStepModel,
            FlowStepModel.flow,
            project_id,
        ),
        sa.select(sa.func.count(ScopeModel.id))
        .join(ScopeModel.feature)
        .where(
            FeatureModel.project_id == project_id,
            ScopeModel.confirmation_status
            == ConfirmationStatus.AI_ASSUMPTION.value,
        ),
    ]
    result = await session.execute(sa.union_all(*statements))
    return sum(result.scalars().all())


async def _load_task_counts(
    session,
    project_id: int,
    user_id: int,
) -> tuple[int, int, int, int]:
    open_condition = CollaborationTaskModel.status == "open"
    statement = sa.select(
        sa.func.sum(sa.case((open_condition, 1), else_=0)),
        sa.func.sum(sa.case((
            sa.and_(
                open_condition,
                CollaborationTaskModel.assigned_to_user_id == user_id,
            ),
            1,
        ), else_=0)),
        sa.func.sum(sa.case((
            sa.and_(
                open_condition,
                CollaborationTaskModel.created_by_user_id == user_id,
            ),
            1,
        ), else_=0)),
        sa.func.sum(sa.case((
            sa.and_(
                CollaborationTaskModel.status == "rejected",
                CollaborationTaskModel.created_by_user_id == user_id,
            ),
            1,
        ), else_=0)),
    ).where(CollaborationTaskModel.project_id == project_id)
    row = (await session.execute(statement)).one()
    return tuple(value or 0 for value in row)


async def _load_task_counts_by_node_kind(session, project_id: int) -> dict:
    statement = (
        sa.select(
            CollaborationTaskModel.target_type,
            sa.func.count(CollaborationTaskModel.id),
        )
        .where(
            CollaborationTaskModel.project_id == project_id,
            CollaborationTaskModel.status == "open",
        )
        .group_by(CollaborationTaskModel.target_type)
    )
    result = await session.execute(statement)
    counts = {
        node_kind: count
        for node_kind, count in result.all()
        if node_kind is not None
    }

    batch_statement = sa.select(CollaborationTaskModel.targets).where(
        CollaborationTaskModel.project_id == project_id,
        CollaborationTaskModel.status == "open",
        CollaborationTaskModel.task_type == "confirm_nodes",
    )
    batch_result = await session.execute(batch_statement)
    for targets in batch_result.scalars().all():
        for target in targets or []:
            node_kind = target.get("node_kind")
            if node_kind:
                counts[node_kind] = counts.get(node_kind, 0) + 1
    return counts


async def _load_task_counts_by_assignee(session, project_id: int) -> dict:
    statement = (
        sa.select(
            UserModel.email,
            sa.func.count(CollaborationTaskModel.id),
        )
        .join(
            CollaborationTaskModel,
            CollaborationTaskModel.assigned_to_user_id == UserModel.id,
        )
        .where(
            CollaborationTaskModel.project_id == project_id,
            CollaborationTaskModel.status == "open",
        )
        .group_by(UserModel.email)
    )
    result = await session.execute(statement)
    return dict(result.all())


async def load_confirmation_summary(
    session,
    *,
    project_id: int,
    user_id: int,
) -> dict:
    ai_assumption_count = await _count_ai_assumptions(session, project_id)
    (
        open_task_count,
        assigned_to_me_count,
        created_by_me_count,
        rejected_count,
    ) = await _load_task_counts(session, project_id, user_id)
    by_node_kind = await _load_task_counts_by_node_kind(session, project_id)
    by_assignee = await _load_task_counts_by_assignee(session, project_id)
    return {
        "ai_assumption_count": ai_assumption_count,
        "open_task_count": open_task_count,
        "assigned_to_me_count": assigned_to_me_count,
        "created_by_me_count": created_by_me_count,
        "rejected_count": rejected_count,
        "by_node_kind": by_node_kind,
        "by_assignee": by_assignee,
    }
