from __future__ import annotations

import logging
from backend.api.modules.project_lifecycle.schemas.project import ProjectDetailResponse
from backend.integration.skill_backed_services.skill_imports import import_skill_module
from backend.integration.skill_backed_services.spl_export_models import SplExportOutput

logger = logging.getLogger(__name__)


class SplSyntaxExportService:
    """
    Adapter service to load and execute the spl-syntax-export-skill.
    Does not fall back to local non-skill SPL generation.
    """

    def __init__(self) -> None:
        try:
            self._core = import_skill_module("spl-syntax-export-skill", "spl_syntax_export_skill.core")
            self._skill = self._core.SplSyntaxExportSkill()
            self._available = True
        except Exception as exc:
            logger.error(f"Failed to load spl-syntax-export-skill: {exc}")
            self._available = False

    async def export(self, detail: ProjectDetailResponse) -> str:
        if not self._available:
            raise ValueError("spl_export_skill_unavailable")

        # Convert Pydantic ProjectDetailResponse to raw dictionaries
        detail_dict = detail.model_dump()
        payload = {
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
            "unresolved_gates": detail_dict.get("unresolved_gates", []),
            "export_options": {
                "mode": "syntax",
                "language": "zh-CN",
                "include_trace_links": True,
                "include_warnings": True,
            }
        }

        try:
            # Execute skill (runs synchronously in the executor if needed,
            # but since it's pure code, direct synchronous call is fine)
            result_dict = self._skill.export(payload)
            
            # Validate output using SplExportOutput schema
            output = SplExportOutput.model_validate(result_dict)
            if not output.spl_text:
                raise ValueError("spl_export_invalid_skill_output")

            return output.spl_text
        except Exception as exc:
            logger.error(f"Error during spl-syntax-export-skill execution: {exc}")
            if str(exc) == "spl_export_invalid_skill_output":
                raise ValueError("spl_export_invalid_skill_output") from exc
            raise ValueError("spl_export_invalid_skill_output") from exc
