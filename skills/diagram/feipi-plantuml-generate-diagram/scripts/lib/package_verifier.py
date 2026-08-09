#!/usr/bin/env python3
"""diagram package v1.1 的安全、双向且可重算验证。"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .brief_loader import load_yaml
from .puml_analysis import compute_puml_metrics
from .validation_result import compute_normalized_puml_sha256, compute_sha256


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TOP_FIELDS = {
    "brief": ("brief_path", "brief_sha256"),
    "diagram": ("diagram_path", "puml_sha256"),
    "svg": ("svg_path", "svg_sha256"),
    "parent_brief": ("parent_brief_path", "parent_brief_sha256"),
}


def _safe_relative(value: Any) -> PurePosixPath | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def _load_validation(validation_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(validation_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"validation.json 解析失败：{exc}"]
    if not isinstance(value, dict):
        return None, ["validation.json 根节点必须是对象"]
    return value, []


def verify_package_dir(package_dir: Path) -> list[str]:
    errors: list[str] = []
    package_root = package_dir.resolve()
    validation_path = package_root / "validation.json"
    if not validation_path.is_file():
        return ["缺少 validation.json"]
    try:
        resolved_validation = validation_path.resolve(strict=True)
        resolved_validation.relative_to(package_root)
    except (OSError, ValueError):
        return ["validation.json 解析后越出 package"]
    data, load_errors = _load_validation(resolved_validation)
    if data is None:
        return load_errors

    if data.get("schema_version") != "1.1":
        errors.append("schema_version 必须为 1.1")
    for field in ("diagram_id", "profile", "profile_version"):
        if not isinstance(data.get(field), str) or not data.get(field):
            errors.append(f"{field} 不能为空")

    profile = data.get("profile")
    typed = isinstance(profile, str) and profile != "fallback"
    final_status = data.get("final_status")
    if final_status not in {"success", "blocked"}:
        errors.append("final_status 仅允许 success 或 blocked")
    if data.get("render_result") not in {"ok", "failed", "skipped", "syntax_error"}:
        errors.append("render_result 枚举无效")
    if final_status == "blocked" and not isinstance(data.get("blocked_reason"), str):
        errors.append("final_status=blocked 时 blocked_reason 必须是字符串")
    elif final_status == "blocked" and not data.get("blocked_reason", "").strip():
        errors.append("final_status=blocked 时 blocked_reason 不能为空")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        return errors + ["artifacts 必须是对象"]

    # 第一阶段只解析合同和路径；只要发现危险路径，就在读取任何 artifact 前返回。
    resolved: dict[str, Path] = {}
    allowed_names = set(TOP_FIELDS)
    extras = sorted(set(artifacts) - allowed_names)
    if extras:
        errors.append(f"artifacts 包含未注册条目：{extras}")
    required = {"diagram"}
    if typed:
        required.update({"brief", "svg"})
    elif data.get("final_status") == "success":
        required.add("svg")
    missing = sorted(required - set(artifacts))
    if missing:
        errors.append(f"artifacts 缺少必需条目：{missing}")

    for name, (path_field, hash_field) in TOP_FIELDS.items():
        top_path = data.get(path_field)
        top_hash = data.get(hash_field)
        if top_path or top_hash:
            if _safe_relative(top_path) is None:
                errors.append(f"{path_field} 必须是安全的包内相对路径")
            if not isinstance(top_hash, str) or not SHA256_RE.fullmatch(top_hash):
                errors.append(f"{hash_field} 必须是小写 SHA-256")

    for name, item in artifacts.items():
        if name not in TOP_FIELDS:
            continue
        if not isinstance(item, dict):
            errors.append(f"artifacts.{name} 必须是对象")
            continue
        if set(item) != {"path", "sha256"}:
            errors.append(f"artifacts.{name} 必须且只能包含 path、sha256")
        rel = _safe_relative(item.get("path"))
        expected_hash = item.get("sha256")
        if rel is None:
            errors.append(f"artifacts.{name}.path 必须是安全的包内相对路径")
            continue
        if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
            errors.append(f"artifacts.{name}.sha256 必须是小写 SHA-256")
        target = (package_root / Path(*rel.parts)).resolve()
        try:
            target.relative_to(package_root)
        except ValueError:
            errors.append(f"artifacts.{name}.path 越出 package")
            continue
        path_field, hash_field = TOP_FIELDS[name]
        if data.get(path_field) != rel.as_posix():
            errors.append(f"{path_field} 与 artifacts.{name}.path 不一致")
        if data.get(hash_field) != expected_hash:
            errors.append(f"{hash_field} 与 artifacts.{name}.sha256 不一致")
        resolved[name] = target

    # 顶层字段也必须反向找到 artifact，不能只写一边。
    for name, (path_field, hash_field) in TOP_FIELDS.items():
        has_top = bool(data.get(path_field) or data.get(hash_field))
        if has_top and name not in artifacts:
            errors.append(f"{path_field}/{hash_field} 存在但 artifacts.{name} 缺失")

    if errors:
        return errors

    # 第二阶段才读取已证明位于包内的普通文件。
    for name, target in resolved.items():
        if not target.is_file():
            errors.append(f"artifacts.{name} 文件不存在：{artifacts[name]['path']}")
            continue
        if compute_sha256(str(target)) != artifacts[name]["sha256"]:
            errors.append(f"artifacts.{name}.sha256 不匹配")
    if errors:
        return errors

    diagram_path = resolved.get("diagram")
    if diagram_path is None:
        return errors + ["artifacts.diagram 缺失"]
    try:
        normalized_hash = compute_normalized_puml_sha256(str(diagram_path))
        puml_text = diagram_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return errors + [f"diagram artifact 必须是可读 UTF-8：{exc}"]
    if normalized_hash != data.get("normalized_puml_sha256"):
        errors.append("normalized_puml_sha256 不匹配")

    metrics = data.get("metrics")
    metric_keys = {"node_count", "edge_count", "max_degree"}
    if not isinstance(metrics, dict) or set(metrics) != metric_keys:
        errors.append("metrics 必须且只能包含 node_count、edge_count、max_degree")
    elif any(type(metrics[key]) is not int or metrics[key] < 0 for key in metric_keys):
        errors.append("metrics 各字段必须是非负整数")
    else:
        actual_metrics = compute_puml_metrics(str(profile), puml_text)
        if metrics != actual_metrics:
            errors.append(f"metrics 与实际 PUML 不一致：期望 {actual_metrics}，合同为 {metrics}")

    brief: Any = None
    if typed:
        brief_path = resolved.get("brief")
        if brief_path is None:
            errors.append("typed package 缺少 brief artifact")
        else:
            try:
                brief = load_yaml(brief_path)
            except Exception as exc:
                errors.append(f"brief artifact 解析失败：{exc}")
            if not isinstance(brief, dict):
                errors.append("brief artifact 根节点必须是对象")
            else:
                if brief.get("diagram_id") != data.get("diagram_id"):
                    errors.append("diagram_id 与 brief 不一致")
                if brief.get("diagram_type") != profile:
                    errors.append("profile 与 brief.diagram_type 不一致")

    if isinstance(brief, dict) and brief.get("view") == "module_detail":
        ref = brief.get("parent_component_ref")
        contract_ref = data.get("parent_component_ref")
        if not isinstance(ref, dict) or not isinstance(contract_ref, dict):
            errors.append("module_detail 缺少双向 parent_component_ref")
        if "parent_brief" not in resolved:
            errors.append("module_detail 缺少 parent_brief artifact")
        elif isinstance(ref, dict) and isinstance(contract_ref, dict):
            expected_ref = dict(ref)
            expected_ref["overview_brief_path"] = data.get("parent_brief_path")
            expected_ref["overview_brief_sha256"] = data.get("parent_brief_sha256")
            if contract_ref != expected_ref:
                errors.append("validation.parent_component_ref 与 brief/parent_brief artifact 不一致")
            try:
                overview = load_yaml(resolved["parent_brief"])
            except Exception as exc:
                errors.append(f"parent_brief artifact 解析失败：{exc}")
            else:
                if not isinstance(overview, dict) or overview.get("diagram_type") != "component" or overview.get("view") != "overview":
                    errors.append("parent_brief artifact 必须是 component/overview brief")
                else:
                    if overview.get("diagram_id") != ref.get("overview_diagram_id"):
                        errors.append("parent overview diagram_id 与引用不一致")
                    parent_id = brief.get("parent_component_id")
                    if parent_id != ref.get("component_id"):
                        errors.append("parent_component_id 与 parent_component_ref.component_id 不一致")
                    matches = [
                        item for item in overview.get("nodes", [])
                        if isinstance(item, dict) and item.get("id") == parent_id
                    ]
                    if len(matches) != 1:
                        errors.append("parent_component_id 未在 parent_brief 中恰好命中一个节点")
    elif "parent_brief" in artifacts or data.get("parent_component_ref"):
        errors.append("非 module_detail 包不得声明 parent_brief/parent_component_ref")

    if data.get("final_status") == "success":
        if data.get("render_result") != "ok":
            errors.append("final_status=success 时 render_result 必须为 ok")
        if not isinstance(data.get("render_server"), str) or not data.get("render_server", "").strip():
            errors.append("final_status=success 时 render_server 不能为空")
        if "svg" not in resolved:
            errors.append("final_status=success 时必须包含当前 SVG artifact")
        else:
            try:
                svg_bytes = resolved["svg"].read_bytes()
            except OSError as exc:
                errors.append(f"svg artifact 无法读取：{exc}")
            else:
                if b"<svg" not in svg_bytes.lower():
                    errors.append("final_status=success 时 svg artifact 必须包含 SVG 根元素")
        if data.get("blocked_reason"):
            errors.append("final_status=success 时 blocked_reason 必须为空")
        if typed:
            for field in ("brief_check", "coverage_check", "layout_check"):
                if data.get(field) != "ok":
                    errors.append(f"final_status=success 时 {field} 必须为 ok")
    return errors
