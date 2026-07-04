from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from .core import SplSemanticExportSkill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spl-semantic-export-skill",
        description="LLM-backed semantic compiler export to SPL.",
    )
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to a JSON file containing the RequirementSpace snapshot payload.",
    )
    parser.add_argument(
        "--output-file",
        help="Path to save the generated .spl output file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        input_path = Path(args.input_json)
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        
        skill = SplSemanticExportSkill()
        result = skill.export(payload)
        
        if args.output_file:
            out_path = Path(args.output_file)
            out_path.write_text(result["spl_text"], encoding="utf-8")
            print(f"Exported SPL semantic to {out_path}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"spl-semantic-export-skill failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
