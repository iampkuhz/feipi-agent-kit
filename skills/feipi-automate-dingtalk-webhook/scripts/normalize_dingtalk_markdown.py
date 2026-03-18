#!/usr/bin/env python3
"""删除钉钉不支持的 Markdown 语法，尽量保留纯文本内容。"""

from __future__ import annotations

import re
import sys


SEPARATOR_RE = re.compile(
    r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$"
)
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HORIZONTAL_RULE_RE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
HTML_TAG_RE = re.compile(r"</?[^>\n]+>")


def is_table_header(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return "|" in lines[index] and bool(SEPARATOR_RE.match(lines[index + 1]))


def normalize_markdown(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    i = 0

    while i < len(lines):
        if is_table_header(lines, i):
            i += 2
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                if not stripped:
                    break
                if "|" not in line or SEPARATOR_RE.match(line):
                    break
                i += 1
            continue

        line = lines[i]
        i += 1

        if FENCE_RE.match(line) or HORIZONTAL_RULE_RE.match(line):
            continue

        line = HTML_TAG_RE.sub("", line)
        output.append(line)

    while len(output) > 1 and output[-1] == "" and output[-2] == "":
        output.pop()

    return "\n".join(output)


def main() -> int:
    source = sys.stdin.read()
    sys.stdout.write(normalize_markdown(source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
