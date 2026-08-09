#!/usr/bin/env python3
"""输出实际 PlantUML 图面的 node/edge/max_degree 指标。"""

from __future__ import annotations

import argparse
from pathlib import Path

from puml_analysis import compute_puml_metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True)
    parser.add_argument("diagram")
    args = parser.parse_args()
    path = Path(args.diagram)
    if not path.is_file():
        raise SystemExit(f"diagram 文件不存在：{path}")
    metrics = compute_puml_metrics(args.type, path.read_text(encoding="utf-8"))
    print("\t".join(str(metrics[key]) for key in ("node_count", "edge_count", "max_degree")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
