"""
Phase 1: Generation Choice Group Service

Choice group 统一候选草稿机制的核心服务层。包含：
- GenerationChoiceSettings: 候选数与并发配置
- GenerationCandidate / CandidateContext / CandidateRunResult: 候选数据协议
- BaseGenerationChoiceAdapter: 各生成器 adapter 的抽象基类
- run_candidate_generation: 通用并发候选生成 runner
- GenerationChoiceService: choice group 的创建、重新生成、重试入口
- GenerationChoiceApplier: 采纳时分派到具体 draft_type 的 persist 方法
"""
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeAlias

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.modules.decision_workflow.ports.ports import (
    BaseGenerationChoiceAdapter,
    CandidateContext,
    GenerationCandidate,
    CandidateError,
    CandidateRunResult,
)
from backend.core.logging import get_logger, log_event
from backend.core.logging.events import (
    CHOICE_GROUP_REGENERATED,
)
from backend.database.model import ChoiceGroupModel, ChoiceModel

logger = get_logger(__name__)

LARGE_SCENARIO_BATCH_THRESHOLD = 25
SCENARIO_TIMEOUT_FEATURE_BATCH_SIZE = 50


# ═══════════════════════════════════════════════
# GenerationChoiceSettings
# ═══════════════════════════════════════════════

@dataclass(frozen=True)
class GenerationChoiceSettings:
    """多候选生成的配置。从环境变量读取，支持运行时覆盖。"""
    candidate_count: int = 2
    max_concurrency: int = 3
    timeout_seconds: int = 120
    partial_success_min: int = 1
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "GenerationChoiceSettings":
        return cls(
            candidate_count=max(1, min(5, int(os.getenv("GENERATION_CHOICE_CANDIDATE_COUNT", "2")))),
            max_concurrency=max(1, min(8, int(os.getenv("GENERATION_CHOICE_MAX_CONCURRENCY", "3")))),
            timeout_seconds=int(os.getenv("GENERATION_CHOICE_TIMEOUT_SECONDS", "120")),
            partial_success_min=max(1, int(os.getenv("GENERATION_CHOICE_PARTIAL_SUCCESS_MIN", "1"))),
            enabled=os.getenv("GENERATION_CHOICE_GROUP_ENABLED", "true").lower() == "true",
        )

    def with_overrides(self, candidate_count: int | None = None) -> "GenerationChoiceSettings":
        """返回带请求级覆盖的新配置副本。"""
        if candidate_count is None:
            return self
        clamped = max(1, min(5, candidate_count))
        return GenerationChoiceSettings(
            candidate_count=clamped,
            max_concurrency=self.max_concurrency,
            timeout_seconds=self.timeout_seconds,
            partial_success_min=self.partial_success_min,
            enabled=self.enabled,
        )

    def is_generation_type_enabled(self, generation_type: str) -> bool:
        """检查指定的 generation_type 是否默认走 choice group。"""
        if not self.enabled:
            return False
        disabled_types_str = os.getenv("GENERATION_CHOICE_GROUP_DISABLED_TYPES", "")
        disabled_types = {t.strip() for t in disabled_types_str.split(",") if t.strip()}
        return generation_type not in disabled_types


# ═══════════════════════════════════════════════
# 候选策略
# ═══════════════════════════════════════════════

CANDIDATE_STRATEGIES = [
    "balanced",
    "comprehensive",
    "minimal",
    "risk_averse",
    "workflow_first",
]


def _strategy_for_index(index: int) -> str:
    """根据候选 index 分配策略。"""
    if index < len(CANDIDATE_STRATEGIES):
        return CANDIDATE_STRATEGIES[index]
    return "balanced"


# 进度回调: (index, phase, message)
# phase: "start" | "complete" | "fail"
ProgressCallback: TypeAlias = Callable[[int, str, str], None]


def _resolve_candidate_strategy(
    index: int,
    resolved_strategies: list[Any] | None,
    base_context: CandidateContext | None,
) -> tuple[str, str, str | None, str | None]:
    if resolved_strategies and index < len(resolved_strategies):
        strategy = resolved_strategies[index]
        return (
            strategy.id,
            strategy.label,
            strategy.description,
            strategy.instruction,
        )
    if base_context and base_context.strategy_id:
        return (
            base_context.strategy_id,
            base_context.strategy_label,
            base_context.strategy_description,
            base_context.strategy_instruction,
        )

    strategy_id = _strategy_for_index(index)
    from backend.api.modules.project_configuration.application.generation_strategy_config_service import (
        DEFAULT_STRATEGIES,
    )
    default = next(
        (item for item in DEFAULT_STRATEGIES if item["id"] == strategy_id),
        None,
    )
    if default:
        return (
            strategy_id,
            default["label"],
            default.get("description"),
            default.get("instruction"),
        )
    return strategy_id, strategy_id, None, None


