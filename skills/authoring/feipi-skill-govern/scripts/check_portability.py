#!/usr/bin/env python3
"""Detect fixed machine paths and common macOS/Linux shell portability traps."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", "coverage",
}
CODE_SUFFIXES = {".sh", ".bash", ".py", ".js", ".mjs", ".cjs", ".ts", ".pl", ".rb"}

# Catch concrete machine-specific locations, including temporary test outputs.
# Build the root names from pieces so this checker does not report its own rules.
ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9_])/(?:"
    r"Users|home|Applications|Library|opt|usr|tmp|private|var|etc|System|Volumes|"
    r"mnt|root|workspace|proc|run|dev"
    r")(?:/[^\s\"'`),;]+)?"
)
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s\"'`),;]+")
RIPGREP_COMMAND = re.compile(r"(?<![A-Za-z0-9_])rg\s+(?:-[A-Za-z]+\s+)*[^\s]" )


def code_files(skill_dir: Path):
    for current, directories, files in os.walk(skill_dir):
        directories[:] = [name for name in directories if name not in SKIP_DIRS]
        for name in files:
            path = Path(current) / name
            if path.suffix.lower() in CODE_SUFFIXES:
                yield path


def is_regex_example(value: str) -> bool:
    """Wildcard path fragments are search patterns, not usable filesystem paths."""
    return any(fragment in value for fragment in (".*", "[^", "\\", "(?:", "|"))


def scan_file(path: Path, skill_dir: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    problems = []
    lines = text.splitlines()
    relative = path.relative_to(skill_dir)

    for number, line in enumerate(lines, 1):
        path_line = re.sub(r"https?://[^\s\"'`]+", "", line)
        for match in ABSOLUTE_PATH.finditer(path_line):
            literal = match.group(0)
            context = path_line[max(0, match.start() - 20):match.start()]
            relative_prefix = path_line[match.start() - 1:match.start()] if match.start() else ""
            standard_path = literal in {"/usr/bin/env", "/dev/null", "/dev/stdin"}
            escaped_regex_delimiter = relative_prefix == "\\"
            if not is_regex_example(literal) and "${TMPDIR:-" not in context \
                    and relative_prefix != "." and not escaped_regex_delimiter and not standard_path:
                problems.append((number, f"固定机器/临时绝对路径：{literal}"))
        for match in WINDOWS_ABSOLUTE_PATH.finditer(path_line):
            literal = match.group(0)
            if not is_regex_example(literal):
                problems.append((number, f"Windows 盘符绝对路径：{literal}"))
        if relative.as_posix() != "scripts/check_portability.py" and RIPGREP_COMMAND.search(line):
            problems.append((number, "调用 ripgrep（rg）；安装与校验应使用基础工具或显式检查依赖"))

    if relative.suffix.lower() in {".sh", ".bash"}:
        checks = (
            (r"\b(?:mapfile|readarray)\b|\bdeclare\s+-A\b", "使用 Bash 4 专属语法，macOS 系统 Bash 3.2 不支持"),
            (r"\breadlink\s+-f\b", "readlink -f 不是 macOS/BSD 可移植选项"),
            (r"\bsed\s+-i(?:\s|$)", "sed -i 在 GNU/BSD 参数语法不同，需条件分支或改用临时文件"),
        )
        for pattern, message in checks:
            if re.search(pattern, text):
                problems.append((1, message))
        if re.search(r"\bstat\s+-c\b", text) and not re.search(r"\bstat\s+-f\b", text):
            problems.append((1, "stat -c 缺少 BSD/macOS stat -f 兼容分支"))
        if re.search(r"\bdate\s+-d\b", text) and not re.search(r"\bdate\s+-j\b", text):
            problems.append((1, "date -d 缺少 BSD/macOS date -j 兼容分支"))

    return [(relative.as_posix(), number, message) for number, message in problems]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path, help="需要审计的 skill 根目录")
    args = parser.parse_args()
    skill_dir = args.skill_dir.resolve()
    if not skill_dir.is_dir():
        print(f"不是目录：{skill_dir}", file=sys.stderr)
        return 2

    problems = [problem for path in code_files(skill_dir) for problem in scan_file(path, skill_dir)]
    if problems:
        print("跨平台/路径检查失败：")
        for path, number, message in problems:
            print(f"  {path}:{number}: {message}")
        return 1
    print(f"跨平台/路径检查通过：{skill_dir.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
