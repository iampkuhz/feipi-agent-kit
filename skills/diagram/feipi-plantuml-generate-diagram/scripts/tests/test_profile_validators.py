#!/usr/bin/env python3
"""Profile 跨字段与边界规则的纯本地回归。"""

from __future__ import annotations

import json
import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.brief_loader import load_yaml, validate_schema
from lib.puml_analysis import compute_puml_metrics
from lib.profile_validators import validate_profile_semantics
from check_coverage import (
    check_activity_coverage,
    check_component_coverage,
    normalize_text,
)


def example(profile: str, name: str | None = None) -> dict:
    stem = name or profile
    return load_yaml(SKILL_DIR / "assets" / "examples" / profile / f"{stem}-brief.example.yaml")


def schema_errors(profile: str, data: dict) -> list[str]:
    schema_path = SKILL_DIR / "assets" / "validation" / "types" / f"{profile}-brief.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    validate_schema(data, schema, "", errors)
    return errors


class ComponentBoundaryTests(unittest.TestCase):
    def boundary_brief(self) -> dict:
        data = example("component")
        data["nodes"] = [
            {"id": f"n{i}", "name": f"业务系统{i}", "group": "request_domain", "type": "system", "description": "独立系统边界"}
            for i in range(1, 9)
        ]
        pairs = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 1), (1, 5), (1, 6)]
        data["relations"] = [
            {"id": f"E{i}", "from": f"n{source}", "to": f"n{target}", "description": "结构关系"}
            for i, (source, target) in enumerate(pairs, start=1)
        ]
        return data

    def test_eight_nodes_ten_edges_degree_four_pass(self) -> None:
        data = self.boundary_brief()
        self.assertEqual([], schema_errors("component", data))
        self.assertEqual([], validate_profile_semantics("component", data)[0])

    def test_nine_nodes_fail(self) -> None:
        data = self.boundary_brief()
        data["nodes"].append({"id": "n9", "name": "业务系统9", "group": "request_domain", "type": "system", "description": "独立系统边界"})
        self.assertTrue(any("最多允许 8 项" in item for item in schema_errors("component", data)))

    def test_eleven_edges_fail(self) -> None:
        data = self.boundary_brief()
        data["relations"].append({"id": "E11", "from": "n3", "to": "n7", "description": "结构关系"})
        self.assertTrue(any("最多允许 10 项" in item for item in schema_errors("component", data)))

    def test_degree_five_fail(self) -> None:
        data = self.boundary_brief()
        data["relations"] = [
            {"id": f"E{i}", "from": "n1", "to": f"n{i + 1}", "description": "结构关系"}
            for i in range(1, 6)
        ]
        errors = validate_profile_semantics("component", data)[0]
        self.assertTrue(any("连接度不得超过 4" in item for item in errors))

    def test_hidden_legal_rectangle_is_rejected_and_counted(self) -> None:
        data = example("component")
        diagram_path = SKILL_DIR / "assets" / "examples" / "component" / "component-diagram.example.puml"
        raw = diagram_path.read_text(encoding="utf-8").replace(
            "@enduml", 'rectangle "TemperatureProcessor" as hidden_impl\n@enduml'
        )
        errors = check_component_coverage(data, raw, normalize_text(raw))
        self.assertTrue(any("hidden_impl" in item for item in errors))
        self.assertEqual(4, compute_puml_metrics("component", raw)["node_count"])

        raw_unaliased = raw.replace('rectangle "TemperatureProcessor" as hidden_impl', 'rectangle "TemperatureProcessor"')
        errors = check_component_coverage(data, raw_unaliased, normalize_text(raw_unaliased))
        self.assertTrue(any("__unbound_object" in item for item in errors))

    def test_overview_table_field_name_is_rejected(self) -> None:
        data = example("component")
        data["nodes"][0]["name"] = "alarm_record.status"
        errors = validate_profile_semantics("component", data)[0]
        self.assertTrue(any("实现细节" in item for item in errors))

    def test_module_detail_parent_contract_binds_hash_id_and_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            overview = base / "evidence" / "overview.yaml"
            overview.parent.mkdir()
            shutil.copyfile(
                SKILL_DIR / "assets" / "examples" / "component" / "component-brief.example.yaml",
                overview,
            )
            data = example("component")
            data["diagram_id"] = "D5"
            data["view"] = "module_detail"
            data["groups"] = [{"id": "detail", "name": "签发细化", "description": "只展开签发系统"}]
            data["nodes"] = [
                {"id": "constraint_unit", "name": "约束单元", "group": "detail", "type": "module", "description": "约束凭据"},
                {"id": "issue_unit", "name": "签发单元", "group": "detail", "type": "component", "description": "生成凭据"},
            ]
            data["relations"] = [{"id": "E1", "from": "constraint_unit", "to": "issue_unit", "description": "传递约束"}]
            data["parent_component_id"] = "issue_system"
            data["parent_component_ref"] = {
                "overview_diagram_id": "D1",
                "component_id": "issue_system",
                "overview_brief_path": "evidence/overview.yaml",
                "overview_brief_sha256": hashlib.sha256(overview.read_bytes()).hexdigest(),
            }
            source = base / "detail.yaml"
            self.assertEqual([], validate_profile_semantics("component", data, source)[0])

            data["parent_component_ref"]["overview_brief_sha256"] = "0" * 64
            errors = validate_profile_semantics("component", data, source)[0]
            self.assertTrue(any("SHA-256" in item or "sha256" in item for item in errors))

            data["parent_component_ref"]["overview_brief_path"] = "../outside.yaml"
            errors = validate_profile_semantics("component", data, source)[0]
            self.assertTrue(any("安全的相对路径" in item for item in errors))


