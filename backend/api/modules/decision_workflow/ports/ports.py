from __future__ import annotations
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from backend.database.model import ChoiceModel

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 数据协议
# ═══════════════════════════════════════════════

@dataclass
class CandidateContext:
    """传递给 adapter.generate_candidate 的上下文。"""
    index: int
    strategy: str
    seed_hint: str | None = None
    user_feedback: str | None = None
    target: dict | None = None
    project_id: int | None = None
    session: AsyncSession | None = field(
        default=None,
        metadata={"help": "DB session, adapters can use it to load project context during generate"},
    )
    strategy_id: str | None = None
    strategy_label: str | None = None
    strategy_description: str | None = None
    strategy_instruction: str | None = None


@dataclass
class GenerationCandidate:
    """一个完整候选草稿。adapter.generate_candidate 的返回值。"""
    title: str
    rationale: str
    payload: dict
    preview: dict = field(default_factory=dict)
    draft_type: str = ""
    apply_mode: str = "draft_payload"
    patch: dict | None = None
    score: dict = field(default_factory=dict)
    # UX-3: 差异化描述，帮助用户快速区分候选
    comparison_summary: str = ""
    # UX-6: 采纳行为说明
    apply_behavior: str = "append"  # overwrite | append | merge
    apply_behavior_description: str = ""
    strategy_id: str | None = None
    strategy_label: str | None = None


@dataclass
class CandidateError:
    """单个候选生成失败的记录。"""
    index: int
    strategy: str
    error_type: str = "unknown"  # timeout | llm_error | validation_error | unknown
    message: str = ""
    detail: str | None = None


@dataclass
class CandidateRunResult:
    """并发候选生成的整体结果。"""
    candidates: list[GenerationCandidate]
    errors: list[CandidateError] = field(default_factory=list)
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    duration_ms: int = 0


# ═══════════════════════════════════════════════
# BaseGenerationChoiceAdapter & ChoiceAdapterRegistry
# ═══════════════════════════════════════════════

class BaseGenerationChoiceAdapter(ABC):
    """生成器 adapter 基类。每种 generation_type 实现一个子类。"""

    generation_type: str = ""

    @abstractmethod
    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """生成单个候选草稿。"""
        ...

    @abstractmethod
    async def apply_candidate(self, payload: dict, session: AsyncSession, **kwargs) -> dict:
        """采纳时，将候选 payload 写入真实模型。"""
        ...

    def is_duplicate(
        self, candidate: GenerationCandidate, existing: list[GenerationCandidate]
    ) -> bool:
        """判断当前候选与已有候选是否重复。各 adapter 可覆盖此方法。"""
        return any(
            c.title == candidate.title and c.draft_type == candidate.draft_type
            for c in existing
        )

    def compute_context_hash(self, target: dict | None, session: AsyncSession) -> str | None:
        """计算上下文哈希，用于采纳前 stale 校验。子类可覆盖以包含更多字段。"""
        if not target:
            return None
        raw = json.dumps(target, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def is_context_stale(
        self, choice: ChoiceModel, session: AsyncSession
    ) -> tuple[bool, str | None]:
        """检查采纳前的上下文是否已过期。返回 (is_stale, reason)。"""
        return False, None


class ChoiceAdapterRegistry:
    """Choice Adapter 显式注册器。"""

    def register(self, generation_type: str, adapter_cls: type[BaseGenerationChoiceAdapter]) -> None:
        from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
            _adapter_registry,
            get_generation_choice_applier,
        )
        _adapter_registry[generation_type] = adapter_cls
        adapter_cls.generation_type = generation_type
        get_generation_choice_applier().register(generation_type, adapter_cls)


def build_strategy_feedback(context: CandidateContext, task_label: str) -> str:
    """Helper to build strategy instruction string to inject into user message."""
    label = context.strategy_label or context.strategy or "默认"
    desc = context.strategy_description or ""
    instruction = context.strategy_instruction or ""

    feedback = f"本候选方案的生成策略：\n"
    feedback += f"- 策略名称：{label}\n"
    if desc:
        feedback += f"- 策略说明：{desc}\n"
    if instruction:
        feedback += f"- 生成侧重点：{instruction}\n"
    
    feedback += f"\n当前任务：{task_label}。\n"
    feedback += f"请在满足原始需求、项目上下文和输出格式约束的前提下，按上述策略生成本候选。"
    return feedback



