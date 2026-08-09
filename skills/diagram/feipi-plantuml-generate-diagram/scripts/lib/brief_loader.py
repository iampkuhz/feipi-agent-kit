#!/usr/bin/env python3
"""Brief 加载与 schema 校验。"""

from __future__ import annotations

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
            "ruby", "-e",
            "require 'yaml'; require 'json'; "
            "data = YAML.safe_load(File.read(ARGV[0]), aliases: false); "
            "puts JSON.generate(data)",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Ruby 解析 YAML 失败")
        return json.loads(result.stdout)


def validate_schema(instance: Any, schema: dict, path: str, errors: list[str]) -> None:
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
                errors.append(f"{_path_dot(path, key)} 缺少必填字段")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key not in properties:
                if schema.get("additionalProperties") is False:
                    errors.append(f"{_path_dot(path, key)} 不允许出现额外字段")
                continue
            validate_schema(value, properties[key], _path_dot(path, key), errors)
        return

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path or 'root'} 至少需要 {min_items} 项")
        if max_items is not None and len(instance) > max_items:
            errors.append(f"{path or 'root'} 最多允许 {max_items} 项")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(instance):
                validate_schema(item, item_schema, f"{path}[{index}]", errors)
        return

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        pattern = schema.get("pattern")
        enum_val = schema.get("enum")
        if min_length is not None and len(instance) < min_length:
            errors.append(f"{path} 长度不能少于 {min_length}")
        if max_length is not None and len(instance) > max_length:
            errors.append(f"{path} 长度不能超过 {max_length}")
        if pattern and re.match(pattern, instance) is None:
            errors.append(f"{path} 格式不匹配：{pattern}")
        if enum_val and instance not in enum_val:
            errors.append(f"{path} 必须是 {enum_val} 之一")


def _path_dot(base: str, key: str) -> str:
    return f"{base}.{key}" if base else key


def ensure_unique(items: list[dict], field: str, prefix: str, errors: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for index, item in enumerate(items):
        value = item.get(field)
        if not isinstance(value, str):
            continue
        if value in seen:
            errors.append(f"{prefix}[{index}].{field} 重复：{value}")
        else:
            seen.add(value)
            ordered.append(value)
    return ordered


def validate_brief_file(brief_path: str, schema_path: str) -> tuple[bool, list[str], list[str], Any]:
    """校验 brief YAML。返回 (success, errors, warnings, data)。"""
    brief_p = Path(brief_path).expanduser().resolve()
    schema_p = Path(schema_path).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not brief_p.is_file():
        return False, [f"brief 文件不存在：{brief_p}"], [], None
    if not schema_p.is_file():
        return False, [f"schema 文件不存在：{schema_p}"], [], None

    try:
        data = load_yaml(brief_p)
    except Exception as exc:
        return False, [f"brief 解析失败：{exc}"], [], None

    try:
        schema = json.loads(schema_p.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"schema 解析失败：{exc}"], [], None

    if not isinstance(data, dict):
        return False, ["brief 根节点必须是对象"], [], None

    validate_schema(data, schema, "", errors)
    if errors:
        return False, errors, warnings, data

    return True, errors, warnings, data
