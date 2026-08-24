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
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

    def test_timeline_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "session-timing.jsonl"
            summary = root / "session-timing-summary.json"
            self.run_cli("init", "--log", str(log))

            phase = self.run_cli(
                "start", "--log", str(log), "--stage", "phase_1_material_modeling",
                "--activity", "phase", "--label", "阶段 1",
            ).stdout.strip()
            resource = self.run_cli(
                "start", "--log", str(log), "--stage", "phase_1_material_modeling",
                "--activity", "resource_read", "--label", "user-materials",
            ).stdout.strip()
            self.run_cli("end", "--log", str(log), "--span-id", resource)

            self.run_cli(
                "record-subagent", "--log", str(log), "--agent-role", "patent_prior_art_researcher",
                "--agent-id", "agent-1", "--model", "gpt-5.6-luna", "--reasoning-effort", "medium",
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
            self.run_cli("end", "--log", str(log), "--span-id", phase)

            diagram_validation = root / "validation.json"
            diagram_validation.write_text(
                json.dumps({"timings": {"render_ms": 12.5, "static_validation_ms": 7.25}}),
                encoding="utf-8",
            )
            self.run_cli(
                "ingest-diagram", "--log", str(log), "--label", "D1",
                "--validation", str(diagram_validation),
            )
            self.run_cli("summarize", "--log", str(log), "--output", str(summary))

            data = json.loads(summary.read_text(encoding="utf-8"))
            self.assertIn("phase_1_material_modeling", data["phases"])
            self.assertEqual(1, data["activities"]["resource_read"]["execution_count"])
            self.assertEqual(12.5, data["activities"]["render"]["duration_ms"])
            self.assertEqual(7.25, data["activities"]["validation"]["duration_ms"])
            self.assertEqual(1, data["subagents"]["unique_count"])
            self.assertEqual(1, data["subagents"]["execution_count"])
            self.assertEqual(1, data["subagents"]["wait_count"])
            self.assertEqual([], data["incomplete_spans"])


if __name__ == "__main__":
    unittest.main()
