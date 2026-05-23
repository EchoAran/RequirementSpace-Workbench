from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import KanoSkill


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kano-skill",
        description="Run fixed-demographic Kano analysis from a requirement and feature tree.",
    )
    parser.add_argument(
        "--requirement-input",
        default="examples/requirement.txt",
        help="Path to a text file containing the initial requirement.",
    )
    parser.add_argument(
        "--requirement-text",
        default=None,
        help="Initial requirement text. When provided, --requirement-input is ignored.",
    )
    parser.add_argument(
        "--feature-tree-input",
        default="examples/feature_tree.json",
        help="Path to a feature tree JSON file.",
    )
    parser.add_argument(
        "--feature-tree-text",
        default=None,
        help="Feature tree JSON text. When provided, --feature-tree-input is ignored.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Optional config JSON path. Uses bundled defaults when omitted.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key. Defaults to OPENAI_API_KEY.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the full result JSON object.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory where JSON output files are written.",
    )
    return parser


def _resolve_input_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute() or path.exists():
        return path

    project_path = PROJECT_ROOT / path
    if project_path.exists():
        return project_path

    return path


def _resolve_output_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _read_requirement(args: argparse.Namespace) -> str:
    if args.requirement_text is not None:
        return args.requirement_text
    return _resolve_input_path(args.requirement_input).read_text(encoding="utf-8").strip()


def _read_feature_tree(args: argparse.Namespace) -> str:
    if args.feature_tree_text is not None:
        return args.feature_tree_text
    return _resolve_input_path(args.feature_tree_input).read_text(encoding="utf-8")


def _print_section(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def print_result(result: dict[str, Any], json_only: bool = False) -> None:
    printable = result.get("feature_satisfaction_reasons", [])
    if json_only:
        print(json.dumps(printable, ensure_ascii=False, indent=2))
        return

    _print_section("Feature Satisfaction Reasons", printable)


def write_outputs(result: dict[str, Any], output_dir: str) -> dict[str, str]:
    out_dir = _resolve_output_path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    feature_details = [
        {
            "Feature": row.get("feature", ""),
            "Kano_Category": row.get("kano_category", ""),
            "Kano_Category_Name": row.get("kano_category_name", ""),
            "satisfaction_distribution": row.get("satisfaction_distribution", {}),
            "reason_summary": row.get("reason_summary", {}),
            "explanation": row.get("explanation", ""),
        }
        for row in result.get("results", [])
    ]
    result["feature_satisfaction_reasons"] = feature_details

    files = {
        "feature_satisfaction_reasons.json": feature_details,
    }

    written: dict[str, str] = {}
    for filename, payload in files.items():
        path = out_dir / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written[filename] = str(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        requirement_text = _read_requirement(args)
        feature_tree = _read_feature_tree(args)
        analyzer = KanoSkill(config_path=args.config, api_key=args.api_key)
        result = analyzer.analyze(requirement_text=requirement_text, feature_tree=feature_tree)
        written_files = write_outputs(result, args.output_dir)
        result["output_files"] = written_files
        print_result(result, json_only=args.json_only)
        return 0
    except Exception as exc:
        print(f"kano-skill failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
