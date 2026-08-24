#!/usr/bin/env python3
"""session_timing.py 的端到端合同测试。"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "session_timing.py"


class SessionTimingTests(unittest.TestCase):
    def run_cli_raw(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *args], capture_output=True, text=True,
            check=False, timeout=10,
        )

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        completed = self.run_cli_raw(*args)
        if completed.returncode != 0:
            self.fail(f"CLI failed ({completed.returncode}): {completed.stderr}")
        return completed

    def span(self, log: Path, stage: str, activity: str, label: str) -> None:
        span_id = self.run_cli(
            "start", "--log", str(log), "--stage", stage,
            "--activity", activity, "--label", label,
        ).stdout.strip()
        self.run_cli("end", "--log", str(log), "--span-id", span_id)

    @staticmethod
    def write_diagram_observation(path: Path, *, cache_hit: bool) -> None:
        if cache_hit:
            timings = {"total_ms": 3.0, "render_ms": 0.0, "static_validation_ms": 3.0, "cache_hit": True}
            counters = {
                "render_http_requests": 0, "render_rounds": 0,
                "package_validation_runs": 1, "package_verifier_runs": 1, "cache_hits": 1,
            }
        else:
            timings = {"total_ms": 19.75, "render_ms": 12.5, "static_validation_ms": 7.25, "cache_hit": False}
            counters = {
                "render_http_requests": 1, "render_rounds": 1,
                "package_validation_runs": 1, "package_verifier_runs": 1, "cache_hits": 0,
            }
        path.write_text(
            json.dumps(
                {
                    "final_status": "success", "render_result": "ok",
                    "last_run_timings": timings, "last_run_counters": counters,
                }
            ),
            encoding="utf-8",
        )

    def test_complete_timeline_summary_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "session-timing.jsonl"
            summary_path = root / "session-timing-summary.json"
            initialized = self.run_cli("init", "--log", str(log), "--runtime-session-id", "runtime-42")
            first_session_id = initialized.stdout.splitlines()[0].split("=", 1)[1]

            phase_1 = self.run_cli(
                "start", "--log", str(log), "--stage", "phase_1_material_modeling",
                "--activity", "phase", "--label", "phase-1",
            ).stdout.strip()
            self.span(log, "phase_1_material_modeling", "resource_read", "user-materials-and-entry-resource")
            self.span(log, "phase_1_material_modeling", "retrieval", "two-query-lanes")
            self.run_cli(
                "record-subagent", "--log", str(log),
                "--agent-role", "patent_prior_art_researcher", "--agent-id", "agent-1",
                "--model", "gpt-5.6-luna", "--effective-model", "gpt-5.6-luna",
                "--reasoning-effort", "medium", "--effective-reasoning-effort", "medium",
            )
            execution = self.run_cli(
                "start", "--log", str(log), "--stage", "phase_1_material_modeling",
                "--activity", "subagent_execution", "--label", "research-1",
                "--agent-role", "patent_prior_art_researcher", "--agent-id", "agent-1",
                "--model", "gpt-5.6-luna", "--reasoning-effort", "medium",
            ).stdout.strip()
            wait = self.run_cli(
                "start", "--log", str(log), "--stage", "phase_1_material_modeling",
                "--activity", "subagent_wait", "--label", "research-1",
                "--agent-role", "patent_prior_art_researcher", "--agent-id", "agent-1",
            ).stdout.strip()
            self.run_cli("end", "--log", str(log), "--span-id", wait)
            self.run_cli("end", "--log", str(log), "--span-id", execution)
            self.run_cli("end", "--log", str(log), "--span-id", phase_1)

            self.run_cli(
                "start", "--log", str(log), "--stage", "phase_2_idea_confirmation",
                "--activity", "phase", "--label", "phase-2",
            )
            self.run_cli(
                "end", "--log", str(log), "--stage", "phase_2_idea_confirmation",
                "--activity", "phase",
            )

            phase_3 = self.run_cli(
                "start", "--log", str(log), "--stage", "phase_3_final_drafting",
                "--activity", "phase", "--label", "phase-3",
            ).stdout.strip()
            self.span(log, "phase_3_final_drafting", "diagram_generation", "D1-D2")
            diagram_validation = root / "validation.json"
            self.write_diagram_observation(diagram_validation, cache_hit=False)
            self.run_cli(
                "ingest-diagram", "--log", str(log), "--label", "D1",
                "--validation", str(diagram_validation),
            )
            self.write_diagram_observation(diagram_validation, cache_hit=True)
            self.run_cli(
                "ingest-diagram", "--log", str(log), "--label", "D1-cache",
                "--validation", str(diagram_validation),
            )
            self.run_cli("end", "--log", str(log), "--span-id", phase_3)

            phase_4 = self.run_cli(
                "start", "--log", str(log), "--stage", "phase_4_review_delivery",
                "--activity", "phase", "--label", "phase-4",
            ).stdout.strip()
            disclosure_validation = root / "disclosure-validation.json"
            disclosure_validation.write_text(
                json.dumps(
                    {
                        "operation_counts": {
                            "disclosure_validation_runs": 1,
                            "diagram_package_verifier_runs": 2,
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.run_cli(
                "run", "--log", str(log), "--stage", "phase_4_review_delivery",
                "--activity", "validation", "--label", "disclosure-package",
                "--result-json", str(disclosure_validation), "--",
                "python3", "-c", "pass",
            )
            self.run_cli("end", "--log", str(log), "--span-id", phase_4)

            self.run_cli(
                "summarize", "--log", str(log), "--output", str(summary_path),
                "--require-complete", "--close-session",
            )
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertTrue(data["coverage"]["complete"])
            self.assertEqual([], data["incomplete_spans"])
            self.assertEqual("runtime-42", data["runtime_session_id"])
            self.assertTrue(data["ended_at"])
            self.assertGreaterEqual(data["session_wall_duration_ms"], 0)
            self.assertEqual("session-timing.jsonl", data["timing_log"])
            self.assertEqual(4, len(data["phases"]))
            for item in data["phases"].values():
                self.assertTrue(item["started_at"])
                self.assertTrue(item["ended_at"])
                self.assertEqual(1, item["execution_count"])
            self.assertEqual(1, data["activities"]["resource_read"]["execution_count"])
            self.assertEqual(1, data["activities"]["retrieval"]["execution_count"])
            self.assertEqual(1, data["activities"]["diagram_generation"]["execution_count"])
            self.assertEqual(2, data["activities"]["render"]["execution_count"])
            self.assertEqual(12.5, data["activities"]["render"]["duration_ms"])
            self.assertEqual(3, data["activities"]["validation"]["execution_count"])
            self.assertEqual(1, data["subagents"]["unique_count"])
            self.assertEqual(1, data["subagents"]["execution_count"])
            self.assertEqual(1, data["subagents"]["wait_count"])
            self.assertEqual("gpt-5.6-luna", data["subagents"]["assignments"][0]["effective_model"])
            self.assertEqual(
                {
                    "render_http_requests": 1, "render_rounds": 1,
                    "package_validation_runs": 2, "package_verifier_runs": 2, "cache_hits": 1,
                },
                data["diagram_operations"],
            )
            self.assertEqual(
                {"disclosure_validation_runs": 1, "diagram_package_verifier_runs": 2},
                data["final_validation_operations"],
            )
            self.assertEqual(4, data["total_package_verifier_runs"])
            events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            sources = [event.get("source") for event in events if event.get("source")]
            self.assertEqual(
                ["D1/validation.json", "D1/validation.json", "D1-cache/validation.json", "D1-cache/validation.json"],
                sources,
            )
            closed_commands = (
                ("start", "--log", str(log), "--stage", "phase_1_material_modeling", "--activity", "phase", "--label", "late"),
                ("end", "--log", str(log), "--stage", "phase_4_review_delivery", "--activity", "phase"),
                (
                    "record-subagent", "--log", str(log), "--agent-role", "late", "--agent-id", "late-1",
                    "--model", "gpt-5.6-luna", "--reasoning-effort", "medium",
                ),
                ("ingest-diagram", "--log", str(log), "--label", "late", "--validation", str(diagram_validation)),
                (
                    "run", "--log", str(log), "--stage", "phase_4_review_delivery",
                    "--activity", "validation", "--label", "late", "--", "python3", "-c", "pass",
                ),
            )
            for command in closed_commands:
                with self.subTest(command=command[0]):
                    rejected = self.run_cli_raw(*command)
                    self.assertEqual(2, rejected.returncode)
                    self.assertIn("已关闭", rejected.stderr)
            new_session = self.run_cli("init", "--log", str(log))
            new_session_id = new_session.stdout.splitlines()[0].split("=", 1)[1]
            self.assertNotEqual(first_session_id, new_session_id)

    def test_incomplete_session_cannot_close_or_be_reinitialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "session-timing.jsonl"
            self.run_cli("init", "--log", str(log))
            incomplete = self.run_cli_raw(
                "summarize", "--log", str(log), "--require-complete", "--close-session",
            )
            self.assertEqual(1, incomplete.returncode)
            summary = json.loads(incomplete.stdout)
            self.assertFalse(summary["coverage"]["complete"])
            self.assertEqual(4, len(summary["coverage"]["missing_phases"]))
            self.assertEqual(5, len(summary["coverage"]["missing_activities"]))
            self.assertEqual(2, self.run_cli_raw("init", "--log", str(log)).returncode)
            resumed = self.run_cli("init", "--log", str(log), "--resume")
            self.assertIn("resumed=true", resumed.stdout)

    def test_diagram_ingest_rejects_historical_or_incomplete_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "session-timing.jsonl"
            validation = root / "validation.json"
            self.run_cli("init", "--log", str(log))
            validation.write_text(
                json.dumps(
                    {
                        "final_status": "success", "render_result": "ok",
                        "timings": {"total_ms": 20, "render_ms": 12, "static_validation_ms": 8},
                    }
                ),
                encoding="utf-8",
            )
            completed = self.run_cli_raw(
                "ingest-diagram", "--log", str(log), "--label", "D1", "--validation", str(validation),
            )
            self.assertEqual(2, completed.returncode)
            self.assertIn("last_run_timings", completed.stderr)

    def test_exit_two_is_review_required_and_unreported_model_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "session-timing.jsonl"
            self.run_cli("init", "--log", str(log))
            self.run_cli(
                "record-subagent", "--log", str(log), "--agent-role", "reviewer",
                "--agent-id", "agent-unknown", "--model", "gpt-5.6-sol", "--reasoning-effort", "high",
            )
            completed = self.run_cli_raw(
                "run", "--log", str(log), "--stage", "phase_4_review_delivery",
                "--activity", "validation", "--label", "review-required", "--",
                "python3", "-c", "raise SystemExit(2)",
            )
            self.assertEqual(2, completed.returncode)
            events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            spawn = next(event for event in events if event["event"] == "subagent_spawn")
            self.assertEqual("unknown", spawn["effective_model"])
            self.assertEqual("runtime_not_reported", spawn["fallback_reason"])
            end = next(
                event for event in events
                if event.get("label") == "review-required" and event["event"] == "span_end"
            )
            self.assertEqual("review_required", end["status"])


if __name__ == "__main__":
    unittest.main()
