from backend.api.modules.decision_workflow.ports.ports import (
    GenerationCandidate,
    CandidateContext,
    BaseGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.flow.application.flow_generation_service import FlowGenerationService
from backend.database.model import BusinessObjectModel, FlowModel
from sqlalchemy import select


class FlowGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple flow + business object candidates."""

    generation_type = "flow"

    def __init__(self):
        self._service = FlowGenerationService()

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one flow + business object candidate."""
        from backend.api.modules.decision_workflow.ports.ports import build_strategy_feedback
        strategy_hint = build_strategy_feedback(context, "生成流程与业务对象")
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            user_feedback=combined,
            session=context.session,
        )

        flows = response_payload.get("flows", [])
        business_objects = response_payload.get("business_objects", [])

        strat_lbl = context.strategy_label or context.strategy
        return GenerationCandidate(
            title=f"{strat_lbl} — {len(flows)} 个流程, {len(business_objects)} 个业务对象",
            rationale=f"按 {strat_lbl} 策略生成的流程与业务对象",
            payload=draft_payload,
            preview={
                "flow_count": len(flows),
                "flows": [
                    {
                        "flow_name": f.get("flow_name", ""),
                        "feature_names": f.get("feature_names", []),
                        "step_count": len(f.get("flow_steps", [])),
                        "step_names": [s.get("step_name", "") for s in f.get("flow_steps", [])],
                    }
                    for f in flows
                ],
                "business_object_count": len(business_objects),
                "business_objects": [
                    bo.get("business_object_name", "") for bo in business_objects
                ],
            },
            draft_type="flow",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(strat_lbl, flows, business_objects),
            apply_behavior="overwrite",
            apply_behavior_description="此方案将新增流程与业务对象到项目",
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(self, payload: dict, session, **kwargs) -> dict:
        project_id = payload["project_id"]
        flows = await session.execute(select(FlowModel).where(FlowModel.project_id == project_id))
        for flow in flows.scalars().all():
            await session.delete(flow)
        await session.flush()
        business_objects = await session.execute(
            select(BusinessObjectModel).where(BusinessObjectModel.project_id == project_id)
        )
        for business_object in business_objects.scalars().all():
            await session.delete(business_object)
        await session.flush()
        result = await self._service._persist_flow_generation_draft(
            draft=payload, session=session,
        )
        from backend.api.modules.requirements_core.public import get_notifier
        await get_notifier().mark_stale(
            project_id=payload["project_id"],
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
        )
        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        def _flow_names(c: GenerationCandidate) -> frozenset:
            return frozenset(
                f.get("flow_name", "") for f in (c.payload or {}).get("flows", [])
            )
        return any(_flow_names(e) == _flow_names(candidate) for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        from backend.database.model import FeatureModel, ActorModel, BusinessObjectModel
        payload = choice.payload or {}
        flows = payload.get("flows", [])
        for f in flows:
            for fid in f.get("feature_ids", []):
                feature = await session.get(FeatureModel, fid)
                if not feature:
                    return True, f"功能（id={fid}）已被删除，此候选可能不适用"
            for fid in f.get("actor_ids", []):
                actor = await session.get(ActorModel, fid)
                if not actor:
                    return True, f"参与者（id={fid}）已被删除，此候选可能不适用"
        for bo in payload.get("business_objects", []):
            if bo.get("id"):
                bo_model = await session.get(BusinessObjectModel, bo["id"])
                if not bo_model:
                    return True, f"业务对象已被删除，此候选可能不适用"
        return False, None

    @staticmethod
    def _make_comparison_summary(strategy, flows, business_objects):
        descriptions = {
            "balanced": "流程设计均衡",
            "comprehensive": "流程全面覆盖",
            "minimal": "核心流程集",
            "risk_averse": "保守流程设计",
            "workflow_first": "流程驱动编排",
        }
        desc = descriptions.get(strategy, strategy)
        flow_names = ", ".join(f["flow_name"] for f in flows[:3])
        return (
            f"{desc}：{len(flows)} 个流程（{flow_names}），"
            f"{len(business_objects)} 个业务对象"
        )
