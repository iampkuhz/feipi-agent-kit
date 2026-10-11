"""单进程计时与结构化脚本回执；不修正或掩盖异常读数。"""

from __future__ import annotations

import json
import time
from pathlib import Path


class RunClock:
    def __init__(self):
        self.start_ns = time.monotonic_ns()
        self.render_ns = 0

    def timings(self):
        total_ns = time.monotonic_ns() - self.start_ns
        static_ns = total_ns - self.render_ns
        if total_ns < 0 or self.render_ns < 0 or static_ns < 0:
            raise ValueError("timing_observation_invalid: 单进程计时出现负区间")
        return {
            "total_ms": round(total_ns / 1_000_000, 3),
            "render_ms": round(self.render_ns / 1_000_000, 3),
            "static_validation_ms": round(static_ns / 1_000_000, 3),
        }


def receipt_fields(output):
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
