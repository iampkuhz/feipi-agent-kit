#!/usr/bin/env python3
"""时序 note 几何选择、阈值、内容保留和批量 CLI 回归。"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from plan_sequence_notes import plan_files
from lib.sequence_notes import display_width, plan_brief, plan_diagram, wrap_text
from lib.brief_loader import load_yaml
from lib.profile_validators import validate_profile_semantics


def diagram(text="说明", source="a", target="c"):
    return {"id": "D1", "participants": ["a", "b", "c"],
            "geometry": {"left": 0, "right": 128, "x": {"a": 14, "b": 64, "c": 114}},
            "notes": [{"id": "M1", "from": source, "to": target, "text": text}]}


def note(value):
    return plan_diagram(value)["notes"][0]


class SequenceNotesTests(unittest.TestCase):
    def test_physical_direction_and_return_arrow(self):
        for source, target, expected in [("a", "b", "right"), ("b", "a", "right"),
                                          ("b", "c", "left"), ("c", "b", "left")]:
            with self.subTest(source=source, target=target):
                self.assertEqual(note(diagram(source=source, target=target))["placement"], expected)

    def test_equal_space_prefers_right(self):
        self.assertEqual(note(diagram())["placement"], "right")

    def test_four_lines_and_three_saved_exact_boundary(self):
        result = note(diagram("中" * 20))
        self.assertEqual((result["side_line_count"], result["across_line_count"]), (4, 1))
        self.assertEqual(result["placement"], "across")
        self.assertTrue(result["puml"].startswith("note across\n"))

    def test_three_side_lines_stay_inline(self):
        self.assertEqual(note(diagram("中" * 15))["placement"], "right")

    def test_four_lines_but_only_two_saved_stay_inline(self):
        result = note(diagram("中" * 15 + "\n另"))
        self.assertEqual((result["side_line_count"], result["across_line_count"]), (4, 2))
        self.assertEqual(result["placement"], "right")

    def test_self_message(self):
        self.assertEqual(note(diagram(source="a", target="a"))["placement"], "right")
        self.assertEqual(note(diagram(source="c", target="c"))["placement"], "left")

    def test_no_side_space_uses_across(self):
        value = diagram()
        value["geometry"] = {"left": 10, "right": 118, "x": {"a": 14, "b": 64, "c": 114}}
        result = note(value)
        self.assertEqual(result["reason"], "no_side_space")
        self.assertIsNone(result["side_line_count"])

    def test_no_space_anywhere_rejected(self):
        value = diagram()
        value["geometry"] = {"left": 0, "right": 4, "x": {"a": 1, "b": 2, "c": 3}}
        with self.assertRaisesRegex(ValueError, "均无足够空间"):
            note(value)

    def test_width_tracks_distance_to_edge(self):
        left_pair = note(diagram(source="a", target="b"))
        whole_span = note(diagram())
        self.assertGreater(left_pair["widths"]["right"], whole_span["widths"]["right"])

    def test_mixed_width_and_content_preserved(self):
        text = "校验API请求编号，核对payment_status和金额。"
        lines = wrap_text(text, 12)
        self.assertEqual("".join(lines), text)
        self.assertTrue(all(display_width(line) <= 12 for line in lines))
        self.assertEqual(display_width("中Ae\u0301"), 4)
        self.assertEqual(wrap_text("Ae\u0301B", 2), ["Ae\u0301", "B"])

    def test_words_and_explicit_paragraphs(self):
        self.assertEqual(wrap_text("hello world", 7), ["hello", "world"])
        self.assertEqual(wrap_text("一\\n二\n\n三", 4), ["一", "二", "", "三"])
        self.assertEqual(wrap_text("abcdefghijkl", 5), ["abcde", "fghij", "kl"])

    def test_estimated_geometry_and_batch_isolation(self):
        a = diagram()
        del a["geometry"]
        b = diagram()
        b["id"] = "D2"
        result = {"diagrams": [plan_diagram(a), plan_diagram(b)]}
        self.assertEqual([d["geometry_source"] for d in result["diagrams"]], ["estimated", "provided"])
        self.assertEqual(len(result["diagrams"]), 2)

    def test_invalid_batch_is_contextual(self):
        invalid = [
            {"participants": ["a", "a", "c"]},
            {"participants": ["a"]},
            {"geometry": {"left": 0, "right": 10, "x": {"a": 1, "b": 3}}},
            {"geometry": {"left": 0, "right": 10, "x": {"a": 3, "b": 2, "c": 1}}},
            {"geometry": {"left": False, "right": 128, "x": {"a": 14, "b": 64, "c": 114}}},
            {"geometry": {"left": 0, "right": float("nan"), "x": {"a": 14, "b": 64, "c": 114}}},
            {"typo": True},
        ]
        for changes in invalid:
            value = diagram()
            value.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                plan_diagram(value)

    def test_invalid_notes(self):
        for changes in [{"from": "missing"}, {"text": ""}, {"text": "end note\na -> b"},
                        {"text": "!include foo"}, {"text": "**粗体**"}, {"text": "<b>粗体</b>"},
                        {"text": "前\t后"}, {"text": None}, {"unknown": 1}]:
            value = diagram()
            value["notes"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, r"notes\[0\]"):
                note(value)

    def test_duplicates_rejected(self):
        value = diagram()
        value["notes"].append(copy.deepcopy(value["notes"][0]))
        with self.assertRaisesRegex(ValueError, "note id 重复"):
            note(value)

    def test_cli_batch_and_input_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, second, output = (Path(tmp) / name for name in ["brief.yaml", "other.yaml", "output.json"])
            original = (SCRIPTS.parent / "assets/examples/sequence/sequence-brief.example.yaml").read_text()
            source.write_text(original)
            second.write_text(original)  # 同图编号跨不同文件合法，输出以路径区分。
            cmd = [sys.executable, str(SCRIPTS / "plan_sequence_notes.py"), "--brief", str(source), str(second)]
            run = subprocess.run(cmd + ["--output", str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(len(result["diagrams"]), 2)
            self.assertNotEqual(result["diagrams"][0]["brief"], result["diagrams"][1]["brief"])
            self.assertEqual(result["diagrams"][0]["notes"][0]["placement"], "right")
            self.assertEqual(result["visual_review"], "pending")
            self.assertEqual(subprocess.run(cmd + ["--output", str(source)], capture_output=True).returncode, 2)
            old_output = output.read_text()
            second.write_text("bad: true")
            run = subprocess.run(cmd + ["--output", str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(output.read_text(), old_output)
            self.assertIn(str(second), run.stderr)
            self.assertEqual(source.read_text(), original)

    def test_brief_without_notes_and_single_message_note(self):
        data = load_yaml(SCRIPTS.parent / "assets/examples/sequence/sequence-brief.example.yaml")
        for message in data["messages"]:
            message.pop("note", None)
        self.assertEqual(plan_brief(data)["notes"], [])
        data["messages"][1]["note"] = "校验请求"
        planned = plan_brief(data)["notes"][0]
        self.assertEqual(planned["id"], data["messages"][1]["id"])
        self.assertEqual(planned["from"], data["messages"][1]["from"])
        self.assertEqual(planned["to"], data["messages"][1]["to"])

    def test_normal_brief_validation_rejects_invalid_note_and_geometry(self):
        for value in ["", "end note", 42]:
            data = load_yaml(SCRIPTS.parent / "assets/examples/sequence/sequence-brief.example.yaml")
            data["messages"][0]["note"] = value
            self.assertTrue(validate_profile_semantics("sequence", data)[0])
        data = load_yaml(SCRIPTS.parent / "assets/examples/sequence/sequence-brief.example.yaml")
        data["layout"]["note_geometry"] = {"left": 0, "right": 100, "x": {}}
        self.assertTrue(validate_profile_semantics("sequence", data)[0])

    def test_documented_examples_match_generated_notes(self):
        examples = SCRIPTS.parent / "assets/examples/sequence"
        result = plan_files([examples / "sequence-brief.example.yaml",
                             examples / "sequence-process-s-brief.example.yaml"])
        paths = [examples / "sequence-diagram.example.puml",
                 examples / "sequence-process-s-diagram.example.puml"]
        placements = set()
        for planned, path in zip(result["diagrams"], paths):
            source = path.read_text()
            for planned_note in planned["notes"]:
                self.assertIn(planned_note["puml"], source)
                placements.add(planned_note["placement"])
        self.assertEqual(placements, {"left", "right", "across"})


if __name__ == "__main__":
    unittest.main()
