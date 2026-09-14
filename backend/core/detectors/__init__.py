"""backend/core/detectors Package.

负责扫描需求空间数据模型并产生结构检测信号（Issue/Finding数据），不决定展示类型或决定AI处理能力。

"""

from backend.core.detectors.how_issue_detector import HowIssueDetector
from backend.core.detectors.scope_issue_detector import ScopeIssueDetector
from backend.core.detectors.what_issue_detector import WhatIssueDetector
from backend.schemas import (
    Issue,
    IssueSeverity,
    IssueStage,
    IssueTarget,
)
