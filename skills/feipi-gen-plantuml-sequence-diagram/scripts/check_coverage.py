#!/usr/bin/env python3
"""检查 brief 与 PlantUML 时序图的覆盖关系。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PARTICIPANT_RE = re.compile(
    r'^\s*(participant|actor|database)\s+"([^"]+)"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b'
)

MESSAGE_RE = re.compile(
    r'^[^\'"]*\b([A-Za-z_][A-Za-z0-9_]*)\s*(-{1,2}>|<-{1,2}|-->>|<<--|-[xX]->|<-[xX]-)\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$'
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
        print(f"brief 文件不存在：{brief_path}", file=sys.stderr)
        return 1
    if not diagram_path.is_file():
        print(f"diagram 文件不存在：{diagram_path}", file=sys.stderr)
        return 1

    try:
        brief = load_yaml(brief_path)
    except Exception as exc:  # noqa: BLE001
        print(f"brief 解析失败：{exc}", file=sys.stderr)
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
        match = PARTICIPANT_RE.match(line)
        if match:
            alias_to_name[match.group(3)] = match.group(2)

    expected_participants = brief.get("participants", [])
    expected_messages = brief.get("messages", [])

    participant_ids = {item.get("id") for item in expected_participants if isinstance(item, dict)}

    for index, participant in enumerate(expected_participants):
        if not isinstance(participant, dict):
            continue
        comp_id = participant.get("id")
        comp_name = participant.get("name")
        if isinstance(comp_id, str) and comp_id not in alias_to_name:
            errors.append(f"participants[{index}].id 未以 alias 落图：{comp_id}")
        if isinstance(comp_id, str) and isinstance(comp_name, str):
            diagram_name = alias_to_name.get(comp_id)
            if diagram_name and normalize_text(diagram_name) != normalize_text(comp_name):
                errors.append(f"participants[{index}] 展示名与 brief 不一致：{comp_name}")
            if normalize_text(comp_name) not in normalized_text:
                errors.append(f"participants[{index}].name 未落图：{comp_name}")

    extra_aliases = sorted(alias for alias in alias_to_name if alias not in participant_ids)
    if extra_aliases:
        errors.append(f"存在 brief 未定义的额外参与者 alias: {extra_aliases}")

    # Check groups (box/separator)
    expected_groups = brief.get("groups", [])
    if expected_groups:
        for index, group in enumerate(expected_groups):
            if not isinstance(group, dict):
                continue
            group_name = group.get("name")
            group_participants = group.get("participants", [])
            if isinstance(group_name, str) and f'box "{group_name}"' not in raw_text:
                errors.append(f"groups[{index}].name 未落图：{group_name}")
            for pidx, pid in enumerate(group_participants):
                if isinstance(pid, str) and pid not in alias_to_name:
                    errors.append(f"groups[{index}].participants[{pidx}] 引用了未定义 alias: {pid}")

    lines = raw_text.splitlines()
    for index, message in enumerate(expected_messages):
        if not isinstance(message, dict):
            continue
        msg_id = message.get("id")
        from_id = message.get("from")
        to_id = message.get("to")
        description = message.get("description")

        matched_line = False
        if all(isinstance(value, str) for value in (msg_id, from_id, to_id)):
            for line in lines:
                if from_id in line and to_id in line and msg_id in line:
                    matched_line = True
                    break
        if not matched_line:
            errors.append(f"messages[{index}] 未找到包含 from/to/id 的连线：{msg_id}")

        if isinstance(msg_id, str) and msg_id not in raw_text:
            errors.append(f"messages[{index}].id 未落图：{msg_id}")
        if isinstance(description, str) and normalize_text(description) not in normalized_text:
            errors.append(f"messages[{index}].description 未落图：{description}")

    if errors:
        for error in errors:
            print(f"[错误] {error}", file=sys.stderr)
        return 1

    print("coverage_check=ok")
    print(f"coverage_participants={len(expected_participants)}")
    print(f"coverage_messages={len(expected_messages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
