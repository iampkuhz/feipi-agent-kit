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
from urllib.parse import urlparse


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
MAX_TASK_INPUT_BYTES = 12 * 1024


@dataclass(frozen=True)
class StageSpec:
    name: str
    status: str
    input_path: str
    handoff_path: str
    to_stage: str
    required_files: tuple[str, ...]


@dataclass(frozen=True)
class TaskSpec:
    task_type: str
    role: str
    checkpoint: str
    result: str
    minimum_check: str
    instruction_refs: tuple[str, ...]
    skill_dependencies: tuple[str, ...]
    allowed_writes: tuple[str, ...]
    judgment_contract_id: str
    return_contract_id: str
    result_owner: str = "main_agent"


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
FIXED_TASK_SPECS = {
    "stages/agents/subject-boundary-task.md": TaskSpec(
        "subject-boundary",
        "patent_subject_boundary_analyst",
        "phase-1-subject-boundary",
        "disclosure-workspace/working/stages/phase-1/subject-boundary.tsv",
        "tsv",
        ("references/roles/subject-boundary.md",),
        (),
        (),
        "JUDGMENT-SUBJECT-BOUNDARY-V1",
        "RETURN-SUBJECT-BOUNDARY-TSV-V1",
    ),
    "stages/agents/prior-art-object-task.md": TaskSpec(
        "prior-art-object",
        "patent_prior_art_researcher",
        "phase-1-research-object",
        "disclosure-workspace/working/stages/phase-1/research-object.tsv",
        "tsv",
        ("references/roles/prior-art-research.md",),
        (),
        (),
        "JUDGMENT-PRIOR-ART-OBJECT-V1",
        "RETURN-PRIOR-ART-OBJECT-TSV-V1",
    ),
    "stages/agents/prior-art-mechanism-task.md": TaskSpec(
        "prior-art-mechanism",
        "patent_prior_art_researcher",
        "phase-1-research-mechanism",
        "disclosure-workspace/working/stages/phase-1/research-mechanism.tsv",
        "tsv",
        ("references/roles/prior-art-research.md",),
        (),
        (),
        "JUDGMENT-PRIOR-ART-MECHANISM-V1",
        "RETURN-PRIOR-ART-MECHANISM-TSV-V1",
    ),
    "stages/agents/innovation-value-task.md": TaskSpec(
        "innovation-value",
        "patent_innovation_value_analyst",
        "phase-1-innovation-candidates",
        "disclosure-workspace/working/stages/phase-1/innovation-candidates.tsv",
        "tsv",
        ("references/roles/innovation-value.md",),
        (),
        (),
        "JUDGMENT-INNOVATION-VALUE-V1",
        "RETURN-INNOVATION-VALUE-TSV-V1",
    ),
    "stages/agents/semantic-review-task.md": TaskSpec(
        "semantic-review",
        "patent_semantic_reviewer",
        "phase-4-semantic-review",
        "disclosure-workspace/working/stages/phase-4/semantic-review.tsv",
        "tsv",
        ("references/reviews/semantic-review.md",),
        (),
        (),
        "JUDGMENT-SEMANTIC-REVIEW-V1",
        "RETURN-SEMANTIC-REVIEW-TSV-V1",
    ),
}
TASK_FILES = set(FIXED_TASK_SPECS)
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
TASK_FIELD_NAMES = (
    "contract_version",
    "task_type",
    "role",
    "checkpoint",
    "result",
    "result_owner",
    "minimum_check",
    "timing",
    "关键事件",
    "允许写入",
    "本 Skill 资源",
    "依赖 Skill",
    "禁止动作",
)
TASK_REQUIRED_DENY_LINES = (
    "- 只读取上述动态输入；禁止读取完整阶段缓存、原始材料、未列出的会话文件或其他任务的输入切片。",
    "- 除“本 Skill 资源”所列文件外，禁止读取本 Skill 其他资源。",
    "- 除“依赖 Skill”所列 Skill 外，禁止加载其他 Skill。",
)
TASK_RETURN_LINES = (
    "- `result_owner=main_agent` 时，subagent 只返回符合 `minimum_check` 的结构化内容，由主 agent 校验后写入 `result`。",
    "- 只返回结构化结果与一行终态关键事件，不返回日志、正文副本或推理过程。",
)
TASK_TIMING_PATH = "disclosure-workspace/working/session-timing.jsonl"
TASK_EVENT_CONTRACT = "MILESTONE|DECISION|BLOCKED|COMPLETE；仅一行；最多 240 字符"
TASK_FORBIDDEN_ACTIONS = "读取未列输入|写入未授权路径|返回日志或推理过程"
TASK_DYNAMIC_INPUT_PATTERN = re.compile(
    r"^- path：`(?P<path>[^`\r\n]+)`；sha256：`(?P<sha256>[0-9a-f]{64})`$"
)
SEMANTIC_CHECK_IDS = (
    "SEM-IMPLEMENTATION",
    "SEM-SYSTEM-BOUNDARY",
    "SEM-INNOVATION-VALUE",
    "SEM-GENERALIZATION",
    "SEM-CAUSALITY",
    "SEM-FLOW",
    "SEM-KEYWORDS",
    "SEM-EVIDENCE",
    "SEM-PUBLIC-LEAK",
)
FORBIDDEN_RESOURCE_BASENAMES = {
    "SKILL.md",
    "MAINTAINER_HISTORY.md",
    "stage-delivery-contract.md",
    "content-quality-gates.md",
    "checkpoint-task-catalog.json",
}
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
RAW_TASK_TOKEN_PATTERN = re.compile(r"[^\s`]+")
ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_.:/-])(/[A-Za-z0-9_./{}*?\[\]~-]+)")
WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z]:\\[^\s`]+)")
BARE_SKILL_RESOURCE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"(?:references|assets|agents|handbook|cases|schemas?|scripts)/"
    r"[A-Za-z0-9_./{}*?\[\]-]+"
)
DEPENDENCY_SKILL_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])\$?(feipi-[a-z0-9-]+)")
HTTP_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
RECEIPT_VERSION = 1
SLICE_VERSION = 1
PHASE_1_SOURCE_SETS = {
    "subject-boundary": (
        "disclosure-workspace/working/stages/shared/material-index.tsv",
        "disclosure-workspace/working/stages/shared/evidence-cards.md",
        "disclosure-workspace/working/stages/phase-1/analysis-plan.json",
    ),
    "prior-art-object": (
        "disclosure-workspace/working/stages/shared/material-index.tsv",
        "disclosure-workspace/working/stages/shared/evidence-cards.md",
        "disclosure-workspace/working/stages/phase-1/analysis-plan.json",
    ),
    "prior-art-mechanism": (
        "disclosure-workspace/working/stages/shared/material-index.tsv",
        "disclosure-workspace/working/stages/shared/evidence-cards.md",
        "disclosure-workspace/working/stages/phase-1/analysis-plan.json",
    ),
    "innovation-value": (
        "disclosure-workspace/working/stages/shared/evidence-cards.md",
        "disclosure-workspace/working/stages/phase-1/delivery-goals.md",
        "disclosure-workspace/working/stages/phase-1/subject-boundary.tsv",
        "disclosure-workspace/working/stages/phase-1/research.tsv",
    ),
}
DIAGRAM_SOURCE_SET = (
    "disclosure-workspace/working/stages/phase-3/content-core.json",
    "disclosure-workspace/working/stages/phase-3/diagram-plan.json",
)
DIAGRAM_RENDERER_PREFLIGHT = "stages/phase-3/renderer-preflight.json"


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
    validate_task_parser = subparsers.add_parser("validate-task")
    validate_task_parser.add_argument("--working", required=True, help="disclosure-workspace/working 路径")
    validate_task_parser.add_argument(
        "--task",
        required=True,
        help="相对 working 的 stages/agents/*-task.md 路径",
    )
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


def task_error(rule_id: str, message: str) -> ContractError:
    return ContractError(f"[{rule_id}] {message}")


def task_spec_for(root: Path, relative: str) -> TaskSpec:
    fixed = FIXED_TASK_SPECS.get(relative)
    if fixed is not None:
        return fixed

    diagram_match = re.fullmatch(r"stages/agents/diagram-(D[1-9][0-9]*)-task\.md", relative)
    visual_match = re.fullmatch(r"stages/agents/visual-review-(D[1-9][0-9]*)-task\.md", relative)
    if diagram_match is None and visual_match is None:
        raise task_error("TASK-001", f"未注册的 subagent 任务类型：{relative}")

    diagram_id = (diagram_match or visual_match).group(1)
    diagram_ids, output_dirs = load_diagram_plan(root)
    if diagram_id not in diagram_ids:
        raise task_error("TASK-002", f"动态任务未绑定当前图示计划：{relative}:{diagram_id}")
    if diagram_match is not None:
        output_dir = output_dirs[diagram_id]
        return TaskSpec(
            "diagram",
            "patent_diagram_engineer",
            f"phase-3-diagram-{diagram_id}",
            f"disclosure-workspace/working/stages/phase-3/diagrams/{diagram_id}-result.tsv",
            "tsv",
            ("references/roles/diagram-engineer.md",),
            ("feipi-plantuml-generate-diagram",),
            (f"{output_dir}/",),
            f"JUDGMENT-DIAGRAM-{diagram_id}-V1",
            f"RETURN-DIAGRAM-{diagram_id}-TSV-V1",
        )
    return TaskSpec(
        "visual-review",
        "patent_visual_reviewer",
        f"phase-4-visual-review-{diagram_id}",
        f"disclosure-workspace/working/stages/phase-4/visual/{diagram_id}-review.tsv",
        "tsv",
        ("references/reviews/visual-review.md",),
        (),
        (),
        f"JUDGMENT-VISUAL-REVIEW-{diagram_id}-V1",
        f"RETURN-VISUAL-REVIEW-{diagram_id}-TSV-V1",
    )


def task_diagram_id(relative: str) -> str | None:
    match = re.fullmatch(
        r"stages/agents/(?:diagram-|visual-review-)(D[1-9][0-9]*)-task\.md",
        relative,
    )
    return match.group(1) if match else None


def task_field_value(items: tuple[str, ...]) -> str:
    return "|".join(items) if items else "无"


def parse_task_fields(lines: list[str], relative: str) -> dict[str, str]:
    metadata_lines = lines[: lines.index("## 输入")] if "## 输入" in lines else lines
    fields: dict[str, str] = {}
    for name in TASK_FIELD_NAMES:
        prefix = f"- {name}: `"
        matches = [line for line in metadata_lines if line.startswith(prefix)]
        if len(matches) != 1 or not matches[0].endswith("`"):
            raise task_error("TASK-001", f"subagent 任务文件字段缺失或重复：{relative}:{name}")
        fields[name] = matches[0][len(prefix) : -1]
    field_lines = [line for line in metadata_lines if line.startswith("- ") and ": `" in line]
    known_field_lines = {f"- {name}: `{fields[name]}`" for name in TASK_FIELD_NAMES}
    unexpected = [line for line in field_lines if line not in known_field_lines]
    if unexpected:
        raise task_error("TASK-001", f"subagent 任务文件含未注册元数据字段：{relative}")
    return fields


def task_path_tokens(text: str) -> set[str]:
    tokens = {match.group(1).strip() for match in INLINE_CODE_PATTERN.finditer(text)}
    tokens.update(match.group(1) for match in ABSOLUTE_PATH_PATTERN.finditer(text))
    tokens.update(match.group(1) for match in WINDOWS_ABSOLUTE_PATH_PATTERN.finditer(text))
    tokens.update(match.group(0).rstrip(".,;:，。；：") for match in BARE_SKILL_RESOURCE_PATTERN.finditer(text))
    tokens.update(
        match.group(0).strip("'\"<>(),，。；：")
        for match in RAW_TASK_TOKEN_PATTERN.finditer(text)
        if "/" in match.group(0) or "\\" in match.group(0)
    )
    return tokens


def validate_task_reference_safety(
    text: str,
    relative: str,
    allowed_paths: set[str],
) -> None:
    lowered = text.lower()
    if "file:/" in lowered or "file：/" in lowered:
        raise task_error("TASK-005", f"subagent 任务文件禁止 file URI：{relative}")
    if "／" in text or "＼" in text:
        raise task_error("TASK-005", f"subagent 任务文件禁止全角斜杠：{relative}")
    tokens = task_path_tokens(text)
    path_tokens: list[str] = []
    for token in sorted(tokens):
        if token.startswith(("http://", "https://")):
            continue
        is_path_reference = (
            "/" in token
            or "\\" in token
            or token.startswith((".", "~"))
            or re.match(r"^[A-Za-z]:", token) is not None
            or Path(token).suffix.lower() in {".md", ".json", ".tsv", ".yaml", ".yml", ".svg", ".puml"}
        )
        if not is_path_reference:
            continue
        path_tokens.append(token)
        path = Path(token)
        if path.is_absolute() or token.startswith("~") or re.match(r"^[A-Za-z]:", token):
            raise task_error("TASK-005", f"subagent 任务文件禁止绝对路径：{relative}:{token}")
        if ".." in path.parts or "\\" in token:
            raise task_error("TASK-005", f"subagent 任务文件禁止路径越界：{relative}:{token}")
        if any(marker in token for marker in ("*", "?", "[", "]")):
            raise task_error("TASK-005", f"subagent 任务文件禁止通配符：{relative}:{token}")
        is_broad_task_directory = (
            re.match(
                r"^(?:disclosure-workspace|stages|references|assets|agents|handbook|cases|schemas?|scripts)(?:/|$)",
                token,
            )
            is not None
            and not path.suffix
        )
        if (token.endswith("/") or is_broad_task_directory) and token not in allowed_paths:
            raise task_error("TASK-005", f"subagent 任务文件禁止目录级宽泛引用：{relative}:{token}")
    for token in path_tokens:
        if token not in allowed_paths:
            raise task_error("TASK-003", f"subagent 任务文件引用了未授权路径：{relative}:{token}")


def validate_disclosure_relative_path(value: str, relative: str) -> None:
    lowered = value.lower()
    path = Path(value)
    first = path.parts[0] if path.parts else ""
    if "file:/" in lowered or "file：/" in lowered:
        raise task_error("TASK-005", f"动态输入禁止 file URI：{relative}:{value}")
    if "／" in value or "＼" in value:
        raise task_error("TASK-005", f"动态输入禁止全角斜杠：{relative}:{value}")
    if (
        not value
        or path.is_absolute()
        or value.startswith("~")
        or ".." in path.parts
        or "\\" in value
        or ":" in first
    ):
        raise task_error("TASK-005", f"动态输入必须是相对 disclosure-dir 的安全路径：{relative}:{value}")
    if any(marker in value for marker in ("*", "?", "[", "]")):
        raise task_error("TASK-005", f"动态输入禁止通配符：{relative}:{value}")
    if value.endswith("/") or not path.suffix:
        raise task_error("TASK-005", f"动态输入禁止目录级宽泛引用：{relative}:{value}")


def disclosure_file(root: Path, value: str, relative: str) -> Path:
    validate_disclosure_relative_path(value, relative)
    disclosure_dir = root.parent.parent
    if value == "disclosure.md":
        candidate = disclosure_dir / value
        path_parts = Path(value).parts
    elif value.startswith("disclosure-workspace/"):
        candidate = disclosure_dir / value
        path_parts = Path(value).parts
    else:
        raise task_error("TASK-004", f"动态输入路径不在 disclosure-dir 允许根：{relative}:{value}")
    cursor = disclosure_dir
    for part in path_parts:
        cursor /= part
        if cursor.is_symlink():
            raise task_error("TASK-004", f"动态输入不得为符号链接：{relative}:{value}")
    try:
        candidate.resolve().relative_to(disclosure_dir.resolve())
    except ValueError as exc:
        raise task_error("TASK-004", f"动态输入路径越界：{relative}:{value}") from exc
    if not candidate.is_file() or candidate.stat().st_size == 0:
        raise task_error("TASK-004", f"动态输入缺失、为空或非普通文件：{relative}:{value}")
    if candidate.stat().st_nlink != 1:
        raise task_error("TASK-004", f"动态输入不得为硬链接：{relative}:{value}")
    return candidate


def normalized_file_set_digest(root: Path, paths: tuple[str, ...] | list[str], relative: str) -> str:
    if len(paths) != len(set(paths)):
        raise task_error("TASK-004", f"规范化输入集合不得包含重复路径：{relative}")
    digest = hashlib.sha256()
    for value in sorted(paths):
        path = disclosure_file(root, value, relative)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hash_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_slice_envelope(path: Path, relative: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise task_error("TASK-004", f"动态输入切片必须是 JSON envelope：{relative}") from exc
    if not isinstance(value, dict):
        raise task_error("TASK-004", f"动态输入切片顶层必须是对象：{relative}")
    return value


def validate_slice_envelope(
    root: Path,
    relative: str,
    spec: TaskSpec,
    path_value: str,
    path: Path,
) -> None:
    if spec.task_type not in PHASE_1_SOURCE_SETS and spec.task_type != "diagram":
        return
    envelope = load_slice_envelope(path, relative)
    expected: dict[str, object] = {
        "slice_version": SLICE_VERSION,
        "task_type": spec.task_type,
        "role": spec.role,
        "checkpoint": spec.checkpoint,
    }
    if spec.task_type in PHASE_1_SOURCE_SETS:
        source_paths = PHASE_1_SOURCE_SETS[spec.task_type]
    else:
        source_paths = DIAGRAM_SOURCE_SET
        diagram_id = task_diagram_id(relative)
        _, output_dirs = load_diagram_plan(root)
        expected.update(
            {
                "diagram_id": diagram_id,
                "purpose": Path(output_dirs[diagram_id]).name.removeprefix(f"{diagram_id}-"),
                "diagram_plan_sha256": hash_file(
                    require_file(root, "stages/phase-3/diagram-plan.json")
                ),
            }
        )
    expected["source_set_sha256"] = normalized_file_set_digest(root, source_paths, relative)
    for name, expected_value in expected.items():
        if envelope.get(name) != expected_value:
            raise task_error(
                "TASK-004",
                f"动态输入 JSON envelope 未绑定当前任务或上游集合：{relative}:{path_value}:{name}",
            )
    if not isinstance(envelope.get("payload"), dict):
        raise task_error("TASK-004", f"动态输入 JSON envelope payload 必须是对象：{relative}:{path_value}")
    if spec.task_type == "diagram":
        payload = envelope["payload"]
        assert isinstance(payload, dict)
        preflight_path = require_file(root, DIAGRAM_RENDERER_PREFLIGHT)
        try:
            preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise task_error("TASK-004", "renderer preflight receipt 必须是合法 JSON") from exc
        renderer_url = preflight.get("renderer_url") if isinstance(preflight, dict) else None
        parsed = urlparse(renderer_url) if isinstance(renderer_url, str) else None
        if (
            not isinstance(preflight, dict)
            or preflight.get("final_status") != "success"
            or preflight.get("process_management_allowed") is not False
            or preflight.get("startup_policy") != "podman_once"
            or parsed is None
            or parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise task_error("TASK-004", "renderer preflight receipt 未绑定可用 loopback renderer")
        if payload.get("renderer_url") != renderer_url:
            raise task_error("TASK-004", "逐图 payload.renderer_url 与 preflight receipt 不一致")
        if payload.get("renderer_preflight_sha256") != hash_file(preflight_path):
            raise task_error("TASK-004", "逐图 payload.renderer_preflight_sha256 与 receipt 不一致")


def expected_dynamic_inputs(root: Path, relative: str, spec: TaskSpec) -> tuple[str, ...] | re.Pattern[str]:
    if spec.task_type in {
        "subject-boundary", "prior-art-object", "prior-art-mechanism", "innovation-value",
    }:
        escaped = re.escape(spec.task_type)
        return re.compile(
            rf"^disclosure-workspace/working/stages/agents/inputs/{escaped}-input\.json$"
        )
    diagram_id = task_diagram_id(relative)
    if spec.task_type == "diagram":
        return (
            f"disclosure-workspace/working/stages/agents/inputs/diagram-{diagram_id}-input.json",
        )
    if spec.task_type == "semantic-review":
        return (
            "disclosure.md",
            "disclosure-workspace/disclosure-internal.md",
            "disclosure-workspace/disclosure-manifest.json",
            "disclosure-workspace/working/stages/phase-3/handoff.md",
        )
    _, output_dirs = load_diagram_plan(root)
    output_dir = output_dirs[diagram_id]
    return tuple(
        f"{output_dir}/{name}"
        for name in ("brief.normalized.yaml", "diagram.puml", "diagram.svg", "validation.json")
    )


def parse_dynamic_inputs(lines: list[str], relative: str) -> list[tuple[str, str]]:
    try:
        start = lines.index("### 动态输入") + 1
        judgment_start = lines.index("## 需要判断")
        end = next(
            (
                index
                for index in range(start, judgment_start)
                if lines[index].startswith("- 只读取")
            ),
            judgment_start,
        )
    except ValueError as exc:
        raise task_error("TASK-001", f"subagent 任务文件缺少动态输入节：{relative}") from exc
    entries: list[tuple[str, str]] = []
    for line in lines[start:end]:
        if not line.strip():
            continue
        match = TASK_DYNAMIC_INPUT_PATTERN.fullmatch(line)
        if match is None:
            raise task_error("TASK-001", f"动态输入行不符合 path+sha256 合同：{relative}:{line}")
        entries.append((match.group("path"), match.group("sha256")))
    if not entries:
        raise task_error("TASK-001", f"动态输入清单不得为空：{relative}")
    return entries


def validate_dynamic_inputs(
    root: Path,
    relative: str,
    spec: TaskSpec,
    entries: list[tuple[str, str]],
) -> None:
    paths = [path for path, _ in entries]
    if len(paths) != len(set(paths)):
        raise task_error("TASK-004", f"动态输入路径不得重复：{relative}")
    for value in paths:
        validate_disclosure_relative_path(value, relative)
    expected = expected_dynamic_inputs(root, relative, spec)
    if isinstance(expected, re.Pattern):
        if len(paths) != 1 or expected.fullmatch(paths[0]) is None:
            raise task_error("TASK-004", f"Phase 1 任务只允许读取本 task_type 的单个输入切片：{relative}")
    elif tuple(paths) != expected:
        raise task_error("TASK-004", f"动态输入清单不符合 task_type/D 绑定：{relative}")

    for value, declared_hash in entries:
        path = disclosure_file(root, value, relative)
        if spec.task_type in {
            "subject-boundary", "prior-art-object", "prior-art-mechanism", "innovation-value", "diagram",
        } and path.stat().st_size > MAX_TASK_INPUT_BYTES:
            raise task_error("TASK-004", f"动态输入切片超过 12 KiB：{relative}:{value}")
        actual_hash = hash_file(path)
        if declared_hash != actual_hash:
            raise task_error("TASK-004", f"动态输入 sha256 不匹配：{relative}:{value}")
        validate_slice_envelope(root, relative, spec, value, path)


def validate_task_authority(
    text: str,
    lines: list[str],
    fields: dict[str, str],
    spec: TaskSpec,
    relative: str,
    dynamic_paths: set[str],
) -> None:
    if HTTP_URL_PATTERN.search(text):
        raise task_error("TASK-003", f"subagent 任务文件禁止夹带 URL；研究 URL 只能位于 hash slice payload：{relative}")
    expected = {
        "contract_version": "2",
        "task_type": spec.task_type,
        "role": spec.role,
        "checkpoint": spec.checkpoint,
        "result": spec.result,
        "result_owner": spec.result_owner,
        "minimum_check": spec.minimum_check,
        "timing": TASK_TIMING_PATH,
        "关键事件": TASK_EVENT_CONTRACT,
        "允许写入": task_field_value(spec.allowed_writes),
        "本 Skill 资源": task_field_value(spec.instruction_refs),
        "依赖 Skill": task_field_value(spec.skill_dependencies),
        "禁止动作": TASK_FORBIDDEN_ACTIONS,
    }
    for name, value in expected.items():
        if fields.get(name) != value:
            rule_id = "TASK-002" if name in {
                "task_type", "role", "checkpoint", "result", "result_owner", "minimum_check",
            } else "TASK-003"
            raise task_error(rule_id, f"subagent 任务字段未按任务路径绑定：{relative}:{name}")

    for deny_line in TASK_REQUIRED_DENY_LINES:
        if lines.count(deny_line) != 1:
            raise task_error("TASK-003", f"subagent 任务缺少精确禁读声明：{relative}")
    allowed_paths = {
        spec.result,
        TASK_TIMING_PATH,
        *spec.allowed_writes,
        *spec.instruction_refs,
        *dynamic_paths,
    }
    validate_task_reference_safety(text, relative, allowed_paths)
    dependency_names = {match.group(1) for match in DEPENDENCY_SKILL_PATTERN.finditer(text)}
    unexpected_dependencies = dependency_names - set(spec.skill_dependencies)
    if unexpected_dependencies:
        raise task_error(
            "TASK-003",
            f"subagent 任务引用了未授权依赖 Skill：{relative}:{','.join(sorted(unexpected_dependencies))}",
        )
    for dependency in spec.skill_dependencies:
        if text.count(dependency) != 1:
            raise task_error("TASK-003", f"依赖 Skill 只允许在白名单字段声明一次：{relative}:{dependency}")
    for instruction_ref in spec.instruction_refs:
        if text.count(instruction_ref) != 1:
            raise task_error("TASK-003", f"本 Skill 资源只允许在白名单字段声明一次：{relative}:{instruction_ref}")
    for forbidden_name in FORBIDDEN_RESOURCE_BASENAMES:
        if forbidden_name in text and forbidden_name not in allowed_paths:
            raise task_error("TASK-003", f"subagent 任务文件引用了未授权 Skill 资源：{relative}:{forbidden_name}")


def validate_task_contract_sections(lines: list[str], spec: TaskSpec, relative: str) -> None:
    judgment_index = lines.index("## 需要判断")
    return_index = lines.index("## 返回")
    judgment_lines = [line for line in lines[judgment_index + 1 : return_index] if line]
    return_lines = [line for line in lines[return_index + 1 :] if line]
    expected_judgment = [f"- contract_id: `{spec.judgment_contract_id}`"]
    expected_return = [f"- contract_id: `{spec.return_contract_id}`", *TASK_RETURN_LINES]
    if judgment_lines != expected_judgment:
        raise task_error("TASK-001", f"需要判断只允许 TaskSpec 注册的精确 contract_id 行：{relative}")
    if return_lines != expected_return:
        raise task_error("TASK-001", f"返回只允许 TaskSpec 注册的 contract_id 与固定返回说明：{relative}")


def validate_task_file(
    root: Path,
    relative: str,
) -> tuple[TaskSpec, list[tuple[str, str]]] | None:
    is_dynamic = re.fullmatch(
        r"stages/agents/(?:diagram-D[1-9][0-9]*|visual-review-D[1-9][0-9]*)-task\.md",
        relative,
    )
    if relative not in TASK_FILES and is_dynamic is None:
        return None
    path = require_file(root, relative)
    if path.stat().st_size > MAX_TASK_BYTES:
        raise task_error("TASK-001", f"subagent 任务文件超过 12 KiB：{relative}")
    lines = path.read_text(encoding="utf-8").splitlines()
    expected_headings = ["## 输入", "## 需要判断", "## 返回"]
    headings = [line for line in lines if line.startswith("## ")]
    if headings != expected_headings:
        raise task_error("TASK-001", f"subagent 任务文件章节不符合合同：{relative}")
    text = "\n".join(lines)
    spec = task_spec_for(root, relative)
    fields = parse_task_fields(lines, relative)
    entries = parse_dynamic_inputs(lines, relative)
    validate_dynamic_inputs(root, relative, spec, entries)
    validate_task_authority(text, lines, fields, spec, relative, {item[0] for item in entries})
    validate_task_contract_sections(lines, spec, relative)
    return spec, entries


def task_spec_identity(spec: TaskSpec) -> dict[str, object]:
    return {
        "task_type": spec.task_type,
        "role": spec.role,
        "checkpoint": spec.checkpoint,
        "result": spec.result,
        "result_owner": spec.result_owner,
        "minimum_check": spec.minimum_check,
        "instruction_refs": list(spec.instruction_refs),
        "skill_dependencies": list(spec.skill_dependencies),
        "allowed_writes": list(spec.allowed_writes),
        "judgment_contract_id": spec.judgment_contract_id,
        "return_contract_id": spec.return_contract_id,
    }


def dispatch_receipt_relative(relative: str) -> str:
    name = Path(relative).name
    if not re.fullmatch(r"[A-Za-z0-9-]+-task\.md", name):
        raise task_error("TASK-006", f"任务路径无法映射安全 receipt：{relative}")
    return f"stages/agents/receipts/{Path(name).stem}.dispatch.json"


def current_task_receipt(
    root: Path,
    relative: str,
) -> tuple[dict[str, object], TaskSpec]:
    validated = validate_task_file(root, relative)
    if validated is None:
        raise task_error("TASK-006", f"任务未注册，不能生成 receipt：{relative}")
    spec, entries = validated
    paths = [value for value, _ in entries]
    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "task_path": relative,
        "task_sha256": hash_file(require_file(root, relative)),
        "task_spec": task_spec_identity(spec),
        "dynamic_input_set_sha256": normalized_file_set_digest(root, paths, relative),
    }
    return receipt, spec


def save_json_atomic(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_dispatch_receipt(root: Path, relative: str) -> str:
    receipt, _ = current_task_receipt(root, relative)
    receipt["validated_at"] = datetime.now(timezone.utc).isoformat()
    receipt_relative = dispatch_receipt_relative(relative)
    receipt_path = resolve_fixed(root, receipt_relative)
    save_json_atomic(receipt_path, receipt)
    return receipt_relative


def validate_dispatch_receipt(root: Path, relative: str) -> str:
    expected, _ = current_task_receipt(root, relative)
    receipt_relative = dispatch_receipt_relative(relative)
    receipt_path = resolve_fixed(root, receipt_relative)
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise task_error("TASK-006", f"任务尚未 validate-task 或缺少 dispatch receipt：{relative}")
    if receipt_path.stat().st_nlink != 1:
        raise task_error("TASK-006", f"dispatch receipt 不得为硬链接：{relative}")
    try:
        actual = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise task_error("TASK-006", f"dispatch receipt 不是合法 JSON：{relative}") from exc
    if not isinstance(actual, dict) or set(actual) != {*expected, "validated_at"}:
        raise task_error("TASK-006", f"dispatch receipt 字段不符合合同：{relative}")
    validated_at = actual.pop("validated_at")
    if not isinstance(validated_at, str) or not validated_at:
        raise task_error("TASK-006", f"dispatch receipt 缺少 validated_at：{relative}")
    try:
        parsed_validated_at = datetime.fromisoformat(validated_at)
    except ValueError as exc:
        raise task_error("TASK-006", f"dispatch receipt validated_at 不是 ISO-8601：{relative}") from exc
    if parsed_validated_at.utcoffset() is None:
        raise task_error("TASK-006", f"dispatch receipt validated_at 必须包含时区：{relative}")
    if actual != expected:
        raise task_error("TASK-006", f"dispatch receipt 已因任务或动态输入变化失效：{relative}")
    return receipt_relative


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


def diagram_svg_sha256(root: Path, output_dir: str, relative: str) -> str:
    svg_relative = f"{output_dir}/diagram.svg"
    return hash_file(disclosure_file(root, svg_relative, relative))


def validate_semantic_join(root: Path, aggregate_rows: list[dict[str, str]]) -> None:
    relative = "stages/phase-4/semantic-review.tsv"
    source_rows = read_tsv_rows(root, relative)
    if not source_rows:
        raise ContractError(f"语义复核结果不得为空：{relative}")

    fields = ("artifact_id", "review_type", "status", "bound_sha256", "conclusion")
    semantic_task = "stages/agents/semantic-review-task.md"
    semantic_spec = FIXED_TASK_SPECS[semantic_task]
    semantic_inputs = expected_dynamic_inputs(root, semantic_task, semantic_spec)
    if not isinstance(semantic_inputs, tuple):
        raise task_error("TASK-005", "语义复核动态输入合同不是固定集合")
    expected_bound_sha256 = normalized_file_set_digest(root, list(semantic_inputs), semantic_task)

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
            if row.get("bound_sha256") != expected_bound_sha256:
                raise task_error(
                    "TASK-005",
                    f"语义复核 bound_sha256 未绑定四项动态输入规范化集合：{label}:{row_number}",
                )
            values.append(tuple(row.get(field, "") for field in fields))
        if len(values) != len(set(values)):
            raise ContractError(f"语义复核结果不得重复：{label}")
        return set(values)

    source = normalized(source_rows, relative)
    source_ids = tuple(row["artifact_id"] for row in source_rows)
    if source_ids != SEMANTIC_CHECK_IDS:
        missing = ",".join(item for item in SEMANTIC_CHECK_IDS if item not in source_ids) or "none"
        extra = ",".join(item for item in source_ids if item not in SEMANTIC_CHECK_IDS) or "none"
        raise task_error(
            "TASK-005",
            f"语义复核必须按固定顺序包含 9 个 check id：missing={missing}; extra={extra}",
        )
    aggregate_semantic = [row for row in aggregate_rows if row.get("review_type") == "semantic"]
    aggregate = normalized(aggregate_semantic, "stages/phase-4/review.tsv") if aggregate_semantic else set()
    if source != aggregate:
        raise ContractError("聚合 review.tsv 未完整汇合 semantic-review.tsv")
    aggregate_ids = tuple(row["artifact_id"] for row in aggregate_semantic)
    if aggregate_ids != SEMANTIC_CHECK_IDS:
        raise task_error("TASK-005", "聚合 review.tsv 的语义 check id 顺序与源结果不一致")


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
        actual_svg_hash = diagram_svg_sha256(root, expected_path, f"phase-3:{diagram_id}")
        if hashes != {actual_svg_hash}:
            raise ContractError(f"逐图、聚合结果与 build map 的 hash 未绑定实际 diagram.svg：{diagram_id}")
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
        actual_svg_hash = diagram_svg_sha256(root, output_dirs[diagram_id], f"phase-4:{diagram_id}")
        if build_by_id[diagram_id].get("sha256") != actual_svg_hash:
            raise ContractError(f"build map hash 未绑定实际 diagram.svg：{diagram_id}")
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


def stage_task_files(root: Path, stage: StageSpec) -> tuple[str, ...]:
    if stage.name == "phase_1_material_modeling":
        return (
            "stages/agents/subject-boundary-task.md",
            "stages/agents/prior-art-object-task.md",
            "stages/agents/prior-art-mechanism-task.md",
            "stages/agents/innovation-value-task.md",
        )
    if stage.name == "phase_3_final_drafting":
        diagram_ids, _ = load_diagram_plan(root)
        return tuple(f"stages/agents/diagram-{diagram_id}-task.md" for diagram_id in diagram_ids)
    if stage.name == "phase_4_review_delivery":
        diagram_ids, _ = load_diagram_plan(root)
        return (
            "stages/agents/semantic-review-task.md",
            *(f"stages/agents/visual-review-{diagram_id}-task.md" for diagram_id in diagram_ids),
        )
    return ()


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
    for task_relative in stage_task_files(root, stage):
        cache_files.add(validate_dispatch_receipt(root, task_relative))
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
        "stages/shared", "stages/agents", "stages/agents/inputs", "stages/agents/receipts",
        "stages/phase-1", "stages/phase-2",
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


def validate_task_command(root: Path, relative: str) -> None:
    if (
        Path(relative).is_absolute()
        or ".." in Path(relative).parts
        or "\\" in relative
        or "／" in relative
        or "file:/" in relative.lower()
        or any(marker in relative for marker in ("*", "?", "[", "]"))
    ):
        raise task_error("TASK-005", f"--task 必须是安全的 working 相对路径：{relative}")
    task_spec_for(root, relative)
    receipt_relative = write_dispatch_receipt(root, relative)
    print(f"task_valid={relative}")
    print(f"dispatch_receipt={receipt_relative}")


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
        elif args.command == "validate-task":
            validate_task_command(root, args.task)
        return 0
    except (ContractError, OSError, UnicodeError, csv.Error) as exc:
        print(f"stage_handoff_error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
