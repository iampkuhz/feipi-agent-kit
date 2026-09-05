#!/usr/bin/env python3
"""活动图真实控制流回归；fixture 来自已成功渲染的 Gate 图源码。"""

from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR.parent))

from check_coverage import check_activity_coverage, normalize_text
from lib.brief_loader import load_yaml
from lib.puml_analysis import (
    analyze_activity_flow, compute_puml_metrics, parse_activities, parse_activity_relations,
)


def diagram(body: str) -> str:
    return f"@startuml\nstart\n{body}\n@enduml\n"


def edges(raw: str) -> set[tuple[str, str, str]]:
    return {(edge.source, edge.target, edge.label) for edge in parse_activity_relations(raw)}


class ActivityControlFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = (TEST_DIR / "activity-gate-control-flow.puml").read_text(encoding="utf-8")
        self.brief = load_yaml(TEST_DIR / "activity-gate-control-flow-brief.yaml")

    def coverage(self, raw: str, brief: dict | None = None) -> list[str]:
        return check_activity_coverage(brief or self.brief, raw, normalize_text(raw))

    def test_rendered_gate_fixture_matches_every_brief_transition(self) -> None:
        expected = {(item["from"], item["to"], item.get("description", ""))
                    for item in self.brief["transitions"]}
        self.assertEqual(expected, edges(self.gate))
        self.assertEqual(9, len(parse_activity_relations(self.gate)))
        self.assertEqual([], self.coverage(self.gate))
        self.assertIn(("S1", "S6", "plan / run"), expected)
        self.assertFalse(any(source == "S5" for source, _, _ in edges(self.gate)))
        self.assertEqual({"node_count": 10, "edge_count": 9, "max_degree": 2},
                         compute_puml_metrics("activity", self.gate))

    def test_missing_real_edge_is_rejected(self) -> None:
        brief = copy.deepcopy(self.brief)
        brief["transitions"] = [item for item in brief["transitions"]
                                if (item["from"], item["to"]) != ("S1", "S6")]
        self.assertTrue(any("额外转移" in error for error in self.coverage(self.gate, brief)))

    def test_fake_cross_branch_edge_is_rejected(self) -> None:
        brief = copy.deepcopy(self.brief)
        brief["transitions"].append({"from": "S5", "to": "S6"})
        self.assertTrue(any("S5 -> S6" in error for error in self.coverage(self.gate, brief)))

    def test_changed_branch_label_is_rejected(self) -> None:
        errors = self.coverage(self.gate.replace("then (health)", "then (other)"))
        self.assertTrue(any("未落图" in error for error in errors))
        self.assertTrue(any("额外转移" in error for error in errors))

    def test_sequential_steps_and_end(self) -> None:
        self.assertEqual({("S1", "S2", "")}, edges(diagram(":S1 输入;\n:S2 输出;\nend")))

    def test_mutually_exclusive_branches_merge(self) -> None:
        raw = diagram(":S1 输入;\nif (条件) then (是)\n:S2 接受;\nelse (否)\n:S3 拒绝;\nendif\n:S4 输出;\nstop")
        self.assertEqual({("S1", "S2", "是"), ("S1", "S3", "否"),
                          ("S2", "S4", ""), ("S3", "S4", "")}, edges(raw))

    def test_terminated_branch_does_not_join(self) -> None:
        for terminal in ("stop", "end"):
            with self.subTest(terminal=terminal):
                raw = diagram(f":S1 输入;\nif (条件) then (是)\n:S2 接受;\n{terminal}\nelse (否)\n:S3 拒绝;\nendif\n:S4 输出;\nstop")
                self.assertEqual({("S1", "S2", "是"), ("S1", "S3", "否"),
                                  ("S3", "S4", "")}, edges(raw))

    def test_if_without_else_keeps_bypass(self) -> None:
        raw = diagram(":S1 输入;\nif (条件) then (是)\n:S2 处理;\nendif\n:S3 输出;\nstop")
        self.assertEqual({("S1", "S2", "是"), ("S1", "S3", ""), ("S2", "S3", "")}, edges(raw))

    def test_no_else_terminated_then_keeps_bypass(self) -> None:
        raw = diagram(":S1 输入;\nif (条件) then (是)\n:S2 处理;\nstop\nendif\n:S3 输出;\nstop")
        self.assertEqual({("S1", "S2", "是"), ("S1", "S3", "")}, edges(raw))

    def test_nested_branches_restore_entry_and_join(self) -> None:
        raw = diagram(":S1 输入;\nif (外层) then (外是)\n:S2 分流;\nif (内层) then (内是)\n:S3 接受;\nelse (内否)\n:S4 拒绝;\nendif\nelse (外否)\n:S5 旁路;\nendif\n:S6 输出;\nstop")
        self.assertEqual({("S1", "S2", "外是"), ("S1", "S5", "外否"),
                          ("S2", "S3", "内是"), ("S2", "S4", "内否"),
                          ("S3", "S6", ""), ("S4", "S6", ""), ("S5", "S6", "")}, edges(raw))

    def test_consecutive_decisions_preserve_all_labels(self) -> None:
        raw = diagram(":S1 输入;\nif (外层) then (外是)\nif (内层) then (内是)\n:S2 处理;\nendif\nelse (外否)\n:S3 旁路;\nendif\n:S4 输出;\nstop")
        self.assertEqual({("S1", "S2", "外是 && 内是"), ("S1", "S3", "外否"),
                          ("S1", "S4", "外是"), ("S2", "S4", ""), ("S3", "S4", "")}, edges(raw))

    def test_missing_endif_is_an_explicit_coverage_error(self) -> None:
        raw = self.gate.replace("endif", "", 1)
        self.assertTrue(any("缺少 endif" in error for error in self.coverage(raw)))
        with self.assertRaisesRegex(ValueError, "缺少 endif"):
            parse_activity_relations(raw)

    def test_unknown_control_flow_is_not_silently_accepted(self) -> None:
        for control in ("while (条件)", "endwhile", "repeat", "fork", "fork again", "end fork",
                        "switch (条件)", "case (是)", "endswitch", "goto target", "detach", "kill",
                        "elseif (条件) then (是)", "S1 --> S2", "if (条件)"):
            with self.subTest(control=control):
                errors = self.coverage(self.gate.replace("start\n", f"start\n{control}\n", 1))
                self.assertTrue(any("不支持或无法解析" in error for error in errors), errors)

    def test_unmatched_and_duplicate_branch_markers_fail(self) -> None:
        for body in ("else (否)", "endif", "if (条件) then (是)\nelse (否)\nelse (重复)\nendif"):
            with self.subTest(body=body):
                self.assertTrue(analyze_activity_flow(diagram(body)).errors)

    def test_unreachable_step_after_stop_fails(self) -> None:
        raw = diagram(":S1 输入;\nstop\n:S2 不可达;")
        self.assertTrue(any("不可达" in error for error in analyze_activity_flow(raw).errors))

    def test_invalid_declarations_are_rejected_but_still_counted(self) -> None:
        raw = diagram('activity "S1 输入" as S1\nactivity "S2 输出" as S2\nS1 --> S2\nstop')
        self.assertEqual(2, len(parse_activities(raw)))
        self.assertTrue(any("不支持 activity 声明语法" in error for error in self.coverage(raw)))
        self.assertEqual(2, compute_puml_metrics("activity", raw)["node_count"])

    def test_legend_note_and_skinparam_do_not_create_steps(self) -> None:
        raw = diagram("skinparam activity {\nBackgroundColor white\n}\n:S1 输入;\nnote right\n:S99 说明;\nif (说明) then (说明)\nend note\n:S2 输出;\nstop\nlegend right\n:S98 说明;\nendlegend")
        self.assertEqual({("S1", "S2", "")}, edges(raw))
        self.assertEqual(2, len(parse_activities(raw)))

    def test_block_comments_do_not_create_steps(self) -> None:
        raw = diagram(":S1 输入;\n/'\n:S99 说明;\nif (说明) then (说明)\n'/\n:S2 输出;\nstop")
        self.assertEqual({("S1", "S2", "")}, edges(raw))
        self.assertEqual(2, len(parse_activities(raw)))

    def test_unclosed_display_block_fails(self) -> None:
        self.assertTrue(any("展示块未闭合" in error for error in
                            analyze_activity_flow(diagram(":S1 输入;\nlegend\n说明")).errors))

    def test_single_modern_entry_and_diagram_boundaries_required(self) -> None:
        for raw in (diagram(":S1 输入;").replace("start\n", ""),
                    diagram("start\n:S1 输入;"),
                    diagram(":S1 输入;").replace("@enduml", "")):
            with self.subTest(raw=raw):
                self.assertTrue(analyze_activity_flow(raw).errors)

    def test_modern_activity_default_vertical_layout_passes(self) -> None:
        skill = TEST_DIR.parent.parent
        for stem in ("activity", "activity-branch"):
            with self.subTest(stem=stem):
                result = subprocess.run(
                    ["bash", str(skill / "scripts/lint_layout.sh"), "--type", "activity",
                     str(skill / f"assets/examples/activity/{stem}-diagram.example.puml"),
                     str(skill / f"assets/examples/activity/{stem}-brief.example.yaml")],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_modern_activity_rejects_generic_direction_declarations(self) -> None:
        skill = TEST_DIR.parent.parent
        brief = skill / "assets/examples/activity/activity-brief.example.yaml"
        raw = (skill / "assets/examples/activity/activity-diagram.example.puml").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "activity.puml"
            for direction in ("top to bottom direction", "left to right direction"):
                with self.subTest(direction=direction):
                    target.write_text(raw.replace("start\n", f"{direction}\nstart\n"))
                    result = subprocess.run(
                        ["bash", str(skill / "scripts/lint_layout.sh"), "--type", "activity",
                         str(target), str(brief)], capture_output=True, text=True, check=False,
                    )
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("默认纵向", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
