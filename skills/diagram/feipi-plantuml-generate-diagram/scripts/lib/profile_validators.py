#!/usr/bin/env python3
"""Typed profile 的跨字段、引用、编号与密度约束。"""

from __future__ import annotations

import collections
import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .brief_loader import load_yaml

E_ID = re.compile(r"^E([1-9][0-9]*)$")
S_ID = re.compile(r"^S([1-9][0-9]*)(?:\.([1-9][0-9]*))?$")
MR_ID = re.compile(r"^[MR][1-9][0-9]*$")
IMPLEMENTATION_TERM = re.compile(
    r"(?:\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b|"
    r"\.jar\b|\bjar\b|class\b|function\b|handler\b|processor\b|"
    r"类$|函数|字段|方法$|表字段)",
    re.IGNORECASE,
)


def _items(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key, [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _unique_ids(items: list[dict[str, Any]], key: str, errors: list[str]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        value = item.get("id")
        if not isinstance(value, str):
            continue
        if value in seen:
            errors.append(f"{key}[{index}].id 重复：{value}")
        seen.add(value)
        ids.append(value)
    return ids


def _validate_edges(
    edges: list[dict[str, Any]],
    edge_key: str,
    node_ids: set[str],
    errors: list[str],
    *,
    require_e_ids: bool,
    max_degree: int | None = None,
) -> tuple[int, int]:
    degree: collections.Counter[str] = collections.Counter()
    edge_ids: list[str] = []
    endpoint_pairs: list[tuple[str, str]] = []
    for index, edge in enumerate(edges):
        edge_id = edge.get("id")
        if isinstance(edge_id, str):
            edge_ids.append(edge_id)
            if require_e_ids and not E_ID.fullmatch(edge_id):
                errors.append(f"{edge_key}[{index}].id 必须使用 E1...En：{edge_id}")
        source = edge.get("from")
        target = edge.get("to")
        if source not in node_ids:
            errors.append(f"{edge_key}[{index}].from 引用了未定义节点：{source}")
        if target not in node_ids:
            errors.append(f"{edge_key}[{index}].to 引用了未定义节点：{target}")
        if isinstance(source, str) and isinstance(target, str):
            if source == target:
                errors.append(f"{edge_key}[{index}] 不允许自连接：{source}")
            degree[source] += 1
            degree[target] += 1
            endpoint_pairs.append((source, target))
    if len(edge_ids) != len(set(edge_ids)):
        errors.append(f"{edge_key}.id 不允许重复")
    if len(endpoint_pairs) != len(set(endpoint_pairs)):
        errors.append(f"{edge_key} 不允许重复的 from/to 组合")
    if require_e_ids:
        numeric = sorted(int(match.group(1)) for value in edge_ids if (match := E_ID.fullmatch(value)))
        if numeric and numeric != list(range(1, len(numeric) + 1)):
            errors.append(f"{edge_key}.id 必须从 E1 连续编号")
    actual_max = max(degree.values(), default=0)
    if max_degree is not None and actual_max > max_degree:
        errors.append(f"{edge_key} 单节点连接度不得超过 {max_degree}，实际最大值：{actual_max}")
    return len(edges), actual_max


def _validate_s_ids(ids: list[str], field: str, errors: list[str]) -> None:
    parsed: list[tuple[int, int | None]] = []
    for value in ids:
        match = S_ID.fullmatch(value)
        if not match:
            errors.append(f"{field} 必须使用 S1...Sn 或 Sx.y：{value}")
            continue
        parsed.append((int(match.group(1)), int(match.group(2)) if match.group(2) else None))
    top = sorted({major for major, minor in parsed if minor is None})
    if top and top != list(range(1, max(top) + 1)):
        errors.append(f"{field} 顶层步骤必须从 S1 连续编号")
    top_set = set(top)
    children: dict[int, list[int]] = collections.defaultdict(list)
    for major, minor in parsed:
        if minor is not None:
            if major not in top_set:
                errors.append(f"{field} 子步骤 S{major}.{minor} 缺少父步骤 S{major}")
            children[major].append(minor)
    for major, minors in children.items():
        ordered = sorted(set(minors))
        if ordered != list(range(1, max(ordered) + 1)):
            errors.append(f"{field} 的 S{major}.x 子步骤必须从 1 连续编号")


def _validate_sequence(data: dict[str, Any], errors: list[str]) -> None:
    participants = _items(data, "participants")
    messages = _items(data, "messages")
    participant_ids = set(_unique_ids(participants, "participants", errors))
    message_ids = _unique_ids(messages, "messages", errors)
    scheme = data.get("numbering_scheme", "interaction_mr")
    for index, message in enumerate(messages):
        source = message.get("from")
        target = message.get("to")
        if source not in participant_ids:
            errors.append(f"messages[{index}].from 引用了未定义参与者：{source}")
        if target not in participant_ids:
            errors.append(f"messages[{index}].to 引用了未定义参与者：{target}")
    if scheme == "interaction_mr":
        invalid = [value for value in message_ids if not MR_ID.fullmatch(value)]
        if invalid:
            errors.append(f"interaction_mr 只允许 M/R 编号：{invalid}")
    elif scheme == "process_s":
        invalid = [value for value in message_ids if not S_ID.fullmatch(value)]
        if invalid:
            errors.append(f"process_s 只允许 S 编号，禁止混用 M/R：{invalid}")
        _validate_s_ids(message_ids, "messages.id", errors)
    else:
        errors.append(f"未知 numbering_scheme：{scheme}")


def _safe_relative_path(value: Any) -> PurePosixPath | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def _validate_parent_component_ref(
    data: dict[str, Any],
    errors: list[str],
    source_path: Path | None,
) -> None:
    parent_id = data.get("parent_component_id")
    ref = data.get("parent_component_ref")
    if not isinstance(parent_id, str) or not parent_id:
        errors.append("module_detail 必须声明唯一 parent_component_id")
        return
    if not isinstance(ref, dict):
        errors.append("module_detail 必须声明 parent_component_ref 并绑定来源 overview brief")
        return
    if ref.get("component_id") != parent_id:
        errors.append("parent_component_ref.component_id 必须与 parent_component_id 一致")
    overview_diagram_id = ref.get("overview_diagram_id")
    if not isinstance(overview_diagram_id, str) or not re.fullmatch(r"D[1-9][0-9]*|[a-z][a-z0-9-]*", overview_diagram_id):
        errors.append("parent_component_ref.overview_diagram_id 格式无效")
    rel = _safe_relative_path(ref.get("overview_brief_path"))
    if rel is None:
        errors.append("parent_component_ref.overview_brief_path 必须是安全的相对路径，禁止绝对路径和 ..")
        return
    expected_hash = ref.get("overview_brief_sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        errors.append("parent_component_ref.overview_brief_sha256 必须是小写 SHA-256")
        return
    if source_path is None:
        errors.append("module_detail 父组件来源校验需要 brief 文件路径")
        return
    base = source_path.resolve().parent
    overview_path = (base / Path(*rel.parts)).resolve()
    try:
        overview_path.relative_to(base)
    except ValueError:
        errors.append("parent_component_ref.overview_brief_path 越出 brief 目录")
        return
    if not overview_path.is_file():
        errors.append(f"parent_component_ref.overview_brief_path 不存在：{rel.as_posix()}")
        return
    actual_hash = hashlib.sha256(overview_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        errors.append("parent_component_ref.overview_brief_sha256 与来源 overview brief 不一致")
        return
    try:
        overview = load_yaml(overview_path)
    except Exception as exc:
        errors.append(f"parent_component_ref 来源 overview brief 解析失败：{exc}")
        return
    if not isinstance(overview, dict):
        errors.append("parent_component_ref 来源 overview brief 根节点必须是对象")
        return
    if overview.get("diagram_type") != "component" or overview.get("view") != "overview":
        errors.append("parent_component_ref 必须指向 component/overview brief")
    if overview.get("diagram_id") != overview_diagram_id:
        errors.append("parent_component_ref.overview_diagram_id 与来源 overview brief 不一致")
    matched = [
        node for node in _items(overview, "nodes")
        if node.get("id") == parent_id
    ]
    if len(matched) != 1:
        errors.append("parent_component_id 必须在来源 overview brief 中恰好命中一个节点")


def _validate_component(
    data: dict[str, Any],
    errors: list[str],
    source_path: Path | None = None,
) -> None:
    groups = _items(data, "groups")
    nodes = _items(data, "nodes")
    relations = _items(data, "relations")
    group_ids = set(_unique_ids(groups, "groups", errors))
    node_ids = set(_unique_ids(nodes, "nodes", errors))
    view = data.get("view")
    parent = data.get("parent_component_id")
    if view == "module_detail":
        _validate_parent_component_ref(data, errors, source_path)
        if len(groups) != 1:
            errors.append("module_detail 只能使用一个分组展开一个父组件")
    if view == "overview" and (parent is not None or data.get("parent_component_ref") is not None):
        errors.append("overview 不允许声明 parent_component_id 或 parent_component_ref")
    allowed_overview = {"business_domain", "system", "physical_endpoint"}
    for index, node in enumerate(nodes):
        if node.get("group") not in group_ids:
            errors.append(f"nodes[{index}].group 引用了未定义分组：{node.get('group')}")
        if view == "overview" and node.get("type") not in allowed_overview:
            errors.append(f"nodes[{index}].type 不能作为 overview 顶层节点：{node.get('type')}")
        if view == "overview" and IMPLEMENTATION_TERM.search(str(node.get("name", ""))):
            errors.append(f"nodes[{index}].name 疑似实现细节，不能放在 overview 顶层")
        if view == "module_detail" and node.get("type") not in {"component", "module"}:
            errors.append(f"nodes[{index}].type 在 module_detail 中只能是 component 或 module")
        if view == "module_detail" and node.get("id") == parent:
            errors.append("module_detail 不得把父组件本身重复画成细化节点")
    _validate_edges(relations, "relations", node_ids, errors, require_e_ids=True, max_degree=4)


def _validate_activity(data: dict[str, Any], errors: list[str]) -> None:
    steps = _items(data, "steps")
    transitions = _items(data, "transitions")
    step_ids_list = _unique_ids(steps, "steps", errors)
    step_ids = set(step_ids_list)
    _validate_s_ids(step_ids_list, "steps.id", errors)
    top_count = sum(1 for value in step_ids_list if S_ID.fullmatch(value) and "." not in value)
    if top_count < 5 or top_count > 10:
        errors.append(f"activity 顶层步骤必须为 5–10 个，实际：{top_count}")
    for index, step in enumerate(steps):
        name = str(step.get("name", ""))
        if re.search(r"[。；;，,：:]", name):
            errors.append(f"steps[{index}].name 必须是单一动作短语，不能包含句子型标点")
    _validate_edges(transitions, "transitions", step_ids, errors, require_e_ids=False)
    connected: set[str] = set()
    for transition in transitions:
        if isinstance(transition.get("from"), str):
            connected.add(transition["from"])
        if isinstance(transition.get("to"), str):
            connected.add(transition["to"])
    isolated = sorted(step_ids - connected)
    if isolated:
        errors.append(f"steps 存在孤立步骤：{isolated}")
    narrative = data.get("narrative_step_ids", [])
    narrative_ids = set(narrative) if isinstance(narrative, list) else set()
    if narrative_ids != step_ids or len(narrative) != len(narrative_ids):
        errors.append("narrative_step_ids 必须与 steps.id 完全一致且无重复")


def _validate_deployment(data: dict[str, Any], errors: list[str]) -> None:
    zones = _items(data, "zones")
    nodes = _items(data, "nodes")
    connections = _items(data, "connections")
    zone_ids = set(_unique_ids(zones, "zones", errors))
    node_ids = set(_unique_ids(nodes, "nodes", errors))
    for index, node in enumerate(nodes):
        if node.get("zone") not in zone_ids:
            errors.append(f"nodes[{index}].zone 引用了未定义物理区：{node.get('zone')}")
    _validate_edges(connections, "connections", node_ids, errors, require_e_ids=True, max_degree=4)
    if not any(node.get("type") in {"endpoint", "hsm", "human_transfer"} for node in nodes):
        errors.append("deployment 至少需要一个物理端点、HSM 或人工交接点")
    node_by_id = {str(node.get("id")): node for node in nodes}
    zone_by_node = {node_id: node.get("zone") for node_id, node in node_by_id.items()}
    if not any(zone_by_node.get(str(edge.get("from"))) != zone_by_node.get(str(edge.get("to"))) for edge in connections):
        errors.append("deployment 至少需要一条跨物理区连接")

    adjacency: dict[str, set[str]] = collections.defaultdict(set)
    valid_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for edge in connections:
        source_id, target_id = str(edge.get("from")), str(edge.get("to"))
        source, target = node_by_id.get(source_id), node_by_id.get(target_id)
        if source is None or target is None:
            continue
        adjacency[source_id].add(target_id)
        adjacency[target_id].add(source_id)
        valid_pairs.append((source, target))
    isolated = sorted(node_ids - set(adjacency))
    if isolated:
        errors.append(f"deployment 存在未连接的端点：{isolated}")

    def connected_mode_boundary() -> bool:
        visited: set[str] = set()
        for start in node_ids:
            if start in visited:
                continue
            stack = [start]
            modes: set[str] = set()
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                node = node_by_id.get(current)
                if node and node.get("mode") in {"online", "offline"}:
                    modes.add(str(node.get("mode")))
                stack.extend(adjacency.get(current, set()) - visited)
            if {"online", "offline"}.issubset(modes):
                return True
        return False

    observed = {
        "cross_network": any(
            source.get("network_id") and target.get("network_id")
            and source.get("network_id") != target.get("network_id")
            for source, target in valid_pairs
        ),
        "cross_chain": any(
            source.get("chain_id") and target.get("chain_id")
            and source.get("chain_id") != target.get("chain_id")
            for source, target in valid_pairs
        ),
        "online_offline": connected_mode_boundary(),
        "hsm": any(node.get("type") == "hsm" and node_id in adjacency for node_id, node in node_by_id.items()),
        "manual_transfer": any(
            node.get("type") == "human_transfer" and node_id in adjacency
            for node_id, node in node_by_id.items()
        ),
        "manual_handoff": any(
            node.get("type") == "human_handoff" and node_id in adjacency
            for node_id, node in node_by_id.items()
        ),
    }
    triggers = data.get("boundary_triggers", {})
    if isinstance(triggers, dict):
        for key, actual in observed.items():
            declared = triggers.get(key)
            if declared is not actual:
                errors.append(
                    f"boundary_triggers.{key}={str(declared).lower()} 与端点/连接语义"
                    f"（实际 {str(actual).lower()}）不一致"
                )


def validate_profile_semantics(
    diagram_type: str,
    data: Any,
    source_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["brief 根节点必须是对象"], warnings
    if data.get("diagram_type") != diagram_type:
        errors.append(f"diagram_type 与 profile 不一致：{data.get('diagram_type')} != {diagram_type}")
        return errors, warnings
    if diagram_type == "sequence":
        _validate_sequence(data, errors)
    elif diagram_type == "component":
        _validate_component(data, errors, source_path)
    elif diagram_type == "activity":
        _validate_activity(data, errors)
    elif diagram_type == "deployment":
        _validate_deployment(data, errors)
    return errors, warnings
