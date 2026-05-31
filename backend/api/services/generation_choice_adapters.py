"""
Phase 3: Generation Choice Adapters for Actor and Scenario.

Each adapter wraps the existing generation service to produce multiple
candidates through the Phase 1 concurrent runner framework.

Adapter registration is automatic via @register_adapter, which also
registers apply_candidate with the GenerationChoiceApplier.
"""
import hashlib
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.services.generation_choice_service import (
    GenerationCandidate,
    CandidateContext,
    BaseGenerationChoiceAdapter,
    get_generation_choice_applier,
    register_adapter,
)
from backend.api.services.actor_generation_service import ActorGenerationService
from backend.api.services.scenario_generation_service import ScenarioGenerationService
from backend.database.model import (
    FeatureModel,
    ActorModel,
    ScenarioModel,
    BusinessObjectModel,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# ActorGenerationChoiceAdapter
# ═══════════════════════════════════════════════════════════════════

@register_adapter("actor")
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
        actor_names = [a["actor_name"] for a in actors]

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
        # Count existing actors to determine behavior description
        from backend.database.model import ActorModel
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
        from backend.api.services.perception_job_invalidation_service import (
            mark_perception_jobs_stale,
        )
        await mark_perception_jobs_stale(
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


# ═══════════════════════════════════════════════════════════════════
# ScenarioGenerationChoiceAdapter
# ═══════════════════════════════════════════════════════════════════

@register_adapter("scenario")
class ScenarioGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple scenario candidates for a feature+actor pair."""

    generation_type = "scenario"

    def __init__(self):
        from backend.api.services.service_registry import scenario_generation_service
        self._service = scenario_generation_service

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one scenario candidate for a pair or single target.

        Target format:
          pair:  {"generation_mode": "pair",  "feature_id": 12, "actor_id": 3}
          single: {"generation_mode": "single", "feature_id": 12}
        """
        target = context.target or {}
        generation_mode = target.get("generation_mode", "pair")
        feature_id = target.get("feature_id")
        actor_id = target.get("actor_id")

        strategy_hint = f"请按 {context.strategy} 风格生成本场景集。"
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            feature_id=feature_id,
            actor_id=actor_id,
            generation_mode=generation_mode,
            user_feedback=combined,
            session=context.session,
        )

        scenarios = response_payload.get("scenarios", [])
        feature_name = scenarios[0].get("feature_name", "") if scenarios else ""
        actor_name = scenarios[0].get("actor_name", "") if scenarios else ""

        # Build preview
        preview = {
            "scenario_count": len(scenarios),
            "generation_mode": generation_mode,
            "feature_id": feature_id,
            "feature_name": feature_name,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "scenarios": [
                {
                    "scenario_name": s["scenario_name"],
                    "scenario_content": s["scenario_content"][:100],
                }
                for s in scenarios
            ],
        }

        return GenerationCandidate(
            title=f"{feature_name} × {actor_name} — {len(scenarios)} 个场景",
            rationale=f"按 {context.strategy} 策略为 {feature_name} × {actor_name} 生成的场景集",
            payload=draft_payload,
            preview=preview,
            draft_type="scenario",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(
                context.strategy, scenarios, feature_name, actor_name,
            ),
            apply_behavior="append",
            apply_behavior_description=f"此方案将为 {feature_name} × {actor_name} 新增场景",
        )

    async def apply_candidate(self, payload: dict, session: AsyncSession, **kwargs) -> dict:
        """Persist scenario payload to ScenarioModel (append mode)."""
        # Reuse the existing persist method
        result = await self._service._persist_scenario_generation_draft(
            draft=payload,
            session=session,
        )

        # Invalidate perception jobs
        from backend.api.services.perception_job_invalidation_service import (
            mark_perception_jobs_stale,
        )
        await mark_perception_jobs_stale(
            project_id=payload["project_id"],
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        """Detect duplicates by comparing scenario name sets."""
        def _scenario_names(c: GenerationCandidate) -> frozenset:
            return frozenset(
                s.get("scenario_name", "") for s in (c.payload or {}).get("scenarios", [])
            )
        c_names = _scenario_names(candidate)
        return any(_scenario_names(e) == c_names for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        """Check if feature/actor has been deleted or changed since generation."""
        from backend.database.model import FeatureModel, ActorModel
        payload = choice.payload or {}
        feature_id = payload.get("feature_id") or (choice.choice_group.target or {}).get("feature_id")
        actor_id = payload.get("actor_id") or (choice.choice_group.target or {}).get("actor_id")

        if feature_id:
            feature = await session.get(FeatureModel, feature_id)
            if not feature:
                return True, f"功能（id={feature_id}）已被删除，此候选可能不适用"

        if actor_id:
            actor = await session.get(ActorModel, actor_id)
            if not actor:
                return True, f"参与者（id={actor_id}）已被删除，此候选可能不适用"

        return False, None

    @staticmethod
    def _make_comparison_summary(
        strategy: str, scenarios: list[dict], feature_name: str, actor_name: str,
    ) -> str:
        descriptions = {
            "balanced": "场景覆盖均衡",
            "comprehensive": "全面覆盖正向与异常路径",
            "minimal": "核心主路径场景",
            "risk_averse": "保守场景集",
            "workflow_first": "流程驱动场景编排",
        }
        desc = descriptions.get(strategy, strategy)
        scenario_names = ", ".join(s["scenario_name"] for s in scenarios[:3])
        return (
            f"{desc}：{len(scenarios)} 个场景（{scenario_names}）"
            f" — 针对 {feature_name} × {actor_name}"
        )


# ═══════════════════════════════════════════════════════════════════
# AcceptanceCriteriaGenerationChoiceAdapter
# ═══════════════════════════════════════════════════════════════════

@register_adapter("acceptance_criteria")
class AcceptanceCriteriaGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple AC candidates for one or more scenarios."""

    generation_type = "acceptance_criteria"

    def __init__(self):
        from backend.api.services.service_registry import (
            acceptance_criteria_generation_service,
        )
        self._service = acceptance_criteria_generation_service

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one AC candidate for a single or batch of scenarios."""
        target = context.target or {}
        mode = target.get("generation_mode", "single")
        scenario_ids = target.get("scenario_ids", [])

        # For choice groups we support single and batch, not full mode
        if mode not in ("single", "batch") or not scenario_ids:
            raise ValueError(
                f"unsupported_ac_generation_mode: {mode}, "
                "choice group supports single/batch only"
            )

        strategy_hint = f"请按 {context.strategy} 风格生成验收标准。"
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            generation_mode=mode,
            scenario_ids=scenario_ids,
            user_feedback=combined,
            session=context.session,
        )

        criteria = response_payload.get("acceptance_criteria", [])
        scenario_id = scenario_ids[0] if scenario_ids else None

        # Load scenario name for preview
        scenario_name = target.get("scenario_name", f"scenario_{scenario_id}")

        return GenerationCandidate(
            title=f"{scenario_name} — {len(criteria)} 条验收标准",
            rationale=f"按 {context.strategy} 策略生成的验收标准",
            payload=draft_payload,
            preview={
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "mode": mode,
                "criterion_count": len(criteria),
                "criteria": [
                    {
                        "content": c.get("criterion_content", ""),
                        "scenario_id": c.get("scenario_id"),
                    }
                    for c in criteria
                ],
            },
            draft_type="acceptance_criteria",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(
                context.strategy, criteria, scenario_name,
            ),
            apply_behavior="append",
            apply_behavior_description=f"此方案将为 {scenario_name} 新增验收标准",
        )

    async def apply_candidate(self, payload: dict, session, **kwargs) -> dict:
        """Persist AC payload — append mode."""
        result = await self._service._persist_acceptance_criteria_generation_draft(
            draft=payload, session=session,
        )
        from backend.api.services.perception_job_invalidation_service import (
            mark_perception_jobs_stale,
        )
        await mark_perception_jobs_stale(
            project_id=payload["project_id"],
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
        )
        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        def _content_set(c: GenerationCandidate) -> frozenset:
            return frozenset(
                ac.get("criterion_content", "")
                for ac in (c.payload or {}).get("acceptance_criteria", [])
            )
        return any(_content_set(e) == _content_set(candidate) for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        from backend.database.model import ScenarioModel
        payload = choice.payload or {}
        for ac in payload.get("acceptance_criteria", []):
            sid = ac.get("scenario_id")
            if sid:
                s = await session.get(ScenarioModel, sid)
                if not s:
                    return True, f"场景（id={sid}）已被删除，此候选可能不适用"
        return False, None

    @staticmethod
    def _make_comparison_summary(strategy, criteria, scenario_name):
        descriptions = {
            "balanced": "标准覆盖均衡",
            "comprehensive": "全面覆盖验收条件",
            "minimal": "核心验收标准",
            "risk_averse": "保守标准集",
            "workflow_first": "流程驱动标准",
        }
        desc = descriptions.get(strategy, strategy)
        return f"{desc}：{len(criteria)} 条标准（针对 {scenario_name}）"


# ═══════════════════════════════════════════════════════════════════
# FeatureGenerationChoiceAdapter
# ═══════════════════════════════════════════════════════════════════

@register_adapter("feature")
class FeatureGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple feature tree candidates (initial generation only)."""

    generation_type = "feature"

    def __init__(self):
        from backend.api.services.service_registry import feature_generation_service
        self._service = feature_generation_service

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one feature tree candidate."""
        strategy_hint = f"请按 {context.strategy} 风格生成功能树。"
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            user_feedback=combined,
            session=context.session,
        )

        features = response_payload.get("features", [])
        feature_names = [f.get("feature_name", "") for f in features]

        return GenerationCandidate(
            title=f"{context.strategy.capitalize()} — {len(features)} 项功能",
            rationale=f"按 {context.strategy} 策略生成的功能树",
            payload=draft_payload,
            preview={
                "feature_count": len(features),
                "features": features,
            },
            draft_type="feature",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(
                context.strategy, features,
            ),
            apply_behavior="overwrite",
            apply_behavior_description="此方案将替换项目的完整功能树",
        )

    async def apply_candidate(self, payload: dict, session, **kwargs) -> dict:
        """Persist feature tree — overwrite mode, rejects if features already exist."""
        try:
            result = await self._service._persist_feature_generation_draft(
                draft=payload, session=session,
            )
        except ValueError as e:
            if "features_already_exist" in str(e):
                raise ValueError(
                    "项目已有功能列表，此候选与当前项目状态不兼容。"
                    "请重新生成或先删除现有功能。"
                ) from e
            raise

        from backend.api.services.perception_job_invalidation_service import (
            mark_perception_jobs_stale,
        )
        await mark_perception_jobs_stale(
            project_id=payload["project_id"],
            stages={"what", "how", "scope"},
            perception_kinds={"FEATURE", "SCENARIO", "ACCEPTANCE_CRITERION", "FLOW"},
            session=session,
        )
        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        def _feature_names(c: GenerationCandidate) -> frozenset:
            return frozenset(
                f.get("feature_name", "") for f in (c.payload or {}).get("features", [])
            )
        return any(_feature_names(e) == _feature_names(candidate) for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        from backend.database.model import FeatureModel
        project_id = choice.payload.get("project_id") or choice.choice_group.project_id
        existing = await session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        )
        existing_features = existing.scalars().all()
        # If project had no features at generation time but now has some
        generated_features = (choice.payload or {}).get("features", [])
        if not generated_features:
            return False, None
        if existing_features:
            return True, (
                f"项目已包含 {len(existing_features)} 项功能。"
                "此完整树候选可能不再适用。请重新生成。"
            )
        return False, None

    @staticmethod
    def _make_comparison_summary(strategy, features):
        descriptions = {
            "balanced": "功能树均衡",
            "comprehensive": "功能全面覆盖",
            "minimal": "最小功能集",
            "risk_averse": "保守功能定义",
            "workflow_first": "流程驱动功能",
        }
        desc = descriptions.get(strategy, strategy)
        feature_names = ", ".join(f["feature_name"] for f in features[:4])
        return f"{desc}：{len(features)} 项功能（{feature_names}）"


# ═══════════════════════════════════════════════════════════════════
# FlowGenerationChoiceAdapter
# ═══════════════════════════════════════════════════════════════════

@register_adapter("flow")
class FlowGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple flow + business object candidates."""

    generation_type = "flow"

    def __init__(self):
        from backend.api.services.flow_generation_service import FlowGenerationService
        self._service = FlowGenerationService()

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one flow + business object candidate."""
        strategy_hint = f"请按 {context.strategy} 风格生成流程与业务对象。"
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            user_feedback=combined,
            session=context.session,
        )

        flows = response_payload.get("flows", [])
        business_objects = response_payload.get("business_objects", [])

        return GenerationCandidate(
            title=f"{context.strategy.capitalize()} — {len(flows)} 个流程, {len(business_objects)} 个业务对象",
            rationale=f"按 {context.strategy} 策略生成的流程与业务对象",
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
            comparison_summary=self._make_comparison_summary(context.strategy, flows, business_objects),
            apply_behavior="append",
            apply_behavior_description="此方案将新增流程与业务对象到项目",
        )

    async def apply_candidate(self, payload: dict, session, **kwargs) -> dict:
        result = await self._service._persist_flow_generation_draft(
            draft=payload, session=session,
        )
        from backend.api.services.perception_job_invalidation_service import (
            mark_perception_jobs_stale,
        )
        await mark_perception_jobs_stale(
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


# ═══════════════════════════════════════════════════════════════════
# ScopeGenerationChoiceAdapter
# ═══════════════════════════════════════════════════════════════════

@register_adapter("scope")
class ScopeGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple scope/Kano candidates for features."""

    generation_type = "scope"

    def __init__(self):
        from backend.api.services.service_registry import scope_generation_service
        self._service = scope_generation_service

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one scope/Kano candidate."""
        # Full scope can be heavy; limit to 2 candidates
        strategy_hint = f"请按 {context.strategy} 风格生成范围分析。"
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            user_feedback=combined,
            session=context.session,
        )

        scopes = response_payload.get("scopes", [])

        # Build lightweight preview (omit base64 for candidate comparison)
        return GenerationCandidate(
            title=f"{context.strategy.capitalize()} — {len(scopes)} 项范围决策",
            rationale=f"按 {context.strategy} 策略生成的范围分析",
            payload=draft_payload,
            preview={
                "scope_count": len(scopes),
                "scopes": [
                    {
                        "feature_name": s.get("feature_name", ""),
                        "scope_status": s.get("scope_status", ""),
                        "reason": s.get("reason", "")[:200],
                        "kano_category": s.get("kano_category", ""),
                    }
                    for s in scopes
                ],
            },
            draft_type="scope",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(context.strategy, scopes),
            apply_behavior="overwrite",
            apply_behavior_description="此方案将替换当前范围决策",
        )

    async def apply_candidate(self, payload: dict, session, **kwargs) -> dict:
        result = await self._service._persist_scope_generation_draft(
            draft=payload, session=session,
        )
        # Update Project Kano Status to generated (completed)
        from backend.database.model import ProjectModel
        project_id = payload["project_id"]
        project = await session.get(ProjectModel, project_id)
        if project:
            project.kano_status = "generated"
            project.unlocked_stages = "what,how,scope"

        from backend.api.services.perception_job_invalidation_service import (
            mark_perception_jobs_stale,
        )
        await mark_perception_jobs_stale(
            project_id=payload["project_id"],
            stages={"scope"},
            perception_kinds={"SCOPE"},
            session=session,
        )
        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        def _scope_keys(c: GenerationCandidate) -> frozenset:
            return frozenset(
                (s.get("feature_id"), s.get("scope_status"))
                for s in (c.payload or {}).get("scopes", [])
            )
        return any(_scope_keys(e) == _scope_keys(candidate) for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        from backend.database.model import FeatureModel
        payload = choice.payload or {}
        for s in payload.get("scopes", []):
            fid = s.get("feature_id")
            if fid:
                feature = await session.get(FeatureModel, fid)
                if not feature:
                    return True, f"功能（id={fid}）已被删除，此候选可能不适用"
        return False, None

    @staticmethod
    def _make_comparison_summary(strategy, scopes):
        descriptions = {
            "balanced": "范围划分均衡",
            "comprehensive": "全面范围分析",
            "minimal": "核心范围定义",
            "risk_averse": "保守范围",
            "workflow_first": "流程驱动范围",
        }
        desc = descriptions.get(strategy, strategy)
        current = sum(1 for s in scopes if s.get("scope_status") == "current")
        postponed = sum(1 for s in scopes if s.get("scope_status") == "postponed")
        excluded = sum(1 for s in scopes if s.get("scope_status") == "exclude")
        return f"{desc}：{len(scopes)} 项（当前={current}, 推迟={postponed}, 不纳入={excluded}）"
