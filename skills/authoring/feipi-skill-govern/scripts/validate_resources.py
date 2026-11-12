#!/usr/bin/env python3
"""校验源码维护资料和运行资源的边界，不加载第三方依赖。"""

import argparse
import os
from pathlib import Path
import re


DEVELOPMENT = {"maintenance", "tests", "evals", "node_modules", ".git", "__pycache__"}
MAINTENANCE_REF = re.compile(r"(?<![A-Za-z0-9_-])maintenance[/\\][^\s`'\"<>)]*")
TARGET_PREFIX = re.compile(r"(?:<target_skill>|\$(?:TARGET_DIR|ROOT_DIR)|\$\{(?:TARGET_DIR|ROOT_DIR)\})[/\\]$")


def validate_resources(skill, require_maintenance=False):
    maintenance = skill / "maintenance"
    if require_maintenance or maintenance.exists():
        for name in ("README.md", "terminology.md"):
            path = maintenance / name
            if not path.is_file() or not path.read_text(encoding="utf-8").strip():
                raise ValueError(f"缺少非空源码维护资料：{path}")

    for directory, dirs, files in os.walk(skill):
        for name in dirs + files:
            path = Path(directory) / name
            if name not in DEVELOPMENT and path.is_symlink() and "maintenance" in path.resolve().parts:
                raise ValueError(f"运行内容引用源码维护目录：{path} (资源链接)")
        dirs[:] = [name for name in dirs if name not in DEVELOPMENT]
        for name in files:
            path = Path(directory) / name
            if path.name == "package-lock.json":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in MAINTENANCE_REF.finditer(text):
                if skill.name == "feipi-skill-govern":
                    # 治理规则可说明目录本身、读取目标源码；不得依赖自身被排除的文件。
                    if match.group().rstrip("/\\") == "maintenance":
                        continue
                    if TARGET_PREFIX.search(text[:match.start()]):
                        continue
                    if path.relative_to(skill).parts[0] == "templates" \
                            and text[:match.start()].endswith("$SKILL_DIR/"):
                        continue
                line = text.count("\n", 0, match.start()) + 1
                raise ValueError(f"运行内容引用源码维护目录：{path}:{line} ({match.group()})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", type=Path)
    parser.add_argument("--require-maintenance", action="store_true")
    args = parser.parse_args()
    try:
        validate_resources(args.skill, args.require_maintenance)
    except (OSError, ValueError) as error:
        parser.exit(1, f"[FAIL] {error}\n")
    print("[PASS] 源码维护资料与运行资源边界通过")


if __name__ == "__main__":
    main()
