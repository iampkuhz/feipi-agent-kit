#!/usr/bin/env python3
"""入口编排/路径/依赖的隔离回归；HTTP 与 PNG fixture 不是真实渲染证明。"""

import base64
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_mindmap as runner
from generate_mindmap import generate
from lib.brief_loader import load_yaml

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5f8AAAAASUVORK5CYII=")


@contextmanager
def renderer_fixture(*, delay=0, fail_render=False):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            time.sleep(delay)
            failed = fail_render and len(requests) > 1
            self.send_response(500 if failed else 200)
            self.send_header("Content-Type", "image/svg+xml")
            self.end_headers()
            try:
                self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40"><text x="1" y="20">fixture</text></svg>')
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mindmap 路径 ' ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.brief = self.root / "输入 brief.json"
        self.data = load_yaml(SKILL / "assets/examples/mindmap/mindmap-brief.example.yaml")
        self.brief.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        self.out = self.root / "图包 output"

    @staticmethod
    def fixture_preview(_svg, png, _log):
        png.write_bytes(PNG)

    def run_fixture(self, url="auto"):
        with patch.object(runner, "missing_dependencies", return_value=[]), patch.object(runner, "make_preview", side_effect=self.fixture_preview):
            return runner.run(self.brief, self.out, url)

    def test_custom_endpoint_paths_and_compact_receipt(self):
        with renderer_fixture() as (url, requests):
            result = self.run_fixture(url + "/plantuml")
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(result["visual_review"], "pending")
        self.assertEqual(len(requests), 2)  # 一个预检请求，一个图包请求。
        self.assertTrue(all(p.startswith("/plantuml/svg/") for p in requests))
        self.assertEqual(json.loads((self.out / "run-result.json").read_text()), result)
        self.assertTrue(all(Path(p).is_absolute() for p in result["paths"].values()))
        contract = json.loads((self.out / "validation.json").read_text())
        self.assertEqual(contract["metrics"]["node_count"], 13)
        self.assertEqual(contract["counters"]["render_rounds"], 1)
        self.assertEqual(contract["counters"]["package_verifier_runs"], 1)

    def test_environment_port_does_not_get_replaced_by_default(self):
        with renderer_fixture() as (url, requests), patch.dict(os.environ, {"AGENT_PLANTUML_SERVER_PORT": url.rsplit(":", 1)[1]}):
            result = self.run_fixture()
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(len(requests), 2)
        self.assertEqual(json.loads((self.out / "renderer-preflight.json").read_text())["renderer_url"], url)

    def test_slow_success_has_no_extra_request_or_retry(self):
        with renderer_fixture(delay=1.1) as (url, requests):
            result = self.run_fixture(url)
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(len(requests), 2)

    def test_preflight_timeout_stops_before_source_and_package(self):
        with renderer_fixture(delay=2.5) as (url, requests):
            result = self.run_fixture(url)
        self.assertEqual((result["status"], result["stage"]), ("blocked", "preflight"))
        self.assertEqual(len(requests), 1)
        self.assertFalse((self.out / "diagram.puml").exists())
        self.assertNotIn("validation", result["paths"])

    def test_package_failure_is_not_retried_and_keeps_contract(self):
        with renderer_fixture(fail_render=True) as (url, requests):
            result = self.run_fixture(url)
        self.assertEqual((result["status"], result["stage"]), ("blocked", "validate"))
        self.assertEqual(len(requests), 2)
        self.assertIn("validation", result["paths"])
        self.assertNotIn("preview", result["paths"])
        receipt = json.loads((self.out / "validation.json").read_text())
        self.assertEqual(receipt["attempt_index"], 1)
        self.assertEqual(receipt["failure_class"], "renderer")

    def test_invalid_brief_and_missing_dependency_never_invoke_renderer(self):
        self.data["nodes"][1]["parent"] = "missing"
        self.brief.write_text(json.dumps(self.data))
        with patch.object(runner, "missing_dependencies", return_value=[]), patch.object(runner, "invoke") as invoke:
            result = runner.run(self.brief, self.out)
            self.assertEqual(result["stage"], "brief")
            invoke.assert_not_called()
        with patch.object(runner, "missing_dependencies", return_value=["rsvg-convert"]), patch.object(runner, "invoke") as invoke:
            result = runner.run(self.brief, self.out)
            self.assertEqual(result["reason"], "missing_dependencies")
            self.assertIn("rsvg-convert", result["issues"][0])
            invoke.assert_not_called()

    def test_missing_yaml_dependency_is_reported(self):
        with patch.object(runner.importlib.util, "find_spec", return_value=None), patch.object(runner.shutil, "which", side_effect=lambda name: None if name == "ruby" else "/fixture/" + name):
            self.assertEqual(runner.missing_dependencies(), ["PyYAML 或 Ruby（读取 YAML）"])

    def test_existing_source_and_receipt_are_preserved(self):
        self.out.mkdir()
        for filename in ("diagram.puml", "renderer-preflight.json", "validation.json"):
            path = self.out / filename
            path.write_text("用户已有内容")
            with patch.object(runner, "invoke") as invoke:
                result = runner.run(self.brief, self.out)
                self.assertEqual(result["reason"], "existing_package")
                self.assertEqual(path.read_text(), "用户已有内容")
                invoke.assert_not_called()
            path.unlink()

    def test_preview_failure_preserves_validated_svg(self):
        with renderer_fixture() as (url, requests), patch.object(runner, "missing_dependencies", return_value=[]), patch.object(runner, "make_preview", side_effect=runner.RunError("preview", "preview_failed", ["fixture 转换失败"])):
            result = runner.run(self.brief, self.out, url)
        self.assertEqual((result["status"], result["stage"]), ("blocked", "preview"))
        self.assertEqual(len(requests), 2)
        self.assertIn("svg", result["paths"])
        self.assertNotIn("preview", result["paths"])
        self.assertEqual(json.loads((self.out / "validation.json").read_text())["final_status"], "success")

    def test_preview_timeout_and_invalid_png_remove_temporary_output(self):
        self.out.mkdir()
        svg, png, log = self.out / "diagram.svg", self.out / "diagram.png", self.out / "run.log"
        for error in (subprocess.TimeoutExpired("fixture", 30), None):
            def invoke(_cmd, _stage, _log, **_kwargs):
                png.with_suffix(".pending.png").write_text("not a PNG")
                if error:
                    raise error
                return 0
            with patch.object(runner, "invoke", side_effect=invoke):
                with self.assertRaises((runner.RunError, subprocess.TimeoutExpired)):
                    runner.make_preview(svg, png, log)
            self.assertFalse(png.exists())
            self.assertFalse(png.with_suffix(".pending.png").exists())

    def test_relocated_skill_cli_resolves_resources_outside_cwd(self):
        installed = self.root / "安装 skill"
        shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        converter = fake_bin / "rsvg-convert"
        converter.write_text("#!/bin/sh\nexit 99\n")  # 非法 brief 不应调用它。
        converter.chmod(0o755)
        self.data["diagram_id"] = "invalid_id"
        self.brief.write_text(json.dumps(self.data))
        env = {**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
        result = subprocess.run([
            sys.executable, str(installed / "scripts/run_mindmap.py"), "--brief", self.brief.name,
            "--out-dir", self.out.name,
        ], cwd=self.root, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["stage"], "brief", receipt)
        self.assertIn("diagram_id", receipt["issues"][0])


class SameFileTests(unittest.TestCase):
    def test_same_file_variants_reach_coverage_and_preserve_input(self):
        data = load_yaml(SKILL / "assets/examples/mindmap/mindmap-brief.example.yaml")
        raw = generate(data).replace("+++[#DBEAFE] 目标用户与使用场景\n", "")
        for variant in ("identical", "relative", "symlink", "hardlink"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="same file 中文 '") as tmp:
                root = Path(tmp)
                diagram, brief = root / "diagram.puml", root / "brief.normalized.yaml"
                diagram.write_text(raw)
                brief.write_text(json.dumps(data, ensure_ascii=False))
                inputs = [diagram, brief]
                if variant in ("symlink", "hardlink"):
                    inputs = [root / "源码 alias.puml", root / "需求 alias.json"]
                    for source, alias in zip((diagram, brief), inputs):
                        if variant == "symlink":
                            alias.symlink_to(source)
                        else:
                            os.link(source, alias)
                args = [p.name if variant == "relative" else str(p) for p in inputs]
                result = subprocess.run([
                    "bash", str(SCRIPTS / "validate_package.sh"), "--diagram-type", "mindmap",
                    "--diagram", args[0], "--brief", args[1], "--out-dir", str(root),
                    "--server-url", "http://127.0.0.1:1",
                ], cwd=root, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotIn("identical", result.stderr)
                contract = json.loads((root / "validation.json").read_text())
                self.assertEqual(contract["failure_class"], "coverage")
                self.assertEqual(contract["counters"]["render_http_requests"], 0)
                self.assertEqual(diagram.read_text(), raw)

    def test_parent_overview_same_file_copy_reaches_brief_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evidence").mkdir()
            parent = root / "evidence/overview.json"
            parent.write_text('{}')
            brief = root / "brief.normalized.yaml"
            brief.write_text(json.dumps({"diagram_id": "D1", "diagram_type": "component", "parent_component_ref": {
                "overview_brief_path": "evidence/overview.json", "overview_brief_sha256": hashlib.sha256(parent.read_bytes()).hexdigest(),
            }}))
            diagram = root / "diagram.puml"
            diagram.write_text("@startuml\ncomponent Test\n@enduml\n")
            result = subprocess.run([
                "bash", str(SCRIPTS / "validate_package.sh"), "--diagram-type", "component",
                "--brief", str(brief), "--diagram", str(diagram), "--out-dir", str(root),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            contract = json.loads((root / "validation.json").read_text())
            self.assertEqual(contract["blocked_reason"], "brief_validation_failed")
            self.assertEqual(contract["counters"]["render_http_requests"], 0)
            self.assertEqual(parent.read_text(), '{}')


if __name__ == "__main__":
    unittest.main()
