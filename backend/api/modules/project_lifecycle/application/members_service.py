from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.model import (
    UserModel,
    ProjectModel,
    ProjectMemberModel,
    ProjectMemberRole,
    ProjectMemberStatus,
    beijing_now,
)
from backend.core.actor_context import ActorContext
from backend.services.audit_service import AuditService

audit_service = AuditService()


class ProjectMemberService:
    async def list_members(self, project_id: int, session: AsyncSession) -> list[ProjectMemberModel]:
        """列出项目的所有成员，包含用户信息"""
        from sqlalchemy.orm import selectinload
        query = (
            select(ProjectMemberModel)
            .options(selectinload(ProjectMemberModel.user))
            .where(ProjectMemberModel.project_id == project_id)
            .order_by(ProjectMemberModel.created_at.asc())
        )
        res = await session.execute(query)
        return list(res.scalars().all())

    async def add_member(
        self,
        project_id: int,
        email: str,
        role: str,
        actor: ActorContext,
        session: AsyncSession,
    ) -> ProjectMemberModel:
        """添加新成员到项目"""
        # 1. 检查角色有效性
        if role not in [r.value for r in ProjectMemberRole]:
            raise ValueError("invalid_role")

        # 2. 检查用户是否存在
        user_query = select(UserModel).where(UserModel.email == email)
        user_res = await session.execute(user_query)
        user = user_res.scalar_one_or_none()
        if not user:
            raise ValueError("user_not_found")

        # 3. 检查是否已经是成员
        member_query = select(ProjectMemberModel).where(
            ProjectMemberModel.project_id == project_id,
            ProjectMemberModel.user_id == user.id,
        )
        member_res = await session.execute(member_query)
        member = member_res.scalar_one_or_none()

        now = beijing_now()
        is_reactivated = False
        if member:
            if member.status == ProjectMemberStatus.ACTIVE.value:
                raise ValueError("member_already_exists")
            # 重新激活被移除的成员
            member.status = ProjectMemberStatus.ACTIVE.value
            member.role = role
            member.invited_by_user_id = actor.user_id
            member.joined_at = now
            member.updated_at = now
            is_reactivated = True
        else:
            member = ProjectMemberModel(
                project_id=project_id,
                user_id=user.id,
                role=role,
                status=ProjectMemberStatus.ACTIVE.value,
                invited_by_user_id=actor.user_id,
                joined_at=now,
            )
            session.add(member)
            await session.flush()  # to get member.id

        # Record structured audit log
        summary = f"重新激活成员 {user.email}，角色为 {role}" if is_reactivated else f"添加成员 {user.email}，角色为 {role}"
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="member_added",
            summary=summary,
            target_type="project_member",
            target_id=member.id,
            actor=actor,
            diff={"role": role, "status": "active"},
        )

        await session.commit()
        return member

    async def update_member(
        self,
        project_id: int,
        member_id: int,
        role: str,
        status: str,
        actor: ActorContext,
        session: AsyncSession,
    ) -> ProjectMemberModel:
        """更新项目成员的角色或状态"""
        # 1. 检查参数有效性
        if role not in [r.value for r in ProjectMemberRole]:
            raise ValueError("invalid_role")
        if status not in [s.value for s in ProjectMemberStatus]:
            raise ValueError("invalid_status")

        # 2. 获取成员
        from sqlalchemy.orm import selectinload
        query = (
            select(ProjectMemberModel)
            .options(selectinload(ProjectMemberModel.user))
            .where(
                ProjectMemberModel.id == member_id,
                ProjectMemberModel.project_id == project_id,
            )
        )
        res = await session.execute(query)
        member = res.scalar_one_or_none()
        if not member:
            raise ValueError("member_not_found")

        # 3. 如果是降级/移除 owner，需防孤立 owner 校验
        if member.role == ProjectMemberRole.OWNER.value:
            if role != ProjectMemberRole.OWNER.value or status != ProjectMemberStatus.ACTIVE.value:
                owner_count = await self._count_active_owners(project_id, session)
                if owner_count <= 1:
                    raise ValueError("cannot_remove_last_owner")

        old_role = member.role
        old_status = member.status

        member.role = role
        member.status = status
        member.updated_at = beijing_now()

        # Record structured audit log
        diff = {}
        if old_role != role:
            diff["role"] = {"before": old_role, "after": role}
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type="member_role_changed",
                summary=f"更新成员 {member.user.email} 的角色为 {role}",
                target_type="project_member",
                target_id=member.id,
                actor=actor,
                diff=diff,
            )
        if old_status != status:
            diff["status"] = {"before": old_status, "after": status}
            action = "member_status_changed" if status == "active" else "member_removed"
            summary_text = f"更新成员 {member.user.email} 的状态为 {status}" if status == "active" else f"移除成员 {member.user.email}"
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type=action,
                summary=summary_text,
                target_type="project_member",
                target_id=member.id,
                actor=actor,
                diff=diff,
            )

        await session.commit()
        return member

    async def remove_member(
        self,
        project_id: int,
        member_id: int,
        actor: ActorContext,
        session: AsyncSession,
    ) -> ProjectMemberModel:
        """移除项目成员 (置为 removed 状态)"""
        from sqlalchemy.orm import selectinload
        query = (
            select(ProjectMemberModel)
            .options(selectinload(ProjectMemberModel.user))
            .where(
                ProjectMemberModel.id == member_id,
                ProjectMemberModel.project_id == project_id,
            )
        )
        res = await session.execute(query)
        member = res.scalar_one_or_none()
        if not member:
            raise ValueError("member_not_found")

        # 校验：防孤立 owner
        if member.role == ProjectMemberRole.OWNER.value:
            owner_count = await self._count_active_owners(project_id, session)
            if owner_count <= 1:
                raise ValueError("cannot_remove_last_owner")

        old_status = member.status
        member.status = ProjectMemberStatus.REMOVED.value
        member.updated_at = beijing_now()

        # Record structured audit log
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="member_removed",
            summary=f"移除成员 {member.user.email}",
            target_type="project_member",
            target_id=member.id,
            actor=actor,
            diff={"status": {"before": old_status, "after": "removed"}},
        )

        await session.commit()
        return member

    async def _count_active_owners(self, project_id: int, session: AsyncSession) -> int:
        """计算项目当前活跃 Owner 的数量"""
        query = select(func.count(ProjectMemberModel.id)).where(
            ProjectMemberModel.project_id == project_id,
            ProjectMemberModel.role == ProjectMemberRole.OWNER.value,
            ProjectMemberModel.status == ProjectMemberStatus.ACTIVE.value,
        )
        res = await session.execute(query)
        return res.scalar_one() or 0
