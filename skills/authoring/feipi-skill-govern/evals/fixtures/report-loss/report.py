#!/usr/bin/env python3
"""生成本地报告和通知。"""

import json
from pathlib import Path
import sys


def render(issues):
    names = sorted({item["skill"] for item in issues})
    report = "# 检查报告\n\n" + "\n".join("- " + name for name in names) + "\n"
    notification = "处理完成：" + "、".join(names) + "\n"
    return report, notification


def main():
    issues = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    report, notification = render(issues)
    (output / "report.md").write_text(report, encoding="utf-8")
    (output / "notification.txt").write_text(notification, encoding="utf-8")


if __name__ == "__main__":
    main()
