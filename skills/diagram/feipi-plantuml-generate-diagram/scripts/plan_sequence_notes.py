#!/usr/bin/env python3
"""直接读取一个或多个 sequence brief，批量规划消息内的 note。"""

import argparse
import json
from pathlib import Path
import sys

from lib.brief_loader import validate_brief_file
from lib.profile_validators import validate_profile_semantics
from lib.sequence_notes import plan_brief


def plan_files(paths):
    schema = Path(__file__).resolve().parents[1] / "assets/validation/types/sequence-brief.schema.json"
    diagrams = []
    for path in paths:
        success, errors, _, brief = validate_brief_file(str(path), str(schema))
        if success:
            errors, _ = validate_profile_semantics("sequence", brief, path)
        if errors:
            raise ValueError(f"{path}: " + "; ".join(errors))
        planned = plan_brief(brief)
        # 不同 brief 可以沿用同一个 diagram_id，以源文件路径区分。
        planned["brief"] = str(path.resolve())
        diagrams.append(planned)
    return {"unit": "display_columns", "visual_review": "pending", "diagrams": diagrams}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, nargs="+", type=Path, help="原始 sequence brief YAML，可一次传多个")
    parser.add_argument("--output", type=Path, help="规划 JSON；省略时输出至 stdout")
    args = parser.parse_args()
    try:
        if args.output and args.output.resolve() in {p.resolve() for p in args.brief}:
            raise ValueError("output 不能覆盖输入 brief")
        result = plan_files(args.brief)
        content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
    except (ValueError, OSError) as exc:
        print(f"note 排版失败：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
