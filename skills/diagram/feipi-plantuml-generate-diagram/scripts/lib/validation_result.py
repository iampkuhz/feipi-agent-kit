#!/usr/bin/env python3
"""统一 validation.json 写入工具。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class ValidationResult:
    schema_version: str = "1.1"
    skill_name: str = "feipi-plantuml-generate-diagram"
    diagram_id: str = ""
    diagram_type: str = "fallback"
    profile: str = "fallback"
    profile_version: str = "1.0"
    brief_path: str = ""
    diagram_path: str = ""
    svg_path: str = ""
    brief_check: str = "skipped"
    coverage_check: str = "skipped"
    layout_check: str = "skipped"
    render_result: str = "pending"
    render_server: str = ""
    brief_sha256: str = ""
    puml_sha256: str = ""
    normalized_puml_sha256: str = ""
    svg_sha256: str = ""
    parent_brief_path: str = ""
    parent_brief_sha256: str = ""
    parent_component_ref: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, dict[str, str]] = field(default_factory=dict)
    metrics: dict[str, int] = field(
        default_factory=lambda: {"node_count": 0, "edge_count": 0, "max_degree": 0}
    )
    final_status: str = "pending"
    blocked_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def set_success(self) -> None:
        self.final_status = "success"
        self.blocked_reason = ""

    def set_blocked(self, reason: str) -> None:
        self.final_status = "blocked"
        self.blocked_reason = reason

    def set_render_server_unavailable(self) -> None:
        self.render_result = "skipped"
        self.final_status = "blocked"
        self.blocked_reason = "render_server_unavailable"

    def set_render_syntax_error(self) -> None:
        self.render_result = "syntax_error"
        self.final_status = "blocked"
        self.blocked_reason = "render_syntax_error"


def compute_sha256(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def normalize_puml_text(text: str) -> str:
    """统一换行、去除行尾空白/首尾空行，并保留唯一末尾换行。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def compute_normalized_puml_sha256(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    normalized = normalize_puml_text(p.read_text(encoding="utf-8-sig"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _relative_artifact(path: str, package_dir: Path) -> str:
    if not path:
        return ""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(package_dir.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"artifact 必须位于 package 内：{resolved}") from exc


def write_validation_json(
    result: ValidationResult,
    output_path: str,
    package_dir: str | None = None,
) -> Path:
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    package = Path(package_dir).resolve() if package_dir else p.parent.resolve()
    source_brief = result.brief_path
    source_diagram = result.diagram_path
    source_svg = result.svg_path
    source_parent_brief = result.parent_brief_path
    if source_brief and Path(source_brief).is_file():
        result.brief_sha256 = compute_sha256(source_brief)
        relative = _relative_artifact(source_brief, package)
        result.brief_path = relative
        result.artifacts["brief"] = {"path": relative, "sha256": result.brief_sha256}
    else:
        result.brief_path = ""
    if source_diagram and Path(source_diagram).is_file():
        result.puml_sha256 = compute_sha256(source_diagram)
        result.normalized_puml_sha256 = compute_normalized_puml_sha256(source_diagram)
        relative = _relative_artifact(source_diagram, package)
        result.diagram_path = relative
        result.artifacts["diagram"] = {"path": relative, "sha256": result.puml_sha256}
    else:
        result.diagram_path = ""
    if source_svg and Path(source_svg).is_file():
        result.svg_sha256 = compute_sha256(source_svg)
        relative = _relative_artifact(source_svg, package)
        result.svg_path = relative
        result.artifacts["svg"] = {"path": relative, "sha256": result.svg_sha256}
    else:
        result.svg_path = ""
    if source_parent_brief and Path(source_parent_brief).is_file():
        result.parent_brief_sha256 = compute_sha256(source_parent_brief)
        relative = _relative_artifact(source_parent_brief, package)
        result.parent_brief_path = relative
        result.artifacts["parent_brief"] = {
            "path": relative,
            "sha256": result.parent_brief_sha256,
        }
        if result.parent_component_ref:
            result.parent_component_ref["overview_brief_path"] = relative
            result.parent_component_ref["overview_brief_sha256"] = result.parent_brief_sha256
    else:
        result.parent_brief_path = ""

    # 防御性收口：success 只能代表当前 SVG 已由明确 renderer 生成，且 typed
    # profile 的三段确定性检查均通过。调用方不能直接写出“假绿”合同。
    invalid_success = []
    if result.final_status == "success":
        if result.render_result != "ok":
            invalid_success.append("render_result_not_ok")
        if not result.render_server.strip():
            invalid_success.append("render_server_missing")
        if "svg" not in result.artifacts:
            invalid_success.append("svg_missing")
        elif not source_svg or b"<svg" not in Path(source_svg).read_bytes().lower():
            invalid_success.append("svg_invalid")
        if result.profile != "fallback":
            for field_name in ("brief_check", "coverage_check", "layout_check"):
                if getattr(result, field_name) != "ok":
                    invalid_success.append(f"{field_name}_not_ok")
        if invalid_success:
            result.final_status = "blocked"
            result.blocked_reason = "invalid_success_contract:" + ",".join(invalid_success)
    p.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n")
    return p
