"""Issue Resolution Package — 问题处理能力。

本包负责执行待处理问题的具体处理操作，包括：
  - AI 修复求解（AI strategies）
  - 生成型草稿（generation draft）
  - 打开面板定位（open panel）
  - Patch 验证与指纹计算

依赖方向（遵守阶段三 capability registry 约束）：
  issue_resolution → detectors (只读结构检测)
  issue_resolution → issue_capabilities (只读能力定义)
  issue_resolution → schemas / services (标准依赖)

禁止：
  issue_resolution → findings
  issue_capabilities → issue_resolution
"""

from backend.core.issue_resolution.base_solver import BaseIssueSolver
from backend.core.issue_resolution.registry import IssueSolverRegistry
from backend.core.issue_resolution.generation_draft_solver import (
    GenerationDraftIssueSolver,
)
from backend.core.issue_resolution.open_panel_solver import OpenPanelIssueSolver

__all__ = [
    "BaseIssueSolver",
    "GenerationDraftIssueSolver",
    "IssueSolverRegistry",
    "OpenPanelIssueSolver",
]
