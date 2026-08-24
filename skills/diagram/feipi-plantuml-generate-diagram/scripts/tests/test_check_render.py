#!/usr/bin/env python3
"""check_render.sh 的单请求渲染回归。"""

from __future__ import annotations

import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
CHECK_RENDER = SCRIPT_DIR / "check_render.sh"
VALID_DIAGRAM = SCRIPT_DIR.parent / "assets/examples/fallback/fallback-diagram.example.puml"


class _Handler(BaseHTTPRequestHandler):
    mode = "success"
    request_count = 0

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        type(self).request_count += 1
        if type(self).mode == "syntax":
            body = b'<svg xmlns="http://www.w3.org/2000/svg"><text>Syntax Error [From string (line 2)]</text></svg>'
        elif type(self).mode == "invalid":
            body = b"not svg"
        else:
            body = b'<svg xmlns="http://www.w3.org/2000/svg"><text>ok</text></svg>'
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class CheckRenderTests(unittest.TestCase):
    def run_case(self, mode: str) -> tuple[subprocess.CompletedProcess[str], int]:
        handler = type("CaseHandler", (_Handler,), {"mode": mode, "request_count": 0})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "diagram.svg"
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
                return completed, handler.request_count
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_success_uses_one_svg_request(self) -> None:
        completed, count = self.run_case("success")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(1, count)
        self.assertIn("render_result=ok", completed.stdout)

    def test_syntax_error_uses_one_svg_request(self) -> None:
        completed, count = self.run_case("syntax")
        self.assertEqual(2, completed.returncode)
        self.assertEqual(1, count)
        self.assertIn("render_result=syntax_error", completed.stdout)

    def test_non_svg_response_is_not_accepted(self) -> None:
        completed, count = self.run_case("invalid")
        self.assertEqual(4, completed.returncode)
        self.assertEqual(1, count)


if __name__ == "__main__":
    unittest.main()
