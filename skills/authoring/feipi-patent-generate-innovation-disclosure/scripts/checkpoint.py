#!/usr/bin/env python3
"""维护专利交底任务的单文件、可恢复执行检查点。"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import hashlib
import html
import io
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


CHECKPOINT_RELATIVE = PurePosixPath("disclosure-workspace/working/CHECKPOINT.md")
CATALOG_PATH = Path(__file__).resolve().parents[1] / "agents/subagents/checkpoint-task-catalog.json"
STATE_MARKER_PREFIX = "<!-- checkpoint-state-v1: "
STATE_MARKER_SUFFIX = " -->"
STATE_VERSION = 1
STAGES = (
    "phase_1_material_modeling",
    "phase_2_idea_confirmation",
    "phase_3_final_drafting",
    "phase_4_review_delivery",
)
STATUSES = {"active", "waiting_user", "blocked", "complete"}
TASK_STATUSES = {"pending", "completed"}
CHECK_TYPES = ("nonempty", "markdown", "json", "tsv")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
OWNER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")


class CheckpointError(ValueError):
    """检查点合同错误。"""


@dataclass(frozen=True)
class Task:
    order: int
    task_id: str
    title: str
    owner: str
    result: str
    minimum_check: str
    status: str = "pending"
    sha256: str | None = None

    def definition(self) -> tuple[object, ...]:
        return self.order, self.task_id, self.title, self.owner, self.result, self.minimum_check

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.task_id,
            "minimum_check": self.minimum_check,
            "order": self.order,
            "owner": self.owner,
            "result": self.result,
            "sha256": self.sha256,
            "status": self.status,
            "title": self.title,
        }


@dataclass(frozen=True)
class CatalogTask:
    task_id: str
    title: str
    allowed_owners: tuple[str, ...]
    result: str
    minimum_check: str


@dataclass(frozen=True)
class CatalogTemplate:
    template_id: str
    task_id_regex: str
    result_regex: str
    allowed_owners: tuple[str, ...]
    minimum_check: str
    min_instances: int
    max_instances: int


CatalogNode = CatalogTask | CatalogTemplate


@dataclass(frozen=True)
class State:
    stage: str
    status: str
    inputs: tuple[str, ...]
    tasks: tuple[Task, ...]
    rollback_reason: str | None = None
    pause_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "inputs": list(self.inputs),
            "pause_reason": self.pause_reason,
            "rollback_reason": self.rollback_reason,
            "stage": self.stage,
            "status": self.status,
            "tasks": [task.as_dict() for task in self.tasks],
            "version": STATE_VERSION,
        }


@dataclass(frozen=True)
class ArtifactInspection:
    valid: bool
    reason: str
    sha256: str | None = None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="维护 working/CHECKPOINT.md 执行检查点")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_root(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--root", "--disclosure-root", dest="root", required=True,
            help="交底书根目录；检查点固定写入 disclosure-workspace/working/CHECKPOINT.md",
        )

    def add_stage_definition(subparser: argparse.ArgumentParser) -> None:
        add_root(subparser)
        subparser.add_argument("--stage", required=True, choices=STAGES)
        subparser.add_argument(
            "--input", action="append", required=True,
            help="本阶段输入；可重复并按出现顺序记录",
        )
        subparser.add_argument(
            "--task", action="append", nargs=5, required=True,
            metavar=("ID", "TITLE", "OWNER", "RESULT", "CHECK"),
            help="有序任务；OWNER 为稳定职责标识，CHECK 为一种最低检查类型",
        )

    start = subparsers.add_parser("start-stage", help="开始或重新进入一个阶段")
    add_stage_definition(start)

    rollback = subparsers.add_parser("rollback-stage", help="按主 agent 的显式决定回退阶段")
    add_stage_definition(rollback)
    rollback.add_argument("--reason", required=True, help="主 agent 明确给出的回退原因")

    complete = subparsers.add_parser("complete-task", help="校验结果并完成一个任务")
    add_root(complete)
    complete.add_argument("--task", "--task-id", dest="task_id", required=True)

    wait_user = subparsers.add_parser("wait-user", help="记录等待用户决定")
    add_root(wait_user)
    wait_user.add_argument("--reason", required=True)

    block = subparsers.add_parser("block", help="记录当前阻塞")
    add_root(block)
    block.add_argument("--reason", required=True)

    resume = subparsers.add_parser("resume", help="只读返回恢复位置")
    add_root(resume)

    validate = subparsers.add_parser("validate", help="只读校验检查点及已交付结果")
    add_root(validate)
    return parser.parse_args(argv)


def clean_text(raw: object, label: str, *, maximum: int = 4096) -> str:
    if not isinstance(raw, str):
        raise CheckpointError(f"{label} 必须是字符串")
    value = raw.strip()
    if not value:
        raise CheckpointError(f"{label} 不得为空")
    if len(value) > maximum:
        raise CheckpointError(f"{label} 超过 {maximum} 字符")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CheckpointError(f"{label} 不得包含控制字符或换行")
    return value


def disclosure_root(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.exists() or not path.is_dir():
        raise CheckpointError("--root 必须指向已存在的交底书根目录")
    return path.resolve()


def normalize_result(raw: object) -> str:
    value = clean_text(raw, "结果文件", maximum=1024)
    if "\\" in value:
        raise CheckpointError(f"结果路径必须使用 /：{value}")
    path = PurePosixPath(value)
    raw_parts = value.split("/")
    if path.is_absolute() or value.startswith("~"):
        raise CheckpointError(f"结果路径必须相对交底书根：{value}")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise CheckpointError(f"结果路径包含非法路径段：{value}")
    normalized = path.as_posix()
    if normalized == CHECKPOINT_RELATIVE.as_posix():
        raise CheckpointError("结果文件不得是 CHECKPOINT.md 自身")
    return normalized


def normalize_owner(raw: object, task_id: str) -> str:
    owner = clean_text(raw, f"任务 {task_id} owner", maximum=128)
    if not OWNER_PATTERN.fullmatch(owner):
        raise CheckpointError(f"任务 {task_id} owner 必须是小写稳定标识")
    return owner


def existing_path_has_symlink(root: Path, relative: PurePosixPath) -> bool:
    current = root
    for part in relative.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(mode):
            return True
    return False


def secure_relative_path(root: Path, relative: str | PurePosixPath) -> Path:
    normalized = normalize_result(str(relative))
    pure = PurePosixPath(normalized)
    if existing_path_has_symlink(root, pure):
        raise CheckpointError(f"路径不得经过符号链接：{normalized}")
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise CheckpointError(f"路径越出交底书根：{normalized}") from exc
    return candidate


def checkpoint_path(root: Path, *, create_parent: bool = False) -> Path:
    relative = CHECKPOINT_RELATIVE
    if existing_path_has_symlink(root, relative):
        raise CheckpointError("CHECKPOINT.md 路径不得经过符号链接")
    path = root.joinpath(*relative.parts)
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise CheckpointError("CHECKPOINT.md 路径越出交底书根") from exc
    if create_parent:
        current = root
        for part in relative.parts[:-1]:
            current = current / part
            if current.exists():
                mode = current.lstat().st_mode
                if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                    raise CheckpointError(f"检查点父路径不是实际目录：{current}")
            else:
                current.mkdir()
    return path


def parse_minimum_check(raw: str) -> str:
    check = clean_text(raw, "最低检查", maximum=32)
    if check not in CHECK_TYPES:
        raise CheckpointError(f"不支持的最低检查：{check}")
    return check


def tasks_from_args(raw_tasks: Sequence[Sequence[str]]) -> tuple[Task, ...]:
    tasks: list[Task] = []
    seen_ids: set[str] = set()
    seen_results: set[str] = set()
    for order, raw in enumerate(raw_tasks, start=1):
        task_id = clean_text(raw[0], f"任务 {order} ID", maximum=128)
        title = clean_text(raw[1], f"任务 {task_id} 标题", maximum=512)
        owner = normalize_owner(raw[2], task_id)
        result = normalize_result(raw[3])
        minimum_check = parse_minimum_check(raw[4])
        if task_id in seen_ids:
            raise CheckpointError(f"任务 ID 重复：{task_id}")
        if result in seen_results:
            raise CheckpointError(f"结果文件重复：{result}")
        seen_ids.add(task_id)
        seen_results.add(result)
        tasks.append(Task(order, task_id, title, owner, result, minimum_check))
    return tuple(tasks)


def catalog_owners(raw: object, node_id: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise CheckpointError(f"catalog {node_id} allowed_owners 不得为空")
    owners = tuple(normalize_owner(owner, node_id) for owner in raw)
    if len(set(owners)) != len(owners):
        raise CheckpointError(f"catalog {node_id} allowed_owners 重复")
    return owners


def catalog_regex(raw: object, label: str) -> str:
    pattern = clean_text(raw, label, maximum=2048)
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise CheckpointError(f"{label} 不是有效正则") from exc
    if "instance" not in compiled.groupindex:
        raise CheckpointError(f"{label} 必须包含命名组 instance")
    return pattern


@lru_cache(maxsize=1)
def load_task_catalog() -> dict[str, tuple[CatalogNode, ...]]:
    try:
        mode = CATALOG_PATH.lstat().st_mode
    except FileNotFoundError as exc:
        raise CheckpointError("缺少 agents/subagents/checkpoint-task-catalog.json") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise CheckpointError("checkpoint task catalog 必须是实际普通文件")
    try:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckpointError("checkpoint task catalog 无法解析") from exc
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "stages"}:
        raise CheckpointError("checkpoint task catalog 顶层字段不符合合同")
    if raw.get("schema_version") != "2.0":
        raise CheckpointError("checkpoint task catalog 版本必须为 2.0")
    raw_stages = raw.get("stages")
    if not isinstance(raw_stages, dict) or set(raw_stages) != set(STAGES):
        raise CheckpointError("checkpoint task catalog 阶段集合不完整")

    catalog: dict[str, tuple[CatalogNode, ...]] = {}
    global_ids: set[str] = set()
    global_template_ids: set[str] = set()
    for stage in STAGES:
        raw_nodes = raw_stages.get(stage)
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise CheckpointError(f"checkpoint task catalog 阶段节点为空：{stage}")
        stage_nodes: list[CatalogNode] = []
        stage_results: set[str] = set()
        for index, item in enumerate(raw_nodes, start=1):
            if not isinstance(item, dict):
                raise CheckpointError(f"checkpoint task catalog 节点必须是对象：{stage}:{index}")
            node_type = item.get("type")
            if node_type == "fixed":
                if set(item) != {
                    "type", "task_id", "title", "allowed_owners", "result", "minimum_check",
                }:
                    raise CheckpointError(f"checkpoint task catalog fixed 字段不完整：{stage}:{index}")
                task_id = clean_text(item.get("task_id"), f"catalog {stage} task_id", maximum=128)
                title = clean_text(item.get("title"), f"catalog {task_id} title", maximum=512)
                owners = catalog_owners(item.get("allowed_owners"), task_id)
                result = normalize_result(item.get("result"))
                minimum_check = parse_minimum_check(item.get("minimum_check"))
                if task_id in global_ids:
                    raise CheckpointError(f"checkpoint task catalog ID 重复：{task_id}")
                if result in stage_results:
                    raise CheckpointError(f"checkpoint task catalog 结果重复：{stage}:{result}")
                global_ids.add(task_id)
                stage_results.add(result)
                stage_nodes.append(CatalogTask(task_id, title, owners, result, minimum_check))
                continue
            if node_type == "template":
                if set(item) != {
                    "type", "template_id", "task_id_regex", "result_regex", "allowed_owners",
                    "minimum_check", "min_instances", "max_instances",
                }:
                    raise CheckpointError(f"checkpoint task catalog template 字段不完整：{stage}:{index}")
                template_id = clean_text(
                    item.get("template_id"), f"catalog {stage} template_id", maximum=128,
                )
                if not OWNER_PATTERN.fullmatch(template_id):
                    raise CheckpointError(f"catalog template_id 必须是小写稳定标识：{template_id}")
                if template_id in global_template_ids:
                    raise CheckpointError(f"checkpoint task catalog template_id 重复：{template_id}")
                owners = catalog_owners(item.get("allowed_owners"), template_id)
                task_id_regex = catalog_regex(
                    item.get("task_id_regex"), f"catalog {template_id} task_id_regex",
                )
                result_regex = catalog_regex(
                    item.get("result_regex"), f"catalog {template_id} result_regex",
                )
                minimum_check = parse_minimum_check(item.get("minimum_check"))
                minimum = item.get("min_instances")
                maximum = item.get("max_instances")
                if (
                    type(minimum) is not int
                    or type(maximum) is not int
                    or minimum < 1
                    or maximum < minimum
                ):
                    raise CheckpointError(f"catalog {template_id} 实例数范围非法")
                global_template_ids.add(template_id)
                stage_nodes.append(
                    CatalogTemplate(
                        template_id, task_id_regex, result_regex, owners,
                        minimum_check, minimum, maximum,
                    )
                )
                continue
            raise CheckpointError(f"checkpoint task catalog 节点 type 非法：{stage}:{index}")
        catalog[stage] = tuple(stage_nodes)
    return catalog


def validate_fixed_catalog_task(stage: str, order: int, task: Task, expected: CatalogTask) -> None:
    if task.task_id != expected.task_id:
        raise CheckpointError(
            f"阶段固定任务必须按 catalog 顺序且只能追加：{stage}:{order}:{expected.task_id}"
        )
    if task.title != expected.title:
        raise CheckpointError(f"阶段固定任务标题不匹配：{task.task_id}")
    if task.owner not in expected.allowed_owners:
        raise CheckpointError(f"阶段固定任务 owner 不允许：{task.task_id}:{task.owner}")
    if task.result != expected.result:
        raise CheckpointError(f"阶段固定任务结果路径不匹配：{task.task_id}")
    if task.minimum_check != expected.minimum_check:
        raise CheckpointError(f"阶段固定任务最低检查不匹配：{task.task_id}")


def validate_template_task(template: CatalogTemplate, task: Task, instance_number: int) -> None:
    task_match = re.fullmatch(template.task_id_regex, task.task_id)
    if task_match is None:
        raise CheckpointError(f"模板任务 ID 不匹配：{template.template_id}:{task.task_id}")
    result_match = re.fullmatch(template.result_regex, task.result)
    if result_match is None:
        raise CheckpointError(f"模板任务结果路径不匹配：{template.template_id}:{task.task_id}")
    task_instance = task_match.group("instance")
    result_instance = result_match.group("instance")
    if task_instance != result_instance:
        raise CheckpointError(f"模板任务 task_id/result instance 不一致：{task.task_id}")
    expected_instance = f"D{instance_number}"
    if task_instance != expected_instance:
        raise CheckpointError(
            f"模板任务 instance 必须从 D1 连续编号：{template.template_id}:"
            f"expected={expected_instance}:actual={task_instance}"
        )
    if task.owner not in template.allowed_owners:
        raise CheckpointError(f"模板任务 owner 不允许：{task.task_id}:{task.owner}")
    if task.minimum_check != template.minimum_check:
        raise CheckpointError(f"模板任务最低检查不匹配：{task.task_id}")


def validate_stage_task_catalog(stage: str, tasks: Sequence[Task]) -> None:
    catalog = load_task_catalog()
    nodes = catalog[stage]
    position = 0
    templates = tuple(node for node in nodes if isinstance(node, CatalogTemplate))
    if not templates and len(tasks) < len(nodes):
        raise CheckpointError(f"阶段固定任务不完整：{stage}")
    for node in nodes:
        if isinstance(node, CatalogTask):
            if position >= len(tasks):
                raise CheckpointError(f"阶段固定任务不完整：{stage}:{node.task_id}")
            validate_fixed_catalog_task(stage, position + 1, tasks[position], node)
            position += 1
            continue

        count = 0
        while position < len(tasks):
            task = tasks[position]
            if re.fullmatch(node.task_id_regex, task.task_id) is None:
                break
            if count >= node.max_instances:
                raise CheckpointError(f"模板任务实例超过上限：{node.template_id}:{node.max_instances}")
            validate_template_task(node, task, count + 1)
            count += 1
            position += 1
        if count < node.min_instances:
            raise CheckpointError(
                f"模板任务实例不足：{node.template_id}:{count}/{node.min_instances}"
            )

    for task in tasks[position:]:
        for template in templates:
            if (
                re.fullmatch(template.task_id_regex, task.task_id) is not None
                or re.fullmatch(template.result_regex, task.result) is not None
            ):
                raise CheckpointError(
                    f"模板任务只能在 catalog 固定位置连续出现：{template.template_id}:{task.task_id}"
                )
        for catalog_stage, catalog_nodes in catalog.items():
            if catalog_stage == stage:
                continue
            for node in catalog_nodes:
                if isinstance(node, CatalogTask):
                    if task.task_id == node.task_id:
                        raise CheckpointError(
                            "追加任务不得复用其他阶段固定任务 ID："
                            f"{stage}->{catalog_stage}:{task.task_id}"
                        )
                    if task.result == node.result:
                        raise CheckpointError(
                            "追加任务不得复用其他阶段固定任务结果："
                            f"{stage}->{catalog_stage}:{task.result}"
                        )
                    continue
                if re.fullmatch(node.task_id_regex, task.task_id) is not None:
                    raise CheckpointError(
                        "追加任务不得匹配其他阶段模板任务 ID："
                        f"{stage}->{catalog_stage}:{node.template_id}:{task.task_id}"
                    )
                if re.fullmatch(node.result_regex, task.result) is not None:
                    raise CheckpointError(
                        "追加任务不得匹配其他阶段模板任务结果："
                        f"{stage}->{catalog_stage}:{node.template_id}:{task.result}"
                    )


def state_from_dict(raw: object) -> State:
    if not isinstance(raw, dict):
        raise CheckpointError("检查点机器状态必须是 JSON 对象")
    expected_state_keys = {
        "inputs", "pause_reason", "rollback_reason", "stage", "status", "tasks", "version",
    }
    if (
        set(raw) != expected_state_keys
        or type(raw.get("version")) is not int
        or raw.get("version") != STATE_VERSION
    ):
        raise CheckpointError("检查点机器状态字段或版本不符合合同")
    raw_tasks = raw.get("tasks")
    if not isinstance(raw_tasks, list):
        raise CheckpointError("tasks 必须是数组")
    tasks: list[Task] = []
    expected_task_keys = {
        "id", "minimum_check", "order", "owner", "result", "sha256", "status", "title",
    }
    for item in raw_tasks:
        if not isinstance(item, dict) or set(item) != expected_task_keys:
            raise CheckpointError("任务状态字段不符合合同")
        tasks.append(
            Task(
                order=item.get("order"),
                task_id=item.get("id"),
                title=item.get("title"),
                owner=item.get("owner"),
                result=item.get("result"),
                minimum_check=item.get("minimum_check"),
                status=item.get("status"),
                sha256=item.get("sha256"),
            )
        )
    inputs = raw.get("inputs")
    if not isinstance(inputs, list) or not all(isinstance(item, str) for item in inputs):
        raise CheckpointError("inputs 必须是字符串数组")
    return State(
        stage=raw.get("stage"),
        status=raw.get("status"),
        inputs=tuple(inputs),
        tasks=tuple(tasks),
        rollback_reason=raw.get("rollback_reason"),
        pause_reason=raw.get("pause_reason"),
    )


def validate_state_structure(root: Path, state: State) -> None:
    if not isinstance(state.stage, str) or state.stage not in STAGES:
        raise CheckpointError(f"未知阶段：{state.stage}")
    if not isinstance(state.status, str) or state.status not in STATUSES:
        raise CheckpointError(f"未知检查点状态：{state.status}")
    if not state.inputs:
        raise CheckpointError("本阶段输入不得为空")
    for index, value in enumerate(state.inputs, start=1):
        clean_text(value, f"本阶段输入 {index}")
    if not state.tasks:
        raise CheckpointError("本阶段任务不得为空")
    seen_ids: set[str] = set()
    seen_results: set[str] = set()
    for index, task in enumerate(state.tasks, start=1):
        if type(task.order) is not int or task.order != index:
            raise CheckpointError("任务 order 必须从 1 开始连续递增")
        task_id = clean_text(task.task_id, f"任务 {index} ID", maximum=128)
        clean_text(task.title, f"任务 {task_id} 标题", maximum=512)
        normalize_owner(task.owner, task_id)
        if task_id in seen_ids:
            raise CheckpointError(f"任务 ID 重复：{task_id}")
        seen_ids.add(task_id)
        normalized = normalize_result(task.result)
        if normalized != task.result:
            raise CheckpointError(f"结果路径不是规范形式：{task.result}")
        if normalized in seen_results:
            raise CheckpointError(f"结果文件重复：{normalized}")
        seen_results.add(normalized)
        if not isinstance(task.minimum_check, str) or task.minimum_check not in CHECK_TYPES:
            raise CheckpointError(f"任务最低检查不符合合同：{task_id}")
        if not isinstance(task.status, str) or task.status not in TASK_STATUSES:
            raise CheckpointError(f"未知任务状态：{task_id}:{task.status}")
        if task.status == "pending":
            secure_relative_path(root, normalized)
            if task.sha256 is not None:
                raise CheckpointError(f"未完成任务不得记录 sha256：{task_id}")
        else:
            if not isinstance(task.sha256, str) or not SHA256_PATTERN.fullmatch(task.sha256):
                raise CheckpointError(f"已完成任务 sha256 非法：{task_id}")
    validate_stage_task_catalog(state.stage, state.tasks)
    if state.rollback_reason is not None:
        clean_text(state.rollback_reason, "回退原因")
    if state.status in {"waiting_user", "blocked"}:
        clean_text(state.pause_reason, "等待或阻塞原因")
    elif state.pause_reason is not None:
        raise CheckpointError("非等待/阻塞状态不得记录 pause_reason")
    if state.status == "complete" and any(task.status != "completed" for task in state.tasks):
        raise CheckpointError("complete 状态仍有未完成任务")
    if state.status != "complete" and all(task.status == "completed" for task in state.tasks):
        raise CheckpointError("全部任务已完成时状态必须是 complete")


def markdown_cell(value: object) -> str:
    return html.escape(str(value), quote=False).replace("|", "\\|")


def next_step_text(state: State) -> str:
    if state.status == "waiting_user":
        return f"等待用户：{state.pause_reason}"
    if state.status == "blocked":
        return f"解除阻塞后继续：{state.pause_reason}"
    for task in state.tasks:
        if task.status == "pending":
            return f"执行任务 {task.task_id}：{task.title}"
    if state.status == "complete":
        return "本阶段任务已全部完成"
    return "复核已交付结果并重做首个失效任务"


def render_state(state: State) -> str:
    rollback_reason = state.rollback_reason or "无"
    lines = [
        "# 执行检查点",
        "",
        "## 当前阶段",
        "",
        f"- 阶段 ID：{markdown_cell(state.stage)}",
        f"- 状态：{markdown_cell(state.status)}",
        f"- 回退原因：{markdown_cell(rollback_reason)}",
        "",
        "## 本阶段输入",
        "",
        "| 顺序 | 输入 |",
        "| ---: | --- |",
    ]
    lines.extend(
        f"| {index} | {markdown_cell(value)} |"
        for index, value in enumerate(state.inputs, start=1)
    )
    lines.extend(
        [
            "",
            "## 本阶段任务",
            "",
            "| 顺序 | ID | 标题 | owner | 结果文件 | 最低检查 | 状态 | SHA-256 |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for task in state.tasks:
        lines.append(
            "| "
            + " | ".join(
                (
                    str(task.order),
                    markdown_cell(task.task_id),
                    markdown_cell(task.title),
                    markdown_cell(task.owner),
                    markdown_cell(task.result),
                    markdown_cell(task.minimum_check),
                    markdown_cell(task.status),
                    markdown_cell(task.sha256 or "-"),
                )
            )
            + " |"
        )
    lines.extend(["", "## 当前阶段已交付", ""])
    delivered = [task for task in state.tasks if task.status == "completed"]
    if delivered:
        lines.extend(
            [
                "| 顺序 | ID | 标题 | owner | 结果文件 | 最低检查 | SHA-256 |",
                "| ---: | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for task in delivered:
            lines.append(
                "| "
                + " | ".join(
                    (
                        str(task.order),
                        markdown_cell(task.task_id),
                        markdown_cell(task.title),
                        markdown_cell(task.owner),
                        markdown_cell(task.result),
                        markdown_cell(task.minimum_check),
                        markdown_cell(task.sha256),
                    )
                )
                + " |"
            )
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 下一步",
            "",
            f"- {markdown_cell(next_step_text(state))}",
            "",
            "## 阻塞项",
            "",
        ]
    )
    if state.status == "blocked":
        lines.append(f"- 阻塞：{markdown_cell(state.pause_reason)}")
    else:
        lines.append("- 无")
    canonical_json = json.dumps(
        state.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(canonical_json).decode("ascii")
    lines.extend(["", f"{STATE_MARKER_PREFIX}{encoded}{STATE_MARKER_SUFFIX}"])
    return "\n".join(lines) + "\n"


def load_checkpoint(root: Path) -> State:
    path = checkpoint_path(root)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise CheckpointError("缺少 disclosure-workspace/working/CHECKPOINT.md") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise CheckpointError("CHECKPOINT.md 必须是实际普通文件")
    content = path.read_text(encoding="utf-8")
    marker_line = content.rstrip("\n").split("\n")[-1]
    if not marker_line.startswith(STATE_MARKER_PREFIX) or not marker_line.endswith(STATE_MARKER_SUFFIX):
        raise CheckpointError("CHECKPOINT.md 缺少机器状态标记")
    encoded = marker_line[len(STATE_MARKER_PREFIX) : -len(STATE_MARKER_SUFFIX)]
    try:
        decoded = base64.b64decode(encoded, altchars=b"-_", validate=True)
        raw = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckpointError("CHECKPOINT.md 机器状态无法解析") from exc
    state = state_from_dict(raw)
    validate_state_structure(root, state)
    if content != render_state(state):
        raise CheckpointError("CHECKPOINT.md 不是机器状态的规范渲染结果")
    return state


def atomic_save(root: Path, state: State) -> None:
    validate_state_structure(root, state)
    path = checkpoint_path(root, create_parent=True)
    content = render_state(state)
    descriptor, temp_name = tempfile.mkstemp(prefix=".CHECKPOINT.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    # os.replace 已保证同目录原子可见；部分文件系统不支持目录 fsync。
                    pass
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def read_regular_file(path: Path) -> bytes:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise CheckpointError("结果文件不存在") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise CheckpointError("结果文件不是实际普通文件")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise CheckpointError("结果文件不存在") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise CheckpointError("结果文件不是实际普通文件")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def validate_json(data: bytes) -> None:
    try:
        json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CheckpointError("不是有效 UTF-8 JSON") from exc


def validate_markdown(data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise CheckpointError("不是有效 UTF-8 Markdown") from exc
    if "\x00" in text or not text.strip():
        raise CheckpointError("Markdown 必须是非空 UTF-8 文本")


def validate_tsv(data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise CheckpointError("不是有效 UTF-8 TSV") from exc
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter="\t", strict=True))
    except csv.Error as exc:
        raise CheckpointError("TSV 无法解析") from exc
    if not rows or len(rows[0]) < 2:
        raise CheckpointError("TSV 必须至少包含两列表头")
    if any(not heading.strip() for heading in rows[0]) or len(set(rows[0])) != len(rows[0]):
        raise CheckpointError("TSV 表头不得为空或重复")
    width = len(rows[0])
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != width:
            raise CheckpointError(f"TSV 第 {row_number} 行列数不一致")
        if any("\n" in cell or "\r" in cell for cell in row):
            raise CheckpointError(f"TSV 第 {row_number} 行单元格包含换行")


def inspect_artifact(root: Path, task: Task, *, expected_sha256: str | None = None) -> ArtifactInspection:
    try:
        path = secure_relative_path(root, task.result)
        data = read_regular_file(path)
    except CheckpointError as exc:
        message = str(exc)
        reason = "result_missing" if "不存在" in message else "unsafe_or_nonregular_result"
        return ArtifactInspection(False, reason)
    if not data:
        return ArtifactInspection(False, "check_failed:nonempty")
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        return ArtifactInspection(False, "sha256_changed", digest)
    validators = {
        "nonempty": lambda _data: None,
        "json": validate_json,
        "markdown": validate_markdown,
        "tsv": validate_tsv,
    }
    try:
        validators[task.minimum_check](data)
    except CheckpointError:
        return ArtifactInspection(False, f"check_failed:{task.minimum_check}", digest)
    return ArtifactInspection(True, "valid", digest)


def require_valid_artifact(root: Path, task: Task, *, expected_sha256: str | None = None) -> str:
    result = inspect_artifact(root, task, expected_sha256=expected_sha256)
    if not result.valid or result.sha256 is None:
        raise CheckpointError(f"任务 {task.task_id} 结果无效：{result.reason}")
    return result.sha256


def task_definitions_equal(left: Iterable[Task], right: Iterable[Task]) -> bool:
    return [task.definition() for task in left] == [task.definition() for task in right]


def preserve_valid_completed(root: Path, tasks: tuple[Task, ...]) -> tuple[Task, ...]:
    preserved: list[Task] = []
    for task in tasks:
        if task.status == "completed":
            inspection = inspect_artifact(root, task, expected_sha256=task.sha256)
            if inspection.valid:
                preserved.append(task)
                continue
        preserved.append(replace(task, status="pending", sha256=None))
    return tuple(preserved)


def command_start_stage(root: Path, args: argparse.Namespace) -> None:
    inputs = tuple(clean_text(value, "本阶段输入") for value in args.input)
    tasks = tasks_from_args(args.task)
    validate_stage_task_catalog(args.stage, tasks)
    for task in tasks:
        secure_relative_path(root, task.result)
    path = checkpoint_path(root)
    rollback_reason = None
    if path.exists():
        current = load_checkpoint(root)
        current_index = STAGES.index(current.stage)
        requested_index = STAGES.index(args.stage)
        if current.stage != args.stage:
            if requested_index < current_index:
                raise CheckpointError("阶段后退必须使用 rollback-stage 并显式提供 --reason")
            if requested_index != current_index + 1:
                raise CheckpointError("阶段必须按固定顺序逐阶段开始")
            if current.status != "complete":
                raise CheckpointError("当前阶段尚未完成；只能重新进入当前阶段")
            for task in current.tasks:
                require_valid_artifact(root, task, expected_sha256=task.sha256)
        else:
            if current.inputs != inputs or not task_definitions_equal(current.tasks, tasks):
                raise CheckpointError("当前阶段输入或任务定义变化必须使用 rollback-stage 并提供原因")
            tasks = preserve_valid_completed(root, current.tasks)
            rollback_reason = current.rollback_reason
    elif args.stage != STAGES[0]:
        raise CheckpointError("首次 start-stage 必须从 phase_1_material_modeling 开始")
    status = "complete" if all(task.status == "completed" for task in tasks) else "active"
    state = State(args.stage, status, inputs, tasks, rollback_reason=rollback_reason)
    if path.exists() and state == current:
        print("checkpoint=unchanged")
        print(f"stage={state.stage}")
        print(f"status={state.status}")
        print(f"next_task={next((task.task_id for task in state.tasks if task.status == 'pending'), 'none')}")
        return
    atomic_save(root, state)
    print("checkpoint=started")
    print(f"stage={state.stage}")
    print(f"status={state.status}")
    print(f"next_task={next((task.task_id for task in state.tasks if task.status == 'pending'), 'none')}")


def command_rollback_stage(root: Path, args: argparse.Namespace) -> None:
    current = load_checkpoint(root)
    if STAGES.index(args.stage) > STAGES.index(current.stage):
        raise CheckpointError("rollback-stage 不能前进到更后阶段")
    reason = clean_text(args.reason, "回退原因")
    inputs = tuple(clean_text(value, "本阶段输入") for value in args.input)
    tasks = tasks_from_args(args.task)
    validate_stage_task_catalog(args.stage, tasks)
    for task in tasks:
        secure_relative_path(root, task.result)
    state = State(args.stage, "active", inputs, tasks, rollback_reason=reason)
    if state == current:
        print("checkpoint=unchanged")
        print(f"stage={state.stage}")
        print(f"reason={reason}")
        print(f"next_task={state.tasks[0].task_id}")
        return
    atomic_save(root, state)
    print("checkpoint=rolled_back")
    print(f"stage={state.stage}")
    print(f"reason={reason}")
    print(f"next_task={state.tasks[0].task_id}")


def first_actionable_task(root: Path, state: State) -> Task | None:
    for task in state.tasks:
        if task.status == "pending":
            return task
        inspection = inspect_artifact(root, task, expected_sha256=task.sha256)
        if not inspection.valid:
            return task
    return None


def command_complete_task(root: Path, task_id_raw: str) -> None:
    task_id = clean_text(task_id_raw, "任务 ID", maximum=128)
    state = load_checkpoint(root)
    if state.status in {"waiting_user", "blocked"}:
        raise CheckpointError("当前处于等待或阻塞状态；先用 start-stage 重新进入当前阶段")
    requested = next((task for task in state.tasks if task.task_id == task_id), None)
    if requested is None:
        raise CheckpointError(f"未知任务 ID：{task_id}")
    if requested.status == "completed" and inspect_artifact(
        root, requested, expected_sha256=requested.sha256,
    ).valid:
        actionable = first_actionable_task(root, state)
        print("checkpoint=already_complete")
        print(f"stage={state.stage}")
        print(f"status={state.status}")
        print(f"next_task={actionable.task_id if actionable else 'none'}")
        return
    digest = require_valid_artifact(root, requested)
    tasks = tuple(
        replace(task, status="completed", sha256=digest)
        if task.task_id == task_id else task
        for task in state.tasks
    )
    all_valid = True
    for task in tasks:
        if task.status != "completed":
            all_valid = False
            break
        if not inspect_artifact(root, task, expected_sha256=task.sha256).valid:
            all_valid = False
            break
    new_state = replace(state, tasks=tasks, status="complete" if all_valid else "active")
    atomic_save(root, new_state)
    print("checkpoint=task_completed")
    print(f"stage={new_state.stage}")
    print(f"task_id={task_id}")
    print(f"sha256={digest}")
    print(f"status={new_state.status}")
    next_task = first_actionable_task(root, new_state)
    print(f"next_task={next_task.task_id if next_task else 'none'}")


def command_pause(root: Path, status: str, reason_raw: str) -> None:
    reason = clean_text(reason_raw, "等待或阻塞原因")
    state = load_checkpoint(root)
    tasks = preserve_valid_completed(root, state.tasks)
    if state.status == "complete" and tasks == state.tasks:
        raise CheckpointError("阶段已完成，不能再记录等待或阻塞")
    if state.status == status and state.pause_reason == reason and tasks == state.tasks:
        print("checkpoint=unchanged")
        print(f"stage={state.stage}")
        print(f"status={status}")
        print(f"reason={reason}")
        return
    new_state = replace(state, tasks=tasks, status=status, pause_reason=reason)
    atomic_save(root, new_state)
    print(f"checkpoint={status}")
    print(f"stage={state.stage}")
    print(f"status={status}")
    print(f"reason={reason}")


def command_resume(root: Path) -> None:
    state = load_checkpoint(root)
    print(f"stage={state.stage}")
    actionable = first_actionable_task(root, state)
    if state.status in {"waiting_user", "blocked"}:
        if actionable is not None and actionable.status == "completed":
            inspection = inspect_artifact(root, actionable, expected_sha256=actionable.sha256)
            print("status=redo")
            print(f"task_id={actionable.task_id}")
            print(f"title={actionable.title}")
            print(f"owner={actionable.owner}")
            print(f"result={actionable.result}")
            print(f"check={actionable.minimum_check}")
            print(f"reason={inspection.reason}")
            return
        print(f"status={state.status}")
        print(f"reason={state.pause_reason}")
        return
    if actionable is None:
        print("status=complete")
        return
    print(f"status={'ready' if actionable.status == 'pending' else 'redo'}")
    print(f"task_id={actionable.task_id}")
    print(f"title={actionable.title}")
    print(f"owner={actionable.owner}")
    print(f"result={actionable.result}")
    print(f"check={actionable.minimum_check}")
    if actionable.status == "completed":
        inspection = inspect_artifact(root, actionable, expected_sha256=actionable.sha256)
        print(f"reason={inspection.reason}")


def command_validate(root: Path) -> None:
    state = load_checkpoint(root)
    completed = 0
    for task in state.tasks:
        if task.status == "completed":
            require_valid_artifact(root, task, expected_sha256=task.sha256)
            completed += 1
    if completed == len(state.tasks) and state.status not in {"complete", "waiting_user", "blocked"}:
        raise CheckpointError("所有任务有效完成时状态必须是 complete")
    print("checkpoint=valid")
    print(f"stage={state.stage}")
    print(f"status={state.status}")
    print(f"completed_tasks={completed}")
    print(f"total_tasks={len(state.tasks)}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        root = disclosure_root(args.root)
        if args.command == "start-stage":
            command_start_stage(root, args)
        elif args.command == "rollback-stage":
            command_rollback_stage(root, args)
        elif args.command == "complete-task":
            command_complete_task(root, args.task_id)
        elif args.command == "wait-user":
            command_pause(root, "waiting_user", args.reason)
        elif args.command == "block":
            command_pause(root, "blocked", args.reason)
        elif args.command == "resume":
            command_resume(root)
        elif args.command == "validate":
            command_validate(root)
        return 0
    except (CheckpointError, OSError, UnicodeError, csv.Error) as exc:
        print(f"checkpoint_error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
