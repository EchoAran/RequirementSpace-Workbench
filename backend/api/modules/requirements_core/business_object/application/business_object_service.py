from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.database.model import (
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    AuditLogModel,
    ConfirmationStatus,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)
from backend.api.modules.requirements_core.ports import get_notifier
from backend.api.modules.requirements_core.business_object.schemas import (
    BusinessObjectCreateRequest,
    BusinessObjectUpdateRequest,
    BusinessObjectResponse,
    BusinessObjectAttributeCreateRequest,
    BusinessObjectAttributeUpdateRequest,
    BusinessObjectAttributeResponse,
)


class BusinessObjectService:
    async def create_business_object(
        self,
        project_id: int,
        req: BusinessObjectCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
    ) -> BusinessObjectResponse:
        bo = BusinessObjectModel(
            project_id=project_id,
            name=req.name,
            description=req.description,
            confirmation_status=confirmation_status,
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

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return BusinessObjectResponse(
            business_object_id=bo.id,
            name=bo.name,
            description=bo.description,
            attributes=[],
            confirmation_status=bo.confirmation_status,
        )

    async def update_business_object(
        self,
        project_id: int,
        bo_id: int,
        req: BusinessObjectUpdateRequest,
        session,
    ) -> BusinessObjectResponse:
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

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return BusinessObjectResponse(
            business_object_id=bo.id,
            name=bo.name,
            description=bo.description,
            confirmation_status=bo.confirmation_status,
            attributes=[
                BusinessObjectAttributeResponse(
                    attribute_id=attr.id,
                    business_object_id=attr.business_object_id,
                    name=attr.name,
                    description=attr.description,
                    data_type=attr.data_type,
                    example=attr.example,
                    confirmation_status=attr.confirmation_status,
                )
                for attr in bo.attributes
            ],
        )

    async def delete_business_object(
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

        # 校验是否被任意 FlowStep 的输入/输出引用
        input_use = await session.execute(
            select(1)
            .select_from(flow_step_input_business_object_table)
            .where(flow_step_input_business_object_table.c.business_object_id == bo_id)
            .limit(1)
        )
        output_use = await session.execute(
            select(1)
            .select_from(flow_step_output_business_object_table)
            .where(flow_step_output_business_object_table.c.business_object_id == bo_id)
            .limit(1)
        )
        if input_use.scalar() is not None or output_use.scalar() is not None:
            raise ValueError("business_object_in_use")

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

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return {
            "business_object_id": bo_id,
            "message": "business_object_deleted",
        }

    async def create_business_object_attribute(
        self,
        project_id: int,
        bo_id: int,
        req: BusinessObjectAttributeCreateRequest,
        session,
    ) -> BusinessObjectAttributeResponse:
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
            confirmation_status=ConfirmationStatus.NEEDS_CONFIRMATION.value,
        )
        session.add(attr)
        await session.flush()

        # 审计日志: 新增数据属性
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="create_business_object_attribute",
            summary=f"手动新增数据属性: {attr.name}",
            target_type="business_object_attribute",
            target_id=str(attr.id),
            payload={},
        ))

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return BusinessObjectAttributeResponse(
            attribute_id=attr.id,
            business_object_id=attr.business_object_id,
            name=attr.name,
            description=attr.description,
            data_type=attr.data_type,
            example=attr.example,
            confirmation_status=attr.confirmation_status,
        )

    async def update_business_object_attribute(
        self,
        project_id: int,
        bo_id: int,
        attr_id: int,
        req: BusinessObjectAttributeUpdateRequest,
        session,
    ) -> BusinessObjectAttributeResponse:
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

        # 审计日志: 更新数据属性
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_business_object_attribute",
            summary=f"手动更新数据属性: {attr.name}",
            target_type="business_object_attribute",
            target_id=str(attr.id),
            payload={},
        ))

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return BusinessObjectAttributeResponse(
            attribute_id=attr.id,
            business_object_id=attr.business_object_id,
            name=attr.name,
            description=attr.description,
            data_type=attr.data_type,
            example=attr.example,
            confirmation_status=attr.confirmation_status,
        )

    async def delete_business_object_attribute(
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

        # 审计日志: 删除数据属性
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="delete_business_object_attribute",
            summary=f"手动删除数据属性: ID {attr_id}",
            target_type="business_object_attribute",
            target_id=str(attr_id),
            payload={},
        ))

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )

        return {
            "attribute_id": attr_id,
            "message": "attribute_deleted",
        }

    # Backward-compatible shims for BO operations
    async def create_bo(self, project_id: int, req, session, confirmation_status=None) -> BusinessObjectResponse:
        status = confirmation_status or ConfirmationStatus.NEEDS_CONFIRMATION.value
        return await self.create_business_object(project_id, req, session, status)

    async def update_bo(self, project_id: int, bo_id: int, req, session) -> BusinessObjectResponse:
        return await self.update_business_object(project_id, bo_id, req, session)

    async def delete_bo(self, project_id: int, bo_id: int, session) -> dict:
        return await self.delete_business_object(project_id, bo_id, session)

    async def create_bo_attribute(self, project_id: int, bo_id: int, req, session) -> BusinessObjectAttributeResponse:
        return await self.create_business_object_attribute(project_id, bo_id, req, session)

    async def update_bo_attribute(self, project_id: int, bo_id: int, attr_id: int, req, session) -> BusinessObjectAttributeResponse:
        return await self.update_business_object_attribute(project_id, bo_id, attr_id, req, session)

    async def delete_bo_attribute(self, project_id: int, bo_id: int, attr_id: int, session) -> dict:
        return await self.delete_business_object_attribute(project_id, bo_id, attr_id, session)
