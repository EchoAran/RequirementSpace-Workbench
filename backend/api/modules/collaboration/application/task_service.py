import sqlalchemy as sa
from datetime import datetime, timezone
from fastapi import HTTPException
from backend.database.model import (
    CollaborationTaskModel,
    ProjectMemberModel,
)
from backend.services.audit_service import AuditService
from backend.api.modules.optimistic_lock.public import (
    NodeSnapshotService,
    snapshot_service,
)
from .task_creation_helpers import (
    add_assignment_notification,
    build_batch_confirmation_task,
    build_single_confirmation_task,
    load_validated_target,
    mark_needs_confirmation,
    process_batch_targets,
    record_batch_task_audits,
    record_single_task_audits,
    supersede_open_node_tasks,
    validate_task_assignee,
    validate_task_creator,
)

audit_service = AuditService()
# snapshot_service 由 optimistic_lock 模块提供并在此保持为模块级名称，兼容 collaboration 内部既有导入。
SINGLE_TASK_TITLE_KEY = "collaboration.taskTitles.singleConfirmation"
BATCH_TASK_TITLE_KEY = "collaboration.taskTitles.batchConfirmation"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class TaskService:
    async def create_confirm_task(
        self,
        session,
        project_id: int,
        creator_id: int,
        node_kind: str,
        node_id: int,
        assigned_to_user_id: int,
        title: str | None = None,
        description: str | None = None,
        priority: str = "normal",
        due_at: datetime | None = None,
    ) -> CollaborationTaskModel:
        # 1. Verify creator is owner/admin/editor
        creator_mem = await self._get_active_member(session, project_id, creator_id)
        validate_task_creator(
            creator_mem,
            "Only owner, admin, or editor can create confirmation tasks.",
        )

        # 2. Verify assignee is active member and role != viewer
        assignee_mem = await self._get_active_member(session, project_id, assigned_to_user_id)
        validate_task_assignee(assignee_mem)

        # 3. Generate snapshot and hash & verify node belongs to project
        snap_res, node = await load_validated_target(
            session,
            snapshot_service,
            project_id,
            node_kind,
            node_id,
        )

        await supersede_open_node_tasks(
            session,
            audit_service,
            project_id=project_id,
            node_kind=node_kind,
            node_id=node_id,
            utc_now=utc_now,
        )

        old_status = mark_needs_confirmation(node)

        # 6. Create the task
        task = build_single_confirmation_task(
            project_id=project_id,
            creator_id=creator_id,
            assigned_to_user_id=assigned_to_user_id,
            node_kind=node_kind,
            node_id=node_id,
            title=title or SINGLE_TASK_TITLE_KEY,
            description=description,
            priority=priority,
            due_at=due_at,
            snapshot_result=snap_res,
        )
        session.add(task)
        await session.flush()

        add_assignment_notification(
            session,
            assigned_to_user_id=assigned_to_user_id,
            project_id=project_id,
            task_id=task.id,
            is_batch=False,
        )

        await record_single_task_audits(
            session,
            audit_service,
            task=task,
            project_id=project_id,
            assigned_to_user_id=assigned_to_user_id,
            node_kind=node_kind,
            node_id=node_id,
            old_status=old_status,
        )

        return task

    async def decide_task(
        self,
        session,
        project_id: int,
        task_id: int,
        user_id: int,
        is_admin_or_owner: bool,
        decision: str,
        note: str | None = None,
    ) -> CollaborationTaskModel:
        from .task_decision import decide_task

        return await decide_task(
            session,
            project_id,
            task_id,
            user_id,
            is_admin_or_owner,
            decision,
            note,
            audit_service,
            snapshot_service,
            utc_now,
        )

    async def cancel_task(
        self,
        session,
        project_id: int,
        task_id: int,
        user_id: int,
        is_admin_or_owner: bool,
    ) -> CollaborationTaskModel:
        task = await session.get(CollaborationTaskModel, task_id)
        if not task or task.project_id != project_id:
            raise HTTPException(
                status_code=404,
                detail="Task not found in this project."
            )

        if task.status != "open":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel a task in {task.status} status."
            )

        # Check permission: creator or admin/owner
        if task.created_by_user_id != user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=403,
                detail="Only the creator or a project admin/owner can cancel this task."
            )

        task.status = "cancelled"
        task.completed_at = utc_now()

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="task_cancelled",
            summary="task_cancelled",
            target_type="task",
            target_id=task.id,
            task_id=task.id
        )

        return task

    async def create_batch_confirm_task(
        self,
        session,
        project_id: int,
        creator_id: int,
        targets: list[dict],
        assigned_to_user_id: int,
        title: str | None = None,
        description: str | None = None,
        priority: str = "normal",
        due_at: datetime | None = None,
    ) -> CollaborationTaskModel:
        # 1. Check if creator has permission
        creator_mem = await self._get_active_member(session, project_id, creator_id)
        validate_task_creator(
            creator_mem,
            "Only project owners, admins, or editors can create confirmation tasks.",
        )

        # 2. Verify assignee
        assignee_mem = await self._get_active_member(session, project_id, assigned_to_user_id)
        validate_task_assignee(assignee_mem)

        if not targets:
            raise HTTPException(
                status_code=400,
                detail="At least one target node must be specified."
            )

        processed_targets = await process_batch_targets(
            session,
            snapshot_service,
            project_id,
            targets,
        )

        # 4. Create task
        task = build_batch_confirmation_task(
            project_id=project_id,
            creator_id=creator_id,
            assigned_to_user_id=assigned_to_user_id,
            title=title or BATCH_TASK_TITLE_KEY,
            description=description,
            priority=priority,
            due_at=due_at,
            processed_targets=processed_targets,
        )
        session.add(task)
        await session.flush()  # populated task.id

        add_assignment_notification(
            session,
            assigned_to_user_id=assigned_to_user_id,
            project_id=project_id,
            task_id=task.id,
            is_batch=True,
        )

        await record_batch_task_audits(
            session,
            audit_service,
            task=task,
            project_id=project_id,
            processed_targets=processed_targets,
        )

        return task

    async def _get_active_member(self, session, project_id: int, user_id: int) -> ProjectMemberModel | None:
        query = sa.select(ProjectMemberModel).where(
            sa.and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id,
                ProjectMemberModel.status == "active"
            )
        )
        res = await session.execute(query)
        return res.scalar_one_or_none()
