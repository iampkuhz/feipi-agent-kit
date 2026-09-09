#!/usr/bin/env python3
"""从已验证 brief 确定性生成 mindmap 源码；图包验证仍走统一入口。"""

import argparse
from pathlib import Path
import sys

from lib.brief_loader import validate_brief_file
from lib.mindmap import ordered_tree, validate_mindmap

SKILL_DIR = Path(__file__).resolve().parent.parent


def generate(data: dict) -> str:
    style = (SKILL_DIR / "assets/templates/types/mindmap-style.puml").read_text(encoding="utf-8").rstrip()
    lines = ["@startmindmap", style, f"title {data['title']}", ""]
    colors = ("#DBEAFE", "#D1FAE5", "#FEF3C7", "#EDE9FE", "#FFE4E6", "#CFFAFE")
    branch_index, color = -1, "#E2E8F0"
    for node, depth, side in ordered_tree(data):
        if depth == 2:
            branch_index += 1
            color = colors[branch_index % len(colors)]
        marks = ("-" if side == "left" else "+") * depth
        label = node["label"].strip().replace("\n", r"\n")
        lines.append(f"{marks}[{color}] {label}")
    return "\n".join(lines + ["@endmindmap", ""])


def main() -> int:
    parser = argparse.ArgumentParser(description="生成合法且样式一致的 PlantUML 思维导图源码")
    parser.add_argument("--brief", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    ok, errors, _, data = validate_brief_file(
        args.brief, str(SKILL_DIR / "assets/validation/types/mindmap-brief.schema.json")
    )
    if ok:
        errors.extend(validate_mindmap(data))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    output = Path(args.out)
    if output.resolve() == Path(args.brief).resolve():
        print("输出路径不得覆盖输入 brief", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate(data), encoding="utf-8")
    print(f"diagram={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
