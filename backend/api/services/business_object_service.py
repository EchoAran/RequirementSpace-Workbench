from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.database.model import (
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    AuditLogModel,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.api.schemas.crud_schema import (
    BOCreateRequest,
    BOUpdateRequest,
    BOResponse,
    BOAttributeCreateRequest,
    BOAttributeUpdateRequest,
    BOAttributeResponse,
)


class BusinessObjectService:
    async def create_bo(
        self,
        project_id: int,
        req: BOCreateRequest,
        session,
    ) -> BOResponse:
        bo = BusinessObjectModel(
            project_id=project_id,
            name=req.name,
            description=req.description,
        )
        session.add(bo)
        await session.flush()

        # 审计日志: 新增业务对象
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="create_business_object",
            summary=f"手动新增业务对象: {bo.name}",
            target_type="business_object",
            target_id=str(bo.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return BOResponse(
            business_object_id=bo.id,
            name=bo.name,
            description=bo.description,
            attributes=[],
        )

    async def update_bo(
        self,
        project_id: int,
        bo_id: int,
        req: BOUpdateRequest,
        session,
    ) -> BOResponse:
        result = await session.execute(
            select(BusinessObjectModel)
            .where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.id == bo_id,
            )
            .options(selectinload(BusinessObjectModel.attributes))
        )
        bo = result.scalar_one_or_none()

        if bo is None:
            raise ValueError("business_object_not_found")

        if req.name is not None:
            bo.name = req.name
        if req.description is not None:
            bo.description = req.description

        await session.flush()

        # 审计日志: 更新业务对象
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_business_object",
            summary=f"手动更新业务对象: {bo.name}",
            target_type="business_object",
            target_id=str(bo.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return BOResponse(
            business_object_id=bo.id,
            name=bo.name,
            description=bo.description,
            attributes=[
                BOAttributeResponse(
                    attribute_id=attr.id,
                    business_object_id=attr.business_object_id,
                    name=attr.name,
                    description=attr.description,
                    data_type=attr.data_type,
                    example=attr.example,
                )
                for attr in bo.attributes
            ],
        )

    async def delete_bo(
        self,
        project_id: int,
        bo_id: int,
        session,
    ) -> dict:
        result = await session.execute(
            select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.id == bo_id,
            )
        )
        bo = result.scalar_one_or_none()

        if bo is None:
            raise ValueError("business_object_not_found")

        bo_name = bo.name
        await session.delete(bo)
        await session.flush()

        # 审计日志: 删除业务对象
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="delete_business_object",
            summary=f"手动删除业务对象: {bo_name}",
            target_type="business_object",
            target_id=str(bo_id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return {
            "business_object_id": bo_id,
            "message": "business_object_deleted",
        }

    async def create_bo_attribute(
        self,
        project_id: int,
        bo_id: int,
        req: BOAttributeCreateRequest,
        session,
    ) -> BOAttributeResponse:
        # Verify BO belongs to project
        bo_res = await session.execute(
            select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.id == bo_id,
            )
        )
        if bo_res.scalar_one_or_none() is None:
            raise ValueError("business_object_not_found")

        attr = BusinessObjectAttributeModel(
            business_object_id=bo_id,
            name=req.name,
            description=req.description,
            data_type=req.data_type,
            example=req.example,
        )
        session.add(attr)
        await session.flush()

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return BOAttributeResponse(
            attribute_id=attr.id,
            business_object_id=attr.business_object_id,
            name=attr.name,
            description=attr.description,
            data_type=attr.data_type,
            example=attr.example,
        )

    async def update_bo_attribute(
        self,
        project_id: int,
        bo_id: int,
        attr_id: int,
        req: BOAttributeUpdateRequest,
        session,
    ) -> BOAttributeResponse:
        # Verify BO belongs to project
        bo_res = await session.execute(
            select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.id == bo_id,
            )
        )
        if bo_res.scalar_one_or_none() is None:
            raise ValueError("business_object_not_found")

        attr_res = await session.execute(
            select(BusinessObjectAttributeModel).where(
                BusinessObjectAttributeModel.business_object_id == bo_id,
                BusinessObjectAttributeModel.id == attr_id,
            )
        )
        attr = attr_res.scalar_one_or_none()

        if attr is None:
            raise ValueError("attribute_not_found")

        if req.name is not None:
            attr.name = req.name
        if req.description is not None:
            attr.description = req.description
        if req.data_type is not None:
            attr.data_type = req.data_type
        if req.example is not None:
            attr.example = req.example

        await session.flush()

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return BOAttributeResponse(
            attribute_id=attr.id,
            business_object_id=attr.business_object_id,
            name=attr.name,
            description=attr.description,
            data_type=attr.data_type,
            example=attr.example,
        )

    async def delete_bo_attribute(
        self,
        project_id: int,
        bo_id: int,
        attr_id: int,
        session,
    ) -> dict:
        # Verify BO belongs to project
        bo_res = await session.execute(
            select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.id == bo_id,
            )
        )
        if bo_res.scalar_one_or_none() is None:
            raise ValueError("business_object_not_found")

        attr_res = await session.execute(
            select(BusinessObjectAttributeModel).where(
                BusinessObjectAttributeModel.business_object_id == bo_id,
                BusinessObjectAttributeModel.id == attr_id,
            )
        )
        attr = attr_res.scalar_one_or_none()

        if attr is None:
            raise ValueError("attribute_not_found")

        await session.delete(attr)
        await session.flush()

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"how"},
            session=session,
        )

        return {
            "attribute_id": attr_id,
            "message": "attribute_deleted",
        }
