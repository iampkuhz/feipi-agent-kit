#!/usr/bin/env python3
"""校验 sequence-brief YAML。"""

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
            errors.append(f"{path} 格式不匹配：{pattern}")
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
            errors.append(f"{prefix}[{index}].{field} 重复：{value}")
        else:
            seen.add(value)
            ordered.append(value)
    return ordered


def validate_semantics(data: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    participants = data.get("participants", [])
    messages = data.get("messages", [])
    groups = data.get("groups", [])

    participant_ids = ensure_unique(participants, "id", "participants", errors)
    participant_names = ensure_unique(participants, "name", "participants", errors)

    participant_id_set = set(participant_ids)

    if len(set(participant_names)) != len(participant_names):
        errors.append("participants.name 必须唯一")

    numeric_message_ids: list[int] = []
    return_message_ids: list[int] = []

    for index, message in enumerate(messages):
        from_id = message.get("from")
        to_id = message.get("to")
        msg_id = message.get("id")
        msg_type = message.get("type")

        if from_id not in participant_id_set:
            errors.append(f"messages[{index}].from 引用了未定义参与者：{from_id}")

        if to_id not in participant_id_set:
            errors.append(f"messages[{index}].to 引用了未定义参与者：{to_id}")

        if from_id == to_id:
            warnings.append(f"messages[{index}] 是自环消息，确认是否真的需要")

        if isinstance(msg_id, str):
            if re.match(r"^M[1-9][0-9]*$", msg_id):
                numeric_message_ids.append(int(msg_id[1:]))
            elif re.match(r"^R[1-9][0-9]*$", msg_id):
                return_message_ids.append(int(msg_id[1:]))

    if numeric_message_ids:
        expected = list(range(1, len(numeric_message_ids) + 1))
        actual = sorted(numeric_message_ids)
        if actual != expected:
            warnings.append(f"消息编号建议连续，从 M1 开始，当前为 {actual}")

    if return_message_ids:
        expected = list(range(1, len(return_message_ids) + 1))
        actual = sorted(return_message_ids)
        if actual != expected:
            warnings.append(f"返回消息编号建议连续，从 R1 开始，当前为 {actual}")

    # Validate groups (optional field)
    if groups:
        group_ids = ensure_unique(groups, "id", "groups", errors)
        group_names = ensure_unique(groups, "name", "groups", errors)
        if len(set(group_names)) != len(group_names):
            errors.append("groups.name 必须唯一")

        all_group_participants: set[str] = set()
        for index, group in enumerate(groups):
            if not isinstance(group, dict):
                continue
            group_participants = group.get("participants", [])
            if not isinstance(group_participants, list):
                errors.append(f"groups[{index}].participants 必须是数组")
                continue
            for pidx, pid in enumerate(group_participants):
                if not isinstance(pid, str):
                    errors.append(f"groups[{index}].participants[{pidx}] 必须是字符串")
                    continue
                if pid not in participant_id_set:
                    errors.append(f"groups[{index}].participants[{pidx}] 引用了未定义参与者：{pid}")
                if pid in all_group_participants:
                    warnings.append(f"参与者 {pid} 出现在多个组中")
                all_group_participants.add(pid)

        for pid in participant_ids:
            if pid not in all_group_participants:
                warnings.append(f"参与者 {pid} 未被分配到任何组")

    out_of_scope = data.get("out_of_scope", [])
    if isinstance(out_of_scope, list):
        normalized_components = {normalize_text(name): name for name in participant_names}
        for index, item in enumerate(out_of_scope):
            if not isinstance(item, str):
                continue
            if normalize_text(item) in normalized_components:
                warnings.append(
                    f"out_of_scope[{index}] 与参与者名 {normalized_components[normalize_text(item)]} 重复，请确认边界定义"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 sequence-brief YAML")
    parser.add_argument("brief", help="brief YAML 文件路径")
    parser.add_argument(
        "--schema",
        default=None,
        help="schema JSON 路径，默认使用 skill 内置 schema",
    )
    args = parser.parse_args()

    brief_path = Path(args.brief).expanduser().resolve()
    if not brief_path.is_file():
        print(f"brief 文件不存在：{brief_path}", file=sys.stderr)
        return 1

    script_dir = Path(__file__).resolve().parent
    default_schema = script_dir.parent / "assets" / "validation" / "sequence-brief.schema.json"
    schema_path = Path(args.schema).expanduser().resolve() if args.schema else default_schema
    if not schema_path.is_file():
        print(f"schema 文件不存在：{schema_path}", file=sys.stderr)
        return 1

    try:
        data = load_yaml(brief_path)
    except Exception as exc:  # noqa: BLE001
        print(f"brief 解析失败：{exc}", file=sys.stderr)
        return 1

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"schema 解析失败：{exc}", file=sys.stderr)
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
