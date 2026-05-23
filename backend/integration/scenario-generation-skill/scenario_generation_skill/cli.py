from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .core import ScenarioGeneration, ScenarioPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scenario-generation-skill",
        description="Generate user story, system requirement, and Gherkin from NL context plus one feature.",
    )
    parser.add_argument(
        "-i",
        "--input",
        default="examples/raw_requirement.txt",
        help="Path to the requirement text file.",
    )
    parser.add_argument(
        "--text",
        default=None,
        help="Requirement text. When provided, --input is ignored.",
    )
    parser.add_argument(
        "--feature",
        default="Select Time Periods from Predefined Historical Eras",
        help="Single feature description to expand.",
    )
    parser.add_argument(
        "--feature-file",
        default=None,
        help="Path to a text file containing the single feature description.",
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
        help="Print only the final JSON object.",
    )
    return parser


def _resolve_feature(args: argparse.Namespace) -> str:
    if args.feature_file:
        return Path(args.feature_file).read_text(encoding="utf-8").strip()
    return args.feature


def _print_section(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def print_result(result: dict[str, Any], json_only: bool = False) -> None:
    final = {
        "story": result["story"],
        "system": result["system"],
        "gherkin": result["gherkin"],
    }

    if json_only:
        print(json.dumps(final, ensure_ascii=False, indent=2))
        return

    _print_section("User Story", result["story"])
    _print_section("System Requirement", result["system"])
    _print_section("Gherkin", result["gherkin"])
    _print_section("JSON Result", final)


async def _run_file(args: argparse.Namespace) -> int:
    pipeline = ScenarioPipeline(
        nl_path=args.input,
        feature=_resolve_feature(args),
        config_path=args.config,
        api_key=args.api_key,
    )
    result = await pipeline.run()
    print_result(result, json_only=args.json_only)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    feature = _resolve_feature(args)

    if args.text is not None:
        generator = ScenarioGeneration(config_path=args.config, api_key=args.api_key)
        result = generator.generate(requirement=args.text, feature=feature)
        print_result(result, json_only=args.json_only)
        return 0

    return asyncio.run(_run_file(args))


if __name__ == "__main__":
    sys.exit(main())