class NumberingTests(unittest.TestCase):
    def test_sequence_default_mr_is_backward_compatible(self) -> None:
        data = example("sequence")
        self.assertNotIn("numbering_scheme", data)
        self.assertEqual([], validate_profile_semantics("sequence", data)[0])

    def test_process_s_passes(self) -> None:
        data = example("sequence", "sequence-process-s")
        self.assertEqual([], schema_errors("sequence", data))
        self.assertEqual([], validate_profile_semantics("sequence", data)[0])

    def test_process_s_mixing_fails(self) -> None:
        data = example("sequence", "sequence-process-s")
        data["messages"][1]["id"] = "M1"
        errors = validate_profile_semantics("sequence", data)[0]
        self.assertTrue(any("禁止混用" in item for item in errors))

    def test_process_s_missing_parent_fails(self) -> None:
        data = example("sequence", "sequence-process-s")
        data["messages"] = [item for item in data["messages"] if item["id"] != "S4"]
        errors = validate_profile_semantics("sequence", data)[0]
        self.assertTrue(any("缺少父步骤 S4" in item for item in errors))


class ActivityAndDeploymentTests(unittest.TestCase):
    def test_activity_happy_path(self) -> None:
        data = example("activity")
        self.assertEqual([], schema_errors("activity", data))
        self.assertEqual([], validate_profile_semantics("activity", data)[0])

    def test_activity_narrative_mismatch_fails(self) -> None:
        data = example("activity")
        data["narrative_step_ids"].pop()
        self.assertTrue(any("完全一致" in item for item in validate_profile_semantics("activity", data)[0]))

    def test_activity_jump_number_fails(self) -> None:
        data = example("activity")
        data["steps"][2]["id"] = "S6"
        data["transitions"][1]["to"] = "S6"
        data["transitions"][2]["from"] = "S6"
        data["narrative_step_ids"][2] = "S6"
        self.assertTrue(any("连续编号" in item for item in validate_profile_semantics("activity", data)[0]))

    def test_activity_isolated_step_fails(self) -> None:
        data = example("activity")
        data["transitions"].pop()
        self.assertTrue(any("孤立步骤" in item for item in validate_profile_semantics("activity", data)[0]))

    def test_activity_extra_diagram_step_fails(self) -> None:
        data = example("activity")
        diagram_path = SKILL_DIR / "assets" / "examples" / "activity" / "activity-diagram.example.puml"
        raw = diagram_path.read_text(encoding="utf-8").replace(
            "@enduml", 'activity "S6 额外步骤" as S6\n@enduml'
        )
        errors = check_activity_coverage(data, raw, normalize_text(raw))
        self.assertTrue(any("额外步骤" in item for item in errors))

    def test_activity_hidden_unnumbered_step_fails_and_is_counted(self) -> None:
        data = example("activity")
        diagram_path = SKILL_DIR / "assets" / "examples" / "activity" / "activity-diagram.example.puml"
        raw = diagram_path.read_text(encoding="utf-8").replace(
            "@enduml", 'activity "未编号额外步骤" as hidden_extra\n@enduml'
        )
        errors = check_activity_coverage(data, raw, normalize_text(raw))
        self.assertTrue(any("hidden_extra" in item for item in errors))
        self.assertEqual(6, compute_puml_metrics("activity", raw)["node_count"])

    def test_activity_configured_legend_must_exist(self) -> None:
        data = example("activity")
        data["layout"]["include_legend"] = True
        diagram_path = SKILL_DIR / "assets" / "examples" / "activity" / "activity-diagram.example.puml"
        raw = diagram_path.read_text(encoding="utf-8")
        errors = check_activity_coverage(data, raw, normalize_text(raw))
        self.assertTrue(any("legend" in item for item in errors))

    def test_deployment_happy_path(self) -> None:
        data = example("deployment")
        self.assertEqual([], schema_errors("deployment", data))
        self.assertEqual([], validate_profile_semantics("deployment", data)[0])

    def test_deployment_missing_endpoint_fails(self) -> None:
        data = example("deployment")
        for node in data["nodes"]:
            node["type"] = "system"
        errors = validate_profile_semantics("deployment", data)[0]
        self.assertTrue(any("至少需要一个物理端点" in item for item in errors))

    def test_deployment_missing_connection_fails(self) -> None:
        data = example("deployment")
        data["connections"] = []
        self.assertTrue(any("至少需要 1 项" in item for item in schema_errors("deployment", data)))

    def test_deployment_triggers_are_bidirectional(self) -> None:
        data = example("deployment")
        for key in ("cross_network", "online_offline", "manual_transfer"):
            with self.subTest(key=key):
                changed = json.loads(json.dumps(data))
                changed["boundary_triggers"][key] = False
                errors = validate_profile_semantics("deployment", changed)[0]
                self.assertTrue(any(f"boundary_triggers.{key}" in item for item in errors))

        for key in ("cross_chain", "hsm", "manual_handoff"):
            with self.subTest(key=key):
                changed = json.loads(json.dumps(data))
                changed["boundary_triggers"][key] = True
                errors = validate_profile_semantics("deployment", changed)[0]
                self.assertTrue(any(f"boundary_triggers.{key}" in item for item in errors))

    def test_deployment_observed_cross_chain_requires_trigger(self) -> None:
        data = example("deployment")
        data["nodes"][0]["chain_id"] = "chain_a"
        data["nodes"][1]["chain_id"] = "chain_b"
        errors = validate_profile_semantics("deployment", data)[0]
        self.assertTrue(any("boundary_triggers.cross_chain" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
