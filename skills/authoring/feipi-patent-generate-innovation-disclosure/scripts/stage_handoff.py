#!/usr/bin/env python3
"""Manage compact, hash-bound stage handoffs for patent disclosure sessions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
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
            "stages/agents/prior-art-task.md",
            "stages/phase-1/model.md",
            "stages/phase-1/research.tsv",
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
            "stages/agents/diagram-task.md",
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
            "stages/agents/final-review-task.md",
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
    "stages/phase-3/build-map.tsv": [
        "artifact_id", "path", "sha256", "owner", "status",
    ],
    "stages/phase-4/review.tsv": [
        "artifact_id", "review_type", "status", "bound_sha256", "conclusion",
    ],
}
TASK_FILES = {
    "stages/agents/prior-art-task.md",
    "stages/agents/diagram-task.md",
    "stages/agents/final-review-task.md",
}


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
    seal = subparsers.add_parser("seal")
    seal.add_argument("--working", required=True, help="disclosure-workspace/working 路径")
    seal.add_argument("--stage", required=True, choices=tuple(STAGE_BY_NAME))
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
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"路径越界：{relative}") from exc
    if candidate.is_symlink():
        raise ContractError(f"缓存文件不得是符号链接：{relative}")
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


def validate_tsv_header(root: Path, relative: str) -> None:
    expected = TSV_HEADERS.get(relative)
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
    if relative not in TASK_FILES:
        return
    path = require_file(root, relative)
    if path.stat().st_size > MAX_TASK_BYTES:
        raise ContractError(f"subagent 任务文件超过 12 KiB：{relative}")
    lines = path.read_text(encoding="utf-8").splitlines()
    expected_headings = ["## 输入", "## 需要判断", "## 返回"]
    headings = [line for line in lines if line.startswith("## ")]
    if headings != expected_headings:
        raise ContractError(f"subagent 任务文件章节不符合合同：{relative}")


def validate_cache_file(root: Path, relative: str) -> Path:
    path = require_file(root, relative)
    validate_tsv_header(root, relative)
    validate_task_file(root, relative)
    return path


def cache_digest(root: Path, stage: StageSpec) -> str:
    digest = hashlib.sha256()
    for relative in sorted(set(stage.required_files) - {stage.handoff_path}):
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
        "stages/phase-3", "stages/phase-4",
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
