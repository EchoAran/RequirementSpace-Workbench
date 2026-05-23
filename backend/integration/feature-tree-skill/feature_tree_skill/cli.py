from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .core import FeaturesPipeline, generate_feature_tree


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feature-tree-skill",
        description="Generate a feature tree JSON document from a natural language requirement.",
    )
    parser.add_argument(
        "-i",
        "--input",
        default="examples/raw_requirement.txt",
        help="Path to the requirement text file.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="outputs",
        help="Directory where features.json will be written.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Optional config JSON path. Uses bundled defaults when omitted.",
    )
    parser.add_argument(
        "--req",
        default=None,
        help="Requirement text. When provided, --input is ignored and JSON is printed to stdout.",
    )
    parser.add_argument(
        "--role",
        default=None,
        help="Optional comma-separated role names or path to an actor txt file.",
    )
    parser.add_argument(
        "--actors",
        default=None,
        help="Optional path to an actor txt file.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key. Defaults to OPENAI_API_KEY.",
    )
    return parser


def _role_value(role: str | None) -> str | None:
    if role is None:
        return None

    path = Path(role)
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass

    return role


async def _run_file(args: argparse.Namespace) -> int:
    pipeline = FeaturesPipeline(
        nl_path=args.input,
        actors_path=args.actors if args.role is None else None,
        actors_text=_role_value(args.role),
        output_dir=args.output_dir,
        config_path=args.config,
        api_key=args.api_key,
    )
    result = await pipeline.run()
    print(f"Features generated and written to {result['features_path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    actors = _role_value(args.role)
    if actors is None and args.actors:
        actors = Path(args.actors).read_text(encoding="utf-8")

    if args.req is not None:
        print(
            generate_feature_tree(
                requirement=args.req,
                actors=actors,
                config_path=args.config,
                api_key=args.api_key,
            )
        )
        return 0

    return asyncio.run(_run_file(args))


if __name__ == "__main__":
    sys.exit(main())
