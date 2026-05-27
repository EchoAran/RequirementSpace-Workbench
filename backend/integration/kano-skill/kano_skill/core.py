from __future__ import annotations

import json
import os
import re
from collections import Counter, namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import resources
from pathlib import Path
from typing import Any, Callable, TypeVar


FIXED_PARTICIPANT_COUNT = 5
DEFAULT_MAX_CONCURRENCY = 5
T = TypeVar("T")
R = TypeVar("R")
FIXED_DISTRIBUTION = {
    "age": {
        "0-14": 0.1601,
        "15-64": 0.6933,
        "65+": 0.1467,
    },
    "edu": {
        "Tertiary": 0.1612,
        "Secondary": 0.1565,
        "\u2264Primary": 0.6823,
    },
    "gender": {
        "Female": 0.4906,
        "Male": 0.5094,
    },
}

KANO_CLASSIFICATION = {
    ("A", "A"): "Q",
    ("A", "B"): "A",
    ("A", "C"): "A",
    ("A", "D"): "A",
    ("A", "E"): "O",
    ("B", "A"): "R",
    ("B", "B"): "I",
    ("B", "C"): "I",
    ("B", "D"): "I",
    ("B", "E"): "M",
    ("C", "A"): "R",
    ("C", "B"): "I",
    ("C", "C"): "I",
    ("C", "D"): "I",
    ("C", "E"): "M",
    ("D", "A"): "R",
    ("D", "B"): "I",
    ("D", "C"): "I",
    ("D", "D"): "I",
    ("D", "E"): "M",
    ("E", "A"): "R",
    ("E", "B"): "R",
    ("E", "C"): "R",
    ("E", "D"): "R",
    ("E", "E"): "Q",
}

CATEGORY_NAMES = {
    "A": "Attractive",
    "O": "Performance",
    "M": "Must-be",
    "I": "Indifference",
    "R": "Reverse",
    "Q": "Questionable",
}

ALL_KANO_CATEGORIES = ["A", "O", "M", "I", "R", "Q"]
ALL_SATISFACTION_RATINGS = ["A", "B", "C", "D", "E"]
WORD_TO_LETTER = {
    "Must-be": "M",
    "Performance": "O",
    "Attractive": "A",
    "Indifferent": "I",
}


def _resource_text(package_path: str, filename: str) -> str:
    return resources.files(package_path).joinpath(filename).read_text(encoding="utf-8")


def _load_config(config_path: str | None = None) -> Any:
    if config_path:
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
    else:
        config_dict = json.loads(
            _resource_text("kano_skill.resources.config", "config.json")
        )

    Config = namedtuple("Config", config_dict.keys())
    return Config(**config_dict)


