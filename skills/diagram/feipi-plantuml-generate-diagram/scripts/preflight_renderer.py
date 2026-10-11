#!/usr/bin/env python3
"""一次批次预检；existing-only 仅探测，默认最多一次固定 Podman 启动。"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from lib.runtime_observation import RunClock, atomic_json, receipt_fields

SCRIPTS = Path(__file__).resolve().parent
PODMAN_COMMAND = ["podman", "run", "--rm", "-d", "-p", "8199:8080", "--name", "plantuml",
                  "docker.io/plantuml/plantuml-server:jetty"]


def start_podman(timeout):
    process = subprocess.Popen(PODMAN_COMMAND, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output
    except subprocess.TimeoutExpired:
        # 仅终止本脚本启动的超时命令组，不管理已存在的 renderer/container。
        os.killpg(process.pid, signal.SIGTERM)
        try:
            output, _ = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate()
        return 124, output


def main():
    clock = RunClock()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="")
    parser.add_argument("--server-url", default="auto")
    parser.add_argument("--existing-only", action="store_true", help="探测失败不启动 Podman、不复检")
    args = parser.parse_args()
    timeout_text = os.environ.get("PLANTUML_PODMAN_START_TIMEOUT_SECONDS", "30")
    delay_text = os.environ.get("PLANTUML_PODMAN_READINESS_DELAY_SECONDS", "1")
    try:
        timeout, delay = int(timeout_text), float(delay_text)
        if timeout <= 0 or not math.isfinite(delay) or delay < 0:
            raise ValueError()
    except ValueError:
        parser.error("Podman timeout 必须是正整数，readiness delay 必须是非负有限数")
    receipt = {
        "schema_version": "1", "final_status": "blocked", "renderer_url": "",
        "blocked_reason": "render_server_unavailable", "issue": "", "failure_kind": "",
        "render_target": "", "curl_exit_code": None, "http_status": "",
        "connect_timeout_seconds": 1, "total_timeout_seconds": 2,
        "http_requests": 0, "probe_attempts": 0, "probes": [],
        "podman_start_attempted": False, "podman_start_result": "renderer_available",
        "podman_start_exit_code": None, "podman_start_diagnostic": "",
        "podman_start_timeout_seconds": timeout, "podman_readiness_delay_seconds": delay,
        "startup_policy": "existing_only" if args.existing_only else "podman_once",
        "process_management_allowed": False,
    }
    env = dict(os.environ, PLANTUML_PYTHON=sys.executable)
    with tempfile.TemporaryDirectory(prefix="plantuml-preflight-") as temporary:
        probe = Path(temporary) / "probe.puml"
        svg = Path(temporary) / "probe.svg"
        probe.write_text("@startuml\nAlice -> Bob: preflight\n@enduml\n", encoding="utf-8")

        def run_probe():
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
            return result.returncode

        code = run_probe()
        port = os.environ.get("AGENT_PLANTUML_SERVER_PORT", "8199")
        eligible = ((args.server_url == "auto" and port == "8199") or
                    args.server_url.rstrip("/") in ("http://127.0.0.1:8199", "http://localhost:8199"))
        if code == 4:
            if args.existing_only:
                receipt["podman_start_result"] = "skipped_existing_only"
            elif not eligible:
                receipt["podman_start_result"] = "skipped_nondefault_target"
            elif not shutil.which("podman"):
                receipt["podman_start_result"] = "podman_unavailable"
            else:
                receipt["podman_start_attempted"] = True
                start_code, output = start_podman(timeout)
                receipt["podman_start_exit_code"] = start_code
                receipt["podman_start_diagnostic"] = output
                receipt["podman_start_result"] = {0: "started", 124: "timeout"}.get(start_code, "failed")
                if start_code == 0:
                    time.sleep(delay)
                code = run_probe()
        if code == 5:
            receipt["blocked_reason"] = "render_access_denied"
            if not receipt["podman_start_attempted"]:
                receipt["podman_start_result"] = "skipped_access_denied"
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
