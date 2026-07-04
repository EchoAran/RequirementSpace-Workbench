from __future__ import annotations

from .schema import SplExportInputDict, SplExportOutputDict
from .renderer import SplSyntaxRenderer


class SplSyntaxExportSkill:
    """
    Skill to perform deterministic code-based syntax wrapper export to SPL.
    Uses SplSyntaxRenderer to generate output text, warnings, and trace links.
    """

    def __init__(self) -> None:
        self._renderer = SplSyntaxRenderer()

    def export(self, payload: SplExportInputDict) -> SplExportOutputDict:
        spl_text, warnings, trace_links = self._renderer.render(payload)

        return {
            "spl_text": spl_text,
            "quality": "syntax_shell",
            "warnings": warnings,
            "trace_links": trace_links,
            "coverage_report": None
        }