def _build_candidate_context(
    index: int,
    strategy: tuple[str, str, str | None, str | None],
    base_context: CandidateContext | None,
) -> CandidateContext:
    strategy_id, label, description, instruction = strategy
    return CandidateContext(
        index=index,
        strategy=strategy_id,
        seed_hint=None,
        user_feedback=base_context.user_feedback if base_context else None,
        target=base_context.target if base_context else None,
        project_id=base_context.project_id if base_context else None,
        session=base_context.session if base_context else None,
        strategy_id=strategy_id,
        strategy_label=label,
        strategy_description=description,
        strategy_instruction=instruction,
    )


async def _run_candidate(
    index: int,
    *,
    semaphore: asyncio.Semaphore,
    results: dict[int, GenerationCandidate | Exception],
    timeout_seconds: int,
    generate_one: Callable[[CandidateContext], Awaitable[GenerationCandidate]],
    progress_callback: ProgressCallback | None,
    base_context: CandidateContext | None,
    resolved_strategies: list[Any] | None,
) -> None:
    strategy = _resolve_candidate_strategy(
        index,
        resolved_strategies,
        base_context,
    )
    strategy_id, strategy_label, _, _ = strategy
    context = _build_candidate_context(index, strategy, base_context)
    if progress_callback:
        progress_callback(index, "start", strategy_label)

    async with semaphore:
        try:
            candidate = await asyncio.wait_for(
                generate_one(context),
                timeout=timeout_seconds,
            )
            if candidate:
                if not candidate.strategy_id:
                    candidate.strategy_id = strategy_id
                if not candidate.strategy_label:
                    candidate.strategy_label = strategy_label
            results[index] = candidate
            if progress_callback:
                progress_callback(index, "complete", candidate.title)
        except asyncio.TimeoutError:
            results[index] = TimeoutError(
                f"候选 {index+1} ({strategy_label}) 生成超时 ({timeout_seconds}s)"
            )
            if progress_callback:
                progress_callback(index, "fail", f"超时 ({timeout_seconds}s)")
        except Exception as exc:
            results[index] = exc
            if progress_callback:
                progress_callback(index, "fail", str(exc)[:200])


def _collect_candidate_results(
    count: int,
    results: dict[int, GenerationCandidate | Exception],
    resolved_strategies: list[Any] | None,
) -> tuple[list[GenerationCandidate], list[CandidateError]]:
    candidates = []
    errors = []
    for index in range(count):
        result = results.get(index)
        strategy_id = (
            resolved_strategies[index].id
            if resolved_strategies and index < len(resolved_strategies)
            else _strategy_for_index(index)
        )
        if result is None:
            errors.append(CandidateError(
                index=index,
                strategy=strategy_id,
                error_type="unknown",
                message="候选未完成（任务可能被取消）",
            ))
        elif isinstance(result, GenerationCandidate):
            candidates.append(result)
        elif isinstance(result, asyncio.TimeoutError):
            errors.append(CandidateError(
                index=index,
                strategy=strategy_id,
                error_type="timeout",
                message=str(result),
            ))
        elif isinstance(result, Exception):
            errors.append(CandidateError(
                index=index,
                strategy=strategy_id,
                error_type="llm_error",
                message=str(result)[:300],
            ))
    return candidates, errors


# ═══════════════════════════════════════════════
# 并发候选生成 Runner
# ═══════════════════════════════════════════════

