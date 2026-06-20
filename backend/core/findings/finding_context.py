"""backend/core/findings Package.

负责将底层 detectors 产生的结构化 Issue 信号转换为对用户友好的 Finding 概念，
并根据Finding Policy 将其归类为：ISSUE（待处理问题）、GATE_CONDITION（阶段门禁/阻断条件）或 QUALITY_HINT（质量提示/优化建议），
同时确定 blockingScope。它不负责具体问题的AI修复执行，仅提供展示层所需的元数据声明。
"""

from backend.core.detectors.issue_context_loader import (
    IssueProjectContext,
    load_issue_project_context,
)

__all__ = ["IssueProjectContext", "load_issue_project_context"]
