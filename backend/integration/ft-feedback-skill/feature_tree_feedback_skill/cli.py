from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .core import FeatureTreeFeedbackPipeline, revise_feature_tree


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feature-tree-feedback-skill",
        description="Revise feature tree JSON from user feedback.",
    )
    parser.add_argument(
        "-i",
        "--input",
        default="examples/feature_tree.json",
        help="Path to the original feature tree JSON or text file.",
    )
    parser.add_argument(
        "-f",
        "--feedback-input",
        default="examples/feedback.txt",
        help="Path to the user feedback txt file.",
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
        "--feature-tree",
        default=None,
        help="Original feature tree text. When provided with --feedback, JSON is printed to stdout.",
    )
    parser.add_argument(
        "--feedback",
        default=None,
        help="User feedback text. When provided with --feature-tree, JSON is printed to stdout.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key. Defaults to OPENAI_API_KEY.",
    )
    return parser


async def _run_file(args: argparse.Namespace) -> int:
    pipeline = FeatureTreeFeedbackPipeline(
        feature_tree_path=args.input,
        feedback_path=args.feedback_input,
        output_dir=args.output_dir,
        config_path=args.config,
        api_key=args.api_key,
    )
    result = await pipeline.run()
    print(f"Feature tree revised and written to {result['features_path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.feature_tree is not None or args.feedback is not None:
        if args.feature_tree is None or args.feedback is None:
            parser.error("--feature-tree and --feedback must be provided together.")
        print(
            revise_feature_tree(
                feature_tree=args.feature_tree,
                feedback=args.feedback,
                config_path=args.config,
                api_key=args.api_key,
            )
        )
        return 0

    return asyncio.run(_run_file(args))


if __name__ == "__main__":
    sys.exit(main())
