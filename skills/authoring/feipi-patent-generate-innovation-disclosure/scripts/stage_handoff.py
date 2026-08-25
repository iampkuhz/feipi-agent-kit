#!/usr/bin/env python3
"""Manage compact, hash-bound stage handoffs for patent disclosure sessions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


STATE_HEADER = [
    "stage",
    "status",
    "input_path",
    "input_sha256",
    "cache_sha256",
    "handoff_path",
    "handoff_sha256",
    "sealed_at",
]
MAX_HANDOFF_BYTES = 24 * 1024
MAX_TASK_BYTES = 12 * 1024


@dataclass(frozen=True)
class StageSpec:
    name: str
    status: str
    input_path: str
    handoff_path: str
    to_stage: str
    required_files: tuple[str, ...]


STAGES = (
    StageSpec(
        "phase_1_material_modeling",
        "ready",
        "stages/shared/material-index.tsv",
        "stages/phase-1/handoff.md",
        "phase_2_idea_confirmation",
        (
            "stages/shared/material-index.tsv",
            "stages/shared/evidence-cards.md",
            "stages/agents/subject-boundary-task.md",
            "stages/agents/prior-art-object-task.md",
            "stages/agents/prior-art-mechanism-task.md",
            "stages/agents/innovation-value-task.md",
            "stages/phase-1/analysis-plan.json",
            "stages/phase-1/delivery-goals.md",
            "stages/phase-1/subject-boundary.tsv",
            "stages/phase-1/research-object.tsv",
            "stages/phase-1/research-mechanism.tsv",
            "stages/phase-1/research.tsv",
            "stages/phase-1/innovation-candidates.tsv",
            "stages/phase-1/model.md",
            "stages/phase-1/handoff.md",
        ),
    ),
    StageSpec(
        "phase_2_idea_confirmation",
        "confirmed",
        "stages/phase-1/handoff.md",
        "stages/phase-2/handoff.md",
        "phase_3_final_drafting",
        (
            "stages/phase-2/decision.md",
            "stages/phase-2/handoff.md",
        ),
    ),
    StageSpec(
        "phase_3_final_drafting",
        "built",
        "stages/phase-2/handoff.md",
        "stages/phase-3/handoff.md",
        "phase_4_review_delivery",
        (
            "stages/phase-3/content-core.json",
            "stages/phase-3/diagram-plan.json",
            "stages/phase-3/diagram-result.tsv",
            "stages/phase-3/build-map.tsv",
            "stages/phase-3/handoff.md",
        ),
    ),
    StageSpec(
        "phase_4_review_delivery",
        "reviewed",
        "stages/phase-3/handoff.md",
        "stages/phase-4/handoff.md",
        "delivery",
        (
            "stages/agents/semantic-review-task.md",
            "stages/phase-4/review-plan.json",
            "stages/phase-4/semantic-review.tsv",
            "stages/phase-4/review.tsv",
            "stages/phase-4/handoff.md",
        ),
    ),
)
STAGE_BY_NAME = {stage.name: stage for stage in STAGES}
TSV_HEADERS = {
    "stages/shared/material-index.tsv": [
        "source_id", "source_type", "path_or_locator", "sha256", "relevant_anchors",
    ],
    "stages/phase-1/research.tsv": [
        "lane", "query_id", "source_id", "evidence_status", "locator", "conclusion",
    ],
    "stages/phase-1/research-object.tsv": [
        "lane", "query_id", "source_id", "evidence_status", "locator", "conclusion",
    ],
    "stages/phase-1/research-mechanism.tsv": [
        "lane", "query_id", "source_id", "evidence_status", "locator", "conclusion",
    ],
    "stages/phase-1/subject-boundary.tsv": [
        "subject_id", "technical_object", "use_scenario", "business_domain",
        "system_owner", "physical_boundary", "implemented_scope", "extension_scope",
        "core_mechanism",
    ],
    "stages/phase-1/innovation-candidates.tsv": [
        "candidate_id", "source_fact_ids", "extension_ids", "problem", "mechanism",
        "constraint", "baseline", "difference_hypothesis", "value_chain", "effect",
        "validation_status", "diagram_landing",
    ],
    "stages/phase-3/build-map.tsv": [
        "artifact_id", "path", "sha256", "owner", "status",
    ],
    "stages/phase-3/diagram-result.tsv": [
        "artifact_id", "path", "sha256", "owner", "status",
    ],
    "stages/phase-4/review.tsv": [
        "artifact_id", "review_type", "status", "bound_sha256", "conclusion",
    ],
    "stages/phase-4/semantic-review.tsv": [
        "artifact_id", "review_type", "status", "bound_sha256", "conclusion",
    ],
}
TASK_FILES = {
    "stages/agents/subject-boundary-task.md",
    "stages/agents/prior-art-object-task.md",
    "stages/agents/prior-art-mechanism-task.md",
    "stages/agents/innovation-value-task.md",
    "stages/agents/semantic-review-task.md",
}
JSON_FILES = {
    "stages/phase-1/analysis-plan.json",
    "stages/phase-3/content-core.json",
    "stages/phase-3/diagram-plan.json",
    "stages/phase-4/review-plan.json",
}
DIAGRAM_ID_PATTERN = re.compile(r"^D([1-9][0-9]*)$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DYNAMIC_TASK_PATTERNS = {
    "phase-3": re.compile(r"^diagram-(D[1-9][0-9]*)-task\.md$"),
    "phase-4": re.compile(r"^visual-review-(D[1-9][0-9]*)-task\.md$"),
}
DYNAMIC_RESULT_PATTERNS = {
    "phase-3": re.compile(r"^(D[1-9][0-9]*)-result\.tsv$"),
    "phase-4": re.compile(r"^(D[1-9][0-9]*)-review\.tsv$"),
}
DIAGRAM_RESULT_HEADER = TSV_HEADERS["stages/phase-3/diagram-result.tsv"]
REVIEW_RESULT_HEADER = TSV_HEADERS["stages/phase-4/review.tsv"]


class ContractError(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="管理专利交底四阶段的紧凑 handoff 链")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "status", "validate"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--working", required=True, help="disclosure-workspace/working 路径")
        if command == "validate":
            sub.add_argument("--require-complete", action="store_true")
    for command in ("seal", "rewind"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--working", required=True, help="disclosure-workspace/working 路径")
        sub.add_argument("--stage", required=True, choices=tuple(STAGE_BY_NAME))
    return parser.parse_args()


def working_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if root.name != "working":
        raise ContractError("--working 必须指向 disclosure-workspace/working")
    return root


def state_path(root: Path) -> Path:
    return root / "stages" / "stage-state.tsv"


def resolve_fixed(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ContractError(f"非法相对路径：{relative}")
    candidate = root / relative
    cursor = root
    for part in Path(relative).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ContractError(f"缓存路径不得包含符号链接：{relative}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"路径越界：{relative}") from exc
    return candidate


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(root: Path, relative: str) -> Path:
    path = resolve_fixed(root, relative)
    if not path.is_file() or path.stat().st_size == 0:
        raise ContractError(f"缺少或为空的阶段缓存：{relative}")
    return path


def expected_tsv_header(relative: str) -> list[str] | None:
    expected = TSV_HEADERS.get(relative)
    if expected is not None:
        return expected
    if re.fullmatch(r"stages/phase-3/diagrams/D[1-9][0-9]*-result\.tsv", relative):
        return DIAGRAM_RESULT_HEADER
    if re.fullmatch(r"stages/phase-4/visual/D[1-9][0-9]*-review\.tsv", relative):
        return REVIEW_RESULT_HEADER
    return None


def validate_tsv_header(root: Path, relative: str) -> None:
    expected = expected_tsv_header(relative)
    if expected is None:
        return
    path = require_file(root, relative)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        actual = next(reader, [])
        for row_number, row in enumerate(reader, start=2):
            if len(row) != len(expected):
                raise ContractError(f"TSV 第 {row_number} 行列数不符合合同：{relative}")
            for value in row:
                if "\n" in value or "\r" in value:
                    raise ContractError(f"TSV 单元格不得包含真实换行：{relative}:{row_number}")
                if len(value) > 4096:
                    raise ContractError(f"TSV 单元格超过 4096 字符：{relative}:{row_number}")
                stripped = value.strip()
                if stripped.startswith(("{", "[")):
                    try:
                        nested = json.loads(stripped)
                    except json.JSONDecodeError:
                        nested = None
                    if isinstance(nested, (dict, list)):
                        raise ContractError(f"TSV 单元格不得嵌套 JSON：{relative}:{row_number}")
    if actual != expected:
        raise ContractError(f"TSV 表头不符合合同：{relative}")


def validate_task_file(root: Path, relative: str) -> None:
    is_dynamic = re.fullmatch(
        r"stages/agents/(?:diagram-D[1-9][0-9]*|visual-review-D[1-9][0-9]*)-task\.md",
        relative,
    )
    if relative not in TASK_FILES and is_dynamic is None:
        return
    path = require_file(root, relative)
    if path.stat().st_size > MAX_TASK_BYTES:
        raise ContractError(f"subagent 任务文件超过 12 KiB：{relative}")
    lines = path.read_text(encoding="utf-8").splitlines()
    expected_headings = ["## 输入", "## 需要判断", "## 返回"]
    headings = [line for line in lines if line.startswith("## ")]
    if headings != expected_headings:
        raise ContractError(f"subagent 任务文件章节不符合合同：{relative}")


def validate_json_file(root: Path, relative: str) -> None:
    if relative not in JSON_FILES:
        return
    path = require_file(root, relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"JSON 阶段缓存无法解析：{relative}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON 阶段缓存顶层必须是对象：{relative}")


def load_json_object(root: Path, relative: str) -> dict[str, object]:
    path = require_file(root, relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"JSON 阶段缓存无法解析：{relative}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON 阶段缓存顶层必须是对象：{relative}")
    return value


def validate_diagram_id(raw: object, context: str) -> str:
    if not isinstance(raw, str) or DIAGRAM_ID_PATTERN.fullmatch(raw) is None:
        raise ContractError(f"图示编号不符合 D1...Dn 合同：{context}")
    return raw


def validate_continuous_diagram_ids(ids: list[str], context: str) -> tuple[str, ...]:
    if len(ids) != len(set(ids)):
        raise ContractError(f"图示编号重复：{context}")
    if not 2 <= len(ids) <= 8:
        raise ContractError(f"图示数量必须为 2 至 8：{context}")
    ordered = sorted(ids, key=lambda item: int(DIAGRAM_ID_PATTERN.fullmatch(item).group(1)))
    expected = [f"D{index}" for index in range(1, len(ids) + 1)]
    if ordered != expected:
        raise ContractError(f"图示编号必须从 D1 连续且不得断号：{context}")
    return tuple(expected)


def load_diagram_plan(root: Path) -> tuple[tuple[str, ...], dict[str, str]]:
    relative = "stages/phase-3/diagram-plan.json"
    plan = load_json_object(root, relative)
    diagrams = plan.get("diagrams")
    if not isinstance(diagrams, list):
        raise ContractError(f"图示计划 diagrams 必须是数组：{relative}")
    ids: list[str] = []
    output_dirs: dict[str, str] = {}
    for index, item in enumerate(diagrams):
        context = f"{relative}:diagrams[{index}]"
        if not isinstance(item, dict):
            raise ContractError(f"图示计划条目必须是对象：{context}")
        diagram_id = validate_diagram_id(item.get("diagram_id"), f"{context}.diagram_id")
        purpose = item.get("purpose")
        if not isinstance(purpose, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]*", purpose) is None:
            raise ContractError(f"图示 purpose 必须是小写连字符标识：{context}.purpose")
        output_dir = item.get("output_dir")
        if not isinstance(output_dir, str):
            raise ContractError(f"图示计划缺少 output_dir：{context}")
        validate_package_relative_path(output_dir, relative, index + 1)
        expected_dir = f"disclosure-workspace/diagrams/{diagram_id}-{purpose}"
        if output_dir != expected_dir:
            raise ContractError(f"图示 output_dir 必须等于 {expected_dir}：{context}")
        ids.append(diagram_id)
        output_dirs[diagram_id] = output_dir
    ordered_ids = validate_continuous_diagram_ids(ids, relative)
    if len(output_dirs) != len(ordered_ids):
        raise ContractError(f"图示 output_dir 不得重复绑定：{relative}")
    return ordered_ids, output_dirs


def load_review_plan_ids(root: Path) -> tuple[str, ...]:
    relative = "stages/phase-4/review-plan.json"
    plan = load_json_object(root, relative)
    artifacts = plan.get("diagrams")
    if not isinstance(artifacts, list):
        raise ContractError(f"终审计划 diagrams 必须是数组：{relative}")
    ids: list[str] = []
    for index, item in enumerate(artifacts):
        raw = item
        if isinstance(item, dict):
            raw = item.get("diagram_id", item.get("artifact_id", item.get("id")))
        if isinstance(raw, str) and DIAGRAM_ID_PATTERN.fullmatch(raw):
            ids.append(raw)
        else:
            raise ContractError(f"终审计划含非法图示编号：{relative}:diagrams[{index}]")
    if len(ids) != len(set(ids)):
        raise ContractError(f"终审计划图示编号重复：{relative}")
    return tuple(sorted(ids, key=lambda item: int(DIAGRAM_ID_PATTERN.fullmatch(item).group(1))))


def read_tsv_rows(root: Path, relative: str) -> list[dict[str, str]]:
    validate_tsv_header(root, relative)
    path = require_file(root, relative)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def validate_package_relative_path(value: str, relative: str, row_number: int) -> None:
    path = Path(value)
    first_part = path.parts[0] if path.parts else ""
    if (
        not value.strip()
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or ":" in first_part
        or value.startswith("~")
    ):
        raise ContractError(f"工件路径必须是包内相对路径：{relative}:{row_number}")


def validate_sha256(value: str, relative: str, row_number: int, field: str) -> None:
    if SHA256_PATTERN.fullmatch(value) is None:
        raise ContractError(f"{field} 必须是 64 位小写十六进制 SHA-256：{relative}:{row_number}")


def validate_diagram_artifact_row(
    row: dict[str, str],
    diagram_id: str,
    relative: str,
    row_number: int,
) -> None:
    path = row["path"]
    parts = Path(path).parts
    has_diagram_prefix = (
        len(parts) >= 2
        and parts[0] == "diagrams"
        and parts[1].startswith(f"{diagram_id}-")
    ) or (
        len(parts) >= 3
        and parts[0] == "disclosure-workspace"
        and parts[1] == "diagrams"
        and parts[2].startswith(f"{diagram_id}-")
    )
    if not has_diagram_prefix:
        raise ContractError(f"D 行 path 必须落入对应图示独占目录：{relative}:{row_number}:{diagram_id}")
    validate_sha256(row.get("sha256", ""), relative, row_number, "sha256")
    if row.get("owner") not in {"patent_diagram_engineer", "main_agent"}:
        raise ContractError(f"D 行 owner 不符合制图职责：{relative}:{row_number}:{diagram_id}")
    if row.get("status") != "ready":
        raise ContractError(f"D 行 status 必须为 ready：{relative}:{row_number}:{diagram_id}")


def diagram_rows(
    root: Path,
    relative: str,
    *,
    allow_other_artifacts: bool,
    expected_review_type: str | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    rows = read_tsv_rows(root, relative)
    if not rows:
        raise ContractError(f"TSV 必须包含至少一行结果：{relative}")
    ids: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        artifact_id = row["artifact_id"]
        if "path" in row:
            validate_package_relative_path(row["path"], relative, row_number)
        match = DIAGRAM_ID_PATTERN.fullmatch(artifact_id)
        if match is None:
            if not allow_other_artifacts:
                raise ContractError(f"逐图结果只允许 D 编号：{relative}:{row_number}")
            continue
        ids.append(artifact_id)
        if "path" in row:
            validate_diagram_artifact_row(row, artifact_id, relative, row_number)
        if expected_review_type is not None and row.get("review_type") != expected_review_type:
            raise ContractError(f"逐图复核类型必须为 {expected_review_type}：{relative}:{row_number}")
        if expected_review_type is not None:
            if row.get("status") != "pass":
                raise ContractError(f"逐图复核 status 必须为 pass：{relative}:{row_number}")
            validate_sha256(row.get("bound_sha256", ""), relative, row_number, "bound_sha256")
    if len(ids) != len(set(ids)):
        raise ContractError(f"逐图结果含重复 D 编号：{relative}")
    return ids, rows


def rows_by_diagram_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {
        row["artifact_id"]: row
        for row in rows
        if DIAGRAM_ID_PATTERN.fullmatch(row["artifact_id"]) is not None
    }


def validate_semantic_join(root: Path, aggregate_rows: list[dict[str, str]]) -> None:
    relative = "stages/phase-4/semantic-review.tsv"
    source_rows = read_tsv_rows(root, relative)
    if not source_rows:
        raise ContractError(f"语义复核结果不得为空：{relative}")

    fields = ("artifact_id", "review_type", "status", "bound_sha256", "conclusion")

    def normalized(rows: list[dict[str, str]], label: str) -> set[tuple[str, ...]]:
        values: list[tuple[str, ...]] = []
        for row_number, row in enumerate(rows, start=2):
            if row.get("review_type") != "semantic":
                raise ContractError(f"语义复核结果只允许 semantic 类型：{label}:{row_number}")
            if not row.get("artifact_id"):
                raise ContractError(f"语义复核 artifact_id 不得为空：{label}:{row_number}")
            if row.get("status") != "pass":
                raise ContractError(f"语义复核 status 必须为 pass：{label}:{row_number}")
            validate_sha256(row.get("bound_sha256", ""), label, row_number, "bound_sha256")
            values.append(tuple(row.get(field, "") for field in fields))
        if len(values) != len(set(values)):
            raise ContractError(f"语义复核结果不得重复：{label}")
        return set(values)

    source = normalized(source_rows, relative)
    aggregate_semantic = [row for row in aggregate_rows if row.get("review_type") == "semantic"]
    aggregate = normalized(aggregate_semantic, "stages/phase-4/review.tsv") if aggregate_semantic else set()
    if source != aggregate:
        raise ContractError("聚合 review.tsv 未完整汇合 semantic-review.tsv")


def scan_dynamic_ids(
    root: Path,
    directory_relative: str,
    pattern: re.Pattern[str],
) -> tuple[str, ...]:
    directory = resolve_fixed(root, directory_relative)
    if not directory.is_dir():
        raise ContractError(f"缺少逐图任务目录：{directory_relative}")
    ids = []
    for entry in directory.iterdir():
        match = pattern.fullmatch(entry.name)
        if match is None:
            continue
        relative = f"{directory_relative}/{entry.name}"
        require_file(root, relative)
        ids.append(match.group(1))
    return tuple(sorted(ids, key=lambda item: int(DIAGRAM_ID_PATTERN.fullmatch(item).group(1))))


def require_exact_id_set(
    actual: tuple[str, ...] | list[str],
    expected: tuple[str, ...],
    label: str,
) -> None:
    actual_set = set(actual)
    expected_set = set(expected)
    if len(actual) != len(actual_set) or actual_set != expected_set:
        missing = ",".join(sorted(expected_set - actual_set)) or "none"
        extra = ",".join(sorted(actual_set - expected_set)) or "none"
        raise ContractError(f"{label}与图示计划不一致：missing={missing}; extra={extra}")


def validate_phase_3_dynamic_contract(root: Path) -> tuple[str, ...]:
    diagram_ids, output_dirs = load_diagram_plan(root)
    task_ids = scan_dynamic_ids(root, "stages/agents", DYNAMIC_TASK_PATTERNS["phase-3"])
    result_ids = scan_dynamic_ids(root, "stages/phase-3/diagrams", DYNAMIC_RESULT_PATTERNS["phase-3"])
    require_exact_id_set(task_ids, diagram_ids, "逐图任务集合")
    require_exact_id_set(result_ids, diagram_ids, "逐图结果集合")

    dynamic_files: list[str] = []
    instance_rows: dict[str, dict[str, str]] = {}
    for diagram_id in diagram_ids:
        task_relative = f"stages/agents/diagram-{diagram_id}-task.md"
        result_relative = f"stages/phase-3/diagrams/{diagram_id}-result.tsv"
        validate_task_file(root, task_relative)
        ids, rows = diagram_rows(root, result_relative, allow_other_artifacts=False)
        if ids != [diagram_id] or len(rows) != 1:
            raise ContractError(f"逐图结果必须且只能包含 {diagram_id}：{result_relative}")
        instance_rows[diagram_id] = rows[0]
        dynamic_files.extend((task_relative, result_relative))

    aggregate_ids, aggregate_rows = diagram_rows(
        root,
        "stages/phase-3/diagram-result.tsv",
        allow_other_artifacts=False,
    )
    require_exact_id_set(aggregate_ids, diagram_ids, "聚合图示结果集合")
    build_ids, build_rows = diagram_rows(
        root,
        "stages/phase-3/build-map.tsv",
        allow_other_artifacts=True,
    )
    require_exact_id_set(build_ids, diagram_ids, "build map 图示集合")
    aggregate_by_id = rows_by_diagram_id(aggregate_rows)
    build_by_id = rows_by_diagram_id(build_rows)
    for diagram_id in diagram_ids:
        expected_path = output_dirs[diagram_id]
        hashes = {
            instance_rows[diagram_id].get("sha256", ""),
            aggregate_by_id[diagram_id].get("sha256", ""),
            build_by_id[diagram_id].get("sha256", ""),
        }
        if "" in hashes or len(hashes) != 1:
            raise ContractError(f"逐图、聚合结果与 build map 的 hash 不一致：{diagram_id}")
        paths = {
            instance_rows[diagram_id].get("path", ""),
            aggregate_by_id[diagram_id].get("path", ""),
            build_by_id[diagram_id].get("path", ""),
        }
        if paths != {expected_path}:
            raise ContractError(f"逐图、聚合结果与 build map 的 path 未绑定 diagram plan：{diagram_id}")
    return tuple(dynamic_files)


def validate_phase_4_dynamic_contract(root: Path) -> tuple[str, ...]:
    diagram_ids, output_dirs = load_diagram_plan(root)
    build_ids, build_rows = diagram_rows(
        root,
        "stages/phase-3/build-map.tsv",
        allow_other_artifacts=True,
    )
    require_exact_id_set(build_ids, diagram_ids, "build map 图示集合")
    build_by_id = rows_by_diagram_id(build_rows)
    for diagram_id in diagram_ids:
        if build_by_id[diagram_id].get("path") != output_dirs[diagram_id]:
            raise ContractError(f"build map path 未绑定 diagram plan：{diagram_id}")
    review_plan_ids = load_review_plan_ids(root)
    require_exact_id_set(review_plan_ids, diagram_ids, "终审计划图示集合")

    task_ids = scan_dynamic_ids(root, "stages/agents", DYNAMIC_TASK_PATTERNS["phase-4"])
    result_ids = scan_dynamic_ids(root, "stages/phase-4/visual", DYNAMIC_RESULT_PATTERNS["phase-4"])
    require_exact_id_set(task_ids, diagram_ids, "逐图视觉复核任务集合")
    require_exact_id_set(result_ids, diagram_ids, "逐图视觉复核结果集合")

    dynamic_files: list[str] = []
    instance_rows: dict[str, dict[str, str]] = {}
    for diagram_id in diagram_ids:
        task_relative = f"stages/agents/visual-review-{diagram_id}-task.md"
        result_relative = f"stages/phase-4/visual/{diagram_id}-review.tsv"
        validate_task_file(root, task_relative)
        ids, rows = diagram_rows(
            root,
            result_relative,
            allow_other_artifacts=False,
            expected_review_type="visual",
        )
        if ids != [diagram_id] or len(rows) != 1:
            raise ContractError(f"逐图视觉复核结果必须且只能包含 {diagram_id}：{result_relative}")
        instance_rows[diagram_id] = rows[0]
        dynamic_files.extend((task_relative, result_relative))

    aggregate_ids, aggregate_rows = diagram_rows(
        root,
        "stages/phase-4/review.tsv",
        allow_other_artifacts=True,
        expected_review_type="visual",
    )
    require_exact_id_set(aggregate_ids, diagram_ids, "聚合视觉复核结果集合")
    if any(row.get("review_type") not in {"semantic", "visual"} for row in aggregate_rows):
        raise ContractError("聚合 review.tsv 只允许 semantic / visual 类型")
    validate_semantic_join(root, aggregate_rows)
    aggregate_by_id = rows_by_diagram_id(aggregate_rows)
    for diagram_id in diagram_ids:
        expected_hash = build_by_id[diagram_id].get("sha256", "")
        bound_hashes = {
            instance_rows[diagram_id].get("bound_sha256", ""),
            aggregate_by_id[diagram_id].get("bound_sha256", ""),
        }
        if not expected_hash or "" in bound_hashes or bound_hashes != {expected_hash}:
            raise ContractError(f"逐图视觉复核 hash 未绑定当前 build map：{diagram_id}")
    return tuple(dynamic_files)


def validate_cache_file(root: Path, relative: str) -> Path:
    path = require_file(root, relative)
    validate_tsv_header(root, relative)
    validate_task_file(root, relative)
    validate_json_file(root, relative)
    return path


def cache_digest(root: Path, stage: StageSpec) -> str:
    digest = hashlib.sha256()
    cache_files = set(stage.required_files) - {stage.handoff_path}
    if stage.name == "phase_3_final_drafting":
        cache_files.update(validate_phase_3_dynamic_contract(root))
    elif stage.name == "phase_4_review_delivery":
        cache_files.update(validate_phase_4_dynamic_contract(root))
    for relative in sorted(cache_files):
        path = validate_cache_file(root, relative)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hash_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def validate_handoff(root: Path, stage: StageSpec) -> Path:
    path = require_file(root, stage.handoff_path)
    if path.stat().st_size > MAX_HANDOFF_BYTES:
        raise ContractError(f"handoff 超过 24 KiB：{stage.handoff_path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    expected = [
        "handoff_version: 1",
        f"from_stage: {stage.name}",
        f"to_stage: {stage.to_stage}",
        f"status: {stage.status}",
    ]
    if lines[:4] != expected:
        raise ContractError(f"handoff 头不符合合同：{stage.handoff_path}")
    expected_headings = ["## 决策摘要", "## 传递索引", "## 未决项"]
    headings = [line for line in lines[4:] if line.startswith("## ")]
    if headings != expected_headings:
        raise ContractError(f"handoff 章节不符合合同：{stage.handoff_path}")
    return path


def load_state(root: Path) -> list[dict[str, str]]:
    path = state_path(root)
    if not path.is_file():
        raise ContractError("尚未 init：缺少 stages/stage-state.tsv")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != STATE_HEADER:
            raise ContractError("stage-state.tsv 表头不符合合同")
        rows = list(reader)
    if any(set(row) != set(STATE_HEADER) for row in rows):
        raise ContractError("stage-state.tsv 行字段不完整")
    return rows


def save_state(root: Path, rows: list[dict[str, str]]) -> None:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=".stage-state.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=STATE_HEADER, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def init(root: Path) -> None:
    for relative in (
        "stages/shared", "stages/agents", "stages/phase-1", "stages/phase-2",
        "stages/phase-3", "stages/phase-3/diagrams", "stages/phase-4",
        "stages/phase-4/visual",
    ):
        resolve_fixed(root, relative).mkdir(parents=True, exist_ok=True)
    path = state_path(root)
    if path.exists():
        load_state(root)
        print("stage_handoff=existing")
        return
    save_state(root, [])
    print("stage_handoff=initialized")


def validate_rows(
    root: Path,
    rows: list[dict[str, str]],
    require_complete: bool = False,
) -> list[dict[str, str]]:
    if len(rows) > len(STAGES):
        raise ContractError("stage-state.tsv 阶段数超出合同")
    for index, row in enumerate(rows):
        stage = STAGES[index]
        if row["stage"] != stage.name or row["status"] != stage.status:
            raise ContractError("stage-state.tsv 阶段顺序或状态不符合合同")
        if row["input_path"] != stage.input_path or row["handoff_path"] != stage.handoff_path:
            raise ContractError(f"阶段路径链不符合合同：{stage.name}")
        input_path = require_file(root, row["input_path"])
        handoff_path = validate_handoff(root, stage)
        if hash_file(input_path) != row["input_sha256"]:
            raise ContractError(f"阶段输入 hash 已变化：{stage.name}")
        if cache_digest(root, stage) != row["cache_sha256"]:
            raise ContractError(f"阶段缓存 hash 已变化：{stage.name}")
        if hash_file(handoff_path) != row["handoff_sha256"]:
            raise ContractError(f"handoff hash 已变化：{stage.name}")
        if index > 0 and row["input_sha256"] != rows[index - 1]["handoff_sha256"]:
            raise ContractError(f"跨阶段 hash 断链：{stage.name}")
    if require_complete and len(rows) != len(STAGES):
        raise ContractError(f"阶段链不完整：{len(rows)}/{len(STAGES)}")
    return rows


def validate_state(root: Path, require_complete: bool = False) -> list[dict[str, str]]:
    return validate_rows(root, load_state(root), require_complete=require_complete)


def seal(root: Path, stage_name: str) -> None:
    rows = load_state(root)
    stage = STAGE_BY_NAME[stage_name]
    index = STAGES.index(stage)
    if index > len(rows):
        raise ContractError(f"前置阶段尚未封存：{STAGES[index - 1].name}")
    if len(rows) > len(STAGES) or any(
        row["stage"] != STAGES[row_index].name for row_index, row in enumerate(rows)
    ):
        raise ContractError("stage-state.tsv 阶段顺序不符合合同")
    input_path = require_file(root, stage.input_path)
    handoff_path = validate_handoff(root, stage)
    new_row = {
        "stage": stage.name,
        "status": stage.status,
        "input_path": stage.input_path,
        "input_sha256": hash_file(input_path),
        "cache_sha256": cache_digest(root, stage),
        "handoff_path": stage.handoff_path,
        "handoff_sha256": hash_file(handoff_path),
        "sealed_at": datetime.now(timezone.utc).isoformat(),
    }
    invalidated = []
    if index < len(rows):
        previous = rows[index]
        changed = any(
            previous[field] != new_row[field]
            for field in (
                "status", "input_path", "input_sha256", "cache_sha256",
                "handoff_path", "handoff_sha256",
            )
        )
        if changed:
            validate_rows(root, rows[:index])
            invalidated = [row["stage"] for row in rows[index + 1 :]]
            rows = rows[:index] + [new_row]
        else:
            validate_rows(root, rows)
            rows[index]["sealed_at"] = new_row["sealed_at"]
    else:
        validate_rows(root, rows)
        rows.append(new_row)
    save_state(root, rows)
    print(f"sealed={stage.name}")
    print(f"invalidated={','.join(invalidated) if invalidated else 'none'}")


def rewind(root: Path, stage_name: str) -> None:
    rows = load_state(root)
    stage = STAGE_BY_NAME[stage_name]
    index = STAGES.index(stage)
    if len(rows) > len(STAGES):
        raise ContractError("stage-state.tsv 阶段数超出合同")
    if index > len(rows):
        raise ContractError(f"回退阶段尚不可达：{stage.name}")

    retained = rows[:index]
    validate_rows(root, retained)
    invalidated = [STAGES[row_index].name for row_index in range(index, len(rows))]
    if invalidated:
        save_state(root, retained)

    print(f"rewound={stage.name}")
    print(f"invalidated={','.join(invalidated) if invalidated else 'none'}")
    print(f"valid_stages={len(retained)}")
    print(f"next_stage={stage.name}")


def status(root: Path) -> None:
    rows = validate_state(root)
    if not rows:
        print("last_stage=none")
        print(f"next_stage={STAGES[0].name}")
        print(f"next_input={STAGES[0].input_path}")
        return
    last = rows[-1]
    print(f"last_stage={last['stage']}")
    if len(rows) == len(STAGES):
        print("next_stage=delivery")
        print(f"next_input={last['handoff_path']}")
    else:
        next_stage = STAGES[len(rows)]
        print(f"next_stage={next_stage.name}")
        print(f"next_input={next_stage.input_path}")


def main() -> int:
    args = parse_args()
    try:
        root = working_root(args.working)
        if args.command == "init":
            init(root)
        elif args.command == "seal":
            seal(root, args.stage)
        elif args.command == "rewind":
            rewind(root, args.stage)
        elif args.command == "status":
            status(root)
        elif args.command == "validate":
            rows = validate_state(root, require_complete=args.require_complete)
            print(f"valid_stages={len(rows)}")
        return 0
    except (ContractError, OSError, UnicodeError, csv.Error) as exc:
        print(f"stage_handoff_error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
