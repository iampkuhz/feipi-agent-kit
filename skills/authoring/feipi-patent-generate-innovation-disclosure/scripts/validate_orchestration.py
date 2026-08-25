#!/usr/bin/env python3
"""校验专利交底 subagent 配置、阶段 DAG 与任务包合同。"""

from __future__ import annotations

import json
import stat
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_STAGES = (
    "phase_1_material_modeling",
    "phase_2_idea_confirmation",
    "phase_3_final_drafting",
    "phase_4_review_delivery",
)
EXPECTED_UPSTREAM = {
    "phase_1_material_modeling": [],
    "phase_2_idea_confirmation": ["phase-1-handoff"],
    "phase_3_final_drafting": ["phase-2-handoff"],
    "phase_4_review_delivery": ["phase-3-handoff"],
}

# 这里只固化阶段职责所需的能力，不复制 role 文件中的模型、effort、权限或实例上限。
# role JSON 是这些运行参数的唯一真源。
ROLE_CAPABILITY_CONTRACTS = {
    "patent_subject_boundary_analyst": {
        "technical_subject",
        "implementation_extension_boundary",
    },
    "patent_prior_art_researcher": {
        "object_prior_art_research",
        "mechanism_prior_art_research",
        "source_relevance",
    },
    "patent_innovation_value_analyst": {
        "innovation_effect_mapping",
        "substantial_difference",
        "value_causality",
    },
    "patent_diagram_engineer": {
        "single_diagram_package",
        "package_validation",
    },
    "patent_semantic_reviewer": {
        "generalization_test",
        "causal_deletion_test",
        "external_leak_review",
    },
    "patent_visual_reviewer": {
        "single_svg_visual_review",
        "hash_bound_review",
    },
}
EXPECTED_NODE_ROLES = {
    ("phase_1_material_modeling", "subject-boundary"): "patent_subject_boundary_analyst",
    ("phase_1_material_modeling", "research-object"): "patent_prior_art_researcher",
    ("phase_1_material_modeling", "research-mechanism"): "patent_prior_art_researcher",
    ("phase_1_material_modeling", "innovation-value"): "patent_innovation_value_analyst",
    ("phase_3_final_drafting", "diagram-worker"): "patent_diagram_engineer",
    ("phase_4_review_delivery", "semantic-review"): "patent_semantic_reviewer",
    ("phase_4_review_delivery", "visual-review"): "patent_visual_reviewer",
}
EXPECTED_CRITICAL_EVENTS = ["MILESTONE", "DECISION", "BLOCKED", "COMPLETE"]
EXPECTED_SILENT_EVENTS = [
    "STARTED", "RUNNING", "HEARTBEAT", "STATUS", "TOOL_CALL", "FILE_READ",
    "FILE_WRITE", "CACHE_HIT", "WAIT_TIMEOUT", "RETRYING", "UNCHANGED",
]
REQUIRED_TEMPLATE_FIELDS = {
    "{{role_name}}",
    "{{checkpoint_binding}}",
    "{{timing_log}}",
    "{{key_event_contract}}",
    "{{input_references}}",
    "{{allowed_writes}}",
    "{{forbidden_actions}}",
    "{{judgment_contract}}",
    "{{return_contract}}",
}
ROLE_FIELDS = {
    "schema_version",
    "name",
    "description",
    "model",
    "reasoning_effort",
    "fork_turns",
    "permission",
    "max_instances",
    "allowed_write_templates",
    "capabilities",
    "forbidden_actions",
}
ALLOWED_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}
ALLOWED_PERMISSIONS = {"read_only", "workspace_write"}


