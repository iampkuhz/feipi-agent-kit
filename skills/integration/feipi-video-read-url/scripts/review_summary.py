#!/usr/bin/env python3
"""核对宿主的逐项摘要复核清单；只检查可追溯性，不替代语义阅读。"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from validate_extraction import validate

TEXT_KINDS = {"body", "subtitles", "asr", "ocr", "visual_observation"}
CATEGORIES = {"detail", "comparison", "recommendation", "reason", "condition", "uncertainty"}


def review(manifest_path, summary_path, coverage_path):
    manifest_path, summary_path, coverage_path = map(Path, (manifest_path, summary_path, coverage_path))
    if manifest_path.name != "extraction_manifest.json":
        raise ValueError("expected_extraction_manifest")
    manifest = validate(manifest_path.resolve().parent)
    summary_data = summary_path.read_bytes()
    summary = summary_data.decode("utf-8")
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    if coverage.get("schema") != "feipi-summary-coverage-v1":
        raise ValueError("invalid_summary_coverage_schema")
    texts, hashes = {}, {}
    for artifact in manifest["artifacts"]:
        if artifact["kind"] not in TEXT_KINDS:
            continue
        data = (manifest_path.resolve().parent / artifact["path"]).read_bytes()
        text = data.decode("utf-8")
        if artifact["kind"] in {"ocr", "visual_observation"}:
            text = json.loads(text)["text"]
        if text.strip():
            texts[artifact["id"]] = text
            hashes[artifact["id"]] = hashlib.sha256(data).hexdigest()
    reviewed = coverage.get("reviewed_artifact_ids")
    if not isinstance(reviewed, list) or len(reviewed) != len(set(reviewed)) or set(reviewed) != set(texts):
        raise ValueError("all_content_artifacts_must_be_reviewed")
    if coverage.get("source_review") != "full_available_text_and_images" or coverage.get("summary_review") != "all_units_checked":
        raise ValueError("host_semantic_review_required")
    units, ids = coverage.get("units"), set()
    if not isinstance(units, list) or not units:
        raise ValueError("summary_units_required")
    for unit in units:
        if not isinstance(unit, dict) or not isinstance(unit.get("id"), str) or not unit["id"].strip() or unit["id"] in ids:
            raise ValueError("invalid_summary_unit_id")
        ids.add(unit["id"])
        if not isinstance(unit.get("topic"), str) or not unit["topic"].strip() or unit.get("category") not in CATEGORIES:
            raise ValueError("invalid_summary_unit")
        quote = unit.get("summary_quote")
        if not isinstance(quote, str) or len(quote.strip()) < 4 or quote not in summary:
            raise ValueError("summary_unit_missing:" + unit["id"])
        evidence = unit.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("summary_unit_evidence_required:" + unit["id"])
        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError("invalid_summary_evidence")
            source, excerpt = item.get("artifact_id"), item.get("quote")
            if source not in texts or not isinstance(excerpt, str) or len(excerpt.strip()) < 4 or excerpt not in texts[source]:
                raise ValueError("summary_evidence_not_in_source:" + unit["id"])
    return {"schema": "feipi-summary-review-v1", "status": "traceability_checked",
            "semantic_review": "host_declared", "unit_count": len(units),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "summary_sha256": hashlib.sha256(summary_data).hexdigest(),
            "coverage_sha256": hashlib.sha256(coverage_path.read_bytes()).hexdigest(),
            "source_sha256": hashes,
            "limitation": "引用校验不证明语义完整；主题清点及逐项对照由宿主实际阅读完成。"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("summary")
    parser.add_argument("coverage")
    args = parser.parse_args()
    try:
        print(json.dumps(review(args.manifest, args.summary, args.coverage), ensure_ascii=False, sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
