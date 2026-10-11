#!/usr/bin/env python3
"""计时异常、最终报告复核和缓存原记录保护的回归。"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
from lib.package_verifier import verify_package_dir
from lib.runtime_observation import RunClock
from validate_package import PackageRun
from test_package_verifier import build_package


class ObservationTests(unittest.TestCase):
    def test_clock_rejects_backwards_or_render_exceeding_total(self):
        with patch("lib.runtime_observation.time.monotonic_ns", side_effect=[10_000_000, 9_000_000]):
            clock = RunClock()
            with self.assertRaisesRegex(ValueError, "timing_observation_invalid"):
                clock.timings()
        with patch("lib.runtime_observation.time.monotonic_ns", side_effect=[10_000_000, 11_000_000]):
            clock = RunClock()
            clock.render_ns = 2_000_000
            with self.assertRaisesRegex(ValueError, "timing_observation_invalid"):
                clock.timings()

    def test_writer_does_not_clamp_negative_or_inconsistent_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "validation.json"
            for total, render, static in ((-1, 0, 0), (1, 2, 0), (float("nan"), 0, 0)):
                command = [sys.executable, str(SCRIPTS / "lib/write_validation.py"), "--output", str(path),
                           "--total-duration-ms", str(total), "--render-duration-ms", str(render),
                           "--static-validation-duration-ms", str(static)]
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("timing_observation_invalid", result.stderr)
                self.assertFalse(path.exists())

    def package_run(self, base):
        return PackageRun(argparse.Namespace(
            diagram_type="component", diagram=str(base / "diagram.puml"), brief=str(base / "brief.normalized.yaml"),
            out_dir=str(base), server_url="auto", reuse_valid_package=True,
        ), RunClock())

    def test_cache_checks_final_bytes_after_freezing_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            initial = json.loads((base / "validation.json").read_text())
            run = self.package_run(base)
            observed = []
            original = run.invoke

            def capture(command):
                if "verify_package.py" in str(command[1]):
                    observed.append((base / "validation.json").read_bytes())
                    # 模拟慢 verifier，证明最终 verifier 之后不会再回写 timing。
                    time.sleep(0.02)
                return original(command)

            with patch.object(run, "invoke", side_effect=capture):
                self.assertEqual(run.try_cache(), 0)
            final = (base / "validation.json").read_bytes()
            data = json.loads(final)
            self.assertEqual(len(observed), 2)
            self.assertEqual(final, observed[-1])
            self.assertEqual(data["timings"], initial["timings"])
            self.assertEqual(data["counters"], initial["counters"])
            self.assertEqual(data["last_run_counters"]["package_verifier_runs"], 2)
            self.assertEqual(data["last_run_timings"]["render_ms"], 0)
            self.assertEqual(verify_package_dir(base), [])

    def test_invalid_original_cache_is_not_repaired_into_a_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            path = base / "validation.json"
            data = json.loads(path.read_text())
            data["timings"]["total_ms"] = -1
            path.write_text(json.dumps(data))
            before = path.read_bytes()
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertIsNone(self.package_run(base).try_cache())
            self.assertEqual(path.read_bytes(), before)
            self.assertIn("timings.total_ms", stderr.getvalue())

    def test_final_file_tampering_blocks_success_with_concrete_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            run = self.package_run(base)
            original = run.invoke
            calls = 0

            def corrupt_final(command):
                nonlocal calls
                if "verify_package.py" in str(command[1]):
                    calls += 1
                    if calls == 2:
                        path = base / "validation.json"
                        data = json.loads(path.read_text())
                        data["last_run_timings"]["total_ms"] = -1
                        data["puml_sha256"] = "0" * 64
                        path.write_text(json.dumps(data))
                return original(command)

            stderr, stdout = io.StringIO(), io.StringIO()
            with patch.object(run, "invoke", side_effect=corrupt_final), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
                self.assertEqual(run.try_cache(), 1)
            data = json.loads((base / "validation.json").read_text())
            self.assertEqual(data["blocked_reason"], "package_verification_failed")
            self.assertEqual(data["final_status"], "blocked")
            for expected in ("last_run_timings.total_ms", "puml_sha256"):
                self.assertIn(expected, stderr.getvalue())
                self.assertTrue(any(expected in issue for issue in data["issues"]))
            self.assertNotIn("final_status=success", stdout.getvalue())

    def test_contract_upgrade_does_not_reset_failed_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            path = base / "validation.json"
            data = json.loads(path.read_text())
            data.update(final_status="blocked", render_contract_version="3", repairable=True, attempt_index=2)
            path.write_text(json.dumps(data))
            # 源码已经修改，仍不能因合同升版而获取第三次渲染。
            with (base / "diagram.puml").open("a") as stream:
                stream.write("\n' changed\n")
            with self.assertRaisesRegex(ValueError, "最多 2 次"):
                self.package_run(base).retry_guard()


if __name__ == "__main__":
    unittest.main()
