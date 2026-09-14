from __future__ import annotations

from typing import Any

from typing_extensions import (
    TypedDict,  # using typing_extensions for python 3.8/3.9 compatibility or typing if only 3.9+
)


class ProjectDict(TypedDict):
    project_id: str
    project_name: str
    project_description: str
    user_requirements: str


class ExportOptionsDict(TypedDict, total=False):
    mode: str
    language: str
    include_trace_links: bool
    include_warnings: bool


class SplExportInputDict(TypedDict):
    project: ProjectDict
    actors: list[dict[str, Any]]
    features: list[dict[str, Any]]
    business_objects: list[dict[str, Any]]
    flows: list[dict[str, Any]]
    domain_rules: list[dict[str, Any]]
    rule_links: list[dict[str, Any]]
    unresolved_gates: list[dict[str, Any]]
    export_options: ExportOptionsDict


class WarningSourceDict(TypedDict):
    kind: str
    id: str


class SplExportWarningDict(TypedDict):
    code: str
    message: str
    source: WarningSourceDict | None


class TraceLinkDict(TypedDict):
    spl_ref: str
    source_kind: str
    source_id: str


class CoverageReportDict(TypedDict, total=False):
    coverage_passed: bool
    covered_current_feature_ids: list[int]
    missing_current_feature_ids: list[int]
    unmapped_flow_ids: list[int]
    unmapped_acceptance_criterion_ids: list[int]
    semantic_risks: list[str]


class SplExportOutputDict(TypedDict):
    spl_text: str
    quality: str
    warnings: list[SplExportWarningDict]
    trace_links: list[TraceLinkDict]
    coverage_report: CoverageReportDict | None
