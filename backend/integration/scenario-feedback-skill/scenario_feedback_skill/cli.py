from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .core import ScenarioFeedback, ScenarioFeedbackPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scenario-feedback-skill",
        description="Revise Gherkin JSON from user feedback and existing Gherkin content.",
    )
    parser.add_argument(
        "--feedback-input",
        default="examples/user_feedback.txt",
        help="Path to the user feedback text file.",
    )
    parser.add_argument(
        "--feedback-text",
        default=None,
        help="User feedback text. When provided, --feedback-input is ignored.",
    )
    parser.add_argument(
        "--gherkin-input",
        default="examples/gherkin.json",
        help="Path to the Gherkin content file.",
    )
    parser.add_argument(
        "--gherkin-text",
        default=None,
        help="Gherkin content text or JSON. When provided, --gherkin-input is ignored.",
    )
    parser.add_argument(
        "--feature",
        default=None,
        help="Selected feature name. Defaults to the Feature field in the Gherkin JSON when available.",
    )
    parser.add_argument(
        "--feature-file",
        default=None,
        help="Path to a text file containing the selected feature name.",
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
        help="Print only the revised Gherkin JSON object.",
    )
    return parser


def _resolve_feature(args: argparse.Namespace) -> str | None:
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
    if json_only:
        print(json.dumps(result["revised_gherkin"], ensure_ascii=False, indent=2))
        return

    _print_section("User Feedback", result["user_feedback"])
    _print_section("Original Gherkin", result["gherkin_content"])
    _print_section("Revised Gherkin", result["revised_gherkin"])


async def _run_file(args: argparse.Namespace) -> int:
    pipeline = ScenarioFeedbackPipeline(
        feedback_path=args.feedback_input,
        gherkin_path=args.gherkin_input,
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

    if args.feedback_text is not None or args.gherkin_text is not None:
        if args.feedback_text is None or args.gherkin_text is None:
            parser.error("--feedback-text and --gherkin-text must be provided together.")

        generator = ScenarioFeedback(config_path=args.config, api_key=args.api_key)
        revised = generator.revise(
            user_feedback=args.feedback_text,
            gherkin_content=args.gherkin_text,
            feature=feature,
        )
        print_result(
            {
                "user_feedback": args.feedback_text,
                "gherkin_content": args.gherkin_text,
                "revised_gherkin": revised,
            },
            json_only=args.json_only,
        )
        return 0

    return asyncio.run(_run_file(args))


if __name__ == "__main__":
    sys.exit(main())
