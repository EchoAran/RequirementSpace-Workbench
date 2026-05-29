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
        """Create a ChoiceGroup from AI solver candidates."""
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

        return {
            "id": group.id,
            "project_id": group.project_id,
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
            .options(selectinload(ChoiceGroupModel.choices))
        )
        if status:
            query = query.where(ChoiceGroupModel.status == status)

        res = await session.execute(query)
        groups = res.scalars().all()

        return [
            ChoiceGroupResponse(
                id=group.id,
                project_id=group.project_id,
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
                choices=[
                    ChoiceResponse(
                        id=c.id,
                        choice_group_id=c.choice_group_id,
                        title=c.title,
                        rationale=c.rationale,
                        status=c.status,
                        patch=c.patch,
                        impact_preview=c.impact_preview,
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
    ) -> ChoiceActionResponse:
        """Accepts a choice, applies its patch inside a nested transaction, resolves the choice group, and invalidates affected stages."""
        async with session.begin_nested():
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

            # 3. Apply the patch dynamically
            await self.patch_engine.apply_patch(project_id, choice.patch, session)

            # 4. Update status
            choice.status = "accepted"
            
            # Fetch other choices in the group to reject them
            all_choices_res = await session.execute(
                select(ChoiceModel).where(
                    ChoiceModel.choice_group_id == group.id,
                    ChoiceModel.id != choice_id
                )
            )
            other_choices = all_choices_res.scalars().all()
            for c in other_choices:
                c.status = "rejected"

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
                group.slot_id = None  # Clear slot relation

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
                            {
                                "FEATURE",
                                "SCENARIO",
                                "ACCEPTANCE_CRITERION",
                                "FLOW",
                            }
                        )
                    elif kind == "scenario":
                        stages_to_invalidate.add("what")
                        kinds_to_invalidate.update(
                            {"SCENARIO", "ACCEPTANCE_CRITERION"}
                        )
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
                # P5: before/after full diff in same transaction
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
                    target_remaining = [i.issueId for i in after if i.issueId in (before_ids & after_ids) and i.code == group.issue_code]
                    is_partial = len(resolved_ids) > 0 and len(target_remaining) > 0

            # 审计日志 (after issue regression so variables are defined)
            session.add(AuditLogModel(
                project_id=project_id,
                action_type="accept_choice",
                summary=f"接受选项: {choice.title}",
                target_type="choice",
                target_id=str(choice_id),
                payload={
                    "issue_code": group.issue_code,
                    "resolution_type": "choice",
                    "choice_id": choice_id,
                    "solver_name": choice.title,
                    "context_hash": group.context_hash,
                    "resolved_issue_ids": resolved_ids,
                    "new_issue_ids": new_ids,
                    "partially_resolved": is_partial,
                },
            ))
            await session.flush()

            return ChoiceActionResponse(
                message="choice_accepted",
                choice_id=choice_id,
                status="accepted",
                resolved_issue_ids=resolved_ids,
                remaining_issue_ids=remaining_ids,
                new_issue_ids=new_ids,
                partially_resolved=is_partial,
            )

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

        # 审计日志: 拒绝选项
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="reject_choice",
            summary=f"拒绝选项: {choice.title}",
            target_type="choice",
            target_id=str(choice_id),
            payload={},
        ))

        await session.flush()

        return ChoiceActionResponse(
            message="choice_rejected",
            choice_id=choice_id,
            status="rejected",
        )
