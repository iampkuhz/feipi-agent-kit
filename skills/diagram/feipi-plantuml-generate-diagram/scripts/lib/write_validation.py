#!/usr/bin/env python3
"""CLI wrapper for writing validation.json from shell scripts."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.brief_loader import load_yaml
from lib.profile_registry import resolve_profile
from lib.puml_analysis import compute_puml_metrics
from lib.validation_result import ValidationResult, write_validation_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Write validation.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--skill-name", default="feipi-plantuml-generate-diagram")
    parser.add_argument("--render-contract-version", default="3")
    parser.add_argument("--diagram-type", default="fallback")
    parser.add_argument("--profile", default="fallback")
    parser.add_argument("--diagram-path", default="")
    parser.add_argument("--svg-path", default="")
    parser.add_argument("--brief-check", default="skipped")
    parser.add_argument("--coverage-check", default="skipped")
    parser.add_argument("--layout-check", default="skipped")
    parser.add_argument("--render-result", default="pending")
    parser.add_argument("--render-server", default="")
    parser.add_argument("--final-status", default="pending")
    parser.add_argument("--blocked-reason", default="")
    parser.add_argument("--issue-text", default="")
    parser.add_argument("--attempt-index", type=int, default=0)
    parser.add_argument("--max-render-attempts", type=int, default=2)
    parser.add_argument(
        "--brief-validation-reused", choices=("true", "false"), default="false"
    )
    parser.add_argument("--brief-path", default="")
    parser.add_argument("--package-dir", default="")
    parser.add_argument("--total-duration-ms", type=float, default=0.0)
    parser.add_argument("--render-duration-ms", type=float, default=0.0)
    parser.add_argument("--static-validation-duration-ms", type=float, default=0.0)
    parser.add_argument("--render-http-requests", type=int, default=0)
    parser.add_argument("--render-rounds", type=int, default=0)
    parser.add_argument("--package-validation-runs", type=int, default=1)
    parser.add_argument("--package-verifier-runs", type=int, default=0)
    parser.add_argument("--cache-hits", type=int, default=0)
    args = parser.parse_args()

    profile_config = resolve_profile(args.profile)
    brief_data = None
    if args.brief_path and Path(args.brief_path).is_file():
        try:
            brief_data = load_yaml(Path(args.brief_path))
        except Exception:
            brief_data = None
    diagram_id = ""
    if isinstance(brief_data, dict):
        diagram_id = str(brief_data.get("diagram_id", ""))
    if not diagram_id and args.diagram_path:
        diagram_id = Path(args.diagram_path).stem

    diagram_text = ""
    if args.diagram_path and Path(args.diagram_path).is_file():
        diagram_text = Path(args.diagram_path).read_text(encoding="utf-8")
    parent_component_ref: dict[str, str] = {}
    parent_brief_path = ""
    if isinstance(brief_data, dict) and isinstance(brief_data.get("parent_component_ref"), dict):
        parent_component_ref = {
            str(key): str(value)
            for key, value in brief_data["parent_component_ref"].items()
            if isinstance(key, str) and isinstance(value, str)
        }
        relative = parent_component_ref.get("overview_brief_path", "")
        if relative and args.brief_path:
            rel = PurePosixPath(relative)
            if not rel.is_absolute() and "\\" not in relative and not any(
                part in {"", ".", ".."} for part in rel.parts
            ):
                base = Path(args.brief_path).resolve().parent
                candidate = (base / Path(*rel.parts)).resolve()
                try:
                    candidate.relative_to(base)
                except ValueError:
                    pass
                else:
                    if candidate.is_file():
                        parent_brief_path = str(candidate)

    timings = {
        "total_ms": round(max(0.0, args.total_duration_ms), 3),
        "render_ms": round(max(0.0, args.render_duration_ms), 3),
        "static_validation_ms": round(max(0.0, args.static_validation_duration_ms), 3),
    }
    counters = {
        "render_http_requests": max(0, args.render_http_requests),
        "render_rounds": max(0, args.render_rounds),
        "package_validation_runs": max(0, args.package_validation_runs),
        "package_verifier_runs": max(0, args.package_verifier_runs),
        "cache_hits": max(0, args.cache_hits),
    }
    issues = [
        line.strip()
        for line in args.issue_text.splitlines()
        if line.strip()
    ][:20]
    if args.blocked_reason and not issues:
        issues = [args.blocked_reason]
    over_budget = any(
        marker in issue
        for issue in issues
        for marker in ("最多允许", "显示宽度", "每层最多", "规模预算")
    )
    failure_policy = {
        "missing_startuml": ("syntax", True),
        "missing_enduml": ("syntax", True),
        "brief_validation_failed": ("brief", False),
        "coverage_validation_failed": ("coverage", True),
        "layout_validation_failed": ("layout", True),
        "render_syntax_error": ("syntax", True),
        "render_server_unavailable": ("renderer", False),
        "renderer_missing": ("renderer", False),
        "render_failed": ("renderer", False),
        "render_evidence_missing": ("renderer", False),
        "attempt_limit_exceeded": ("retry_limit", False),
    }
    failure_class, repairable = failure_policy.get(
        args.blocked_reason,
        ("none", False) if args.final_status == "success" else ("contract", False),
    )
    if over_budget:
        failure_class, repairable = "over_budget", False
    attempt_index = max(0, args.attempt_index)
    max_attempts = max(1, args.max_render_attempts)
    result = ValidationResult(
        skill_name=args.skill_name,
        render_contract_version=args.render_contract_version,
        diagram_id=diagram_id,
        diagram_type=args.diagram_type,
        profile=args.profile,
        profile_version=str(profile_config.get("profile_version", "1.0")),
        brief_path=args.brief_path,
        diagram_path=args.diagram_path,
        svg_path=args.svg_path,
        brief_check=args.brief_check,
        coverage_check=args.coverage_check,
        layout_check=args.layout_check,
        render_result=args.render_result,
        render_server=args.render_server,
        final_status=args.final_status,
        blocked_reason=args.blocked_reason,
        failure_class=failure_class,
        repairable=repairable and attempt_index < max_attempts,
        issues=issues,
        attempt_index=attempt_index,
        max_render_attempts=max_attempts,
        attempts_remaining=max(0, max_attempts - attempt_index),
        brief_validation_reused=args.brief_validation_reused == "true",
        metrics=compute_puml_metrics(args.profile, diagram_text),
        timings=timings,
        last_run_timings={**timings, "cache_hit": False},
        counters=counters,
        last_run_counters=dict(counters),
        parent_brief_path=parent_brief_path,
        parent_component_ref=parent_component_ref,
    )
    write_validation_json(result, args.output, args.package_dir or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
