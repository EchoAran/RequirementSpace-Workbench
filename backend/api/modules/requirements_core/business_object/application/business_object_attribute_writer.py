from sqlalchemy import select

from backend.api.modules.requirements_core.business_object.schemas import (
    BusinessObjectAttributeResponse,
)
from backend.database.model import (
    BusinessObjectAttributeModel,
    BusinessObjectModel,
)


async def load_attribute_for_update(
    session,
    project_id: int,
    business_object_id: int,
    attribute_id: int,
    workspace_id: int | None = None,
):
    bo_stmt = select(BusinessObjectModel).where(
        BusinessObjectModel.project_id == project_id,
        BusinessObjectModel.id == business_object_id,
    )
    if workspace_id is not None:
        bo_stmt = bo_stmt.where(BusinessObjectModel.workspace_id == workspace_id)
    business_object_result = await session.execute(bo_stmt)
    if business_object_result.scalar_one_or_none() is None:
        raise ValueError("business_object_not_found")
    attr_stmt = select(BusinessObjectAttributeModel).where(
        BusinessObjectAttributeModel.business_object_id
        == business_object_id,
        BusinessObjectAttributeModel.id == attribute_id,
    )
    if workspace_id is not None:
        attr_stmt = attr_stmt.where(BusinessObjectAttributeModel.workspace_id == workspace_id)
    attribute_result = await session.execute(attr_stmt)
    attribute = attribute_result.scalar_one_or_none()
    if attribute is None:
        raise ValueError("attribute_not_found")
    return attribute


def capture_attribute_state(attribute) -> dict:
    return {
        "name": attribute.name,
        "description": attribute.description,
        "data_type": attribute.data_type,
        "example": attribute.example,
    }


def apply_attribute_updates(attribute, request) -> None:
    if request.name is not None:
        attribute.name = request.name
    if request.description is not None:
        attribute.description = request.description
    if request.data_type is not None:
        attribute.data_type = request.data_type
    if request.example is not None:
        attribute.example = request.example


def build_attribute_update_diff(before: dict, attribute) -> dict:
    after = capture_attribute_state(attribute)
    return {
        field: {"before": before[field], "after": value}
        for field, value in after.items()
        if before[field] != value
    }


def serialize_business_object_attribute(
    attribute,
) -> BusinessObjectAttributeResponse:
    return BusinessObjectAttributeResponse(
        attribute_id=attribute.id,
        business_object_id=attribute.business_object_id,
        name=attribute.name,
        description=attribute.description,
        data_type=attribute.data_type,
        example=attribute.example,
        confirmation_status=attribute.confirmation_status,
    )
