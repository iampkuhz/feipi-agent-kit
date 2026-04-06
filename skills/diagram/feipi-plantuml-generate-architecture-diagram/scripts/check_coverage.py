#!/usr/bin/env python3
"""检查 brief 与 PlantUML 架构图的覆盖关系。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ENTITY_RE = re.compile(
    r'^\s*(actor|component|database|queue|cloud|interface)\s+"([^"]+)"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b'
)


def load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except ModuleNotFoundError:
        cmd = [
            "ruby",
            "-e",
            (
                "require 'yaml'; require 'json'; "
                "data = YAML.safe_load(File.read(ARGV[0]), aliases: false); "
                "puts JSON.generate(data)"
            ),
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Ruby 解析 YAML 失败")
        return json.loads(result.stdout)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\\n", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 brief 与 PlantUML 覆盖关系")
    parser.add_argument("--brief", required=True, help="brief YAML 文件")
    parser.add_argument("--diagram", required=True, help="PlantUML 文件")
    args = parser.parse_args()

    brief_path = Path(args.brief).expanduser().resolve()
    diagram_path = Path(args.diagram).expanduser().resolve()
    if not brief_path.is_file():
        print(f"brief 文件不存在: {brief_path}", file=sys.stderr)
        return 1
    if not diagram_path.is_file():
        print(f"diagram 文件不存在: {diagram_path}", file=sys.stderr)
        return 1

    try:
        brief = load_yaml(brief_path)
    except Exception as exc:  # noqa: BLE001
        print(f"brief 解析失败: {exc}", file=sys.stderr)
        return 1

    if not isinstance(brief, dict):
        print("brief 根节点必须是对象", file=sys.stderr)
        return 1

    raw_text = diagram_path.read_text(encoding="utf-8")
    normalized_text = normalize_text(raw_text)
    errors: list[str] = []

    if "@startuml" not in raw_text or "@enduml" not in raw_text:
        errors.append("diagram 缺少 @startuml 或 @enduml")

    alias_to_name: dict[str, str] = {}
    for line in raw_text.splitlines():
        match = ENTITY_RE.match(line)
        if match:
            alias_to_name[match.group(3)] = match.group(2)

    expected_components = brief.get("components", [])
    expected_layers = brief.get("layers", [])
    expected_flows = brief.get("flows", [])

    component_ids = {item.get("id") for item in expected_components if isinstance(item, dict)}

    for index, layer in enumerate(expected_layers):
        if not isinstance(layer, dict):
            continue
        layer_name = layer.get("name")
        if isinstance(layer_name, str) and layer_name not in raw_text:
            errors.append(f"layers[{index}].name 未落图: {layer_name}")

    for index, component in enumerate(expected_components):
        if not isinstance(component, dict):
            continue
        comp_id = component.get("id")
        comp_name = component.get("name")
        if isinstance(comp_id, str) and comp_id not in alias_to_name:
            errors.append(f"components[{index}].id 未以 alias 落图: {comp_id}")
        if isinstance(comp_id, str) and isinstance(comp_name, str):
            diagram_name = alias_to_name.get(comp_id)
            if diagram_name and normalize_text(diagram_name) != normalize_text(comp_name):
                errors.append(f"components[{index}] 展示名与 brief 不一致: {comp_name}")
            if normalize_text(comp_name) not in normalized_text:
                errors.append(f"components[{index}].name 未落图: {comp_name}")

    extra_aliases = sorted(alias for alias in alias_to_name if alias not in component_ids)
    if extra_aliases:
        errors.append(f"存在 brief 未定义的额外组件 alias: {extra_aliases}")

    lines = raw_text.splitlines()
    for index, flow in enumerate(expected_flows):
        if not isinstance(flow, dict):
            continue
        flow_id = flow.get("id")
        from_id = flow.get("from")
        to_id = flow.get("to")
        description = flow.get("description")

        matched_line = False
        if all(isinstance(value, str) for value in (flow_id, from_id, to_id)):
            for line in lines:
                if from_id in line and to_id in line and flow_id in line:
                    matched_line = True
                    break
        if not matched_line:
            errors.append(f"flows[{index}] 未找到包含 from/to/id 的连线: {flow_id}")

        if isinstance(flow_id, str) and flow_id not in raw_text:
            errors.append(f"flows[{index}].id 未落图: {flow_id}")
        if isinstance(description, str) and normalize_text(description) not in normalized_text:
            errors.append(f"flows[{index}].description 未落图: {description}")

    if errors:
        for error in errors:
            print(f"[错误] {error}", file=sys.stderr)
        return 1

    print("coverage_check=ok")
    print(f"coverage_components={len(expected_components)}")
    print(f"coverage_flows={len(expected_flows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
