#!/usr/bin/env python3
"""登记宿主已实际读取的图片/帧 OCR 与视觉观察；输入不是自动识别结果。"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from content_manifest import MANIFEST, artifact, channel, external_output, finish, safe_path, write_json
from validate_extraction import validate


def record(root, rows):
    root = external_output(root)
    m = validate(root)
    if m.get("schema") != "feipi-content-extraction-v1" or not isinstance(rows, list) or not rows:
        raise ValueError("invalid_observation_input")
    # 全部验证通过后再写文件，拒绝悬空引用、越界路径和非图像来源。
    sources = {a["id"]: a for a in m["artifacts"] if a["kind"] in ("image", "frame")}
    seen = set()
    for row in rows:
        ident = row.get("source_artifact_id")
        if ident not in sources or ident in seen or sources[ident]["read_status"] == "read":
            raise ValueError("invalid_or_duplicate_observation_source")
        if not safe_path(root, sources[ident]["path"]).is_file():
            raise ValueError("observation_source_missing")
        if not isinstance(row.get("ocr_text"), str) or not isinstance(row.get("observation"), str):
            raise ValueError("ocr_and_observation_required")
        if not isinstance(row.get("uncertainties"), list) or not all(isinstance(s, str) for s in row["uncertainties"]):
            raise ValueError("uncertainties_required")
        seen.add(ident)
    dest = root / "observations"
    dest.mkdir(exist_ok=True)
    for row in rows:
        source = sources[row["source_artifact_id"]]
        for kind, text_key in (("ocr", "ocr_text"), ("visual_observation", "observation")):
            path = dest / f"{source['id']}-{kind}.json"
            write_json(path, {"text": row[text_key], "uncertainties": row["uncertainties"],
                              "provenance": "host_model", "source_artifact_id": source["id"],
                              "anchor": source["anchor"]})
            artifact(m, root, f"{source['id']}-{kind}", kind, path, source["anchor"],
                     source_artifact_id=source["id"], provenance="host_model")
        source["read_status"] = "read"
    pending = any(a["read_status"] != "read" for a in sources.values())
    for key in ("ocr", "visual_observation"):
        channel(m, key, "partial" if pending else "complete", *(["host_reading_required"] if pending else []))
    return finish(m, root), m


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir")
    parser.add_argument("observations_json")
    args = parser.parse_args()
    root = Path(args.output_dir).resolve()
    code, m = record(root, json.loads(Path(args.observations_json).read_text(encoding="utf-8")))
    print(f"manifest_path={root / MANIFEST}\nstatus={m['status']}")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
