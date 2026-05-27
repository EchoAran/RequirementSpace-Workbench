from __future__ import annotations

import base64
import logging
import re
import warnings
from io import BytesIO
from typing import Any


logger = logging.getLogger(__name__)
CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")


class KanoChartRenderer:
    RATINGS = ["A", "B", "C", "D", "E"]

    def render_rating_distribution(
        self,
        title: str,
        distribution: dict[str, Any],
        max_count: int | None = None,
    ) -> str | None:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as error:
            logger.warning(
                "Kano chart rendering skipped because matplotlib is unavailable: %s",
                error,
            )
            return None

        counts = [
            int((distribution.get(rating) or {}).get("count", 0))
            for rating in self.RATINGS
        ]
        y_max = self._resolve_y_max(counts, max_count)
        if not any(counts):
            logger.warning(
                "Kano chart rendering produced an empty distribution for %s",
                title,
            )

        fig, ax = plt.subplots(figsize=(5, 3), dpi=120)
        ax.bar(self.RATINGS, counts, color=["#3b82f6", "#22c55e", "#a3a3a3", "#f59e0b", "#ef4444"])
        ax.set_title(self._safe_title(title))
        ax.set_xlabel("Rating")
        ax.set_ylabel("Count")
        ax.set_ylim(0, y_max)
        ax.set_yticks(range(0, y_max + 1))
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()

        buffer = BytesIO()
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Glyph .* missing from font",
                category=UserWarning,
            )
            fig.savefig(buffer, format="png")
        plt.close(fig)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def _safe_title(title: str) -> str:
        if not CJK_PATTERN.search(title or ""):
            return title
        return "Kano rating distribution"

    @staticmethod
    def _resolve_y_max(counts: list[int], max_count: int | None) -> int:
        if max_count is not None and max_count > 0:
            return max_count
        return max(sum(counts), max(counts + [1]), 1)
