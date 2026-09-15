#!/usr/bin/env python3
"""Mindmap 的树语义、受控语法和图包前置校验回归；真实渲染由 test.sh 承担。"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.brief_loader import load_yaml, validate_schema
from lib.mindmap import coverage_errors, layout_errors, parse_mindmap, validate_mindmap
from lib.profile_registry import resolve_profile
from lib.profile_validators import validate_profile_semantics
from lib.puml_analysis import compute_puml_metrics
from generate_mindmap import generate

EXAMPLE = SKILL / "assets/examples/mindmap"
BRIEF = EXAMPLE / "mindmap-brief.example.yaml"
DIAGRAM = EXAMPLE / "mindmap-diagram.example.puml"


class MindmapTests(unittest.TestCase):
    def setUp(self):
        self.data = load_yaml(BRIEF)
        self.raw = DIAGRAM.read_text(encoding="utf-8")

    def test_profile_schema_and_template(self):
        profile = resolve_profile("mindmap")
        self.assertEqual(profile["profile"], "mindmap")
        schema = json.loads(Path(profile["brief_schema"]).read_text())
        for data in (self.data, load_yaml(Path(profile["template"]))):
            errors = []
            validate_schema(data, schema, "", errors)
            self.assertFalse(errors, errors)
            self.assertEqual(validate_profile_semantics("mindmap", data), ([], []))
        bad = copy.deepcopy(self.data)
        bad["nodes"][0]["children"] = []
        errors = []
        validate_schema(bad, schema, "", errors)
        self.assertTrue(errors)

    def test_generated_example_matches_and_metrics_are_from_source(self):
        self.assertEqual(generate(self.data), self.raw)
        self.assertFalse(coverage_errors(self.data, self.raw))
        self.assertFalse(layout_errors(self.raw))
        self.assertEqual(compute_puml_metrics("mindmap", self.raw), {"node_count": 13, "edge_count": 12, "max_degree": 4})
        reduced = self.raw.replace("+++[#DBEAFE] 目标用户与使用场景\n", "")
        self.assertEqual(compute_puml_metrics("mindmap", reduced)["node_count"], 12)
        result = subprocess.run([sys.executable, str(SCRIPTS / "lib/puml_metrics_cli.py"), "--type", "mindmap", str(DIAGRAM)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "13\t12\t4")

    def test_root_duplicate_or_missing_parent_and_cycle(self):
        for index, changes in ((1, {"parent": ""}), (1, {"parent": "absent"}), (1, {"id": "root"}), (1, {"parent": "audience"})):
            with self.subTest(changes=changes):
                data = copy.deepcopy(self.data)
                data["nodes"][index].update(changes)
                self.assertTrue(validate_mindmap(data))

    def test_disconnected_cycle_is_rejected(self):
        self.data["nodes"][1]["parent"] = "design"
        self.data["nodes"][4]["parent"] = "value"
        self.assertTrue(validate_mindmap(self.data))

    def test_budgets_and_duplicate_siblings(self):
        for mutation in ("depth", "children", "labels", "nodes", "width"):
            data = copy.deepcopy(self.data)
            if mutation == "depth":
                data["nodes"] += [{"id": "deep", "parent": "audience", "label": "四层"}, {"id": "deeper", "parent": "deep", "label": "五层"}]
            elif mutation == "children":
                data["nodes"] += [{"id": f"extra_{i}", "parent": "root", "label": f"补充{i}"} for i in range(3)]
            elif mutation == "labels":
                data["nodes"][3]["label"] = data["nodes"][2]["label"]
            elif mutation == "nodes":
                data["nodes"] *= 3
            else:
                data["nodes"][1]["label"] = "长" * 49
            with self.subTest(mutation=mutation):
                self.assertTrue(validate_mindmap(data))

    def test_plain_text_rejects_injected_markup(self):
        for label in ("", " ", "<b>重点</b>", "**重点**", "!include x", "主题\\n伪指令", "条目\t控制", "~转义"):
            self.data["nodes"][1]["label"] = label
            with self.subTest(label=label):
                self.assertTrue(validate_mindmap(self.data))

    def test_missing_extra_wrong_parent_wrong_side(self):
        mutations = (
            self.raw.replace("+++[#DBEAFE] 目标用户与使用场景\n", ""),
            self.raw.replace("@endmindmap", "++ 额外节点\n@endmindmap"),
            self.raw.replace("+++[#DBEAFE] 目标用户", "++++[#DBEAFE] 目标用户"),
            self.raw.replace("--[#D1FAE5] 系统设计", "++[#D1FAE5] 系统设计"),
            self.raw.replace("+++[#DBEAFE] 衡量收益", "++[#DBEAFE] 衡量收益"),
        )
        for raw in mutations:
            self.assertTrue(coverage_errors(self.data, raw))

    def test_same_text_in_different_branches_is_unambiguous(self):
        self.data["nodes"][5]["label"] = self.data["nodes"][2]["label"]
        self.assertFalse(coverage_errors(self.data, generate(self.data)))

    def test_all_directions_and_unordered_parent_definitions(self):
        for direction in ("balanced", "left", "right"):
            self.data["layout"]["direction"] = direction
            raw = generate(self.data)
            self.assertFalse(coverage_errors(self.data, raw))
            self.assertFalse(layout_errors(raw))
        # 根可以晚于子节点定义。
        self.data["nodes"].append(self.data["nodes"].pop(0))
        self.assertFalse(coverage_errors(self.data, generate(self.data)))

    def test_orgmode_colors_boxless_and_multiline(self):
        raw = "@startmindmap\n* 根\n**[#DBEAFE] 右分支\n***_ 叶子\\n补充\nleft side\n** 左分支\n@endmindmap\n"
        nodes, errors = parse_mindmap(raw)
        self.assertFalse(errors, errors)
        self.assertEqual([(n.depth, n.side, n.parent) for n in nodes], [(1, "right", None), (2, "right", 0), (3, "right", 1), (2, "left", 0)])
        self.data["nodes"][1]["label"] = "业务价值\n验收标准"
        self.assertFalse(coverage_errors(self.data, generate(self.data)))

    def test_syntax_boundaries_do_not_silently_pass(self):
        for body in ("+ 根\n+++ 跳级", "+ 根\n+ 另一个根", "+ 根\n** 混用", "+ 根\n!include x", "+ 根\nclass Fake", "+ 根\n-- 左分支\n+++ 错误跨侧", "+ 根\n<style>"):
            raw = f"@startmindmap\n{body}\n@endmindmap"
            self.assertTrue(parse_mindmap(raw)[1], body)
        self.assertTrue(parse_mindmap("' @startmindmap\n+ 根\n' @endmindmap")[1])
        self.assertTrue(parse_mindmap("@startuml\n+ 根\n@enduml")[1])
        self.assertTrue(parse_mindmap("@startmindmap\n+ 根\n@endmindmap\n+ 图外节点")[1])

    def test_layout_requires_real_style_not_comments(self):
        self.assertTrue(layout_errors(self.raw.replace("MaximumWidth 180", "MaximumWidth 900")))
        self.assertTrue(layout_errors(self.raw.replace("    Padding 10", "'    Padding 10")))
        self.assertTrue(layout_errors(self.raw.replace("  node {", "  arrow {")))
        nodes, errors = parse_mindmap(self.raw.replace("title 技术方案评审要点", "/'\n+ 假根\n'/\ntitle 技术方案评审要点"))
        self.assertFalse(errors)
        self.assertEqual(len(nodes), 13)

    def test_invalid_generator_input_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief, out = Path(tmp) / "bad.json", Path(tmp) / "diagram.puml"
            self.data["nodes"][1]["parent"] = "unknown"
            brief.write_text(json.dumps(self.data))
            out.write_text("保留已有源码")
            result = subprocess.run([sys.executable, str(SCRIPTS / "generate_mindmap.py"), "--brief", str(brief), "--out", str(out)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(out.read_text(), "保留已有源码")

    def test_package_negative_paths_write_contract_without_rendering(self):
        # 这些输入应在 HTTP 请求之前被拦截；不是正向渲染证明。
        cases = [
            (self.raw.replace("@endmindmap", ""), self.data, "syntax", "missing_endmindmap"),
            (self.raw.replace("@startmindmap", "@startuml"), self.data, "syntax", "missing_startmindmap"),
            (self.raw.replace("+++[#DBEAFE] 目标用户与使用场景\n", ""), self.data, "coverage", "coverage_validation_failed"),
        ]
        too_deep = copy.deepcopy(self.data)
        too_deep["nodes"] += [{"id": "deep", "parent": "audience", "label": "四层"}, {"id": "deeper", "parent": "deep", "label": "五层"}]
        cases.append((self.raw, too_deep, "over_budget", "brief_validation_failed"))
        for raw, brief_data, failure_class, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                brief, diagram = root / "brief.json", root / "input.puml"
                brief.write_text(json.dumps(brief_data, ensure_ascii=False))
                diagram.write_text(raw)
                result = subprocess.run([
                    "bash", str(SCRIPTS / "validate_package.sh"), "--diagram-type", "mindmap",
                    "--brief", str(brief), "--diagram", str(diagram), "--out-dir", str(root / "package"),
                    "--server-url", "http://127.0.0.1:1",
                ], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                contract = json.loads((root / "package/validation.json").read_text())
                self.assertEqual(contract["profile"], "mindmap")
                self.assertEqual(contract["final_status"], "blocked")
                self.assertEqual(contract["blocked_reason"], reason)
                self.assertEqual(contract["failure_class"], failure_class)
                self.assertEqual(contract["counters"]["render_http_requests"], 0)
                self.assertFalse((root / "package/diagram.svg").exists())


if __name__ == "__main__":
    unittest.main()
