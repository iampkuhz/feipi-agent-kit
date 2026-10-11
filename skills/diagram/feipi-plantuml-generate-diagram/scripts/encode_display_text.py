#!/usr/bin/env python3
"""仅编码输入显示文本，不解析或改写 PlantUML 源码。"""

from __future__ import annotations

import argparse
import sys

from lib.text_codec import encode_display_text


def main() -> int:
    parser = argparse.ArgumentParser(description="编码 PlantUML 显示文本中的字面标点")
    parser.add_argument("--text", help="单段原始显示文本；省略时从 stdin 读取")
    args = parser.parse_args()
    text = args.text if args.text is not None else sys.stdin.read()
    try:
        sys.stdout.write(encode_display_text(text))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
