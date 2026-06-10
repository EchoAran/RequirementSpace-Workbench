from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.database.model import ChoiceGroupModel, ChoiceModel, AuditLogModel
from backend.api.schemas.choice_schema import (
    ChoiceResponse,
    ChoiceGroupResponse,
    ChoiceActionResponse,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.core.detectors.issue_solvers.ai_issue_solver import RepairProposal
from backend.core.engines.patch_engine import GraphPatchEngine

# Phase 1: generation choice 依赖
from backend.api.services.generation_choice_service import (
    get_adapter,
    get_generation_choice_applier,
)


class ChoiceService:
    def __init__(self):
        self.patch_engine = GraphPatchEngine()

    async def create_choice_group(
        self,
        project_id: int,
        source_type: str | None,
        source_id: str | None,
        issue_code: str | None,
        issue_id: str | None,
        stage: str | None,
        target: dict | None,
        context_hash: str | None,
        candidates: list[RepairProposal],
        session,
    ) -> dict:
        """Create a ChoiceGroup from AI solver candidates (issue repair path)."""
        if not candidates:
            raise ValueError("empty_candidates")
        valid = [c for c in candidates if c.patch and c.title]
        if len(valid) < 2:
            raise ValueError("insufficient_valid_candidates")

        group = ChoiceGroupModel(
            project_id=project_id,
            status="open",
            selection_mode="single",
            source_type=source_type,
            source_id=source_id,
            issue_code=issue_code,
            issue_id=issue_id,
            stage=stage,
            target=target if target else None,
            context_hash=context_hash,
        )
        session.add(group)
        await session.flush()

        created_choices = []
        for c in valid:
            choice = ChoiceModel(
                choice_group_id=group.id,
                title=c.title,
                rationale=c.rationale,
                status="candidate",
                patch=c.patch,
                # 旧 path 默认 apply_mode = patch
                apply_mode="patch",
            )
            # P5: generate impact preview for each candidate
            from backend.core.detectors.issue_solvers.impact_preview import build_impact_preview
            try:
                preview = await build_impact_preview(
                    c.patch, project_id, issue_code or "", session,
                )
                choice.impact_preview = preview
            except Exception:
                pass
            session.add(choice)
            created_choices.append(choice)

        await session.flush()

        # Get public_id of the project
        from backend.database.model import ProjectModel
        proj_stmt = select(ProjectModel.public_id).where(ProjectModel.id == project_id)
        project_public_id = (await session.execute(proj_stmt)).scalar_one()
 
        return {
            "id": group.id,
            "project_id": project_public_id,
            "status": group.status,
            "selection_mode": group.selection_mode,
            "source_type": group.source_type,
            "source_id": group.source_id,
            "issue_code": group.issue_code,
            "issue_id": group.issue_id,
            "stage": group.stage,
            "target": group.target,
            "context_hash": group.context_hash,
            "choices": [
                {"id": ch.id, "title": ch.title, "rationale": ch.rationale, "status": ch.status, "patch": ch.patch}
                for ch in created_choices
            ],
        }

    async def list_choice_groups(
        self,
        project_id: int,
        status: str | None,
        session,
    ) -> list[ChoiceGroupResponse]:
        """List all choice groups for a project, optionally filtered by status."""
        query = (
            select(ChoiceGroupModel)
            .where(ChoiceGroupModel.project_id == project_id)
            .options(
                selectinload(ChoiceGroupModel.choices),
                selectinload(ChoiceGroupModel.project)
            )
        )
        if status:
            query = query.where(ChoiceGroupModel.status == status)

        res = await session.execute(query)
        groups = res.scalars().all()

        return [
            ChoiceGroupResponse(
                id=group.id,
                project_id=group.project.public_id,
                slot_id=group.slot_id,
                status=group.status,
                selection_mode=group.selection_mode,
                source_type=group.source_type,
                source_id=group.source_id,
                issue_code=group.issue_code,
                issue_id=group.issue_id,
                stage=group.stage,
                target=group.target,
                context_hash=group.context_hash,
                # Phase 1: 扩展字段
                generation_type=group.generation_type,
                origin_endpoint=group.origin_endpoint,
                candidate_count=group.candidate_count,
                success_count=group.success_count,
                failure_count=group.failure_count,
                status_detail=group.status_detail,
                choices=[
                    ChoiceResponse(
                        id=c.id,
                        choice_group_id=c.choice_group_id,
                        title=c.title,
                        rationale=c.rationale,
                        status=c.status,
                        patch=c.patch,
                        impact_preview=c.impact_preview,
                        # Phase 1: 扩展字段
                        payload=c.payload,
                        draft_type=c.draft_type,
                        apply_mode=c.apply_mode or "patch",
                        preview=c.preview,
                        score=c.score,
                        error=c.error,
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                    )
                    for c in group.choices
                ],
                created_at=group.created_at,
                updated_at=group.updated_at,
            )
            for group in groups
        ]

    async def accept_choice(
        self,
        project_id: int,
        choice_id: int,
        session,
        force: bool = False,
    ) -> ChoiceActionResponse:
        """
        Accepts a choice. Dispatches based on choice.apply_mode:
        - "patch": apply GraphPatch (existing issue repair behavior)
        - "draft_payload": apply via GenerationChoiceApplier (new generation path)
        Stale check runs before draft_payload acceptance unless force=True.
        """
        # 1. Fetch choice
        choice_res = await session.execute(
            select(ChoiceModel)
            .where(ChoiceModel.id == choice_id)
            .options(selectinload(ChoiceModel.choice_group))
        )
        choice = choice_res.scalar_one_or_none()
        if not choice:
            raise ValueError("choice_not_found")

        # 2. Fetch choice group
        group = choice.choice_group
        if not group or group.project_id != project_id:
            raise ValueError("choice_group_not_found")

        if group.status == "resolved":
            raise ValueError("choice_group_already_resolved")

        # 3. 分派: 按 apply_mode 选择采纳路径
        if choice.apply_mode == "patch":
            # --- patch 路径: 现有 issue repair 行为 ---
            async with session.begin_nested():
                result = await self._accept_patch_choice(choice, group, project_id, session)
            # 返回前附加 apply_behavior 字段（patch 型默认为 merge）
            return ChoiceActionResponse(
                message=_accept_message(result),
                choice_id=choice_id,
                status="accepted",
                resolved_issue_ids=result.get("resolved_issue_ids", []),
                remaining_issue_ids=result.get("remaining_issue_ids", []),
                new_issue_ids=result.get("new_issue_ids", []),
                partially_resolved=result.get("partially_resolved", False),
                is_stale=False,
                apply_behavior="merge",
                apply_behavior_description="应用补丁到当前项目状态",
            )

        elif choice.apply_mode == "draft_payload":
            # --- draft_payload 路径: generation choice ---
            # Phase 1: stale 检查 (UX-5)
            if not force and group.generation_type:
                adapter = get_adapter(group.generation_type)
                is_stale, stale_reason = await adapter.is_context_stale(choice, session)
                if is_stale:
                    # 标记 group 为 stale，前端可通过列表查询看到黄色警告（UX-5）
                    group.status = "stale"
                    group.status_detail = {
                        **(group.status_detail or {}),
                        "stale_reason": stale_reason,
                        "stale_at": str(datetime.utcnow()),
                    }
                    # Phase 6: stale audit log
                    session.add(AuditLogModel(
                        project_id=project_id,
                        action_type="generation_choice_group_stale",
                        summary=f"候选过期: {stale_reason}",
                        target_type="choice",
                        target_id=str(choice_id),
                        payload={
                            "generation_type": group.generation_type,
                            "choice_id": choice_id,
                            "stale_reason": stale_reason,
                        },
                    ))
                    await session.flush()
                    return ChoiceActionResponse(
                        message="choice_context_stale",
                        choice_id=choice_id,
                        status="candidate",
                        is_stale=True,
                        stale_reason=stale_reason,
                    )

            # 分派到 applier
            applier = get_generation_choice_applier()
            draft_type = choice.draft_type or group.generation_type or ""
            try:
                apply_result = await applier.apply(
                    draft_type,
                    choice.payload,
                    session,
                    project_id=project_id,
                )
            except Exception as exc:
                raise ValueError(f"choice_apply_failed: {exc}") from exc

            # 更新状态
            choice.status = "accepted"
            await self._reject_siblings(choice, group, session)

            # 清除 perception slot
            if group.slot_id is not None:
                from backend.database.model import PerceptionSlotModel
                slot_res = await session.execute(
                    select(PerceptionSlotModel).where(PerceptionSlotModel.id == group.slot_id)
                )
                slot = slot_res.scalar_one_or_none()
                if slot:
                    await session.delete(slot)
                group.slot_id = None

            group.status = "resolved"

            # Phase 6: audit log with structured payload
            session.add(AuditLogModel(
                project_id=project_id,
                action_type="generation_choice_accepted",
                summary=f"接受 {draft_type} 候选: {choice.title}",
                target_type="choice",
                target_id=str(choice_id),
                payload={
                    "draft_type": draft_type,
                    "choice_id": choice_id,
                    "generation_type": group.generation_type,
                    "candidate_count": group.candidate_count,
                    "success_count": group.success_count,
                    "context_hash": group.context_hash,
                },
            ))
            await session.flush()

            # UX-6: 从 choice 上取采纳行为说明
            # GenerationCandidate 的 apply_behavior 在创建时写入 choice 的 score 或 payload
            # 暂时从 adapter 获取
            adapter_info = _get_apply_behavior(draft_type, choice)
            return ChoiceActionResponse(
                message="choice_accepted",
                choice_id=choice_id,
                status="accepted",
                is_stale=False,
                apply_behavior=adapter_info["behavior"],
                apply_behavior_description=adapter_info["description"],
            )

        else:
            raise ValueError(f"unsupported_choice_apply_mode: {choice.apply_mode}")

    async def _accept_patch_choice(self, choice, group, project_id, session) -> dict:
        """Apply a patch-type choice (existing issue repair logic)."""
        # 3. Apply the patch dynamically
        await self.patch_engine.apply_patch(project_id, choice.patch, session)

        # 4. Update status
        choice.status = "accepted"

        # Reject siblings
        await self._reject_siblings(choice, group, session)

        group.status = "resolved"

        # 5. Delete associated Perception Slot if exists
        if group.slot_id is not None:
            from backend.database.model import PerceptionSlotModel
            slot_res = await session.execute(
                select(PerceptionSlotModel).where(PerceptionSlotModel.id == group.slot_id)
            )
            slot = slot_res.scalar_one_or_none()
            if slot:
                await session.delete(slot)
            group.slot_id = None

        # 6. Analyze patch to dynamically determine affected stages to mark stale
        stages_to_invalidate = set()
        kinds_to_invalidate = set()
        for op in ["addNodes", "updateNodes", "deleteNodes"]:
            for node in choice.patch.get(op, []):
                kind = node.get("kind")
                if kind == "actor":
                    stages_to_invalidate.add("what")
                    kinds_to_invalidate.update(
                        {"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"}
                    )
                elif kind == "feature":
                    stages_to_invalidate.update(["what", "how", "scope"])
                    kinds_to_invalidate.update(
                        {"FEATURE", "SCENARIO", "ACCEPTANCE_CRITERION", "FLOW"}
                    )
                elif kind == "scenario":
                    stages_to_invalidate.add("what")
                    kinds_to_invalidate.update({"SCENARIO", "ACCEPTANCE_CRITERION"})
                elif kind == "acceptance_criterion":
                    stages_to_invalidate.add("what")
                    kinds_to_invalidate.add("ACCEPTANCE_CRITERION")
                elif kind == "business_object":
                    stages_to_invalidate.update(["how", "scope"])
                    kinds_to_invalidate.add("FLOW")
                elif kind == "flow":
                    stages_to_invalidate.add("how")
                    kinds_to_invalidate.add("FLOW")
                elif kind == "flow_step":
                    stages_to_invalidate.add("how")
                    kinds_to_invalidate.add("FLOW")
                elif kind == "scope":
                    stages_to_invalidate.add("scope")
                    kinds_to_invalidate.add("SCOPE")

        for link in choice.patch.get("addLinks", []):
            link_type = link.get("type") or link.get("relationType") or link.get("relation_type")
            if link_type in ["feature_actor_relation", "feature_actor"]:
                stages_to_invalidate.update(["what", "how", "scope"])
                kinds_to_invalidate.update(
                    {"FEATURE", "SCENARIO", "ACCEPTANCE_CRITERION", "FLOW"}
                )
            elif link_type in ["flow_feature_relation", "flow_feature"]:
                stages_to_invalidate.update(["how"])
                kinds_to_invalidate.add("FLOW")

        if stages_to_invalidate:
            await mark_perception_jobs_stale(
                project_id=project_id,
                stages=stages_to_invalidate,
                perception_kinds=kinds_to_invalidate or None,
                session=session,
            )

        # P3: issue regression verification for issue_repair choices
        resolved_ids, remaining_ids, new_ids = [], [], []
        is_partial = False
        if group.source_type == "issue_repair" and group.stage and group.issue_id and group.issue_code:
            from backend.core.detectors.issue_solvers.issue_resolution_verifier import (
                verify_issue_resolved,
            )
            from backend.core.detectors import HowIssueDetector, ScopeIssueDetector, WhatIssueDetector
            from backend.schemas import IssueStage
            _det_map = {
                IssueStage.WHAT.value: WhatIssueDetector(),
                IssueStage.HOW.value: HowIssueDetector(),
                IssueStage.SCOPE.value: ScopeIssueDetector(),
            }
            _det = _det_map.get(group.stage)
            before_ids = set()
            if _det:
                before = await _det.detect(project_id=project_id, session=session)
                before_ids = {i.issueId for i in before}
            try:
                resolved_ids, remaining_ids = await verify_issue_resolved(
                    project_id=project_id,
                    issue_code=group.issue_code,
                    issue_id=group.issue_id,
                    stage=group.stage,
                    session=session,
                )
            except Exception:
                pass
            if _det:
                after = await _det.detect(project_id=project_id, session=session)
                after_ids = {i.issueId for i in after}
                new_ids = list(after_ids - before_ids)
                target_remaining = [
                    i.issueId for i in after
                    if i.issueId in (before_ids & after_ids) and i.code == group.issue_code
                ]
                is_partial = len(resolved_ids) > 0 and len(target_remaining) > 0

        # 审计日志
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="accept_choice",
            summary=f"接受选项: {choice.title}",
            target_type="choice",
            target_id=str(choice_id),
            payload={
                "issue_code": group.issue_code,
                "resolution_type": "choice",
                "choice_id": str(choice.id),
                "solver_name": choice.title,
                "context_hash": group.context_hash,
                "resolved_issue_ids": resolved_ids,
                "new_issue_ids": new_ids,
                "partially_resolved": is_partial,
            },
        ))
        await session.flush()

        return {
            "resolved_issue_ids": resolved_ids,
            "remaining_issue_ids": remaining_ids,
            "new_issue_ids": new_ids,
            "partially_resolved": is_partial,
        }

    async def _reject_siblings(self, accepted_choice, group, session):
        """Mark all other choices in the group as rejected."""
        all_choices_res = await session.execute(
            select(ChoiceModel).where(
                ChoiceModel.choice_group_id == group.id,
                ChoiceModel.id != accepted_choice.id,
            )
        )
        for c in all_choices_res.scalars().all():
            c.status = "rejected"

    async def reject_choice(
        self,
        project_id: int,
        choice_id: int,
        session,
    ) -> ChoiceActionResponse:
        """Marks a choice as rejected."""
        choice_res = await session.execute(
            select(ChoiceModel)
            .where(ChoiceModel.id == choice_id)
            .options(selectinload(ChoiceModel.choice_group))
        )
        choice = choice_res.scalar_one_or_none()
        if not choice:
            raise ValueError("choice_not_found")

        group = choice.choice_group
        if not group or group.project_id != project_id:
            raise ValueError("choice_group_not_found")

        choice.status = "rejected"

        # Phase 6: audit log with generation type if applicable
        gen_type = group.generation_type if group else None
        action = "generation_choice_rejected" if gen_type else "reject_choice"
        session.add(AuditLogModel(
            project_id=project_id,
            action_type=action,
            summary=f"拒绝候选: {choice.title}",
            target_type="choice",
            target_id=str(choice_id),
            payload={"generation_type": gen_type} if gen_type else {},
        ))

        await session.flush()

        return ChoiceActionResponse(
            message="choice_rejected",
            choice_id=choice_id,
            status="rejected",
        )

    async def discard_choice_group(
        self,
        project_id: int,
        group_id: int,
        session,
    ) -> ChoiceGroupResponse:
        """
        Phase 1: 丢弃整个 choice group。
        只允许丢弃 open/stale/failed 的 group。丢弃后不写入真实模型。
        diskard 的 group 不再可操作。
        """
        res = await session.execute(
            select(ChoiceGroupModel)
            .where(ChoiceGroupModel.id == group_id, ChoiceGroupModel.project_id == project_id)
            .options(
                selectinload(ChoiceGroupModel.choices),
                selectinload(ChoiceGroupModel.project)
            )
        )
        group = res.scalar_one_or_none()
        if not group:
            raise ValueError("choice_group_not_found")

        if group.status == "resolved":
            raise ValueError("resolved_group_cannot_be_discarded")

        group.status = "discarded"
        # 所有候选标记为 discarded
        for c in group.choices:
            c.status = "discarded"

        # 审计日志: generation group 与 issue repair group 使用不同 action_type
        is_generation = group.generation_type is not None
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="generation_choice_group_discarded" if is_generation else "discard_choice_group",
            summary=f"丢弃{'生成' if is_generation else '修复'}候选组: {group.generation_type or group.source_type or group.issue_code or ''} (id={group_id})",
            target_type="choice_group",
            target_id=str(group_id),
            payload={
                "generation_type": group.generation_type,
                "source_type": group.source_type,
                "candidate_count": group.candidate_count,
                "success_count": group.success_count,
            },
        ))

        await session.flush()

        # 构建响应
        return ChoiceGroupResponse(
            id=group.id,
            project_id=group.project.public_id,
            slot_id=group.slot_id,
            status=group.status,
            selection_mode=group.selection_mode,
            source_type=group.source_type,
            source_id=group.source_id,
            issue_code=group.issue_code,
            issue_id=group.issue_id,
            stage=group.stage,
            target=group.target,
            context_hash=group.context_hash,
            generation_type=group.generation_type,
            origin_endpoint=group.origin_endpoint,
            candidate_count=group.candidate_count,
            success_count=group.success_count,
            failure_count=group.failure_count,
            status_detail=group.status_detail,
            choices=[
                ChoiceResponse(
                    id=c.id,
                    choice_group_id=c.choice_group_id,
                    title=c.title,
                    rationale=c.rationale,
                    status=c.status,
                    patch=c.patch,
                    impact_preview=c.impact_preview,
                    payload=c.payload,
                    draft_type=c.draft_type,
                    apply_mode=c.apply_mode or "patch",
                    preview=c.preview,
                    score=c.score,
                    error=c.error,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
                for c in group.choices
            ],
            created_at=group.created_at,
            updated_at=group.updated_at,
        )


# ── 内部辅助函数 ──

def _accept_message(result: dict) -> str:
    if result.get("partially_resolved"):
        return "choice_accepted_partially"
    return "choice_accepted"


def _get_apply_behavior(draft_type: str, choice: ChoiceModel) -> dict:
    """从 choice 数据中提取采纳行为说明。暂用 draft_type 给出默认值。"""
    behaviors = {
        "actor": ("overwrite", "此方案将替换项目当前参与者列表"),
        "scenario": ("append", "此方案将新增场景到现有列表"),
        "feature": ("overwrite", "此方案将替换项目的完整功能树"),
        "acceptance_criteria": ("append", "此方案将新增验收标准到现有列表"),
        "flow": ("append", "此方案将新增流程到现有列表"),
        "scope": ("overwrite", "此方案将替换当前范围决策"),
        "project_creation": ("overwrite", "此方案将把项目草稿写入当前项目"),
    }
    return {
        "behavior": behaviors.get(draft_type, ("append", ""))[0],
        "description": behaviors.get(draft_type, ("", ""))[1],
    }
