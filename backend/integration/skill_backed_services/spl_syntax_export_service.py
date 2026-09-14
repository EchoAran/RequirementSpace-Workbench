from __future__ import annotations

import logging

from backend.api.modules.project_lifecycle.public import ProjectDetailResponse
from backend.core.locale import DEFAULT_LOCALE, SupportedLocale
from backend.integration.skill_backed_services.skill_imports import import_skill_module
from backend.integration.skill_backed_services.spl_export_models import SplExportOutput
from backend.integration.skill_backed_services.spl_export_payload import build_spl_export_payload

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

    async def export(
        self,
        detail: ProjectDetailResponse,
        content_locale: SupportedLocale = DEFAULT_LOCALE.value,
    ) -> str:
        if not self._available:
            raise ValueError("spl_export_skill_unavailable")

        payload = build_spl_export_payload(
            detail,
            mode="syntax",
            content_locale=content_locale,
        )

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
