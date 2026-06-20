"""backend/core/detectors Package.

负责扫描需求空间数据模型并产生结构检测信号（Issue/Finding数据），不决定展示类型或决定AI处理能力。

注意：旧 `issue_solvers` 子目录（问题处理与AI修复）已在阶段五中迁移至
`backend/core/issue_resolution` 包。`detectors/issue_solvers/__init__.py` 目前
作为兼容 shim 保留；新代码应直接从 `backend.core.issue_resolution` 导入。
"""

from backend.core.detectors.how_issue_detector import HowIssueDetector
from backend.schemas import (
    Issue,
    IssueSeverity,
    IssueStage,
    IssueTarget,
)
from backend.core.detectors.scope_issue_detector import ScopeIssueDetector
from backend.core.detectors.what_issue_detector import WhatIssueDetector
