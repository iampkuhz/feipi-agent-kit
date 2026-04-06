#!/usr/bin/env python3
"""校验 architecture-brief YAML。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


TYPE_NAMES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
}


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


def validate_schema(instance: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    expected_type = schema.get("type")
    if expected_type:
        py_type = TYPE_NAMES.get(expected_type)
        if py_type is not None and not isinstance(instance, py_type):
            errors.append(f"{path or 'root'} 类型错误，期望 {expected_type}")
            return

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path_dot(path, key)} 缺少必填字段")

        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key not in properties:
                if schema.get("additionalProperties") is False:
                    errors.append(f"{path_dot(path, key)} 不允许出现额外字段")
                continue
            validate_schema(value, properties[key], path_dot(path, key), errors)
        return

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path or 'root'} 至少需要 {min_items} 项")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(instance):
                validate_schema(item, item_schema, f"{path}[{index}]", errors)
        return

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        pattern = schema.get("pattern")
        enum = schema.get("enum")

        if min_length is not None and len(instance) < min_length:
            errors.append(f"{path} 长度不能少于 {min_length}")
        if max_length is not None and len(instance) > max_length:
            errors.append(f"{path} 长度不能超过 {max_length}")
        if pattern and re.match(pattern, instance) is None:
            errors.append(f"{path} 格式不匹配: {pattern}")
        if enum and instance not in enum:
            errors.append(f"{path} 必须是 {enum} 之一")
        return


def path_dot(base: str, key: str) -> str:
    return f"{base}.{key}" if base else key


def ensure_unique(items: list[dict[str, Any]], field: str, prefix: str, errors: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for index, item in enumerate(items):
        value = item.get(field)
        if not isinstance(value, str):
            continue
        if value in seen:
            errors.append(f"{prefix}[{index}].{field} 重复: {value}")
        else:
            seen.add(value)
            ordered.append(value)
    return ordered


def validate_semantics(data: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    layers = data.get("layers", [])
    components = data.get("components", [])
    flows = data.get("flows", [])

    layer_ids = ensure_unique(layers, "id", "layers", errors)
    layer_names = ensure_unique(layers, "name", "layers", errors)
    component_ids = ensure_unique(components, "id", "components", errors)
    component_names = ensure_unique(components, "name", "components", errors)
    flow_ids = ensure_unique(flows, "id", "flows", errors)

    layer_id_set = set(layer_ids)
    component_id_set = set(component_ids)

    if len(set(layer_names)) != len(layer_names):
        errors.append("layers.name 必须唯一")
    if len(set(component_names)) != len(component_names):
        errors.append("components.name 必须唯一")

    colors = [item.get("color") for item in layers if isinstance(item.get("color"), str)]
    if len(colors) != len(set(colors)):
        warnings.append("存在重复层颜色，渲染时可读性可能下降")

    layer_component_count = {layer_id: 0 for layer_id in layer_ids}
    component_flow_count = {component_id: 0 for component_id in component_ids}

    for index, component in enumerate(components):
        layer = component.get("layer")
        if layer not in layer_id_set:
            errors.append(f"components[{index}].layer 引用了未定义层: {layer}")
        else:
            layer_component_count[layer] += 1

    for layer_id, count in layer_component_count.items():
        if count == 0:
            errors.append(f"layer {layer_id} 没有承载任何组件")

    numeric_flow_ids: list[int] = []
    for index, flow in enumerate(flows):
        from_id = flow.get("from")
        to_id = flow.get("to")
        if from_id not in component_id_set:
            errors.append(f"flows[{index}].from 引用了未定义组件: {from_id}")
        else:
            component_flow_count[from_id] += 1
        if to_id not in component_id_set:
            errors.append(f"flows[{index}].to 引用了未定义组件: {to_id}")
        else:
            component_flow_count[to_id] += 1
        if from_id == to_id:
            warnings.append(f"flows[{index}] 是自环流程，确认是否真的需要")
        flow_id = flow.get("id")
        if isinstance(flow_id, str) and re.match(r"^S[1-9][0-9]*$", flow_id):
            numeric_flow_ids.append(int(flow_id[1:]))

    if numeric_flow_ids:
        expected = list(range(1, len(numeric_flow_ids) + 1))
        actual = sorted(numeric_flow_ids)
        if actual != expected:
            warnings.append(f"流程编号建议连续，从 S1 开始，当前为 {actual}")

    for component_id, count in component_flow_count.items():
        if count == 0:
            warnings.append(f"组件 {component_id} 未出现在任何流程中")

    out_of_scope = data.get("out_of_scope", [])
    if isinstance(out_of_scope, list):
        normalized_components = {normalize_text(name): name for name in component_names}
        for index, item in enumerate(out_of_scope):
            if not isinstance(item, str):
                continue
            if normalize_text(item) in normalized_components:
                warnings.append(
                    f"out_of_scope[{index}] 与组件名 {normalized_components[normalize_text(item)]} 重复，请确认边界定义"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 architecture-brief YAML")
    parser.add_argument("brief", help="brief YAML 文件路径")
    parser.add_argument(
        "--schema",
        default=None,
        help="schema JSON 路径，默认使用 skill 内置 schema",
    )
    args = parser.parse_args()

    brief_path = Path(args.brief).expanduser().resolve()
    if not brief_path.is_file():
        print(f"brief 文件不存在: {brief_path}", file=sys.stderr)
        return 1

    script_dir = Path(__file__).resolve().parent
    default_schema = script_dir.parent / "assets" / "validation" / "architecture-brief.schema.json"
    schema_path = Path(args.schema).expanduser().resolve() if args.schema else default_schema
    if not schema_path.is_file():
        print(f"schema 文件不存在: {schema_path}", file=sys.stderr)
        return 1

    try:
        data = load_yaml(brief_path)
    except Exception as exc:  # noqa: BLE001
        print(f"brief 解析失败: {exc}", file=sys.stderr)
        return 1

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"schema 解析失败: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print("brief 根节点必须是对象", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    validate_schema(data, schema, "", errors)
    if not errors:
        validate_semantics(data, errors, warnings)

    for warning in warnings:
        print(f"[警告] {warning}", file=sys.stderr)

    if errors:
        for error in errors:
            print(f"[错误] {error}", file=sys.stderr)
        return 1

    print(f"brief_check=ok")
    print(f"brief_file={brief_path}")
    print(f"brief_warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
