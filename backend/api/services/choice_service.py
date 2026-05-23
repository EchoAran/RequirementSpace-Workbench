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
from backend.core.engines.patch_engine import GraphPatchEngine

class ChoiceService:
    def __init__(self):
        self.patch_engine = GraphPatchEngine()

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
            for op in ["addNodes", "updateNodes", "deleteNodes"]:
                for node in choice.patch.get(op, []):
                    kind = node.get("kind")
                    if kind == "actor":
                        stages_to_invalidate.add("what")
                    elif kind == "feature":
                        stages_to_invalidate.update(["what", "how", "scope"])
                    elif kind == "scenario":
                        stages_to_invalidate.add("how")
                    elif kind == "business_object":
                        stages_to_invalidate.update(["how", "scope"])
                    elif kind == "flow":
                        stages_to_invalidate.add("how")
            
            for link in choice.patch.get("addLinks", []):
                link_type = link.get("type") or link.get("relationType") or link.get("relation_type")
                if link_type in ["feature_actor_relation", "feature_actor"]:
                    stages_to_invalidate.update(["what", "how", "scope"])
                elif link_type in ["flow_feature_relation", "flow_feature"]:
                    stages_to_invalidate.update(["how"])

            if stages_to_invalidate:
                await mark_perception_jobs_stale(
                    project_id=project_id,
                    stages=stages_to_invalidate,
                    session=session,
                )

            # 审计日志: 接受选项
            session.add(AuditLogModel(
                project_id=project_id,
                action_type="accept_choice",
                summary=f"接受选项: {choice.title}",
                target_type="choice",
                target_id=str(choice_id),
                payload={},
            ))

            await session.flush()

            return ChoiceActionResponse(
                message="choice_accepted",
                choice_id=choice_id,
                status="accepted",
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
