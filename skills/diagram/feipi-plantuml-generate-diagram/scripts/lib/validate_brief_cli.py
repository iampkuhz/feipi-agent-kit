#!/usr/bin/env python3
"""CLI wrapper for brief validation from shell scripts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.brief_loader import validate_brief_file
from lib.profile_validators import validate_profile_semantics


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a brief YAML file")
    parser.add_argument("brief", help="brief YAML file path")
    parser.add_argument("--schema", required=True, help="schema JSON file path")
    parser.add_argument("--type", dest="diagram_type", help="执行对应 profile 的语义校验")
    args = parser.parse_args()

    success, errors, warnings, data = validate_brief_file(args.brief, args.schema)

    if success and args.diagram_type:
        semantic_errors, semantic_warnings = validate_profile_semantics(
            args.diagram_type, data, Path(args.brief).expanduser().resolve()
        )
        errors.extend(semantic_errors)
        warnings.extend(semantic_warnings)
        success = not errors

    for w in warnings:
        print(f"[警告] {w}", file=sys.stderr)
    if not success:
        for e in errors:
            print(f"[错误] {e}", file=sys.stderr)
        return 1

    print("brief_check=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
