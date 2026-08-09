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
    parser.add_argument("--brief-path", default="")
    parser.add_argument("--package-dir", default="")
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

    result = ValidationResult(
        skill_name=args.skill_name,
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
        metrics=compute_puml_metrics(args.profile, diagram_text),
        parent_brief_path=parent_brief_path,
        parent_component_ref=parent_component_ref,
    )
    write_validation_json(result, args.output, args.package_dir or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
