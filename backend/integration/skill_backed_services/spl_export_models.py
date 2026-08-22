from __future__ import annotations

from typing import Any

from backend.api.base_schema import CamelModel
from backend.core.locale import DEFAULT_LOCALE, SupportedLocale


class ProjectSummaryModel(CamelModel):
    project_id: str
    project_name: str
    project_description: str
    user_requirements: str


class ExportOptionsModel(CamelModel):
    mode: str = "syntax"  # "syntax" or "semantic"
    language: SupportedLocale = DEFAULT_LOCALE.value
    include_trace_links: bool = True
    include_warnings: bool = True


class SplExportInput(CamelModel):
    project: ProjectSummaryModel
    actors: list[Any] = []
    features: list[Any] = []
    business_objects: list[Any] = []
    flows: list[Any] = []
    unresolved_gates: list[Any] = []
    export_options: ExportOptionsModel


class WarningSourceModel(CamelModel):
    kind: str  # "feature" | "flow" | "business_object" | "scenario" | "project"
    id: str


class SplExportWarning(CamelModel):
    code: str
    message: str
    source: WarningSourceModel | None = None


class TraceLinkModel(CamelModel):
    spl_ref: str
    source_kind: str
    source_id: str


class CoverageReportModel(CamelModel):
    coverage_passed: bool
    covered_current_feature_ids: list[int] = []
    missing_current_feature_ids: list[int] = []
    unmapped_flow_ids: list[int] = []
    unmapped_acceptance_criterion_ids: list[int] = []
    semantic_risks: list[str] = []


class SplExportOutput(CamelModel):
    spl_text: str
    quality: str  # "syntax_shell" | "semantic_with_warnings" | "semantic_verified"
    warnings: list[SplExportWarning] = []
    trace_links: list[TraceLinkModel] = []
    coverage_report: CoverageReportModel | None = None
