from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.decision_workflow.ports.ports import (
    GenerationCandidate,
    CandidateContext,
    BaseGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.actor.application.actor_generation_service import ActorGenerationService
from backend.database.model import ActorModel


class ActorGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple actor-list candidates for a project."""

    generation_type = "actor"

    def __init__(self):
        self._service = ActorGenerationService()

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one actor-list candidate.

        Injects strategy hint via user_feedback so existing generators
        produce varied outputs (balanced / comprehensive / minimal…).
        """
        strategy_hint = f"请按 {context.strategy} 风格生成本候选参与者列表。"
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            user_feedback=combined,
            session=context.session,
        )

        # Re-read project_id from the generated payload
        actors = response_payload.get("actors", [])

        # Determine apply_behavior based on existing actor count
        # (checked at accept time, but we set a default here)
        return GenerationCandidate(
            title=f"{context.strategy.capitalize()} — {len(actors)} 名参与者",
            rationale=f"按 {context.strategy} 策略生成的参与者列表",
            payload=draft_payload,
            preview={
                "actor_count": len(actors),
                "actors": actors,
            },
            draft_type="actor",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(context.strategy, actors),
            apply_behavior="overwrite",
            apply_behavior_description="此方案将替换项目当前参与者列表",
        )

    async def apply_candidate(self, payload: dict, session: AsyncSession, **kwargs) -> dict:
        """Persist actor payload to ActorModel, clearing existing actors first (overwrite)."""
        project_id = payload.get("project_id")
        existing = await session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        existing_actors = existing.scalars().all()

        # UX-6: delete existing actors (overwrite mode)
        for actor in existing_actors:
            await session.delete(actor)
        await session.flush()

        # Persist new actors
        for item in payload.get("actors", []):
            session.add(ActorModel(
                project_id=project_id,
                name=item["actor_name"],
                description=item.get("actor_description", ""),
                confirmation_status="ai_assumption",
            ))
        await session.flush()

        # Invalidate perception jobs
        from backend.api.modules.requirements_core.public import get_notifier
        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what", "how"},
            perception_kinds={"ACTOR", "SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return {
            "project_id": project_id,
            "actor_count": len(payload.get("actors", [])),
            "message": "actors_created",
        }

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        """Detect duplicates by comparing actor name sets."""
        def _actor_names(c: GenerationCandidate) -> frozenset:
            return frozenset(
                a.get("actor_name", "") for a in (c.payload or {}).get("actors", [])
            )
        c_names = _actor_names(candidate)
        return any(_actor_names(e) == c_names for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        """Check if project still exists. Granular actor-list comparison is
        deferred until we store the generation-time actor snapshot in context_hash."""
        from backend.database.model import ProjectModel
        project_id = choice.payload.get("project_id") or choice.choice_group.project_id

        project = await session.get(ProjectModel, project_id)
        if not project:
            return True, "项目已被删除"

        return False, None

    @staticmethod
    def _make_comparison_summary(strategy: str, actors: list[dict]) -> str:
        descriptions = {
            "balanced": "角色划分均衡",
            "comprehensive": "覆盖完整角色体系",
            "minimal": "最简角色集",
            "risk_averse": "保守角色定义",
            "workflow_first": "流程驱动角色",
        }
        desc = descriptions.get(strategy, strategy)
        names = ", ".join(a["actor_name"] for a in actors[:4])
        return f"{desc}：{len(actors)} 名参与者（{names}）"