class ValidationError(ValueError):
    """配置合同不成立。"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise ValidationError(f"缺少配置文件：{path}") from exc
    require(stat.S_ISREG(mode) and not stat.S_ISLNK(mode), f"配置必须是普通文件：{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"JSON 无法解析：{path}") from exc
    require(isinstance(value, dict), f"JSON 顶层必须是对象：{path}")
    return value


def safe_config_path(base: Path, relative: Any, field: str) -> Path:
    require(isinstance(relative, str) and relative.strip(), f"{field} 必须是非空相对路径")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and ".." not in pure.parts and "\\" not in relative, f"{field} 路径越界")
    return base.joinpath(*pure.parts)


def safe_runtime_path(relative: Any, field: str, *, trailing_slash: bool | None = None) -> str:
    require(isinstance(relative, str) and relative.strip(), f"{field} 必须是非空路径")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and ".." not in pure.parts and "\\" not in relative, f"{field} 路径越界")
    if trailing_slash is True:
        require(relative.endswith("/"), f"{field} 必须是目录模板")
    return relative


def string_list(value: Any, field: str, *, allow_empty: bool = False) -> list[str]:
    require(isinstance(value, list), f"{field} 必须是数组")
    require(allow_empty or bool(value), f"{field} 不得为空")
    require(all(isinstance(item, str) and item.strip() for item in value), f"{field} 只能包含非空字符串")
    require(len(value) == len(set(value)), f"{field} 不得包含重复项")
    return value


def validate_runtime(runtime: dict[str, Any]) -> tuple[int, int, int]:
    require(runtime.get("schema_version") == "1.0", "runtime schema_version 必须为 1.0")
    limits = runtime.get("limits")
    require(isinstance(limits, dict), "缺少 runtime limits")
    require(limits.get("max_active_subagents") == 3, "max_active_subagents 必须为 3")
    require(limits.get("max_total_subagents") == 9, "max_total_subagents 必须为 9")
    require(limits.get("allow_recursive_spawn") is False, "必须禁止递归派生 subagent")
    require(limits.get("default_fork_turns") == "none", "fork_turns 必须默认为 none")
    max_task_bytes = limits.get("task_packet_max_bytes")
    require(max_task_bytes == 12 * 1024, "任务包上限必须为 12 KiB")

    checkpoint = runtime.get("checkpoint")
    require(isinstance(checkpoint, dict), "缺少 checkpoint 合同")
    require(checkpoint.get("path") == "disclosure-workspace/working/CHECKPOINT.md", "checkpoint 路径不正确")
    require(checkpoint.get("catalog") == "agents/subagents/checkpoint-task-catalog.json", "checkpoint catalog 路径不正确")
    require(checkpoint.get("coordinator") == "main_agent", "checkpoint 必须由 main_agent 协调")

    reporting = runtime.get("event_reporting")
    require(isinstance(reporting, dict), "缺少关键事件合同")
    require(reporting.get("critical_events") == EXPECTED_CRITICAL_EVENTS, "关键事件集合不正确")
    require(reporting.get("silent_events") == EXPECTED_SILENT_EVENTS, "静默事件集合不正确")
    require(reporting.get("subagent_audience") == "main_agent", "subagent 只能向主 agent 上报")
    require(reporting.get("main_agent_audience") == "user", "主 agent 只向用户上报")
    require(reporting.get("max_lines") == 1 and reporting.get("max_chars") == 240, "关键事件必须为 1 行且不超过 240 字符")
    require(reporting.get("deduplicate") is True, "关键事件必须去重")

    wait = runtime.get("wait_policy")
    require(isinstance(wait, dict), "缺少等待合同")
    require(wait.get("mode") == "event_driven_join", "subagent 汇合必须事件驱动")
    require(wait.get("main_agent_work_while_subagents_run") is True, "主 agent 必须先执行独立工作")
    for key in ("busy_wait", "periodic_poll", "heartbeat", "status_probe_between_waits", "short_wait_loop"):
        require(wait.get(key) is False, f"禁止等待策略：{key}")
    require(
        wait.get("nonterminal_timeout_policy") == "continue_long_event_wait_without_status_probe",
        "非终态超时不得触发状态查询",
    )
    return 3, 9, max_task_bytes


def validate_role(name: str, role: dict[str, Any], max_active: int) -> None:
    require(set(role) == ROLE_FIELDS, f"role 字段集合不正确：{name}")
    require(role.get("schema_version") == "1.0", f"role schema_version 不正确：{name}")
    require(role.get("name") == name, f"role name 与索引不一致：{name}")
    require(isinstance(role.get("description"), str) and role["description"].strip(), f"role description 为空：{name}")
    require(isinstance(role.get("model"), str) and role["model"].strip(), f"role model 为空：{name}")
    require(role.get("reasoning_effort") in ALLOWED_REASONING_EFFORTS, f"role reasoning_effort 非法：{name}")
    require(role.get("permission") in ALLOWED_PERMISSIONS, f"role permission 非法：{name}")
    require(role.get("fork_turns") == "none", f"role 必须使用 fork_turns none：{name}")
    max_instances = role.get("max_instances")
    require(
        isinstance(max_instances, int) and not isinstance(max_instances, bool) and 1 <= max_instances <= max_active,
        f"role max_instances 必须在 1..{max_active}：{name}",
    )

    writes = string_list(role.get("allowed_write_templates"), f"role allowed_write_templates：{name}", allow_empty=True)
    for path in writes:
        safe_runtime_path(path, f"role allowed_write_templates：{name}", trailing_slash=True)
    if role["permission"] == "read_only":
        require(writes == [], f"只读 role 不得声明写路径：{name}")
    else:
        require(bool(writes), f"workspace_write role 必须声明写路径：{name}")

    capabilities = set(string_list(role.get("capabilities"), f"role capabilities：{name}"))
    required = ROLE_CAPABILITY_CONTRACTS[name]
    require(required <= capabilities, f"role 缺少阶段职责能力：{name}:{','.join(sorted(required - capabilities))}")
    string_list(role.get("forbidden_actions"), f"role forbidden_actions：{name}")


def validate_dag(stage_name: str, nodes: Any) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    require(isinstance(nodes, list) and nodes, f"阶段节点为空：{stage_name}")
    node_map: dict[str, dict[str, Any]] = {}
    for node in nodes:
        require(isinstance(node, dict), f"阶段节点必须是对象：{stage_name}")
        node_id = node.get("id")
        require(isinstance(node_id, str) and node_id, f"阶段节点 id 非法：{stage_name}")
        require(node_id not in node_map, f"阶段节点 id 重复：{stage_name}:{node_id}")
        node_map[node_id] = node
    for node_id, node in node_map.items():
        deps = node.get("depends_on")
        require(isinstance(deps, list), f"depends_on 必须是数组：{stage_name}:{node_id}")
        require(len(deps) == len(set(deps)), f"依赖重复：{stage_name}:{node_id}")
        for dependency in deps:
            require(isinstance(dependency, str) and dependency in node_map, f"依赖不存在：{stage_name}:{node_id}:{dependency}")

    visiting: set[str] = set()
    ancestors: dict[str, set[str]] = {}

    def collect(node_id: str) -> set[str]:
        require(node_id not in visiting, f"阶段 DAG 存在环：{stage_name}:{node_id}")
        if node_id in ancestors:
            return ancestors[node_id]
        visiting.add(node_id)
        result: set[str] = set()
        for dependency in node_map[node_id]["depends_on"]:
            result.add(dependency)
            result.update(collect(dependency))
        visiting.remove(node_id)
        ancestors[node_id] = result
        return result

    for node_id in node_map:
        collect(node_id)
    return node_map, ancestors


def validate_task_packet_template(path: Path, max_bytes: int) -> None:
    try:
        size = path.stat().st_size
        content = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeError) as exc:
        raise ValidationError(f"任务包模板不可读：{path}") from exc
    require(size > 0 and size <= max_bytes, "任务包模板必须非空且不超过 12 KiB")
    headings = [line for line in content.splitlines() if line.startswith("## ")]
    require(headings == ["## 输入", "## 需要判断", "## 返回"], "任务包模板必须且只能包含输入/需要判断/返回三节")
    missing = sorted(field for field in REQUIRED_TEMPLATE_FIELDS if field not in content)
    require(not missing, f"任务包模板缺少占位字段：{','.join(missing)}")


def validate_possible_concurrency(
    stage_name: str,
    node_map: dict[str, dict[str, Any]],
    ancestors: dict[str, set[str]],
    roles: dict[str, dict[str, Any]],
    max_active: int,
) -> int:
    """从 DAG 的可比关系推导 subagent 最大并发，而不信任 parallel_group 标签。"""
    subagents = [node_id for node_id, node in node_map.items() if node.get("executor") == "subagent"]
    weights = {
        node_id: node_map[node_id].get("fan_out", {}).get("max_parallel", 1)
        for node_id in subagents
    }
    peak = 0
    for size in range(1, len(subagents) + 1):
        for selected in combinations(subagents, size):
            if any(left in ancestors[right] or right in ancestors[left] for left, right in combinations(selected, 2)):
                continue
            active = sum(weights[node_id] for node_id in selected)
            peak = max(peak, active)
            require(
                active <= max_active,
                f"DAG 推导并发超过 max_active_subagents：{stage_name}:{','.join(selected)}:{active}",
            )
            role_counts: Counter[str] = Counter()
            for node_id in selected:
                role_counts[node_map[node_id]["role_ref"]] += weights[node_id]
            for role_name, count in role_counts.items():
                require(
                    count <= roles[role_name]["max_instances"],
                    f"DAG 推导并发超过 role pool：{stage_name}:{role_name}:{count}",
                )

            write_patterns: list[tuple[str, str]] = []
            for node_id in selected:
                for path in node_map[node_id]["allowed_writes"]:
                    write_patterns.append((node_id, path))
            for (left_id, left_path), (right_id, right_path) in combinations(write_patterns, 2):
                require(
                    left_path != right_path,
                    f"可并发任务写路径重叠：{stage_name}:{left_id}:{right_id}",
                )
    return peak


def validate_stage_nodes(
    stage_name: str,
    stage: dict[str, Any],
    roles: dict[str, dict[str, Any]],
    checkpoint_refs: set[str],
    checkpoint_templates: set[str],
    checkpoint_order: dict[str, int],
    max_active: int,
) -> int:
    require(stage.get("schema_version") == "1.0", f"stage schema_version 不正确：{stage_name}")
    require(stage.get("stage") == stage_name, f"stage 名称与索引不一致：{stage_name}")
    require(stage.get("requires_upstream") == EXPECTED_UPSTREAM[stage_name], f"requires_upstream 链不正确：{stage_name}")
    node_map, ancestors = validate_dag(stage_name, stage.get("nodes"))
    if stage_name == "phase_2_idea_confirmation":
        require(all(node.get("executor") != "subagent" for node in node_map.values()), "阶段 2 禁止 subagent")

    packet_paths: set[str] = set()
    fixed_bindings: Counter[str] = Counter()
    template_bindings: Counter[str] = Counter()
    node_binding: dict[str, str] = {}
    spawn_budget = 0

    for node_id, node in node_map.items():
        executor = node.get("executor")
        require(executor in {"main_agent", "subagent", "user"}, f"executor 非法：{stage_name}:{node_id}")
        require("result" not in node and "result_path" not in node, f"stage 节点不得复制结果路径：{stage_name}:{node_id}")
        fixed_ref = node.get("checkpoint_ref")
        template_ref = node.get("checkpoint_template_ref")
        require(not (fixed_ref and template_ref), f"checkpoint 固定与动态引用不能并存：{stage_name}:{node_id}")
        if executor == "user":
            require(not fixed_ref and not template_ref, f"user 节点不得绑定 checkpoint：{stage_name}:{node_id}")
        else:
            require(bool(fixed_ref) ^ bool(template_ref), f"节点必须引用一个 checkpoint 合同：{stage_name}:{node_id}")
        if fixed_ref:
            require(fixed_ref in checkpoint_refs, f"checkpoint_ref 不属于当前阶段：{stage_name}:{node_id}:{fixed_ref}")
            fixed_bindings[fixed_ref] += 1
            node_binding[node_id] = fixed_ref
        if template_ref:
            require(template_ref in checkpoint_templates, f"checkpoint_template_ref 不属于当前阶段：{stage_name}:{node_id}:{template_ref}")
            template_bindings[template_ref] += 1
            node_binding[node_id] = template_ref

        join = node.get("join")
        if join is not None:
            require(executor == "main_agent", f"join 必须由 main_agent 执行：{stage_name}:{node_id}")
            require(join in {"all_dependencies", "all_instances"}, f"join 语义非法：{stage_name}:{node_id}")
            if join == "all_dependencies":
                require(len(node["depends_on"]) >= 2, f"all_dependencies 至少需要两个依赖：{stage_name}:{node_id}")
            else:
                require(
                    any(node_map[dependency].get("fan_out") is not None for dependency in node["depends_on"]),
                    f"all_instances 必须直接依赖 fan_out 节点：{stage_name}:{node_id}",
                )

        if executor != "subagent":
            require("role_ref" not in node, f"非 subagent 节点不得引用 role：{stage_name}:{node_id}")
            continue

        role_name = node.get("role_ref")
        require(role_name in roles, f"role_ref 不存在：{stage_name}:{node_id}:{role_name}")
        expected_role = EXPECTED_NODE_ROLES.get((stage_name, node_id))
        require(expected_role == role_name, f"subagent 阶段职责不匹配：{stage_name}:{node_id}:{role_name}")
        packet = node.get("task_packet")
        require(isinstance(packet, dict) and packet.get("template_ref") == "default", f"subagent 缺少默认任务包：{stage_name}:{node_id}")
        packet_path = safe_runtime_path(packet.get("path"), f"task_packet:{stage_name}:{node_id}")
        require(packet_path not in packet_paths, f"subagent 任务包路径重复：{stage_name}:{node_id}")
        packet_paths.add(packet_path)
        writes = node.get("allowed_writes")
        require(isinstance(writes, list), f"subagent allowed_writes 必须是数组：{stage_name}:{node_id}")
        for path in writes:
            safe_runtime_path(path, f"allowed_writes:{stage_name}:{node_id}", trailing_slash=True)
        require(writes == roles[role_name]["allowed_write_templates"], f"节点写路径与 role 真源不一致：{stage_name}:{node_id}")

        fan_out = node.get("fan_out")
        instances = 1
        if fan_out is not None:
            require(isinstance(fan_out, dict), f"fan_out 必须是对象：{stage_name}:{node_id}")
            require(fan_out.get("item_key") == "diagram_id", f"动态图任务必须按 diagram_id 展开：{stage_name}:{node_id}")
            instances = fan_out.get("max_parallel")
            require(isinstance(instances, int) and not isinstance(instances, bool) and instances > 0, f"fan_out max_parallel 非法：{stage_name}:{node_id}")
            require(instances <= roles[role_name]["max_instances"], f"fan_out 超过 role worker pool：{stage_name}:{node_id}")
            require(fan_out.get("overflow_policy") == "reuse_pool_sequentially", f"fan_out 溢出策略不正确：{stage_name}:{node_id}")
            require("{diagram_id}" in packet["path"], f"动态图任务包必须按 diagram_id 隔离：{stage_name}:{node_id}")
            if writes:
                require(all("{diagram_id}" in path for path in writes), f"动态图写路径必须按 diagram_id 隔离：{stage_name}:{node_id}")
        spawn_budget += instances

    for reference, count in fixed_bindings.items():
        require(count == 1, f"checkpoint_ref 在阶段内重复绑定：{stage_name}:{reference}")
    for reference, count in template_bindings.items():
        require(count == 1, f"checkpoint_template_ref 在阶段内重复绑定：{stage_name}:{reference}")
    require(set(fixed_bindings) == checkpoint_refs, f"checkpoint_ref 未与阶段节点一一绑定：{stage_name}")
    require(set(template_bindings) == checkpoint_templates, f"checkpoint_template_ref 未与阶段节点一一绑定：{stage_name}")

    # catalog 是恢复顺序真源；任何有 checkpoint 的祖先都必须排在后继之前。
    for node_id, ancestor_ids in ancestors.items():
        if node_id not in node_binding:
            continue
        for ancestor_id in ancestor_ids:
            if ancestor_id not in node_binding:
                continue
            require(
                checkpoint_order[node_binding[ancestor_id]] < checkpoint_order[node_binding[node_id]],
                f"checkpoint catalog 顺序与 DAG 反向：{stage_name}:{ancestor_id}->{node_id}",
            )

    for node_id, node in node_map.items():
        if node.get("fan_out") is None:
            continue
        joins = [
            candidate_id for candidate_id, candidate in node_map.items()
            if node_id in candidate["depends_on"] and candidate.get("join") == "all_instances"
        ]
        require(len(joins) == 1, f"fan_out 必须且只能由一个 all_instances 节点直接汇合：{stage_name}:{node_id}")

    validate_possible_concurrency(stage_name, node_map, ancestors, roles, max_active)
    return spawn_budget


def require_nodes(stage_name: str, node_map: dict[str, dict[str, Any]], node_ids: set[str]) -> None:
    missing = sorted(node_ids - set(node_map))
    require(not missing, f"阶段缺少职责节点：{stage_name}:{','.join(missing)}")


def validate_stage_contracts(stages: dict[str, dict[str, Any]]) -> None:
    phase_1 = {node["id"]: node for node in stages["phase_1_material_modeling"]["nodes"]}
    require_nodes(
        "phase_1_material_modeling",
        phase_1,
        {"research-object", "research-mechanism", "research-join", "delivery-goals", "subject-boundary", "innovation-value", "material-model"},
    )
    require(
        {phase_1["research-object"].get("role_instance"), phase_1["research-mechanism"].get("role_instance")} == {"object", "mechanism"},
        "两条 prior-art lane 必须使用 object/mechanism 独立实例",
    )
    require(
        phase_1["research-join"]["depends_on"] == ["research-object", "research-mechanism"]
        and phase_1["research-join"].get("join") == "all_dependencies",
        "research-join 必须汇合且仅汇合两条检索线",
    )
    require(
        set(phase_1["innovation-value"]["depends_on"]) == {"delivery-goals", "subject-boundary", "research-join"},
        "innovation-value 必须等待交付目标、主体边界与 research-join",
    )
    require(
        set(phase_1["material-model"]["depends_on"]) == {"delivery-goals", "subject-boundary", "research-join", "innovation-value"},
        "material-model 必须等待阶段一四类冻结结果",
    )
    require(
        phase_1["phase-1-handoff"]["depends_on"] == ["material-model"],
        "phase-1-handoff 必须是 material-model 之后的阶段终点",
    )

    phase_2 = {node["id"]: node for node in stages["phase_2_idea_confirmation"]["nodes"]}
    require(
        set(phase_2) == {"idea-decision", "user-confirmation", "phase-2-handoff"},
        "阶段二只能包含思路、显式用户确认和 handoff 三个屏障节点",
    )
    require(
        phase_2["idea-decision"].get("executor") == "main_agent"
        and phase_2["idea-decision"]["depends_on"] == [],
        "idea-decision 必须由 main_agent 在阶段入口形成",
    )
    require(
        phase_2["user-confirmation"].get("executor") == "user"
        and phase_2["user-confirmation"]["depends_on"] == ["idea-decision"]
        and phase_2["user-confirmation"].get("gate") == "explicit_confirmation",
        "user-confirmation 必须是 idea-decision 后的显式确认屏障",
    )
    require(
        phase_2["phase-2-handoff"]["depends_on"] == ["user-confirmation"],
        "phase-2-handoff 不得绕过显式用户确认",
    )

    phase_3 = {node["id"]: node for node in stages["phase_3_final_drafting"]["nodes"]}
    require_nodes(
        "phase_3_final_drafting",
        phase_3,
        {"content-core", "diagram-plan", "public-draft", "diagram-worker", "diagram-join", "manifest", "internal-draft", "build-map"},
    )
    barrier = {"content-core", "diagram-plan"}
    require(phase_3["content-core"]["depends_on"] == [] and phase_3["diagram-plan"]["depends_on"] == [], "phase-3 冻结屏障必须从阶段入口并行建立")
    require(set(phase_3["public-draft"]["depends_on"]) == barrier, "public-draft 必须等待 content-core 与 diagram-plan 屏障")
    require(set(phase_3["diagram-worker"]["depends_on"]) == barrier, "diagram-worker 必须等待 content-core 与 diagram-plan 屏障")
    require(phase_3["public-draft"].get("parallel_group") == phase_3["diagram-worker"].get("parallel_group"), "正文与逐图任务必须声明同一并行组")
    require(phase_3["diagram-worker"].get("checkpoint_template_ref") == "phase-3-diagram", "动态图必须引用 phase-3-diagram checkpoint 模板")
    diagram_fan_out = phase_3["diagram-worker"].get("fan_out")
    require(isinstance(diagram_fan_out, dict) and diagram_fan_out.get("source") == "frozen_diagram_plan", "phase-3 fan_out 必须来自 frozen_diagram_plan")
    require(
        phase_3["diagram-worker"].get("allowed_writes") == ["disclosure-workspace/diagrams/{diagram_id}-{purpose}/"],
        "diagram-worker 必须按 diagram_id 与 purpose 独占写目录",
    )
    require(
        phase_3["diagram-join"]["depends_on"] == ["diagram-worker"] and phase_3["diagram-join"].get("join") == "all_instances",
        "diagram-join 必须等待全部逐图实例",
    )
    require(set(phase_3["manifest"]["depends_on"]) == {"public-draft", "diagram-join"}, "manifest 必须等待正文与全部图")
    require(set(phase_3["internal-draft"]["depends_on"]) == {"public-draft", "diagram-join", "manifest"}, "内部稿必须等待 manifest 追溯真源")
    require(set(phase_3["build-map"]["depends_on"]) == {"internal-draft", "manifest", "diagram-join"}, "build-map 必须等待正文、manifest 与全部图")
    require(
        phase_3["phase-3-handoff"]["depends_on"] == ["build-map"],
        "phase-3-handoff 必须是 build-map 之后的阶段终点",
    )

    phase_4 = {node["id"]: node for node in stages["phase_4_review_delivery"]["nodes"]}
    require_nodes(
        "phase_4_review_delivery",
        phase_4,
        {"review-plan", "semantic-review", "visual-review", "review-join", "validation"},
    )
    visual_fan_out = phase_4["visual-review"].get("fan_out")
    require(isinstance(visual_fan_out, dict) and visual_fan_out.get("source") == "build_map_diagrams", "phase-4 fan_out 必须来自 build_map_diagrams")
    require(
        set(phase_4["review-join"]["depends_on"]) == {"semantic-review", "visual-review"}
        and phase_4["review-join"].get("join") == "all_instances",
        "终审汇合必须等待语义复核与全部逐图视觉复核",
    )
    require(phase_4["validation"]["depends_on"] == ["review-join"], "最终校验必须等待终审汇合")
    require(
        phase_4["timing-summary"]["depends_on"] == ["validation"],
        "timing-summary 必须等待最终校验",
    )
    require(
        phase_4["phase-4-handoff"]["depends_on"] == ["timing-summary"],
        "phase-4-handoff 必须是 timing-summary 之后的阶段终点",
    )


def validate(skill_dir: Path) -> None:
    config_dir = skill_dir / "agents/subagents"
    index = load_json(config_dir / "index.json")
    require(index.get("schema_version") == "1.0", "index schema_version 必须为 1.0")
    require(set(index) == {"schema_version", "runtime", "task_packet_template", "roles", "stages"}, "index 顶层字段不完整")

    runtime_path = safe_config_path(config_dir, index.get("runtime"), "index.runtime")
    template_path = safe_config_path(config_dir, index.get("task_packet_template"), "index.task_packet_template")
    runtime = load_json(runtime_path)
    max_active, max_total, max_task_bytes = validate_runtime(runtime)
    validate_task_packet_template(template_path, max_task_bytes)

    role_index = index.get("roles")
    require(isinstance(role_index, dict) and set(role_index) == set(ROLE_CAPABILITY_CONTRACTS), "角色索引必须恰好包含六个阶段职责角色")
    roles: dict[str, dict[str, Any]] = {}
    for name, relative in role_index.items():
        role = load_json(safe_config_path(config_dir, relative, f"role:{name}"))
        validate_role(name, role, max_active)
        roles[name] = role

    stage_index = index.get("stages")
    require(isinstance(stage_index, dict) and tuple(stage_index) == EXPECTED_STAGES, "阶段索引必须按四阶段顺序完整声明")
    stages: dict[str, dict[str, Any]] = {}
    for name, relative in stage_index.items():
        stages[name] = load_json(safe_config_path(config_dir, relative, f"stage:{name}"))

    catalog_path = safe_config_path(skill_dir, runtime["checkpoint"]["catalog"], "runtime.checkpoint.catalog")
    catalog = load_json(catalog_path)
    require(catalog.get("schema_version") == "2.0", "checkpoint catalog schema_version 必须为 2.0")
    catalog_stages = catalog.get("stages")
    require(isinstance(catalog_stages, dict), "checkpoint catalog 缺少 stages")
    require(set(catalog_stages) == set(EXPECTED_STAGES), "checkpoint catalog 阶段集合不完整")
    checkpoint_refs: dict[str, set[str]] = {stage: set() for stage in EXPECTED_STAGES}
    checkpoint_templates: dict[str, set[str]] = {stage: set() for stage in EXPECTED_STAGES}
    checkpoint_order: dict[str, dict[str, int]] = {stage: {} for stage in EXPECTED_STAGES}
    all_checkpoint_ids: set[str] = set()
    for stage_name, tasks in catalog_stages.items():
        require(stage_name in EXPECTED_STAGES and isinstance(tasks, list), f"checkpoint catalog 阶段非法：{stage_name}")
        for position, task in enumerate(tasks):
            require(isinstance(task, dict), f"checkpoint catalog 任务非法：{stage_name}")
            if task.get("type") == "fixed":
                task_id = task.get("task_id")
                require(isinstance(task_id, str) and task_id, f"固定 checkpoint task_id 非法：{stage_name}")
                require(task_id not in all_checkpoint_ids, f"checkpoint task_id 重复：{task_id}")
                checkpoint_refs[stage_name].add(task_id)
                checkpoint_order[stage_name][task_id] = position
                all_checkpoint_ids.add(task_id)
            elif task.get("type") == "template":
                template_id = task.get("template_id")
                require(isinstance(template_id, str) and template_id, f"checkpoint template_id 非法：{stage_name}")
                require(template_id not in all_checkpoint_ids, f"checkpoint template_id 重复：{template_id}")
                require(isinstance(task.get("task_id_regex"), str), f"checkpoint template 缺少 task_id_regex：{template_id}")
                require(isinstance(task.get("result_regex"), str), f"checkpoint template 缺少 result_regex：{template_id}")
                checkpoint_templates[stage_name].add(template_id)
                checkpoint_order[stage_name][template_id] = position
                all_checkpoint_ids.add(template_id)
            else:
                raise ValidationError(f"checkpoint catalog type 非法：{stage_name}")

    total_spawn_budget = 0
    for stage_name in EXPECTED_STAGES:
        total_spawn_budget += validate_stage_nodes(
            stage_name,
            stages[stage_name],
            roles,
            checkpoint_refs[stage_name],
            checkpoint_templates[stage_name],
            checkpoint_order[stage_name],
            max_active,
        )
    require(total_spawn_budget <= max_total, f"累计 subagent 预算超过 max_total_subagents：{total_spawn_budget}")
    validate_stage_contracts(stages)


def main() -> int:
    skill_dir = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
    try:
        validate(skill_dir)
    except ValidationError as exc:
        print(f"ORCH-001 {exc}", file=sys.stderr)
        return 1
    print("orchestration=valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
