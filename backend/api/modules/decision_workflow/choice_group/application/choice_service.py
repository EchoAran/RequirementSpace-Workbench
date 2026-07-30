from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.database.model import ChoiceGroupModel, ChoiceModel, AuditLogModel
from backend.api.modules.decision_workflow.choice_group.schemas import (
    ChoiceResponse,
    ChoiceGroupResponse,
    ChoiceActionResponse,
)
from backend.core.notifier import get_notifier
from backend.core.issue_resolution.ai.base_ai_solver import RepairProposal
from backend.core.engines.patch_engine import GraphPatchEngine

# Phase 1: generation choice 依赖
from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    get_adapter,
    get_generation_choice_applier,
)

_NODE_INVALIDATION = {
    "actor": (
        {"what"},
        {"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
    ),
    "feature": (
        {"what", "how", "scope"},
        {"FEATURE", "SCENARIO", "ACCEPTANCE_CRITERION", "FLOW"},
    ),
    "scenario": (
        {"what"},
        {"SCENARIO", "ACCEPTANCE_CRITERION"},
    ),
    "acceptance_criterion": (
        {"what"},
        {"ACCEPTANCE_CRITERION"},
    ),
    "business_object": ({"how", "scope"}, {"FLOW"}),
    "flow": ({"how"}, {"FLOW"}),
    "flow_step": ({"how"}, {"FLOW"}),
    "scope": ({"scope"}, {"SCOPE"}),
}

_LINK_INVALIDATION = {
    "feature_actor_relation": (
        {"what", "how", "scope"},
        {"FEATURE", "SCENARIO", "ACCEPTANCE_CRITERION", "FLOW"},
    ),
    "feature_actor": (
        {"what", "how", "scope"},
        {"FEATURE", "SCENARIO", "ACCEPTANCE_CRITERION", "FLOW"},
    ),
    "flow_feature_relation": ({"how"}, {"FLOW"}),
    "flow_feature": ({"how"}, {"FLOW"}),
}


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

        created_choices = await self._create_repair_choices(
            valid,
            group_id=group.id,
            project_id=project_id,
            issue_code=issue_code,
            session=session,
        )
        await session.flush()

        from backend.database.model import ProjectModel
        proj_stmt = select(ProjectModel.public_id).where(ProjectModel.id == project_id)
        project_public_id = (await session.execute(proj_stmt)).scalar_one()
        return self._build_repair_choice_group_response(
            group,
            created_choices,
            project_public_id=project_public_id,
        )

    @staticmethod
    async def _create_repair_choices(
        candidates,
        *,
        group_id: int,
        project_id: int,
        issue_code: str | None,
        session,
    ) -> list[ChoiceModel]:
        created_choices = []
        for candidate in candidates:
            choice = ChoiceModel(
                choice_group_id=group_id,
                title=candidate.title,
                rationale=candidate.rationale,
                status="candidate",
                patch=candidate.patch,
                apply_mode="patch",
            )
            from backend.core.issue_resolution.impact_preview import build_impact_preview
            try:
                preview = await build_impact_preview(
                    candidate.patch,
                    project_id,
                    issue_code or "",
                    session,
                )
                choice.impact_preview = preview
            except Exception:
                pass
            session.add(choice)
            created_choices.append(choice)
        return created_choices

    @staticmethod
    def _build_repair_choice_group_response(
        group: ChoiceGroupModel,
        choices: list[ChoiceModel],
        *,
        project_public_id: str,
    ) -> dict:
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
                {
                    "id": choice.id,
                    "title": choice.title,
                    "rationale": choice.rationale,
                    "status": choice.status,
                    "patch": choice.patch,
                }
                for choice in choices
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
        choice, group = await self._load_choice_for_acceptance(
            project_id,
            choice_id,
            session,
        )
        if choice.apply_mode == "patch":
            return await self._accept_patch_mode_choice(
                choice,
                group,
                project_id=project_id,
                choice_id=choice_id,
                session=session,
            )
        if choice.apply_mode == "draft_payload":
            return await self._accept_draft_payload_choice(
                choice,
                group,
                project_id=project_id,
                choice_id=choice_id,
                session=session,
                force=force,
            )
        raise ValueError(f"unsupported_choice_apply_mode: {choice.apply_mode}")

    @staticmethod
    async def _load_choice_for_acceptance(project_id, choice_id, session):
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
        return choice, group

    async def _accept_patch_mode_choice(
        self,
        choice,
        group,
        *,
        project_id: int,
        choice_id: int,
        session,
    ) -> ChoiceActionResponse:
        async with session.begin_nested():
            result = await self._accept_patch_choice(
                choice,
                group,
                project_id,
                session,
            )
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

    async def _accept_draft_payload_choice(
        self,
        choice,
        group,
        *,
        project_id: int,
        choice_id: int,
        session,
        force: bool,
    ) -> ChoiceActionResponse:
        stale_response = await self._check_generation_choice_staleness(
            choice,
            group,
            project_id=project_id,
            choice_id=choice_id,
            session=session,
            force=force,
        )
        if stale_response:
            return stale_response

        applier = get_generation_choice_applier()
        draft_type = choice.draft_type or group.generation_type or ""
        try:
            await applier.apply(
                draft_type,
                choice.payload,
                session,
                project_id=project_id,
            )
        except Exception as exc:
            raise ValueError(f"choice_apply_failed: {exc}") from exc

        choice.status = "accepted"
        await self._reject_siblings(choice, group, session)
        await self._delete_linked_perception_slot(group, session)
        group.status = "resolved"
        self._record_generation_choice_acceptance(
            choice,
            group,
            project_id=project_id,
            choice_id=choice_id,
            draft_type=draft_type,
            session=session,
        )
        await session.flush()
        adapter_info = _get_apply_behavior(draft_type, choice)
        return ChoiceActionResponse(
            message="choice_accepted",
            choice_id=choice_id,
            status="accepted",
            is_stale=False,
            apply_behavior=adapter_info["behavior"],
            apply_behavior_description=adapter_info["description"],
        )

    @staticmethod
    async def _check_generation_choice_staleness(
        choice,
        group,
        *,
        project_id: int,
        choice_id: int,
        session,
        force: bool,
    ) -> ChoiceActionResponse | None:
        if force or not group.generation_type:
            return None
        adapter = get_adapter(group.generation_type)
        is_stale, stale_reason = await adapter.is_context_stale(choice, session)
        if not is_stale:
            return None

        group.status = "stale"
        group.status_detail = {
            **(group.status_detail or {}),
            "stale_reason": stale_reason,
            "stale_at": str(datetime.now(UTC)),
        }
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

    @staticmethod
    def _record_generation_choice_acceptance(
        choice,
        group,
        *,
        project_id: int,
        choice_id: int,
        draft_type: str,
        session,
    ) -> None:
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

    async def _accept_patch_choice(self, choice, group, project_id, session) -> dict:
        """Apply a patch-type choice (existing issue repair logic)."""
        await self.patch_engine.apply_patch(project_id, choice.patch, session)
        choice.status = "accepted"
        await self._reject_siblings(choice, group, session)
        group.status = "resolved"

        await self._delete_linked_perception_slot(group, session)
        stages, kinds = self._collect_patch_invalidation(choice.patch)
        if stages:
            await get_notifier().mark_stale(
                project_id=project_id,
                stages=stages,
                perception_kinds=kinds or None,
                session=session,
            )

        issue_diff = await self._verify_patch_choice_resolution(
            group,
            project_id,
            session,
        )
        self._record_choice_acceptance_audit(
            choice,
            group,
            project_id,
            issue_diff,
            session,
        )
        await session.flush()
        return issue_diff

    @staticmethod
    async def _delete_linked_perception_slot(group, session) -> None:
        if group.slot_id is None:
            return
        from backend.database.model import PerceptionSlotModel

        slot_res = await session.execute(
            select(PerceptionSlotModel).where(PerceptionSlotModel.id == group.slot_id)
        )
        slot = slot_res.scalar_one_or_none()
        if slot:
            await session.delete(slot)
        group.slot_id = None

    @staticmethod
    def _collect_patch_invalidation(patch: dict) -> tuple[set, set]:
        stages = set()
        kinds = set()
        for op in ["addNodes", "updateNodes", "deleteNodes"]:
            for node in patch.get(op, []):
                invalidation = _NODE_INVALIDATION.get(node.get("kind"))
                if invalidation:
                    stages.update(invalidation[0])
                    kinds.update(invalidation[1])

        for link in patch.get("addLinks", []):
            link_type = link.get("type") or link.get("relationType") or link.get("relation_type")
            invalidation = _LINK_INVALIDATION.get(link_type)
            if invalidation:
                stages.update(invalidation[0])
                kinds.update(invalidation[1])
        return stages, kinds

    @staticmethod
    async def _verify_patch_choice_resolution(group, project_id, session) -> dict:
        resolved_ids, remaining_ids, new_ids = [], [], []
        is_partial = False
        if group.source_type == "issue_repair" and group.stage and group.issue_id and group.issue_code:
            from backend.core.issue_resolution.resolution_verifier import (
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

        return {
            "resolved_issue_ids": resolved_ids,
            "remaining_issue_ids": remaining_ids,
            "new_issue_ids": new_ids,
            "partially_resolved": is_partial,
        }

    @staticmethod
    def _record_choice_acceptance_audit(
        choice,
        group,
        project_id,
        issue_diff,
        session,
    ) -> None:
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="accept_choice",
            summary=f"接受选项: {choice.title}",
            target_type="choice",
            target_id=str(choice.id),
            payload={
                "issue_code": group.issue_code,
                "resolution_type": "choice",
                "choice_id": str(choice.id),
                "solver_name": choice.title,
                "context_hash": group.context_hash,
                "resolved_issue_ids": issue_diff["resolved_issue_ids"],
                "new_issue_ids": issue_diff["new_issue_ids"],
                "partially_resolved": issue_diff["partially_resolved"],
            },
        ))

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
        for choice in group.choices:
            choice.status = "discarded"
        self._record_choice_group_discarded(
            group,
            project_id=project_id,
            group_id=group_id,
            session=session,
        )

        await session.flush()
        return self._build_choice_group_response(group)

    @staticmethod
    def _record_choice_group_discarded(
        group: ChoiceGroupModel,
        *,
        project_id: int,
        group_id: int,
        session,
    ) -> None:
        is_generation = group.generation_type is not None
        session.add(AuditLogModel(
            project_id=project_id,
            action_type=(
                "generation_choice_group_discarded"
                if is_generation
                else "discard_choice_group"
            ),
            summary=(
                f"丢弃{'生成' if is_generation else '修复'}候选组: "
                f"{group.generation_type or group.source_type or group.issue_code or ''} "
                f"(id={group_id})"
            ),
            target_type="choice_group",
            target_id=str(group_id),
            payload={
                "generation_type": group.generation_type,
                "source_type": group.source_type,
                "candidate_count": group.candidate_count,
                "success_count": group.success_count,
            },
        ))

    @staticmethod
    def _build_choice_group_response(
        group: ChoiceGroupModel,
    ) -> ChoiceGroupResponse:
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
                    id=choice.id,
                    choice_group_id=choice.choice_group_id,
                    title=choice.title,
                    rationale=choice.rationale,
                    status=choice.status,
                    patch=choice.patch,
                    impact_preview=choice.impact_preview,
                    payload=choice.payload,
                    draft_type=choice.draft_type,
                    apply_mode=choice.apply_mode or "patch",
                    preview=choice.preview,
                    score=choice.score,
                    error=choice.error,
                    created_at=choice.created_at,
                    updated_at=choice.updated_at,
                )
                for choice in group.choices
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
    if draft_type in {"scenario", "acceptance_criteria", "flow"}:
        return {
            "behavior": "overwrite",
            "description": "采纳该方案会替换对应的现有 AI 生成内容",
        }
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
