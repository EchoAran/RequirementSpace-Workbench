import sqlalchemy as sa
from datetime import datetime, timezone
from fastapi import HTTPException
from backend.database.model import (
    CollaborationTaskModel,
    ProjectMemberModel,
    ConfirmationStatus,
    AuditLogModel,
)
from backend.core.actor_context import get_current_actor
from backend.services.audit_service import AuditService
from backend.api.modules.collaboration.application.node_snapshot_service import NodeSnapshotService, KIND_TO_MODEL

audit_service = AuditService()
snapshot_service = NodeSnapshotService()


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
        if not creator_mem or creator_mem.role not in {"owner", "admin", "editor"}:
            raise HTTPException(
                status_code=403,
                detail="Only owner, admin, or editor can create confirmation tasks."
            )

        # 2. Verify assignee is active member and role != viewer
        assignee_mem = await self._get_active_member(session, project_id, assigned_to_user_id)
        if not assignee_mem:
            raise HTTPException(
                status_code=400,
                detail="Assignee must be an active project member."
            )
        if assignee_mem.role == "viewer":
            raise HTTPException(
                status_code=400,
                detail="Cannot assign tasks to a viewer."
            )

        # 3. Generate snapshot and hash & verify node belongs to project
        snap_res = await snapshot_service.get_snapshot_and_hash(session, node_kind, node_id)
        node = snap_res["node"]
        
        node_project_id = None
        if hasattr(node, "project_id"):
            node_project_id = node.project_id
        elif node_kind == "scope":
            from backend.database.model import FeatureModel
            res_f = await session.execute(sa.select(FeatureModel).where(FeatureModel.id == node.feature_id))
            feat = res_f.scalar_one_or_none()
            node_project_id = feat.project_id if feat else None
        elif node_kind == "acceptance_criterion":
            from backend.database.model import ScenarioModel
            res_s = await session.execute(sa.select(ScenarioModel).where(ScenarioModel.id == node.scenario_id))
            scen = res_s.scalar_one_or_none()
            node_project_id = scen.project_id if scen else None
        elif node_kind == "business_object_attribute":
            from backend.database.model import BusinessObjectModel
            res_b = await session.execute(sa.select(BusinessObjectModel).where(BusinessObjectModel.id == node.business_object_id))
            bo = res_b.scalar_one_or_none()
            node_project_id = bo.project_id if bo else None
        elif node_kind == "flow_step":
            from backend.database.model import FlowModel
            res_fl = await session.execute(sa.select(FlowModel).where(FlowModel.id == node.flow_id))
            fl = res_fl.scalar_one_or_none()
            node_project_id = fl.project_id if fl else None

        if node_project_id != project_id:
            raise HTTPException(
                status_code=404,
                detail=f"Target node {node_kind}:{node_id} not found in this project."
            )

        # 4. If there is an existing open task for the same node, supersede it
        open_tasks_query = sa.select(CollaborationTaskModel).where(
            sa.and_(
                CollaborationTaskModel.project_id == project_id,
                CollaborationTaskModel.target_type == node_kind,
                CollaborationTaskModel.target_id == str(node_id),
                CollaborationTaskModel.status == "open"
            )
        )
        res = await session.execute(open_tasks_query)
        open_tasks = res.scalars().all()
        for old_task in open_tasks:
            old_task.status = "superseded"
            old_task.completed_at = utc_now()
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type="task_superseded",
                summary=f"任务已冲销: 关联节点发起新确认任务",
                target_type="task",
                target_id=old_task.id,
                task_id=old_task.id,
                payload={"superseded_by_task_id": "new_task"}  # will update after insert
            )

        # 5. Set target node's confirmation status to needs_confirmation
        old_status = node.confirmation_status
        if old_status != ConfirmationStatus.NEEDS_CONFIRMATION.value:
            node.confirmation_status = ConfirmationStatus.NEEDS_CONFIRMATION.value

        # 6. Create the task
        default_title = f"请确认 {node_kind}: {getattr(node, 'name', '') or str(node_id)}"
        task = CollaborationTaskModel(
            project_id=project_id,
            task_type="confirm_node",
            title=title or default_title,
            description=description,
            target_type=node_kind,
            target_id=str(node_id),
            status="open",
            priority=priority,
            created_by_user_id=creator_id,
            assigned_to_user_id=assigned_to_user_id,
            content_snapshot=snap_res["snapshot"],
            content_hash=snap_res["hash"],
            due_at=due_at
        )
        session.add(task)
        await session.flush()

        from backend.database.model import NotificationModel
        notif = NotificationModel(
            recipient_user_id=assigned_to_user_id,
            project_id=project_id,
            task_id=task.id,
            event_type="task_assigned",
            title="收到新的确认任务指派",
            body=f"您被指派了确认任务 '{task.title}'。"
        )
        session.add(notif)

        # Update payload for superseded tasks to reference the new task id
        for old_task in open_tasks:
            # We can update raw log payload if needed, or just let it go. We flush first.
            pass

        # 7. Write audit logs
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="task_created",
            summary=f"创建确认任务: {task.title}",
            target_type="task",
            target_id=task.id,
            task_id=task.id,
            payload={
                "assigned_to_user_id": assigned_to_user_id,
                "node_kind": node_kind,
                "node_id": node_id
            }
        )

        if old_status != ConfirmationStatus.NEEDS_CONFIRMATION.value:
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type="update_confirmation_status",
                summary=f"更新 {node_kind} 状态: {old_status} -> needs_confirmation (发起确认任务)",
                target_type=node_kind,
                target_id=node_id,
                task_id=task.id,
                diff={
                    "confirmation_status": {
                        "before": old_status,
                        "after": ConfirmationStatus.NEEDS_CONFIRMATION.value
                    }
                }
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
        # 1. Fetch task
        task = await session.get(CollaborationTaskModel, task_id)
        if not task or task.project_id != project_id:
            raise HTTPException(
                status_code=404,
                detail="Task not found in this project."
            )

        # 2. Check status is open
        if task.status != "open":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot decide on a task in {task.status} status."
            )

        # 3. Check permission: assignee or admin/owner
        is_assignee = (task.assigned_to_user_id == user_id)
        if not is_assignee and not is_admin_or_owner:
            raise HTTPException(
                status_code=403,
                detail="Only the assignee or a project admin/owner can decide on this task."
            )

        # 4. Re-evaluate node hash to check if content changed
        if task.task_type == "confirm_nodes":
            mismatches = []
            targets_to_update = []
            
            for pt in task.targets:
                node_kind = pt["node_kind"]
                node_id = pt["node_id"]
                stored_hash = pt["hash"]
                
                try:
                    snap_res = await snapshot_service.get_snapshot_and_hash(session, node_kind, node_id)
                    current_hash = snap_res["hash"]
                    node = snap_res["node"]
                except Exception:
                    mismatches.append({"node_kind": node_kind, "node_id": node_id, "reason": "deleted"})
                    continue
                
                if current_hash != stored_hash:
                    mismatches.append({"node_kind": node_kind, "node_id": node_id, "reason": "content_changed"})
                else:
                    targets_to_update.append((node, node_kind, node_id))
            
            if mismatches:
                task.status = "superseded"
                task.completed_at = utc_now()
                task.decision_note = note or "批量任务中部分节点内容已变更，自动失效"
                await audit_service.record(
                    session=session,
                    project_id=project_id,
                    action_type="task_superseded",
                    summary=f"批量确认任务已失效 (内容被编辑): {task.title}",
                    target_type="task",
                    target_id=task.id,
                    task_id=task.id,
                    payload={"mismatches": mismatches}
                )
                await session.commit()
                 
                raise HTTPException(
                    status_code=409,
                    detail={"message": "task_content_changed", "mismatches": mismatches}
                )
            
            # Process decision for batch
            task.completed_at = utc_now()
            task.decision_note = note
            acted_as_admin = not is_assignee and is_admin_or_owner
            
            if decision == "approve":
                task.status = "done"
                
                await audit_service.record(
                    session=session,
                    project_id=project_id,
                    action_type="task_approved",
                    summary=f"批量确认任务已通过: {task.title}",
                    target_type="task",
                    target_id=task.id,
                    task_id=task.id,
                    payload={"acted_as_admin": acted_as_admin, "decision_note": note}
                )
                
                for node, node_kind, node_id in targets_to_update:
                    old_status = node.confirmation_status
                    node.confirmation_status = ConfirmationStatus.CONFIRMED.value
                    
                    if old_status != ConfirmationStatus.CONFIRMED.value:
                        await audit_service.record(
                            session=session,
                            project_id=project_id,
                            action_type="update_confirmation_status",
                            summary=f"更新 {node_kind} 状态: {old_status} -> confirmed (批量确认任务通过)",
                            target_type=node_kind,
                            target_id=node_id,
                            task_id=task.id,
                            diff={
                                "confirmation_status": {
                                    "before": old_status,
                                    "after": ConfirmationStatus.CONFIRMED.value
                                }
                            }
                        )
            elif decision == "reject":
                task.status = "rejected"
                
                await audit_service.record(
                    session=session,
                    project_id=project_id,
                    action_type="task_rejected",
                    summary=f"批量确认任务已驳回: {task.title}",
                    target_type="task",
                    target_id=task.id,
                    task_id=task.id,
                    payload={"acted_as_admin": acted_as_admin, "decision_note": note}
                )
                
                for node, node_kind, node_id in targets_to_update:
                    old_status = node.confirmation_status
                    if old_status != ConfirmationStatus.NEEDS_CONFIRMATION.value:
                        node.confirmation_status = ConfirmationStatus.NEEDS_CONFIRMATION.value
                        
                        await audit_service.record(
                            session=session,
                            project_id=project_id,
                            action_type="update_confirmation_status",
                            summary=f"更新 {node_kind} 状态: {old_status} -> needs_confirmation (批量确认任务驳回)",
                            target_type=node_kind,
                            target_id=node_id,
                            task_id=task.id,
                            diff={
                                "confirmation_status": {
                                    "before": old_status,
                                    "after": ConfirmationStatus.NEEDS_CONFIRMATION.value
                                }
                            }
                        )
            if decision not in ("approve", "reject"):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid decision. Must be approve or reject."
                )

            from backend.database.model import NotificationModel
            event_type = "task_decided"
            title = "批量确认任务已被处理"
            decision_str = "已通过" if decision == "approve" else "已驳回"
            body = f"您指派的批量确认任务 '{task.title}' {decision_str}。"
            
            notif = NotificationModel(
                recipient_user_id=task.created_by_user_id,
                project_id=project_id,
                task_id=task.id,
                event_type=event_type,
                title=title,
                body=body
            )
            session.add(notif)

            return task

        if task.task_type in ("resolve_conflict", "review_draft"):
            task.completed_at = utc_now()
            task.decision_note = note
            acted_as_admin = not is_assignee and is_admin_or_owner
            
            if decision == "approve":
                task.status = "done"
                payload = task.payload
                t_type = payload.get("target_type")
                stale_res = payload.get("stale_ai_result")
                
                import importlib
                ai_public = importlib.import_module("backend.api.modules.ai_interaction.public")
                ai_service = ai_public.AIAddSessionService()
                handler = ai_public.AIAddDraftHandler(ai_service)
                
                if t_type.startswith("edit_"):
                    draft_dict = {
                        "project_id": project_id,
                        "original_object": payload.get("stale_ai_result", {}).get("original_object") or payload.get("original_object"),
                        "diff": payload.get("stale_ai_result", {}).get("diff") or stale_res,
                        "target_type": t_type
                    }
                    created_id = await handler._confirm_edit_draft(draft_dict, session)
                else:
                    await handler._pre_confirm_validation(t_type, stale_res, project_id, session)
                    created_id = await handler._persist_generated_object(t_type, stale_res, project_id, session)

                await audit_service.record(
                    session=session,
                    project_id=project_id,
                    action_type="task_approved",
                    summary=f"采纳冲突/草稿建议: {task.title}",
                    target_type="task",
                    target_id=task.id,
                    task_id=task.id,
                    payload={"acted_as_admin": acted_as_admin, "decision_note": note}
                )
            elif decision == "reject":
                task.status = "rejected"
                await audit_service.record(
                    session=session,
                    project_id=project_id,
                    action_type="task_rejected",
                    summary=f"丢弃冲突/草稿建议: {task.title}",
                    target_type="task",
                    target_id=task.id,
                    task_id=task.id,
                    payload={"acted_as_admin": acted_as_admin, "decision_note": note}
                )
            else:
                raise HTTPException(status_code=400, detail="Invalid decision. Must be approve or reject.")

            from backend.database.model import NotificationModel
            event_type = "task_decided"
            title = "冲突/草稿任务已被处理"
            decision_str = "已采纳" if decision == "approve" else "已丢弃"
            body = f"您处理的冲突/草稿建议 '{task.title}' {decision_str}。"
            
            notif = NotificationModel(
                recipient_user_id=task.created_by_user_id,
                project_id=project_id,
                task_id=task.id,
                event_type=event_type,
                title=title,
                body=body
            )
            session.add(notif)

            return task

        # Single task decision logic
        snap_res = await snapshot_service.get_snapshot_and_hash(session, task.target_type, int(task.target_id))
        node = snap_res["node"]
        current_hash = snap_res["hash"]

        if current_hash != task.content_hash:
            # Task superseded due to content change
            task.status = "superseded"
            task.completed_at = utc_now()
            task.decision_note = note or "内容已变更，自动失效"
            
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type="task_superseded",
                summary=f"任务已冲销: 关联节点内容发生语义变更",
                target_type="task",
                target_id=task.id,
                task_id=task.id,
                payload={"reason": "content_hash_mismatch"}
            )
            await session.commit()
            raise HTTPException(
                status_code=409,
                detail="task_content_changed"
            )

        # 5. Process decision
        task.completed_at = utc_now()
        task.decision_note = note
        
        # Audit payload flags for admin override
        acted_as_admin = not is_assignee and is_admin_or_owner

        if decision == "approve":
            task.status = "done"
            old_status = node.confirmation_status
            node.confirmation_status = ConfirmationStatus.CONFIRMED.value

            # Record task approval
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type="task_approved",
                summary=f"确认任务已通过: {task.title}",
                target_type="task",
                target_id=task.id,
                task_id=task.id,
                payload={"acted_as_admin": acted_as_admin, "decision_note": note}
            )

            # Record node status change
            if old_status != ConfirmationStatus.CONFIRMED.value:
                await audit_service.record(
                    session=session,
                    project_id=project_id,
                    action_type="update_confirmation_status",
                    summary=f"更新 {task.target_type} 状态: {old_status} -> confirmed (确认任务通过)",
                    target_type=task.target_type,
                    target_id=int(task.target_id),
                    task_id=task.id,
                    diff={
                        "confirmation_status": {
                            "before": old_status,
                            "after": ConfirmationStatus.CONFIRMED.value
                        }
                    }
                )
        elif decision == "reject":
            task.status = "rejected"
            
            old_status = node.confirmation_status
            if old_status != ConfirmationStatus.NEEDS_CONFIRMATION.value:
                node.confirmation_status = ConfirmationStatus.NEEDS_CONFIRMATION.value

            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type="task_rejected",
                summary=f"确认任务已驳回: {task.title}",
                target_type="task",
                target_id=task.id,
                task_id=task.id,
                payload={"acted_as_admin": acted_as_admin, "decision_note": note}
            )

            if old_status != ConfirmationStatus.NEEDS_CONFIRMATION.value:
                await audit_service.record(
                    session=session,
                    project_id=project_id,
                    action_type="update_confirmation_status",
                    summary=f"更新 {task.target_type} 状态: {old_status} -> needs_confirmation (确认任务驳回)",
                    target_type=task.target_type,
                    target_id=int(task.target_id),
                    task_id=task.id,
                    diff={
                        "confirmation_status": {
                            "before": old_status,
                            "after": ConfirmationStatus.NEEDS_CONFIRMATION.value
                        }
                    }
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid decision. Must be approve or reject."
            )

        from backend.database.model import NotificationModel
        event_type = "task_decided"
        title = "确认任务已被处理"
        decision_str = "已通过" if decision == "approve" else "已驳回"
        body = f"您指派的确认任务 '{task.title}' {decision_str}。"
        
        notif = NotificationModel(
            recipient_user_id=task.created_by_user_id,
            project_id=project_id,
            task_id=task.id,
            event_type=event_type,
            title=title,
            body=body
        )
        session.add(notif)

        return task

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
            summary=f"取消确认任务: {task.title}",
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
        if not creator_mem or creator_mem.role not in ("owner", "admin", "editor"):
            raise HTTPException(
                status_code=403,
                detail="Only project owners, admins, or editors can create confirmation tasks."
            )

        # 2. Verify assignee
        assignee_mem = await self._get_active_member(session, project_id, assigned_to_user_id)
        if not assignee_mem:
            raise HTTPException(
                status_code=400,
                detail="Assignee must be an active project member."
            )
        if assignee_mem.role == "viewer":
            raise HTTPException(
                status_code=400,
                detail="Cannot assign tasks to a viewer."
            )

        if not targets:
            raise HTTPException(
                status_code=400,
                detail="At least one target node must be specified."
            )

        # 3. Process each target node, generate snapshot/hash and verify it belongs to project
        processed_targets = []
        for target in targets:
            node_kind = target["node_kind"]
            node_id = target["node_id"]

            snap_res = await snapshot_service.get_snapshot_and_hash(session, node_kind, node_id)
            node = snap_res["node"]
            
            node_project_id = None
            if hasattr(node, "project_id"):
                node_project_id = node.project_id
            elif node_kind == "scope":
                from backend.database.model import FeatureModel
                res_f = await session.execute(sa.select(FeatureModel).where(FeatureModel.id == node.feature_id))
                feat = res_f.scalar_one_or_none()
                node_project_id = feat.project_id if feat else None
            elif node_kind == "acceptance_criterion":
                from backend.database.model import ScenarioModel
                res_s = await session.execute(sa.select(ScenarioModel).where(ScenarioModel.id == node.scenario_id))
                scen = res_s.scalar_one_or_none()
                node_project_id = scen.project_id if scen else None
            elif node_kind == "business_object_attribute":
                from backend.database.model import BusinessObjectModel
                res_b = await session.execute(sa.select(BusinessObjectModel).where(BusinessObjectModel.id == node.business_object_id))
                bo = res_b.scalar_one_or_none()
                node_project_id = bo.project_id if bo else None
            elif node_kind == "flow_step":
                from backend.database.model import FlowModel
                res_fl = await session.execute(sa.select(FlowModel).where(FlowModel.id == node.flow_id))
                fl = res_fl.scalar_one_or_none()
                node_project_id = fl.project_id if fl else None

            if node_project_id != project_id:
                raise HTTPException(
                    status_code=404,
                    detail=f"Target node {node_kind}:{node_id} not found in this project."
                )

            # Set node status to needs_confirmation if not already
            old_status = node.confirmation_status
            if old_status != ConfirmationStatus.NEEDS_CONFIRMATION.value:
                node.confirmation_status = ConfirmationStatus.NEEDS_CONFIRMATION.value

            processed_targets.append({
                "node_kind": node_kind,
                "node_id": node_id,
                "node_name": getattr(node, "name", None) or snap_res["snapshot"].get("name"),
                "snapshot": snap_res["snapshot"],
                "hash": snap_res["hash"],
                "old_status": old_status,
            })

        # 4. Create task
        task_title = title or f"批量确认任务 ({len(targets)}项)"
        task = CollaborationTaskModel(
            project_id=project_id,
            task_type="confirm_nodes",
            title=task_title,
            description=description,
            target_type=None,
            target_id=None,
            targets=processed_targets,
            status="open",
            priority=priority,
            created_by_user_id=creator_id,
            assigned_to_user_id=assigned_to_user_id,
            due_at=due_at,
        )
        session.add(task)
        await session.flush()  # populated task.id

        from backend.database.model import NotificationModel
        notif = NotificationModel(
            recipient_user_id=assigned_to_user_id,
            project_id=project_id,
            task_id=task.id,
            event_type="task_assigned",
            title="收到新的批量确认指派",
            body=f"您被指派了批量确认任务 '{task.title}'。"
        )
        session.add(notif)

        # 5. Record audit logs for task creation and node status changes
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="task_created",
            summary=f"创建批量确认任务: {task.title}",
            target_type="task",
            target_id=task.id,
            task_id=task.id,
        )

        for pt in processed_targets:
            if pt["old_status"] != ConfirmationStatus.NEEDS_CONFIRMATION.value:
                await audit_service.record(
                    session=session,
                    project_id=project_id,
                    action_type="update_confirmation_status",
                    summary=f"更新 {pt['node_kind']} 状态: {pt['old_status']} -> needs_confirmation (确认任务指派)",
                    target_type=pt["node_kind"],
                    target_id=pt["node_id"],
                    task_id=task.id,
                    diff={
                        "confirmation_status": {
                            "before": pt["old_status"],
                            "after": ConfirmationStatus.NEEDS_CONFIRMATION.value
                        }
                    }
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
