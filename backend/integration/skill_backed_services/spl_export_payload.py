from __future__ import annotations

from typing import Any

from backend.api.modules.project_lifecycle.public import ProjectDetailResponse


def build_spl_export_payload(
    detail: ProjectDetailResponse,
    *,
    mode: str,
    content_locale: str,
) -> dict[str, Any]:
    """Build the shared RequirementSpace snapshot consumed by both SPL exporters."""
    detail_dict = detail.model_dump()
    domain_rules = detail_dict.get("domain_rules", [])
    rule_links = [
        link
        for rule in domain_rules
        for link in rule.get("links", [])
    ]
    return {
        "project": {
            "project_id": detail_dict.get("project_id", ""),
            "project_name": detail_dict.get("project_name", ""),
            "project_description": detail_dict.get("project_description", ""),
            "user_requirements": detail_dict.get("user_requirements", ""),
        },
        "actors": detail_dict.get("actors", []),
        "features": detail_dict.get("features", []),
        "business_objects": detail_dict.get("business_objects", []),
        "flows": detail_dict.get("flows", []),
        "domain_rules": domain_rules,
        "rule_links": rule_links,
        "unresolved_gates": detail_dict.get("unresolved_gates", []),
        "export_options": {
            "mode": mode,
            "language": content_locale,
            "include_trace_links": True,
            "include_warnings": True,
        },
    }
