#!/usr/bin/env python3
"""每批只读探测一次本机 PlantUML 渲染服务。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from lib.runtime_observation import RunClock, atomic_json, receipt_fields

SCRIPTS = Path(__file__).resolve().parent


def main():
    clock = RunClock()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="")
    parser.add_argument("--server-url", default="auto")
    args = parser.parse_args()
    receipt = {
        "schema_version": "1", "final_status": "blocked", "renderer_url": "",
        "blocked_reason": "render_server_unavailable", "issue": "", "failure_kind": "",
        "render_target": "", "curl_exit_code": None, "http_status": "",
        "connect_timeout_seconds": 1, "total_timeout_seconds": 2,
        "http_requests": 0, "probe_attempts": 0, "probes": [],
        "process_management_allowed": False,
    }
    env = dict(os.environ, PLANTUML_PYTHON=sys.executable)
    with tempfile.TemporaryDirectory(prefix="plantuml-preflight-") as temporary:
        probe = Path(temporary) / "probe.puml"
        svg = Path(temporary) / "probe.svg"
        probe.write_text("@startuml\nAlice -> Bob: preflight\n@enduml\n", encoding="utf-8")

        result = subprocess.run(
            ["bash", str(SCRIPTS / "check_render.sh"), str(probe), "--svg-output", str(svg),
             "--server-url", args.server_url, "--timeout", "2"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
        )
        fields = receipt_fields(result.stdout)
        receipt["probe_attempts"] += 1
        requests = int(fields.get("render_http_requests", "0"))
        receipt["http_requests"] += requests
        diagnostic = {
            "render_target": fields.get("render_target", ""),
            "curl_exit_code": int(fields["render_curl_exit_code"]) if fields.get("render_curl_exit_code") else None,
            "http_status": fields.get("render_http_status", ""),
            "failure_kind": fields.get("render_failure_kind", ""),
            "issue": fields.get("render_reason", ""),
        }
        receipt.update(diagnostic)
        receipt["renderer_url"] = fields.get("render_server", "")
        receipt["probes"].append({**diagnostic, "exit_code": result.returncode,
                                  "http_requests": requests, "diagnostic": result.stdout})
        code = result.returncode

        if code == 5:
            receipt["blocked_reason"] = "render_access_denied"
        if code == 0 and receipt["renderer_url"] and svg.is_file() and svg.stat().st_size:
            receipt.update(final_status="success", blocked_reason="")
    # 从这里冻结回执；elapsed 不包含序列化、写入与 stdout 输出。
    receipt["elapsed_ms"] = clock.timings()["total_ms"]
    if not receipt["issue"]:
        receipt["issue"] = receipt["blocked_reason"]
    if args.out:
        atomic_json(Path(args.out), receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    if receipt["final_status"] == "success":
        return 0
    return 5 if receipt["blocked_reason"] == "render_access_denied" else 4


if __name__ == "__main__":
    raise SystemExit(main())
