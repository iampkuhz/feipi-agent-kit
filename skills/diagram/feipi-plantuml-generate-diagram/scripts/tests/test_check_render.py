#!/usr/bin/env python3
"""check_render.sh 的单请求渲染回归。"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
CHECK_RENDER = SCRIPT_DIR / "check_render.sh"
VALIDATE_PACKAGE = SCRIPT_DIR / "validate_package.sh"
VALID_DIAGRAM = SCRIPT_DIR.parent / "assets/examples/fallback/fallback-diagram.example.puml"


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
    def run_case(self, mode: str) -> tuple[subprocess.CompletedProcess[str], int, bool]:
        handler = type("CaseHandler", (_Handler,), {"mode": mode, "request_count": 0})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
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
        thread = threading.Thread(target=server.serve_forever, daemon=True)
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


if __name__ == "__main__":
    unittest.main()
