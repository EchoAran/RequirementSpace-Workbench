"""backend/core/suggestions Package.

负责计算和返回阶段级下一步建议（NextSuggestion）。
主要职责是引导用户进入下一步操作（如 create_draft 生成候选/草稿、navigate 页面跳转、open_panel 打开编辑面板等），
作为一种非阻断性的渐进引导工具。
下一步建议不涉及具体结构异常的“修复”语义，不得调用 IssueRepairService，UI上亦不得暴露任何“AI处理/修复”文案。
"""

from abc import ABC, abstractmethod

from backend.schemas import NextSuggestion


class StageSuggestionPolicy(ABC):
    @abstractmethod
    async def get_next(
        self,
        project_id: int,
        session,
        public_project_id: str | None = None,
    ) -> NextSuggestion:
        pass
