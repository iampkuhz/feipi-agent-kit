#!/usr/bin/env python3
"""校验证据清单形状、来源引用与本地文件边界，不联网。"""

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from content_manifest import CHANNELS, MANIFEST, safe_path


def validate(root):
    m = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if m.get("schema") != "feipi-content-extraction-v1" or m.get("version") != 1:
        raise ValueError("unsupported_manifest_version")
    required = ("platform", "content_id", "original_url", "canonical_url", "content_type", "status", "reasons",
                "metadata", "channels", "artifacts")
    if any(k not in m for k in required):
        raise ValueError("manifest_field_missing")
    if m["status"] not in ("complete", "partial", "blocked", "failed"):
        raise ValueError("invalid_completion_status")
    if m["content_type"] not in ("video", "video_note", "image_note", "unknown"):
        raise ValueError("invalid_content_type")
    statuses = ("complete", "partial", "blocked", "failed", "pending", "not_applicable", "unavailable")
    for k in CHANNELS:
        if m["channels"].get(k, {}).get("status") not in statuses:
            raise ValueError("invalid_channel_status")
        if not isinstance(m["channels"][k].get("reasons"), list):
            raise ValueError("invalid_channel_reasons")
    sources = {}
    for a in m["artifacts"]:
        if not re.fullmatch(r"[a-z0-9_-]+", a.get("id", "")) or a["id"] in sources:
            raise ValueError("invalid_artifact_id")
        if a.get("kind") not in ("source", "body", "subtitles", "asr", "image", "frame", "ocr", "visual_observation") or not isinstance(a.get("anchor"), dict):
            raise ValueError("invalid_artifact_kind_or_anchor")
        if a.get("read_status") not in ("extracted", "pending", "read"):
            raise ValueError("invalid_artifact_read_status")
        if not safe_path(root, a.get("path")).is_file():
            raise ValueError("artifact_missing")
        sources[a["id"]] = a
    for a in m["artifacts"]:
        if a["kind"] in ("ocr", "visual_observation"):
            source = sources.get(a.get("source_artifact_id"), {})
            if source.get("kind") not in ("image", "frame") or source.get("anchor") != a["anchor"]:
                raise ValueError("invalid_observation_reference")
    from frame_plan import check_policy
    check_policy(m)
    return m


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output_dir")
    a = p.parse_args()
    try:
        m = validate(Path(a.output_dir).resolve())
        print(f"manifest_valid=1\nstatus={m['status']}")
    except (ValueError, TypeError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
