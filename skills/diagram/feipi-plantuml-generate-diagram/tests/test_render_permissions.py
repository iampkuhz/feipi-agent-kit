#!/usr/bin/env python3
"""以隔离 curl/Podman 验证权限诊断链路；不冒充真实沙箱或渲染证据。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_mindmap as runner

DIAGRAM = SKILL / "assets/examples/fallback/fallback-diagram.example.puml"
BRIEF = SKILL / "assets/examples/mindmap/mindmap-brief.example.yaml"


class RenderPermissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="plantuml-permission-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fakebin = self.root / "bin"
        fakebin.mkdir()
        (fakebin / "curl").write_text(
            '#!/bin/sh\nprintf "call\\n" >> "$FAKE_CURL_LOG"\n'
            'printf "%s\\n" "$FAKE_CURL_ERROR" >&2\nprintf "000"\n'
            'exit "$FAKE_CURL_EXIT"\n', encoding="utf-8",
        )
        (fakebin / "podman").write_text(
            '#!/bin/sh\nprintf "call\\n" >> "$FAKE_PODMAN_LOG"\nexit 1\n',
            encoding="utf-8",
        )
        for path in fakebin.iterdir():
            path.chmod(0o755)
        self.error = "curl: (7) Failed to connect: Operation not permitted"
        self.env = dict(os.environ, PATH=f"{fakebin}{os.pathsep}{os.environ['PATH']}",
                        AGENT_PLANTUML_SERVER_PORT="8199", FAKE_CURL_EXIT="7",
                        FAKE_CURL_ERROR=self.error, FAKE_CURL_LOG=str(self.root / "curl.log"),
                        FAKE_PODMAN_LOG=str(self.root / "podman.log"))

    def call(self, script, *args):
        return subprocess.run(["bash", str(SCRIPTS / script), *map(str, args)],
                              env=self.env, capture_output=True, text=True, timeout=20)

    def test_connection_permission_errors_are_identified_and_stale_svg_removed(self):
        for error in (self.error, "curl: (7) Failed to connect: Permission denied"):
            with self.subTest(error=error):
                self.env["FAKE_CURL_ERROR"] = error
                svg = self.root / "diagram.svg"
                svg.write_text("stale SVG", encoding="utf-8")
                result = self.call("check_render.sh", DIAGRAM, "--svg-output", svg)
                self.assertEqual(result.returncode, 5, result.stderr)
                self.assertFalse(svg.exists())
                for expected in ("render_failure_kind=permission_denied", error,
                                 "render_target=http://127.0.0.1:8199", "render_curl_exit_code=7",
                                 "render_http_status=000", "render_http_requests=1"):
                    self.assertIn(expected, result.stdout)

    def test_ambiguous_network_and_local_file_errors_are_not_permission_diagnoses(self):
        for code, error in ((7, "Failed to connect: Connection refused"),
                            (7, "Failed to connect to server"),
                            (28, "Operation timed out"),
                            (23, "Failure writing output: Permission denied")):
            with self.subTest(code=code, error=error):
                self.env.update(FAKE_CURL_EXIT=str(code), FAKE_CURL_ERROR=error)
                result = self.call("check_render.sh", DIAGRAM)
                self.assertEqual(result.returncode, 4, result.stderr)
                self.assertNotIn("permission_denied", result.stdout)
                self.assertIn(error, result.stdout)

    def test_preflight_preserves_evidence_without_start_or_recheck(self):
        output = self.root / "renderer-preflight.json"
        result = self.call("preflight_renderer.sh", "--out", output)
        self.assertEqual(result.returncode, 5, result.stderr)
        receipt = json.loads(output.read_text())
        self.assertEqual(receipt["final_status"], "blocked")
        self.assertEqual(receipt["blocked_reason"], "render_access_denied")
        self.assertEqual(receipt["failure_kind"], "permission_denied")
        self.assertEqual(receipt["render_target"], "http://127.0.0.1:8199")
        self.assertEqual(receipt["curl_exit_code"], 7)
        self.assertEqual(receipt["http_status"], "000")
        self.assertEqual(receipt["issue"], self.error)
        self.assertEqual(receipt["probe_attempts"], 1)
        self.assertEqual(receipt["http_requests"], 1)
        self.assertFalse(receipt["podman_start_attempted"])
        self.assertEqual(receipt["podman_start_result"], "skipped_access_denied")
        self.assertEqual(receipt["startup_policy"], "podman_once")
        self.assertFalse(receipt["process_management_allowed"])
        self.assertFalse((self.root / "podman.log").exists())

    def test_package_preserves_permission_reason_and_evidence(self):
        out = self.root / "package"
        result = self.call("validate_package.sh", "--diagram-type", "fallback",
                           "--diagram", DIAGRAM, "--out-dir", out)
        self.assertEqual(result.returncode, 1, result.stderr)
        contract = json.loads((out / "validation.json").read_text())
        self.assertEqual(contract["blocked_reason"], "render_access_denied")
        self.assertEqual(contract["failure_class"], "renderer")
        self.assertFalse(contract["repairable"])
        self.assertEqual(contract["final_status"], "blocked")
        self.assertEqual(contract["counters"]["render_http_requests"], 1)
        self.assertIn("render_reason=" + self.error, contract["issues"])
        self.assertIn("render_curl_exit_code=7", contract["issues"])
        self.assertIn("render_http_status=000", contract["issues"])
        self.assertFalse((out / "diagram.svg").exists())

    def test_mindmap_preflight_propagates_permission_error(self):
        out = self.root / "mindmap"
        with patch.dict(os.environ, self.env), patch.object(runner, "missing_dependencies", return_value=[]):
            result = runner.run(BRIEF, out, "auto")
        self.assertEqual(result["stage"], "preflight")
        self.assertEqual(result["reason"], "render_access_denied")
        self.assertIn(self.error, result["issues"])
        self.assertFalse((out / "diagram.puml").exists())
        self.assertFalse((self.root / "podman.log").exists())

    def test_mindmap_permission_error_after_successful_preflight(self):
        out = self.root / "mindmap"
        invoke = runner.invoke

        def with_successful_preflight(command, stage, log):
            if stage == "preflight":
                # 只替代先前成功的预检；实际图包验证仍调用真实脚本和隔离 curl。
                (out / "renderer-preflight.json").write_text(json.dumps({
                    "final_status": "success", "renderer_url": "http://127.0.0.1:8199",
                }), encoding="utf-8")
                return 0
            return invoke(command, stage, log)

        with patch.dict(os.environ, self.env), patch.object(runner, "missing_dependencies", return_value=[]), \
                patch.object(runner, "invoke", side_effect=with_successful_preflight):
            result = runner.run(BRIEF, out, "auto")
        self.assertEqual(result["stage"], "validate")
        self.assertEqual(result["reason"], "render_access_denied")
        self.assertIn("render_reason=" + self.error, result["issues"])
        self.assertFalse((out / "diagram.svg").exists())


if __name__ == "__main__":
    unittest.main()
