from sqlalchemy import select

from backend.database.model import (
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    ScopeModel,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)

from .types import BusinessObjectIssueItem, ScopeIssueItem


async def _load_business_object_counts(
    business_object_ids: list[int],
    session,
) -> tuple[dict[int, int], dict[int, int]]:
    attribute_count_map: dict[int, int] = {}
    usage_count_map: dict[int, int] = {}
    if not business_object_ids:
        return attribute_count_map, usage_count_map

    attribute_result = await session.execute(
        select(
            BusinessObjectAttributeModel.business_object_id,
            BusinessObjectAttributeModel.id,
        ).where(
            BusinessObjectAttributeModel.business_object_id.in_(
                business_object_ids
            )
        )
    )
    for business_object_id, _attribute_id in attribute_result.all():
        attribute_count_map[business_object_id] = (
            attribute_count_map.get(business_object_id, 0) + 1
        )

    for association_table in (
        flow_step_input_business_object_table,
        flow_step_output_business_object_table,
    ):
        usage_result = await session.execute(
            select(association_table.c.business_object_id).where(
                association_table.c.business_object_id.in_(
                    business_object_ids
                )
            )
        )
        for business_object_id in usage_result.scalars().all():
            usage_count_map[business_object_id] = (
                usage_count_map.get(business_object_id, 0) + 1
            )
    return attribute_count_map, usage_count_map


async def load_issue_business_objects(
    project_id: int,
    session,
    workspace_id: int,
) -> list[BusinessObjectIssueItem]:
    stmt = select(BusinessObjectModel).where(
        BusinessObjectModel.project_id == project_id,
        BusinessObjectModel.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    object_models = result.scalars().all()
    attribute_counts, usage_counts = await _load_business_object_counts(
        [item.id for item in object_models],
        session,
    )
    return [
        BusinessObjectIssueItem(
            business_object_id=item.id,
            name=item.name,
            description=item.description,
            attribute_count=attribute_counts.get(item.id, 0),
            usage_count=usage_counts.get(item.id, 0),
        )
        for item in object_models
    ]


async def load_issue_scopes(
    feature_ids: list[int],
    session,
) -> list[ScopeIssueItem]:
    result = await session.execute(
        select(ScopeModel).where(ScopeModel.feature_id.in_(feature_ids))
        if feature_ids
        else select(ScopeModel).where(False)
    )
    return [
        ScopeIssueItem(
            scope_id=scope.id,
            feature_id=scope.feature_id,
            status=scope.status,
            reason=scope.reason,
        )
        for scope in result.scalars().all()
    ]
