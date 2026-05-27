from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from .core import Gherkin2Code, Gherkin2CodePipeline, write_code_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gherkin2code-skill",
        description="Generate HTML, CSS, and JavaScript from user requirements and Gherkin acceptance criteria.",
    )
    parser.add_argument(
        "--requirement-input",
        default="examples/user_requirement.txt",
        help="Path to the user requirement text file.",
    )
    parser.add_argument(
        "--requirement-text",
        default=None,
        help="User requirement text. When provided, --requirement-input is ignored.",
    )
    parser.add_argument(
        "--acceptance-input",
        default="examples/acceptance_criteria.json",
        help="Path to the acceptance criteria JSON file.",
    )
    parser.add_argument(
        "--acceptance-text",
        default=None,
        help="Acceptance criteria JSON/text. When provided, --acceptance-input is ignored.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory where index.html, script.js, and style.css are written.",
    )
    parser.add_argument("-c", "--config", default=None, help="Optional config JSON path.")
    parser.add_argument("--api-key", default=None, help="OpenAI API key. Defaults to OPENAI_API_KEY.")
    parser.add_argument("--json-only", action="store_true", help="Print only the generated code JSON.")
    return parser


def _print_section(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def print_result(result: dict[str, Any], json_only: bool = False) -> None:
    if json_only:
        print(json.dumps(result["codes"], ensure_ascii=False, indent=2))
        return

    _print_section("User Requirement", result["user_requirement"])
    _print_section("Acceptance Criteria", result["acceptance_criteria"])
    _print_section("Codes", result["codes"])


async def _run_file(args: argparse.Namespace) -> int:
    pipeline = Gherkin2CodePipeline(
        requirement_path=args.requirement_input,
        acceptance_path=args.acceptance_input,
        output_dir=args.output_dir,
        config_path=args.config,
        api_key=args.api_key,
    )
    result = await pipeline.run()
    print_result(result, json_only=args.json_only)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.requirement_text is not None or args.acceptance_text is not None:
        if args.requirement_text is None or args.acceptance_text is None:
            parser.error("--requirement-text and --acceptance-text must be provided together.")

        generator = Gherkin2Code(config_path=args.config, api_key=args.api_key)
        codes = generator.generate(args.requirement_text, args.acceptance_text)
        written_files = write_code_files(codes, output_dir=args.output_dir)
        print_result(
            {
                "user_requirement": args.requirement_text,
                "acceptance_criteria": args.acceptance_text,
                "codes": codes,
                "written_files": written_files,
            },
            json_only=args.json_only,
        )
        return 0

    return asyncio.run(_run_file(args))


if __name__ == "__main__":
    sys.exit(main())
