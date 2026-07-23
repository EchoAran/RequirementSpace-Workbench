from __future__ import annotations

import re
from typing import Any

from backend.core.prompt_resolver import get_content_locale
from backend.integration.skill_backed_services.chart_renderer import KanoChartRenderer
from backend.schemas import FeatureNode


ROLE_TAG_PATTERN = re.compile(r"\s*\[Role:\s*[^\]]+\]\s*$", re.IGNORECASE)


def _canon(value: str) -> str:
    return re.sub(r"\s+", " ", ROLE_TAG_PATTERN.sub("", value or "").strip()).lower()


class KanoScopeAdapter:
    def __init__(self):
        self._chart_renderer = KanoChartRenderer()

    def build_kano_feature_tree(self, leaf_features: list[FeatureNode]) -> dict[str, Any]:
        return {
            "features": [
                {
                    "feature_id": feature.featureId,
                    "name": feature.featureName,
                    "description": feature.featureDescription,
                }
                for feature in leaf_features
            ]
        }

    def to_current_scopes(
        self,
        kano_result: dict[str, Any],
        leaf_features: list[FeatureNode],
    ) -> list[dict]:
        results = kano_result.get("results", [])
        if not isinstance(results, list) or not results:
            raise ValueError("empty_scopes")
        participant_count = self._participant_count(kano_result)
        locale = get_content_locale()

        feature_by_name = {
            _canon(feature.featureName): feature
            for feature in leaf_features
        }
        scopes = []

        for item in results:
            if not isinstance(item, dict):
                raise ValueError("invalid_scope_payload")

            feature_name = str(item.get("feature", "")).strip()
            feature = feature_by_name.get(_canon(feature_name))
            if feature is None:
                raise ValueError("invalid_feature_reference")

            category = str(item.get("kano_category", "I")).strip().upper() or "I"
            better_worse = item.get("better_worse", {}) if isinstance(item.get("better_worse"), dict) else {}
            scope_status = self._scope_status(category, better_worse)
            reason_summary = item.get("reason_summary", {}) if isinstance(item.get("reason_summary"), dict) else {}
            reason = self._reason(
                category=category,
                category_name=str(item.get("kano_category_name", category)),
                scope_status=scope_status,
                better_worse=better_worse,
                reason_summary=reason_summary,
                locale=locale,
            )
            satisfaction_distribution = (
                item.get("satisfaction_distribution", {})
                if isinstance(item.get("satisfaction_distribution"), dict)
                else {}
            )

            scopes.append(
                {
                    "feature_id": feature.featureId,
                    "scope_status": scope_status,
                    "reason": reason,
                    "positive_summary": reason_summary.get("functional_viewpoint"),
                    "negative_summary": reason_summary.get("dysfunctional_viewpoint"),
                    "positive_picture_base64": self._chart_renderer.render_rating_distribution(
                        title=f"{feature.featureName} present",
                        distribution=satisfaction_distribution.get("functional", {}),
                        max_count=participant_count,
                    ),
                    "negative_picture_base64": self._chart_renderer.render_rating_distribution(
                        title=f"{feature.featureName} absent",
                        distribution=satisfaction_distribution.get("dysfunctional", {}),
                        max_count=participant_count,
                    ),
                    "kano_category": category,
                    "kano_category_name": item.get("kano_category_name"),
                }
            )

        return scopes

    @staticmethod
    def _scope_status(category: str, better_worse: dict[str, Any]) -> str:
        if category in {"M", "O"}:
            return "CURRENT"
        if category == "A":
            try:
                better = float(better_worse.get("Better", 0.0))
            except (TypeError, ValueError):
                better = 0.0
            return "CURRENT" if better >= 0.6 else "POSTPONED"
        if category == "R":
            return "EXCLUDE"
        return "POSTPONED"

    @staticmethod
    def _reason(
        category: str,
        category_name: str,
        scope_status: str,
        better_worse: dict[str, Any],
        reason_summary: dict[str, str],
        locale: str,
    ) -> str:
        better = better_worse.get("Better", 0.0)
        worse = better_worse.get("Worse", 0.0)
        functional_viewpoint = str(reason_summary.get("functional_viewpoint", "")).strip()
        dysfunctional_viewpoint = str(reason_summary.get("dysfunctional_viewpoint", "")).strip()

        if locale == "zh-CN":
            localized_category = {
                "A": "魅力型",
                "O": "期望型",
                "M": "必备型",
                "I": "无差异型",
                "R": "反向型",
                "Q": "可疑结果",
            }.get(category, category_name)
            localized_scope = {
                "CURRENT": "当前范围",
                "POSTPONED": "延期范围",
                "EXCLUDE": "排除范围",
            }.get(scope_status, scope_status)
            prefix = (
                f"Kano 类别 {localized_category}({category}) 对应{localized_scope}。"
                f"满意系数={better}，不满意系数={worse}。"
            )
            if functional_viewpoint:
                prefix += f" 用户重视该功能，因为{functional_viewpoint}"
            if dysfunctional_viewpoint:
                prefix += f" 缺少该功能时，用户认为{dysfunctional_viewpoint}"
            return prefix

        prefix = (
            f"Kano category {category_name}({category}) maps to {scope_status}. "
            f"Better={better}, Worse={worse}."
        )
        if functional_viewpoint:
            prefix += f" Users valued its presence because {functional_viewpoint}"
        if dysfunctional_viewpoint:
            prefix += f" When absent, users felt {dysfunctional_viewpoint}"
        return prefix

    @staticmethod
    def _participant_count(kano_result: dict[str, Any]) -> int | None:
        try:
            count = int(kano_result.get("participant_count") or 0)
        except (TypeError, ValueError):
            return None
        return count if count > 0 else None