def _canon_feature(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _extract_feature_from_question(value: str) -> str:
    text = str(value or "").strip()
    patterns = [
        r"how would you feel if the product had\s+(.+?)\??$",
        r"how would you feel if the product did not have\s+(.+?)\??$",
        r"if the feature is present[:：]?\s*(.+)$",
        r"if the feature is not present[:：]?\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return text


def _json_loads_object(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {text}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def _max_concurrency() -> int:
    raw = os.environ.get("KANO_SKILL_MAX_CONCURRENCY", str(DEFAULT_MAX_CONCURRENCY))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_MAX_CONCURRENCY
    return max(1, value)


def _parallel_map(items: list[T], worker: Callable[[T], R]) -> list[R]:
    if len(items) <= 1:
        return [worker(item) for item in items]

    max_workers = min(_max_concurrency(), len(items))
    if max_workers <= 1:
        return [worker(item) for item in items]

    results: list[R | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(worker, item): index
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    return [result for result in results if result is not None]


def _parse_rating_reason(value: Any) -> tuple[str, str]:
    rating = ""
    reason = ""
    if isinstance(value, dict):
        rating = str(value.get("rating", "")).strip()
        reason = str(value.get("reason", "")).strip()
    elif isinstance(value, (list, tuple)):
        if value:
            rating = str(value[0]).strip()
        if len(value) > 1:
            reason = str(value[1]).strip()
    elif value is not None:
        rating = str(value).strip()

    rating = rating[:1].upper() if rating else ""
    if rating not in {"A", "B", "C", "D", "E"}:
        rating = ""
    return rating, reason


def _normalize_users(raw_users: dict[str, Any]) -> dict[str, dict[str, Any]]:
    users: dict[str, dict[str, Any]] = {}
    for index in range(1, FIXED_PARTICIPANT_COUNT + 1):
        user_key = f"User{index}"
        profile = raw_users.get(user_key)
        if not isinstance(profile, dict):
            raise ValueError(f"User_information output is missing {user_key}.")
        users[user_key] = dict(profile)
    return users


def _resolve_feature_key(
    key: Any,
    value: Any,
    feature_aliases: dict[str, str],
    ordered_features: list[str],
) -> str | None:
    candidates: list[str] = []
    if key is not None:
        key_text = str(key)
        candidates.extend([key_text, _extract_feature_from_question(key_text)])
    if isinstance(value, dict):
        for field in ("feature", "Feature", "question", "Question", "name", "Name"):
            if value.get(field):
                field_text = str(value[field])
                candidates.extend([field_text, _extract_feature_from_question(field_text)])

    for candidate in candidates:
        canonical = _canon_feature(candidate)
        if canonical in feature_aliases:
            return feature_aliases[canonical]

    lowered_candidates = [_canon_feature(candidate) for candidate in candidates if candidate]
    for feature in ordered_features:
        feature_canon = _canon_feature(feature)
        if any(feature_canon in candidate or candidate in feature_canon for candidate in lowered_candidates):
            return feature

    for candidate in lowered_candidates:
        match = re.search(
            r"(?:question(?:\s*name)?|item|feature)\s*(\d+)$",
            candidate,
            flags=re.IGNORECASE,
        )
        if match:
            index = int(match.group(1)) - 1
            if 0 <= index < len(ordered_features):
                return ordered_features[index]

    return None


class KanoSkill:
    """Fixed-participant Kano analysis from requirement text and a feature tree."""

    def __init__(self, config_path: str | None = None, api_key: str | None = None) -> None:
        self.args = _load_config(config_path)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None
        self._prompts = self._load_prompts(config_path)
        self._set_proxy()

    def _set_proxy(self) -> None:
        proxy = getattr(self.args, "proxy", None)
        if not proxy:
            return
        os.environ.setdefault("http_proxy", proxy)
        os.environ.setdefault("https_proxy", proxy)

    def _load_prompts(self, config_path: str | None) -> dict[str, str]:
        prompt_names = [
            "User_information.txt",
            "User_perference.txt",
            "User_satisfaction.txt",
            "reasons_sum.txt",
        ]
        prompt_path = getattr(self.args, "prompt_path", None)

        if config_path and prompt_path:
            prompt_dir = Path(prompt_path)
            if not prompt_dir.is_absolute():
                config_dir = Path(config_path).resolve().parent
                candidates = [
                    config_dir / prompt_dir,
                    Path.cwd() / prompt_dir,
                    config_dir.parent / prompt_dir,
                ]
                prompt_dir = next((path for path in candidates if path.exists()), candidates[0])
            return {
                name: (prompt_dir / name).read_text(encoding="utf-8")
                for name in prompt_names
            }

        return {
            name: _resource_text("kano_skill.resources.prompts", name)
            for name in prompt_names
        }

    def _ask_json(self, prompt: str) -> dict[str, Any]:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)

        response = self._client.chat.completions.create(
            model=self.args.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=getattr(self.args, "temperature", 0.2),
        )
        content = response.choices[0].message.content or ""
        return _json_loads_object(content, "OpenAI response")

    @staticmethod
    def extract_features(feature_tree: str | dict[str, Any]) -> list[str]:
        if isinstance(feature_tree, str):
            feature_tree_obj = _json_loads_object(feature_tree, "feature_tree")
        elif isinstance(feature_tree, dict):
            feature_tree_obj = feature_tree
        else:
            raise ValueError("feature_tree must be a JSON string or dict.")

        if isinstance(feature_tree_obj.get("features"), list):
            features = []
            for item in feature_tree_obj["features"]:
                if isinstance(item, dict):
                    value = item.get("name") or item.get("feature_name") or item.get("Feature")
                else:
                    value = item
                if str(value or "").strip():
                    features.append(str(value).strip())
        else:
            level_keys = {
                str(key)
                for key in feature_tree_obj.keys()
                if re.fullmatch(r"L\d+(?:\.[\d.]+)?", str(key))
            }

            leaf_keys = []
            for key in level_keys:
                if key == "L1":
                    prefix = "L2."
                else:
                    match = re.fullmatch(r"L(?P<level>\d+)\.(?P<parts>[\d.]+)", key)
                    if match is None:
                        continue
                    prefix = f"L{int(match.group('level')) + 1}.{match.group('parts')}."
                if not any(candidate.startswith(prefix) for candidate in level_keys):
                    leaf_keys.append(key)

            features = []
            for key in sorted(leaf_keys):
                value = feature_tree_obj.get(key)
                if isinstance(value, dict):
                    value = value.get("name") or value.get("feature_name") or value.get("Feature")
                if str(value or "").strip():
                    features.append(str(value).strip())

        clean_features: list[str] = []
        seen: set[str] = set()
        for feature in features:
            canon = _canon_feature(feature)
            if canon and canon not in seen:
                clean_features.append(feature)
                seen.add(canon)
        if not clean_features:
            raise ValueError("feature_tree must contain at least one unique leaf feature.")
        return clean_features

    def build_participants(self, requirement_text: str) -> dict[str, dict[str, Any]]:
        prompt = self._prompts["User_information.txt"]
        prompt = prompt.replace("{Requirement Replacement Flag}", requirement_text)
        prompt = prompt.replace("{User_num Replacement Flag}", str(FIXED_PARTICIPANT_COUNT))
        prompt = prompt.replace(
            "{Demographic Distribution Flag}",
            json.dumps(FIXED_DISTRIBUTION, ensure_ascii=False, indent=2),
        )
        prompt = prompt.replace(
            "{Demographics}",
            json.dumps(FIXED_DISTRIBUTION, ensure_ascii=False),
        )
        prompt += (
            "\n\nFixed constraints for this skill:\n"
            f"- Return exactly {FIXED_PARTICIPANT_COUNT} users named User1 through User{FIXED_PARTICIPANT_COUNT}.\n"
            "- Use the demographic distribution above as the target distribution for the user set.\n"
            "- Do not add extra users and do not omit any required persona fields."
        )
        return _normalize_users(self._ask_json(prompt))

    def enrich_preferences(
        self,
        requirement_text: str,
        users: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        def enrich_one(item: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
            uid, profile = item
            prompt = self._prompts["User_perference.txt"]
            prompt = prompt.replace("{User Profile Replacement Flag}", json.dumps(profile, ensure_ascii=False))
            prompt = prompt.replace("{Requirement Replacement Flag}", requirement_text)
            enriched_profile = dict(profile)
            enriched_profile.update(self._ask_json(prompt))
            return uid, enriched_profile

        enriched: dict[str, dict[str, Any]] = {}
        for uid, enriched_profile in _parallel_map(list(users.items()), enrich_one):
            enriched[uid] = enriched_profile
        return enriched

    def score_satisfaction(
        self,
        requirement_text: str,
        users: dict[str, dict[str, Any]],
        features: list[str],
    ) -> dict[str, Any]:
        functional_questions = {
            feature: f"How would you feel if the product had {feature}?"
            for feature in features
        }
        dysfunctional_questions = {
            feature: f"How would you feel if the product did not have {feature}?"
            for feature in features
        }
        def score_one(item: tuple[str, dict[str, Any]]) -> tuple[str, Any]:
            uid, profile = item
            prompt = self._prompts["User_satisfaction.txt"]
            prompt = prompt.replace("{User Profile Replacement Flag}", json.dumps(profile, ensure_ascii=False))
            prompt = prompt.replace("{Profile}", json.dumps(profile, ensure_ascii=False))
            prompt = prompt.replace("{Requirement Replacement Flag}", requirement_text)
            prompt = prompt.replace("{Product}", requirement_text)
            prompt = prompt.replace("{Functional Questions Replacement Flag}", json.dumps(functional_questions, ensure_ascii=False))
            prompt = prompt.replace("{Dysfunctional Questions Replacement Flag}", json.dumps(dysfunctional_questions, ensure_ascii=False))
            prompt += (
                "\n\nImportant output-key rule: in both Functional and Dysfunctional objects, "
                "use the exact feature names from the input question JSON as keys. Do not use "
                "generic keys such as Question name 1, Question 1, Item 1, or full question sentences."
            )
            return uid, self._ask_json(prompt)

        scores: dict[str, Any] = {}
        for uid, score in _parallel_map(list(users.items()), score_one):
            scores[uid] = score
        return scores

    def classify(
        self,
        features: list[str],
        satisfaction_scores: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, Counter], dict[str, dict[str, str]], list[dict[str, Any]]]:
        feature_aliases: dict[str, str] = {}
        for feature in features:
            feature_aliases[_canon_feature(feature)] = feature
            feature_aliases[_canon_feature(f"How would you feel if the product had {feature}?")] = feature
            feature_aliases[_canon_feature(f"How would you feel if the product did not have {feature}?")] = feature
        votes_per_feature: dict[str, Counter] = {feature: Counter() for feature in features}
        user_kano_categories: dict[str, dict[str, str]] = {}
        reasons_records: list[dict[str, Any]] = []

        for uid, ratings in satisfaction_scores.items():
            functional_raw = (ratings.get("Functional", {}) or {}) if isinstance(ratings, dict) else {}
            dysfunctional_raw = (ratings.get("Dysfunctional", {}) or {}) if isinstance(ratings, dict) else {}

            functional_ratings: dict[str, str] = {}
            functional_reasons: dict[str, str] = {}
            for key, value in functional_raw.items():
                feature = _resolve_feature_key(key, value, feature_aliases, features)
                if feature is None:
                    continue
                rating, reason = _parse_rating_reason(value)
                functional_ratings[feature] = rating
                functional_reasons[feature] = reason

            dysfunctional_ratings: dict[str, str] = {}
            dysfunctional_reasons: dict[str, str] = {}
            for key, value in dysfunctional_raw.items():
                feature = _resolve_feature_key(key, value, feature_aliases, features)
                if feature is None:
                    continue
                rating, reason = _parse_rating_reason(value)
                dysfunctional_ratings[feature] = rating
                dysfunctional_reasons[feature] = reason

            user_kano_categories[uid] = {}
            for feature in set(functional_ratings) & set(dysfunctional_ratings):
                f_tag = functional_ratings.get(feature, "")
                d_tag = dysfunctional_ratings.get(feature, "")
                kano_category = KANO_CLASSIFICATION.get((f_tag, d_tag), "Q")
                user_kano_categories[uid][feature] = kano_category
                if feature in votes_per_feature:
                    votes_per_feature[feature][kano_category] += 1

            for feature in set(functional_ratings) | set(dysfunctional_ratings):
                reasons_records.append(
                    {
                        "User": uid,
                        "Feature": feature,
                        "Functional_Rating": functional_ratings.get(feature, ""),
                        "Functional_Reason": functional_reasons.get(feature, ""),
                        "Dysfunctional_Rating": dysfunctional_ratings.get(feature, ""),
                        "Dysfunctional_Reason": dysfunctional_reasons.get(feature, ""),
                    }
                )

        final_categories: dict[str, str] = {}
        for feature, counter in votes_per_feature.items():
            if sum(counter.values()) == 0:
                final_categories[feature] = "Q"
                continue
            most_common = counter.most_common()
            top_count = most_common[0][1]
            top_categories = [category for category, count in most_common if count == top_count]
            final_categories[feature] = top_categories[0] if len(top_categories) == 1 else "Q"

        return final_categories, votes_per_feature, user_kano_categories, reasons_records

    def better_worse_rows(self, votes_per_feature: dict[str, Counter]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feature, counter in votes_per_feature.items():
            attractive = int(counter.get("A", 0))
            one_dimensional = int(counter.get("O", 0))
            must_be = int(counter.get("M", 0))
            indifferent = int(counter.get("I", 0))
            denom = attractive + one_dimensional + must_be + indifferent
            if denom == 0:
                better = 0.0
                worse = 0.0
            else:
                better = (attractive + one_dimensional) / denom
                worse = -((must_be + one_dimensional) / denom)

            worse_abs = abs(worse)
            if better >= 0.5 and worse_abs < 0.5:
                quadrant = "Attractive"
            elif better >= 0.5 and worse_abs >= 0.5:
                quadrant = "Performance"
            elif better < 0.5 and worse_abs >= 0.5:
                quadrant = "Must-be"
            else:
                quadrant = "Indifferent"

            rows.append(
                {
                    "Feature": feature,
                    "A": attractive,
                    "O": one_dimensional,
                    "M": must_be,
                    "I": indifferent,
                    "Better": round(better, 4),
                    "Worse": round(worse, 4),
                    "WorseAbs": round(worse_abs, 4),
                    "Quadrant": quadrant,
                    "Kano_Category": WORD_TO_LETTER.get(quadrant, "I"),
                }
            )
        return rows

    def _distribution(self, counter: Counter) -> dict[str, dict[str, float | int]]:
        total = sum(counter.values())
        return {
            category: {
                "count": int(counter.get(category, 0)),
                "ratio": round((counter.get(category, 0) / total), 4) if total else 0.0,
            }
            for category in ALL_KANO_CATEGORIES
        }

    def satisfaction_distributions(
        self,
        features: list[str],
        reasons_records: list[dict[str, Any]],
    ) -> dict[str, dict[str, dict[str, dict[str, float | int]]]]:
        distributions: dict[str, dict[str, dict[str, dict[str, float | int]]]] = {}
        for feature in features:
            rows = [row for row in reasons_records if row.get("Feature") == feature]
            functional_counter = Counter(
                str(row.get("Functional_Rating", "")).strip()[:1].upper()
                for row in rows
                if str(row.get("Functional_Rating", "")).strip()[:1].upper() in ALL_SATISFACTION_RATINGS
            )
            dysfunctional_counter = Counter(
                str(row.get("Dysfunctional_Rating", "")).strip()[:1].upper()
                for row in rows
                if str(row.get("Dysfunctional_Rating", "")).strip()[:1].upper() in ALL_SATISFACTION_RATINGS
            )
            distributions[feature] = {
                "functional": self._rating_distribution(functional_counter),
                "dysfunctional": self._rating_distribution(dysfunctional_counter),
            }
        return distributions

    def _rating_distribution(self, counter: Counter) -> dict[str, dict[str, float | int]]:
        total = sum(counter.values())
        return {
            rating: {
                "count": int(counter.get(rating, 0)),
                "ratio": round((counter.get(rating, 0) / total), 4) if total else 0.0,
            }
            for rating in ALL_SATISFACTION_RATINGS
        }

    def summarize_reasons(
        self,
        features: list[str],
        reasons_records: list[dict[str, Any]],
    ) -> dict[str, dict[str, str]]:
        def summarize_one(feature: str) -> tuple[str, dict[str, str]]:
            rows = [row for row in reasons_records if row.get("Feature") == feature]
            return feature, {
                "functional_viewpoint": self._summarize_reason_group(
                    [
                        str(row.get("Functional_Reason", "")).strip()
                        for row in rows
                        if str(row.get("Functional_Reason", "")).strip()
                    ]
                ),
                "dysfunctional_viewpoint": self._summarize_reason_group(
                    [
                        str(row.get("Dysfunctional_Reason", "")).strip()
                        for row in rows
                        if str(row.get("Dysfunctional_Reason", "")).strip()
                    ]
                ),
            }

        summaries: dict[str, dict[str, str]] = {}
        for feature, summary in _parallel_map(features, summarize_one):
            summaries[feature] = summary
        return summaries

    def _summarize_reason_group(self, reasons: list[str]) -> str:
        if not reasons:
            return ""

        prompt = self._prompts["reasons_sum.txt"]
        prompt = prompt.replace("{Reasons Replacement Flag}", " || ".join(reasons))
        prompt = prompt.replace("{User Reasons}", " || ".join(reasons))
        try:
            summary_obj = self._ask_json(prompt)
        except Exception:
            return " ".join(reasons[:2])

        if summary_obj.get("Viewpoint"):
            return str(summary_obj["Viewpoint"]).strip()

        for value in summary_obj.values():
            if isinstance(value, str) and value.strip():
                return value.strip()
        return " ".join(reasons[:2])

    def _explain(
        self,
        feature: str,
        category: str,
        counter: Counter,
        better_worse: dict[str, Any],
        reason_summary: dict[str, str],
    ) -> str:
        category_name = CATEGORY_NAMES.get(category, category)
        functional_viewpoint = reason_summary.get("functional_viewpoint", "")
        dysfunctional_viewpoint = reason_summary.get("dysfunctional_viewpoint", "")
        if functional_viewpoint and dysfunctional_viewpoint:
            return (
                f"Users valued its presence because {functional_viewpoint} "
                f"When absent, users felt {dysfunctional_viewpoint}"
            )
        if functional_viewpoint:
            return f"Users valued its presence because {functional_viewpoint}"
        if dysfunctional_viewpoint:
            return f"When absent, users felt {dysfunctional_viewpoint}"
        return f"User reasons did not provide a clear explanation for this {category_name} result."

    def analyze(self, requirement_text: str, feature_tree: str | dict[str, Any]) -> dict[str, Any]:
        if not requirement_text or not str(requirement_text).strip():
            raise ValueError("requirement_text is required and cannot be empty.")

        features = self.extract_features(feature_tree)
        users = self.build_participants(requirement_text)
        users = self.enrich_preferences(requirement_text, users)
        satisfaction_scores = self.score_satisfaction(requirement_text, users, features)
        _majority_categories, votes_per_feature, user_kano_categories, reasons_records = self.classify(
            features, satisfaction_scores
        )
        better_worse_rows = self.better_worse_rows(votes_per_feature)
        better_worse_by_feature = {row["Feature"]: row for row in better_worse_rows}
        satisfaction_distributions = self.satisfaction_distributions(features, reasons_records)
        reason_summaries = self.summarize_reasons(features, reasons_records)

        results = []
        for feature in features:
            bw_row = better_worse_by_feature.get(feature, {})
            category = str(bw_row.get("Kano_Category", "I"))
            counter = votes_per_feature.get(feature, Counter())
            reason_summary = reason_summaries.get(feature, {})
            results.append(
                {
                    "feature": feature,
                    "kano_category": category,
                    "kano_category_name": CATEGORY_NAMES.get(category, category),
                    "distribution": self._distribution(counter),
                    "satisfaction_distribution": satisfaction_distributions.get(
                        feature,
                        {
                            "functional": self._rating_distribution(Counter()),
                            "dysfunctional": self._rating_distribution(Counter()),
                        },
                    ),
                    "reason_summary": reason_summary,
                    "better_worse": {
                        "A": int(bw_row.get("A", 0)),
                        "O": int(bw_row.get("O", 0)),
                        "M": int(bw_row.get("M", 0)),
                        "I": int(bw_row.get("I", 0)),
                        "Better": float(bw_row.get("Better", 0.0)),
                        "Worse": float(bw_row.get("Worse", 0.0)),
                        "WorseAbs": float(bw_row.get("WorseAbs", 0.0)),
                        "Quadrant": str(bw_row.get("Quadrant", "Indifferent")),
                    },
                    "explanation": self._explain(feature, category, counter, bw_row, reason_summary),
                }
            )

        return {
            "requirement": requirement_text,
            "participant_count": FIXED_PARTICIPANT_COUNT,
            "fixed_distribution": FIXED_DISTRIBUTION,
            "features": features,
            "results": results,
            "better_worse": better_worse_rows,
            "satisfaction_distributions": satisfaction_distributions,
            "reason_summaries": reason_summaries,
            "participants": users,
            "user_satisfaction": satisfaction_scores,
            "user_kano_categories": user_kano_categories,
            "reason_records": reasons_records,
        }

    def analyze_json(self, requirement_text: str, feature_tree: str | dict[str, Any]) -> str:
        return json.dumps(
            self.analyze(requirement_text=requirement_text, feature_tree=feature_tree),
            ensure_ascii=False,
            indent=2,
        )


def analyze_kano(
    requirement_text: str,
    feature_tree: str | dict[str, Any],
    config_path: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    return KanoSkill(config_path=config_path, api_key=api_key).analyze(
        requirement_text=requirement_text,
        feature_tree=feature_tree,
    )


def analyze_kano_json(
    requirement_text: str,
    feature_tree: str | dict[str, Any],
    config_path: str | None = None,
    api_key: str | None = None,
) -> str:
    return KanoSkill(config_path=config_path, api_key=api_key).analyze_json(
        requirement_text=requirement_text,
        feature_tree=feature_tree,
    )
