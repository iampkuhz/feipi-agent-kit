#!/usr/bin/env python3
"""check_render.sh 的单请求渲染回归。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
SKILL_DIR = TEST_DIR.parent
SCRIPT_DIR = SKILL_DIR / "scripts"
CHECK_RENDER = SCRIPT_DIR / "check_render.sh"
PREFLIGHT_RENDERER = SCRIPT_DIR / "preflight_renderer.sh"
VALIDATE_PACKAGE = SCRIPT_DIR / "validate_package.sh"
VALID_DIAGRAM = SCRIPT_DIR.parent / "assets/examples/fallback/fallback-diagram.example.puml"
ARCH_BRIEF = SCRIPT_DIR.parent / "assets/examples/architecture/architecture-brief.example.yaml"
ARCH_DIAGRAM = SCRIPT_DIR.parent / "assets/examples/architecture/architecture-diagram.example.puml"
ARCH_INVALID_DIAGRAM = TEST_DIR / "architecture-invalid-diagram.puml"


class _Handler(BaseHTTPRequestHandler):
    mode = "success"
    request_count = 0

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        type(self).request_count += 1
        status = 200
        content_type = "image/svg+xml"
        error_header = False
        if type(self).mode == "syntax":
            status = 400
            error_header = True
            body = b'<svg xmlns="http://www.w3.org/2000/svg"><text>error</text></svg>'
        elif type(self).mode == "syntax_metadata":
            status = 400
            body = b'<svg xmlns="http://www.w3.org/2000/svg" data-diagram-type="ERROR"><text>error</text></svg>'
        elif type(self).mode == "server_error":
            status = 500
            body = b'<svg xmlns="http://www.w3.org/2000/svg"><text>Syntax Error [From string (line 2)]</text></svg>'
        elif type(self).mode == "label_only":
            body = b'<svg xmlns="http://www.w3.org/2000/svg"><text>Syntax Error [From string is a user label]</text></svg>'
        elif type(self).mode == "wrong_namespace":
            body = b'<svg><text>not namespaced</text></svg>'
        elif type(self).mode == "html_with_svg_text":
            content_type = "text/html"
            body = b'<html><body>&lt;svg&gt;</body></html>'
        elif type(self).mode == "wrong_content_type":
            content_type = "text/plain"
            body = b'<svg xmlns="http://www.w3.org/2000/svg"><text>ok</text></svg>'
        elif type(self).mode == "invalid":
            body = b"not svg"
        else:
            body = b'<svg xmlns="http://www.w3.org/2000/svg"><text>ok</text></svg>'
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if error_header:
            self.send_header("X-PlantUML-Diagram-Error", "syntax error")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class CheckRenderTests(unittest.TestCase):
    def run_preflight_with_fakes(
        self, *, podman_exit: int, second_probe_success: bool,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object], list[str], int]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            fake_bin = root / "bin"
            scripts.mkdir()
            fake_bin.mkdir()
            preflight = scripts / "preflight_renderer.sh"
            shutil.copy2(PREFLIGHT_RENDERER, preflight)
            check_render = scripts / "check_render.sh"
            check_render.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
count=0
[[ -f \"$FAKE_PROBE_COUNTER\" ]] && count=\"$(cat \"$FAKE_PROBE_COUNTER\")\"
count=$((count + 1))
printf '%s\\n' \"$count\" >\"$FAKE_PROBE_COUNTER\"
svg_output=\"\"
while [[ $# -gt 0 ]]; do
  if [[ \"$1\" == \"--svg-output\" ]]; then
    svg_output=\"$2\"
    shift 2
  else
    shift
  fi
done
if [[ \"$count\" -eq 2 && \"$FAKE_SECOND_PROBE_SUCCESS\" == \"true\" ]]; then
  printf '<svg xmlns=\"http://www.w3.org/2000/svg\"><text>ok</text></svg>\\n' >\"$svg_output\"
  echo 'render_result=ok'
  echo 'render_server=http://127.0.0.1:8199'
  echo 'render_http_requests=1'
  exit 0
fi
echo 'render_result=skipped'
echo 'render_reason=unavailable'
echo 'render_http_requests=1'
exit 4
""",
                encoding="utf-8",
            )
            check_render.chmod(0o755)
            podman = fake_bin / "podman"
            podman.write_text(
                """#!/usr/bin/env bash
printf '%s\\n' \"$*\" >>\"$FAKE_PODMAN_LOG\"
exit \"$FAKE_PODMAN_EXIT\"
""",
                encoding="utf-8",
            )
            podman.chmod(0o755)
            output = root / "renderer-preflight.json"
            counter = root / "probe-count"
            podman_log = root / "podman.log"
            env = dict(os.environ)
            env.update({
                "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                "AGENT_PLANTUML_SERVER_PORT": "8199",
                "FAKE_PROBE_COUNTER": str(counter),
                "FAKE_SECOND_PROBE_SUCCESS": str(second_probe_success).lower(),
                "FAKE_PODMAN_LOG": str(podman_log),
                "FAKE_PODMAN_EXIT": str(podman_exit),
                "PLANTUML_PODMAN_READINESS_DELAY_SECONDS": "0",
            })
            completed = subprocess.run(
                ["bash", str(preflight), "--out", str(output)],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=env,
            )
            data = json.loads(output.read_text(encoding="utf-8"))
            commands = podman_log.read_text(encoding="utf-8").splitlines()
            return completed, data, commands, int(counter.read_text(encoding="utf-8"))

    def run_case(self, mode: str) -> tuple[subprocess.CompletedProcess[str], int, bool]:
        handler = type("CaseHandler", (_Handler,), {"mode": mode, "request_count": 0})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "diagram.svg"
                output.write_text("stale", encoding="utf-8")
                completed = subprocess.run(
                    [
                        "bash",
                        str(CHECK_RENDER),
                        str(VALID_DIAGRAM),
                        "--svg-output",
                        str(output),
                        "--server-url",
                        f"http://127.0.0.1:{server.server_port}",
                        "--timeout",
                        "2",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
                return completed, handler.request_count, output.exists()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_success_uses_one_svg_request(self) -> None:
        completed, count, output_exists = self.run_case("success")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(1, count)
        self.assertTrue(output_exists)
        self.assertIn("render_result=ok", completed.stdout)
        self.assertIn("render_http_requests=1", completed.stdout)

    def test_preflight_writes_single_request_bounded_contract(self) -> None:
        handler = type("PreflightHandler", (_Handler,), {"mode": "success", "request_count": 0})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "renderer-preflight.json"
                completed = subprocess.run(
                    [
                        "bash", str(PREFLIGHT_RENDERER), "--out", str(output),
                        "--server-url", f"http://127.0.0.1:{server.server_port}/plantuml",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                self.assertEqual(1, handler.request_count)
                data = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual("success", data["final_status"])
                self.assertEqual(1, data["connect_timeout_seconds"])
                self.assertEqual(2, data["total_timeout_seconds"])
                self.assertEqual(1, data["probe_attempts"])
                self.assertFalse(data["podman_start_attempted"])
                self.assertEqual("renderer_available", data["podman_start_result"])
                self.assertFalse(data["process_management_allowed"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_preflight_starts_podman_once_then_rechecks_once(self) -> None:
        completed, data, commands, probe_count = self.run_preflight_with_fakes(
            podman_exit=0, second_probe_success=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(2, probe_count)
        self.assertEqual(
            [
                "run --rm -d -p 8199:8080 --name plantuml "
                "docker.io/plantuml/plantuml-server:jetty",
            ],
            commands,
        )
        self.assertEqual("success", data["final_status"])
        self.assertEqual(2, data["http_requests"])
        self.assertEqual(2, data["probe_attempts"])
        self.assertTrue(data["podman_start_attempted"])
        self.assertEqual("started", data["podman_start_result"])
        self.assertEqual(0, data["podman_start_exit_code"])
        self.assertFalse(data["process_management_allowed"])

    def test_preflight_gives_up_after_failed_start_and_one_recheck(self) -> None:
        completed, data, commands, probe_count = self.run_preflight_with_fakes(
            podman_exit=125, second_probe_success=False,
        )
        self.assertEqual(4, completed.returncode)
        self.assertEqual(2, probe_count)
        self.assertEqual(1, len(commands))
        self.assertEqual("blocked", data["final_status"])
        self.assertEqual("render_server_unavailable", data["blocked_reason"])
        self.assertEqual(2, data["http_requests"])
        self.assertEqual(2, data["probe_attempts"])
        self.assertTrue(data["podman_start_attempted"])
        self.assertEqual("failed", data["podman_start_result"])
        self.assertEqual(125, data["podman_start_exit_code"])

    def test_remote_renderer_is_rejected_without_request(self) -> None:
        completed = subprocess.run(
            [
                "bash", str(CHECK_RENDER), str(VALID_DIAGRAM),
                "--server-url", "https://example.com/plantuml", "--timeout", "1",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertEqual(4, completed.returncode)
        self.assertIn("render_http_requests=0", completed.stdout)
        self.assertIn("拒绝非本地 renderer", completed.stderr)

    def test_syntax_error_uses_one_svg_request(self) -> None:
        completed, count, output_exists = self.run_case("syntax")
        self.assertEqual(2, completed.returncode)
        self.assertEqual(1, count)
        self.assertFalse(output_exists)
        self.assertIn("render_result=syntax_error", completed.stdout)

    def test_syntax_error_metadata_survives_stripped_error_header(self) -> None:
        completed, count, output_exists = self.run_case("syntax_metadata")
        self.assertEqual(2, completed.returncode)
        self.assertEqual(1, count)
        self.assertFalse(output_exists)
        self.assertIn("render_result=syntax_error", completed.stdout)

    def test_non_svg_response_is_not_accepted(self) -> None:
        completed, count, output_exists = self.run_case("invalid")
        self.assertEqual(4, completed.returncode)
        self.assertEqual(1, count)
        self.assertFalse(output_exists)

    def test_user_label_is_not_misclassified_as_syntax_error(self) -> None:
        completed, count, _ = self.run_case("label_only")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(1, count)

    def test_http_500_body_is_not_misclassified_as_syntax_error(self) -> None:
        completed, count, output_exists = self.run_case("server_error")
        self.assertEqual(4, completed.returncode)
        self.assertEqual(1, count)
        self.assertFalse(output_exists)

    def test_non_root_or_wrong_namespace_svg_is_rejected(self) -> None:
        for mode in ("wrong_namespace", "html_with_svg_text"):
            with self.subTest(mode=mode):
                completed, count, output_exists = self.run_case(mode)
                self.assertEqual(4, completed.returncode)
                self.assertEqual(1, count)
                self.assertFalse(output_exists)

    def test_svg_requires_svg_content_type(self) -> None:
        completed, count, output_exists = self.run_case("wrong_content_type")
        self.assertEqual(4, completed.returncode)
        self.assertEqual(1, count)
        self.assertFalse(output_exists)

    def test_package_exports_full_and_cache_hit_operation_counts(self) -> None:
        handler = type("PackageHandler", (_Handler,), {"mode": "success", "request_count": 0})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                output = root / "package"
                diagram_input = root / "input.puml"
                diagram_input.write_bytes(VALID_DIAGRAM.read_bytes())
                env = dict(os.environ)
                env["AGENT_PLANTUML_SERVER_PORT"] = str(server.server_port)
                command = [
                    "bash", str(VALIDATE_PACKAGE), "--diagram", str(diagram_input),
                    "--diagram-type", "fallback", "--out-dir", str(output),
                ]
                first = subprocess.run(
                    command, capture_output=True, text=True, check=False, timeout=20, env=env,
                )
                self.assertEqual(0, first.returncode, first.stderr)
                data = json.loads((output / "validation.json").read_text(encoding="utf-8"))
                self.assertEqual(
                    {
                        "render_http_requests": 1, "render_rounds": 1,
                        "package_validation_runs": 1, "package_verifier_runs": 1, "cache_hits": 0,
                    },
                    data["last_run_counters"],
                )
                self.assertFalse(data["last_run_timings"]["cache_hit"])
                second = subprocess.run(
                    [*command, "--reuse-valid-package"], capture_output=True, text=True,
                    check=False, timeout=20, env=env,
                )
                self.assertEqual(0, second.returncode, second.stderr)
                self.assertEqual(1, handler.request_count)
                data = json.loads((output / "validation.json").read_text(encoding="utf-8"))
                self.assertEqual(
                    {
                        "render_http_requests": 0, "render_rounds": 0,
                        "package_validation_runs": 1, "package_verifier_runs": 1, "cache_hits": 1,
                    },
                    data["last_run_counters"],
                )
                self.assertTrue(data["last_run_timings"]["cache_hit"])
                self.assertEqual(0, data["last_run_timings"]["render_ms"])
                with diagram_input.open("a", encoding="utf-8") as handle:
                    handle.write("' changed input\n")
                third = subprocess.run(
                    [*command, "--reuse-valid-package"], capture_output=True, text=True,
                    check=False, timeout=20, env=env,
                )
                self.assertEqual(0, third.returncode, third.stderr)
                self.assertEqual(2, handler.request_count)
                data = json.loads((output / "validation.json").read_text(encoding="utf-8"))
                self.assertFalse(data["last_run_timings"]["cache_hit"])
                self.assertEqual(1, data["last_run_counters"]["package_verifier_runs"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_failed_diagram_must_change_and_total_render_attempts_are_two(self) -> None:
        handler = type("AttemptHandler", (_Handler,), {"mode": "syntax", "request_count": 0})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                output = root / "package"
                diagram = root / "diagram-input.puml"
                diagram.write_bytes(VALID_DIAGRAM.read_bytes())
                command = [
                    "bash", str(VALIDATE_PACKAGE), "--diagram", str(diagram),
                    "--diagram-type", "fallback", "--out-dir", str(output),
                    "--server-url", f"http://127.0.0.1:{server.server_port}/plantuml",
                ]
                first = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
                self.assertEqual(1, first.returncode)
                first_data = json.loads((output / "validation.json").read_text(encoding="utf-8"))
                self.assertEqual(1, first_data["attempt_index"])
                self.assertTrue(first_data["repairable"])

                unchanged = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
                self.assertEqual(1, unchanged.returncode)
                self.assertEqual(1, handler.request_count)
                self.assertIn("失败图未发生变化", unchanged.stderr)

                diagram.write_text(VALID_DIAGRAM.read_text(encoding="utf-8") + "' targeted fix\n", encoding="utf-8")
                handler.mode = "success"
                second = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
                self.assertEqual(0, second.returncode, second.stderr)
                second_data = json.loads((output / "validation.json").read_text(encoding="utf-8"))
                self.assertEqual(2, second_data["attempt_index"])
                self.assertEqual(0, second_data["attempts_remaining"])
                self.assertEqual(2, handler.request_count)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_changed_typed_diagram_reuses_frozen_brief_validation(self) -> None:
        handler = type("BriefCacheHandler", (_Handler,), {"mode": "success", "request_count": 0})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                output = root / "package"
                diagram = root / "diagram-input.puml"
                diagram.write_bytes(ARCH_INVALID_DIAGRAM.read_bytes())
                command = [
                    "bash", str(VALIDATE_PACKAGE), "--diagram-type", "architecture",
                    "--brief", str(ARCH_BRIEF), "--diagram", str(diagram),
                    "--out-dir", str(output),
                    "--server-url", f"http://127.0.0.1:{server.server_port}/plantuml",
                ]
                first = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
                self.assertEqual(1, first.returncode)
                self.assertTrue((output / ".brief-lock.json").is_file())
                self.assertEqual(0, handler.request_count)

                diagram.write_bytes(ARCH_DIAGRAM.read_bytes())
                second = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
                self.assertEqual(0, second.returncode, second.stderr)
                data = json.loads((output / "validation.json").read_text(encoding="utf-8"))
                self.assertTrue(data["brief_validation_reused"])
                self.assertEqual(1, handler.request_count)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