async def run_candidate_generation(
    count: int,
    max_concurrency: int,
    timeout_seconds: int,
    generate_one: Callable[[CandidateContext], Awaitable[GenerationCandidate]],
    progress_callback: ProgressCallback | None = None,
    base_context: CandidateContext | None = None,
    resolved_strategies: list[Any] | None = None,
) -> CandidateRunResult:
    """
    通用并发候选生成 runner。

    参数:
        count: 请求候选数
        max_concurrency: 最大并发数
        timeout_seconds: 单候选超时秒数
        generate_one: 生成单个候选的协程函数
        progress_callback: 进度回调 (index, phase, message)
        base_context: 传递给 generate_one 的上下文模板

    返回:
        CandidateRunResult 包含成功候选和失败信息
    """
    started = time.monotonic()
    semaphore = asyncio.Semaphore(max_concurrency)
    results: dict[int, GenerationCandidate | Exception] = {}
    tasks = [
        _run_candidate(
            index,
            semaphore=semaphore,
            results=results,
            timeout_seconds=timeout_seconds,
            generate_one=generate_one,
            progress_callback=progress_callback,
            base_context=base_context,
            resolved_strategies=resolved_strategies,
        )
        for index in range(count)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    duration_ms = int((time.monotonic() - started) * 1000)
    candidates, errors = _collect_candidate_results(
        count,
        results,
        resolved_strategies,
    )
    return CandidateRunResult(
        candidates=candidates,
        errors=errors,
        total_count=count,
        success_count=len(candidates),
        failure_count=len(errors),
        duration_ms=duration_ms,
    )


# ═══════════════════════════════════════════════
# Adapter 注册表
# ═══════════════════════════════════════════════

_adapter_registry: dict[str, type[BaseGenerationChoiceAdapter]] = {}


def register_adapter(generation_type: str):
    """装饰器：将 adapter 类注册到全局注册表。
    同时将 adapter 的 apply_candidate 方法注册到 GenerationChoiceApplier。"""
    def decorator(cls: type[BaseGenerationChoiceAdapter]) -> type[BaseGenerationChoiceAdapter]:
        _adapter_registry[generation_type] = cls
        cls.generation_type = generation_type
        # 自动注册 apply_candidate 到 applier（通过闭包绑定类）
        applier = get_generation_choice_applier()
        applier.register(generation_type, cls)
        return cls
    return decorator


def get_adapter(generation_type: str) -> BaseGenerationChoiceAdapter:
    """按 generation_type 查找并实例化 adapter。"""
    cls = _adapter_registry.get(generation_type)
    if not cls:
        raise ValueError(f"unsupported_generation_type: {generation_type}")
    return cls()


# ═══════════════════════════════════════════════
# GenerationChoiceService
# ═══════════════════════════════════════════════

class GenerationChoiceService:
    """Choice group 的创建、重新生成、重试服务。"""

    def __init__(self, settings: GenerationChoiceSettings | None = None):
        self.settings = settings or GenerationChoiceSettings.from_env()

    async def create_choice_group(
        self,
        project_id: int,
        generation_type: str,
        target: dict | None = None,
        candidate_count: int | None = None,
        user_feedback: str | None = None,
        session: AsyncSession | None = None,
        progress_callback: ProgressCallback | None = None,
        issue_code: str | None = None,
        issue_id: str | None = None,
        stage: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        context_hash: str | None = None,
    ) -> dict:
        """Create and persist a generation choice group."""
        from .choice_group_creator import create_choice_group

        return await create_choice_group(
            settings=self.settings,
            project_id=project_id,
            generation_type=generation_type,
            target=target,
            candidate_count=candidate_count,
            user_feedback=user_feedback,
            session=session,
            progress_callback=progress_callback,
            issue_fields={
                "issue_code": issue_code,
                "issue_id": issue_id,
                "stage": stage,
                "source_type": source_type,
                "source_id": source_id,
                "context_hash": context_hash,
            },
            get_adapter=get_adapter,
            run_candidate_generation=run_candidate_generation,
            build_choice_group_response=_build_choice_group_response,
            logger=logger,
            large_batch_threshold=LARGE_SCENARIO_BATCH_THRESHOLD,
            timeout_feature_batch_size=SCENARIO_TIMEOUT_FEATURE_BATCH_SIZE,
        )

    async def regenerate_choice_group(
        self,
        project_id: int,
        group_id: int,
        user_feedback: str | None = None,
        session: AsyncSession | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict:
        """重新生成整个 choice group: 旧 group 标记 discarded，新建一个。"""
        # 加载旧 group
        res = await session.execute(
            select(ChoiceGroupModel)
            .where(ChoiceGroupModel.id == group_id, ChoiceGroupModel.project_id == project_id)
        )
        old_group = res.scalar_one_or_none()
        if not old_group:
            raise ValueError("choice_group_not_found")
        if old_group.status == "resolved":
            raise ValueError("choice_group_already_resolved")

        # 标记旧 group
        old_group.status = "discarded"
        old_group.status_detail = {
            **(old_group.status_detail or {}),
            "superseded_by": f"regenerated_at_{int(time.time())}",
            "supersede_reason": "用户主动重新生成",
        }
        # 标记旧 choices
        choices_res = await session.execute(
            select(ChoiceModel).where(ChoiceModel.choice_group_id == old_group.id)
        )
        for c in choices_res.scalars().all():
            c.status = "discarded"

        await session.flush()

        # 用旧 group 的参数创建新 group
        response = await self.create_choice_group(
            project_id=project_id,
            generation_type=old_group.generation_type or "",
            target=old_group.target,
            user_feedback=user_feedback,
            session=session,
            progress_callback=progress_callback,
        )
        log_event(
            logger,
            logging.INFO,
            "domain",
            CHOICE_GROUP_REGENERATED,
            "Choice group regenerated",
            project_id=project_id,
            choice_group_id=response.get("id") if isinstance(response, dict) else None,
            generation_type=old_group.generation_type,
            source_type=old_group.source_type,
            status=response.get("status") if isinstance(response, dict) else None,
        )
        return response

    async def regenerate_choice(
        self,
        project_id: int,
        choice_id: int,
        user_feedback: str | None = None,
        session: AsyncSession | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict:
        """重新生成单个 choice，作为新候选取代原 choice。"""
        choice, group = await self._load_regeneratable_choice(
            project_id,
            choice_id,
            session,
        )
        adapter = get_adapter(group.generation_type or "")
        strategy = await self._resolve_regeneration_strategy(
            choice,
            group,
            project_id=project_id,
            session=session,
        )
        candidate = await self._run_choice_regeneration(
            group,
            adapter=adapter,
            strategy=strategy,
            project_id=project_id,
            user_feedback=user_feedback,
            progress_callback=progress_callback,
        )
        self._add_regenerated_choice(
            group,
            candidate,
            strategy=strategy,
            session=session,
        )
        group.candidate_count = (group.candidate_count or 0) + 1
        group.success_count = (group.success_count or 0) + 1
        await session.flush()
        all_choices_res = await session.execute(
            select(ChoiceModel).where(ChoiceModel.choice_group_id == group.id)
        )
        all_choices = list(all_choices_res.scalars().all())
        return _build_choice_group_response(group, all_choices)

    @staticmethod
    async def _load_regeneratable_choice(project_id, choice_id, session):
        res = await session.execute(
            select(ChoiceModel)
            .where(ChoiceModel.id == choice_id)
            .options(selectinload(ChoiceModel.choice_group).selectinload(ChoiceGroupModel.project))
        )
        choice = res.scalar_one_or_none()
        if not choice:
            raise ValueError("choice_not_found")

        group = choice.choice_group
        if not group or group.project_id != project_id:
            raise ValueError("choice_group_not_found")
        if group.status == "resolved":
            raise ValueError("choice_group_already_resolved")
        return choice, group

    @staticmethod
    async def _resolve_regeneration_strategy(
        choice,
        group,
        *,
        project_id: int,
        session,
    ) -> tuple[str, str, str | None, str | None]:
        strategy_id = choice.strategy_id or "balanced"
        strategy_label = choice.strategy_label
        strategy_description = None
        strategy_instruction = None

        if project_id and session:
            from backend.api.modules.project_configuration.public import resolve_generation_strategies
            resolved_strategies = await resolve_generation_strategies(
                project_id=project_id,
                generation_type=group.generation_type or "",
                session=session,
            )
            strat_item = next((s for s in resolved_strategies if s.id == strategy_id), None)
            if strat_item:
                strategy_label = strat_item.label
                strategy_description = strat_item.description
                strategy_instruction = strat_item.instruction

        if not strategy_label:
            from backend.api.modules.project_configuration.application.generation_strategy_config_service import (
                DEFAULT_STRATEGIES,
            )
            default_item = next((s for s in DEFAULT_STRATEGIES if s["id"] == strategy_id), None)
            if default_item:
                strategy_label = default_item["label"]
                strategy_description = default_item.get("description")
                strategy_instruction = default_item.get("instruction")
            else:
                strategy_label = strategy_id
        return (
            strategy_id,
            strategy_label,
            strategy_description,
            strategy_instruction,
        )

    async def _run_choice_regeneration(
        self,
        group,
        *,
        adapter: BaseGenerationChoiceAdapter,
        strategy: tuple[str, str, str | None, str | None],
        project_id: int,
        user_feedback: str | None,
        progress_callback: ProgressCallback | None,
    ) -> GenerationCandidate:
        strategy_id, label, description, instruction = strategy
        base_ctx = CandidateContext(
            index=group.candidate_count or 0,
            strategy=strategy_id,
            user_feedback=user_feedback,
            target=group.target,
            project_id=project_id,
            strategy_id=strategy_id,
            strategy_label=label,
            strategy_description=description,
            strategy_instruction=instruction,
        )
        result = await run_candidate_generation(
            count=1,
            max_concurrency=1,
            timeout_seconds=self.settings.timeout_seconds,
            generate_one=adapter.generate_candidate,
            progress_callback=progress_callback,
            base_context=base_ctx,
        )
        if not result.candidates:
            error_msg = result.errors[0].message if result.errors else "regenerate_choice_failed"
            raise RuntimeError(f"choice_regenerate_failed: {error_msg}")
        return result.candidates[0]

    @staticmethod
    def _add_regenerated_choice(
        group,
        candidate: GenerationCandidate,
        *,
        strategy: tuple[str, str, str | None, str | None],
        session,
    ) -> None:
        strategy_id, strategy_label, _, _ = strategy
        new_choice = ChoiceModel(
            choice_group_id=group.id,
            title=candidate.title,
            rationale=candidate.rationale,
            status="candidate",
            patch=candidate.patch or {},
            payload=candidate.payload,
            draft_type=candidate.draft_type or group.generation_type or "",
            apply_mode=candidate.apply_mode,
            preview=candidate.preview,
            score=candidate.score if candidate.score else None,
            strategy_id=candidate.strategy_id or strategy_id,
            strategy_label=candidate.strategy_label or strategy_label,
        )
        session.add(new_choice)


# ═══════════════════════════════════════════════
# GenerationChoiceApplier
# ═══════════════════════════════════════════════

class GenerationChoiceApplier:
    """采纳 generation choice 时分派到对应 draft_type 的 persist 方法。

    每个 adapter 类注册到 applier，采纳时实例化 adapter 并调用 apply_candidate。
    """

    def __init__(self):
        self._adapter_classes: dict[str, type[BaseGenerationChoiceAdapter]] = {}

    def register(self, draft_type: str, adapter_cls: type[BaseGenerationChoiceAdapter]):
        """注册一个 adapter 类。"""
        self._adapter_classes[draft_type] = adapter_cls

    async def apply(
        self,
        draft_type: str,
        payload: dict,
        session: AsyncSession,
        **kwargs,
    ) -> dict:
        """按 draft_type 实例化 adapter 并调用 apply_candidate。"""
        adapter_cls = self._adapter_classes.get(draft_type)
        if not adapter_cls:
            raise ValueError(f"unsupported_draft_type_for_apply: {draft_type}")
        adapter = adapter_cls()
        return await adapter.apply_candidate(payload, session, **kwargs)


# 全局单例
_generation_choice_applier = GenerationChoiceApplier()


def get_generation_choice_applier() -> GenerationChoiceApplier:
    return _generation_choice_applier


# ═══════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════

def _build_choice_group_response(
    group: ChoiceGroupModel,
    choices: list[ChoiceModel],
    project_public_id: str | None = None,
) -> dict:
    """将 ChoiceGroupModel + ChoiceModel 列表构建为响应 dict。"""
    proj_pub_id = project_public_id
    if proj_pub_id is None and group.project is not None:
        proj_pub_id = group.project.public_id
    if proj_pub_id is None:
        proj_pub_id = str(group.project_id)
 
    return {
        "id": group.id,
        "project_id": proj_pub_id,
        "slot_id": group.slot_id,
        "status": group.status,
        "selection_mode": group.selection_mode,
        "source_type": group.source_type,
        "source_id": group.source_id,
        "issue_code": group.issue_code,
        "issue_id": group.issue_id,
        "stage": group.stage,
        "target": group.target,
        "context_hash": group.context_hash,
        "generation_type": group.generation_type,
        "origin_endpoint": group.origin_endpoint,
        "candidate_count": group.candidate_count,
        "success_count": group.success_count,
        "failure_count": group.failure_count,
        "status_detail": group.status_detail,
        "choices": [
            {
                "id": c.id,
                "choice_group_id": c.choice_group_id,
                "title": c.title,
                "rationale": c.rationale,
                "status": c.status,
                "patch": c.patch,
                "impact_preview": c.impact_preview,
                "payload": c.payload,
                "draft_type": c.draft_type,
                "apply_mode": c.apply_mode,
                "preview": c.preview,
                "score": c.score,
                "error": c.error,
                "strategy_id": c.strategy_id,
                "strategy_label": c.strategy_label,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in choices
        ],
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
    }
