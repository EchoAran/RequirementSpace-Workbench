"""Issue Capability Registry — 单一事实来源

本模块是纯静态定义，只依赖 Python 标准库。
不得导入 findings、issue_resolution、API services、solver、database model 或 session。

依赖方向:
  findings               → issue_capabilities
  issue_resolution       → issue_capabilities
  API schemas / services → issue_capabilities

  issue_capabilities -X→ findings
  issue_capabilities -X→ issue_resolution
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class IssueCapabilityKind(str, Enum):
    """Issue 处理能力枚举。

    ai_repair         → AI 修复，调用 AI solver 生成 repair draft 或 choice group
    generation_draft  → 生成型草稿（场景、AC、Scope 等），由 GenerationDraftIssueSolver 处理
    open_panel        → 定位处理，打开对应编辑面板由用户手动操作
    manual_action     → 查看处理建议，系统无法自动修复时的回退
    unsupported       → 暂不支持自动处理
    """
    AI_REPAIR = "ai_repair"
    GENERATION_DRAFT = "generation_draft"
    OPEN_PANEL = "open_panel"
    MANUAL_ACTION = "manual_action"
    UNSUPPORTED = "unsupported"


@dataclass
class IssueCapabilityDefinition:
    """单个 issue code 的处理能力定义。"""
    kind: IssueCapabilityKind
    action_label: str
    enabled: bool = True


# ── 所有已知 issue code ──────────────────────────────────────────────

KNOWN_ISSUE_CODES: set[str] = {
    # What stage
    "ACTOR_WITHOUT_FEATURE",
    "LEAF_FEATURE_WITHOUT_ACTOR",
    "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO",
    "SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS",
    "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA",
    "DUPLICATE_SCENARIO_NAME",
    # How stage
    "LEAF_FEATURE_WITHOUT_FLOW",
    "FLOW_WITHOUT_FEATURE",
    "FLOW_WITHOUT_STEPS",
    "ACTOR_ACTION_STEP_WITHOUT_ACTOR",
    "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES",
    "UNREACHABLE_FLOW_STEP",
    "BUSINESS_OBJECT_WITHOUT_USAGE",
    "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES",
    # Scope stage
    "LEAF_FEATURE_WITHOUT_SCOPE",
    "SCOPE_WITHOUT_REASON",
}

# ── 处理能力静态映射 ──────────────────────────────────────────────────

ISSUE_CAPABILITIES: dict[str, IssueCapabilityDefinition] = {
    # ========== AI 修复 (有 AI solver) ==========
    # Scope
    "SCOPE_WITHOUT_REASON": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    # What
    "LEAF_FEATURE_WITHOUT_ACTOR": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    "SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    "DUPLICATE_SCENARIO_NAME": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    "ACTOR_WITHOUT_FEATURE": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    # How
    "LEAF_FEATURE_WITHOUT_FLOW": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    "FLOW_WITHOUT_FEATURE": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    "FLOW_WITHOUT_STEPS": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    "BUSINESS_OBJECT_WITHOUT_USAGE": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),
    "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.AI_REPAIR,
        action_label="AI 修复",
    ),

    # ========== 生成草稿 (generation draft solver) ==========
    "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.GENERATION_DRAFT,
        action_label="生成草稿",
    ),
    "LEAF_FEATURE_WITHOUT_SCOPE": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.GENERATION_DRAFT,
        action_label="生成草稿",
    ),

    # ========== 定位处理 (open panel solver) ==========
    "ACTOR_ACTION_STEP_WITHOUT_ACTOR": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.OPEN_PANEL,
        action_label="定位处理",
    ),
    "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.OPEN_PANEL,
        action_label="定位处理",
    ),
    "UNREACHABLE_FLOW_STEP": IssueCapabilityDefinition(
        kind=IssueCapabilityKind.OPEN_PANEL,
        action_label="定位处理",
    ),
}


def get_issue_capability(code: str) -> IssueCapabilityDefinition:
    """获取指定 issue code 的处理能力定义。

    已知 code 返回对应定义，未知 code 返回 unsupported。
    """
    return ISSUE_CAPABILITIES.get(
        code,
        IssueCapabilityDefinition(
            kind=IssueCapabilityKind.UNSUPPORTED,
            action_label="暂不支持自动处理",
            enabled=False,
        ),
    )


def codes_with_capability(kind: IssueCapabilityKind) -> set[str]:
    """返回指定处理能力类型的所有 issue code 集合。"""
    return {
        code
        for code, cap in ISSUE_CAPABILITIES.items()
        if cap.kind == kind
    }
