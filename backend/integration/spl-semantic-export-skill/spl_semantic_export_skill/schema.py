from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


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
    actors: List[Dict[str, Any]]
    features: List[Dict[str, Any]]
    business_objects: List[Dict[str, Any]]
    flows: List[Dict[str, Any]]
    unresolved_gates: List[Dict[str, Any]]
    export_options: ExportOptionsDict


class WarningSourceDict(TypedDict):
    kind: str
    id: str


class SplExportWarningDict(TypedDict):
    code: str
    message: str
    source: Optional[WarningSourceDict]


class TraceLinkDict(TypedDict):
    spl_ref: str
    source_kind: str
    source_id: str


class CoverageReportDict(TypedDict, total=False):
    coverage_passed: bool
    covered_current_feature_ids: List[int]
    missing_current_feature_ids: List[int]
    unmapped_flow_ids: List[int]
    unmapped_acceptance_criterion_ids: List[int]
    semantic_risks: List[str]


class SplExportOutputDict(TypedDict):
    spl_text: str
    quality: str
    warnings: List[SplExportWarningDict]
    trace_links: List[TraceLinkDict]
    coverage_report: Optional[CoverageReportDict]
