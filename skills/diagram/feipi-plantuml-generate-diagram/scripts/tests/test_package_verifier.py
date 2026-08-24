#!/usr/bin/env python3
"""v1.1 package 合同的安全与双向一致回归。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.puml_analysis import compute_puml_metrics
from lib.package_verifier import verify_package_dir
from lib.validation_result import compute_normalized_puml_sha256, compute_sha256


PUML = """@startuml
top to bottom direction
skinparam nodesep 30
skinparam ranksep 50
package "业务域" as domain {
  component "来源系统" as source
  component "目标系统" as target
}
source --> target : E1
@enduml
"""


def build_package(base: Path) -> dict:
    brief = {
        "diagram_id": "D9",
        "diagram_type": "component",
        "title": "组件测试图",
        "summary": "用于验证 diagram package 双向合同的合成 brief。",
        "view": "overview",
        "groups": [{"id": "domain", "name": "业务域", "description": "测试边界"}],
        "nodes": [
            {"id": "source", "name": "来源系统", "group": "domain", "type": "system", "description": "来源职责"},
            {"id": "target", "name": "目标系统", "group": "domain", "type": "system", "description": "目标职责"},
        ],
        "relations": [{"id": "E1", "from": "source", "to": "target", "description": "传递对象"}],
        "layout": {"direction": "top_to_bottom", "include_legend": False},
    }
    brief_path = base / "brief.normalized.yaml"
    diagram_path = base / "diagram.puml"
    svg_path = base / "diagram.svg"
    brief_path.write_text(json.dumps(brief, ensure_ascii=False) + "\n", encoding="utf-8")
    diagram_path.write_text(PUML, encoding="utf-8")
    svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>fixture</text></svg>\n', encoding="utf-8")
    validation = {
        "schema_version": "1.1",
        "render_contract_version": "2",
        "skill_name": "feipi-plantuml-generate-diagram",
        "diagram_id": "D9",
        "diagram_type": "component",
        "profile": "component",
        "profile_version": "1.1",
        "brief_path": "brief.normalized.yaml",
        "diagram_path": "diagram.puml",
        "svg_path": "diagram.svg",
        "brief_check": "ok",
        "coverage_check": "ok",
        "layout_check": "ok",
        "render_result": "ok",
        "render_server": "synthetic-test-fixture",
        "brief_sha256": compute_sha256(str(brief_path)),
        "puml_sha256": compute_sha256(str(diagram_path)),
        "normalized_puml_sha256": compute_normalized_puml_sha256(str(diagram_path)),
        "svg_sha256": compute_sha256(str(svg_path)),
        "parent_brief_path": "",
        "parent_brief_sha256": "",
        "parent_component_ref": {},
        "artifacts": {
            "brief": {"path": "brief.normalized.yaml", "sha256": compute_sha256(str(brief_path))},
            "diagram": {"path": "diagram.puml", "sha256": compute_sha256(str(diagram_path))},
            "svg": {"path": "diagram.svg", "sha256": compute_sha256(str(svg_path))},
        },
        "metrics": compute_puml_metrics("component", PUML),
        "timings": {"total_ms": 3.0, "render_ms": 1.0, "static_validation_ms": 2.0},
        "last_run_timings": {
            "total_ms": 3.0, "render_ms": 1.0, "static_validation_ms": 2.0, "cache_hit": False,
        },
        "counters": {
            "render_http_requests": 1, "render_rounds": 1,
            "package_validation_runs": 1, "package_verifier_runs": 1, "cache_hits": 0,
        },
        "last_run_counters": {
            "render_http_requests": 1, "render_rounds": 1,
            "package_validation_runs": 1, "package_verifier_runs": 1, "cache_hits": 0,
        },
        "final_status": "success",
        "blocked_reason": "",
    }
    (base / "validation.json").write_text(json.dumps(validation, ensure_ascii=False) + "\n", encoding="utf-8")
    return validation


class PackageVerifierTests(unittest.TestCase):
    def mutate(self, base: Path, callback) -> None:
        path = base / "validation.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")

    def test_valid_typed_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            self.assertEqual([], verify_package_dir(base))

    def test_observation_contract_rejects_missing_or_inconsistent_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            self.mutate(base, lambda data: data.pop("counters"))
            self.assertTrue(any("counters 字段集合" in item for item in verify_package_dir(base)))
            build_package(base)
            self.mutate(base, lambda data: data["last_run_timings"].__setitem__("total_ms", 99))
            self.assertTrue(any("render_ms + static_validation_ms" in item for item in verify_package_dir(base)))

    def test_observation_contract_rejects_old_render_contract_and_bad_cache_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            self.mutate(base, lambda data: data.__setitem__("render_contract_version", "1"))
            self.assertTrue(any("render_contract_version" in item for item in verify_package_dir(base)))
            build_package(base)
            def break_cache(data):
                data["last_run_timings"] = {
                    "total_ms": 2.0, "render_ms": 1.0,
                    "static_validation_ms": 1.0, "cache_hit": True,
                }
                data["last_run_counters"]["cache_hits"] = 1
            self.mutate(base, break_cache)
            self.assertTrue(any("cache hit" in item for item in verify_package_dir(base)))

    def test_success_rejects_svg_text_without_svg_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            svg_path = base / "diagram.svg"
            svg_path.write_text("<html>&lt;svg&gt;</html>\n", encoding="utf-8")
            self.mutate(
                base,
                lambda data: (
                    data.__setitem__("svg_sha256", compute_sha256(str(svg_path))),
                    data["artifacts"]["svg"].__setitem__("sha256", compute_sha256(str(svg_path))),
                ),
            )
            self.assertTrue(any("合法且非错误的 SVG 根文档" in item for item in verify_package_dir(base)))

    def test_success_rejects_plantuml_error_svg_even_with_matching_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            svg_path = base / "diagram.svg"
            svg_path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" data-diagram-type="ERROR"><text>error</text></svg>\n',
                encoding="utf-8",
            )
            digest = compute_sha256(str(svg_path))
            self.mutate(
                base,
                lambda data: (
                    data.__setitem__("svg_sha256", digest),
                    data["artifacts"]["svg"].__setitem__("sha256", digest),
                ),
            )
            self.assertTrue(any("非错误" in item for item in verify_package_dir(base)))

    def test_non_object_validation_and_artifact_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            (base / "validation.json").write_text("[]\n", encoding="utf-8")
            self.assertTrue(any("根节点" in item for item in verify_package_dir(base)))
            build_package(base)
            self.mutate(base, lambda data: data["artifacts"].__setitem__("diagram", "bad"))
            self.assertTrue(any("artifacts.diagram 必须是对象" in item for item in verify_package_dir(base)))

    def test_unsafe_path_is_rejected_before_artifact_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            self.mutate(base, lambda data: data["artifacts"]["diagram"].__setitem__("path", "../../outside"))
            self.assertTrue(any("安全的包内相对路径" in item for item in verify_package_dir(base)))

    def test_validation_symlink_cannot_escape_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "package"
            base.mkdir()
            build_package(base)
            outside = root / "outside-validation.json"
            outside.write_text((base / "validation.json").read_text(encoding="utf-8"), encoding="utf-8")
            (base / "validation.json").unlink()
            (base / "validation.json").symlink_to(outside)
            self.assertTrue(any("validation.json" in item and "越出" in item for item in verify_package_dir(base)))

    def test_typed_contract_requires_all_three_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            self.mutate(base, lambda data: data["artifacts"].pop("svg"))
            errors = verify_package_dir(base)
            self.assertTrue(any("缺少必需条目" in item for item in errors))
            self.assertTrue(any("svg_path/svg_sha256" in item for item in errors))

    def test_success_requires_render_checks_and_nonnegative_actual_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            def break_contract(data):
                data["render_result"] = "skipped"
                data["coverage_check"] = "failed"
                data["metrics"]["node_count"] = -1
            self.mutate(base, break_contract)
            errors = verify_package_dir(base)
            self.assertTrue(any("render_result" in item for item in errors))
            self.assertTrue(any("coverage_check" in item for item in errors))
            self.assertTrue(any("非负整数" in item for item in errors))

    def test_status_enums_and_blocked_reason_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            def break_status(data):
                data["final_status"] = "maybe"
                data["render_result"] = "unknown"
            self.mutate(base, break_status)
            errors = verify_package_dir(base)
            self.assertTrue(any("final_status 仅允许" in item for item in errors))
            self.assertTrue(any("render_result 枚举" in item for item in errors))

    def test_metrics_are_recomputed_from_actual_puml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            self.mutate(base, lambda data: data["metrics"].__setitem__("edge_count", 9))
            self.assertTrue(any("实际 PUML" in item for item in verify_package_dir(base)))

    def test_artifact_content_tamper_invalidates_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            with (base / "diagram.puml").open("a", encoding="utf-8") as handle:
                handle.write("' tampered\n")
            self.assertTrue(any("sha256 不匹配" in item for item in verify_package_dir(base)))

    def test_non_utf8_diagram_returns_diagnostic_instead_of_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            diagram = base / "diagram.puml"
            diagram.write_bytes(b"\xff\xfe\x00broken")
            digest = compute_sha256(str(diagram))
            def refresh_raw_hash(data):
                data["puml_sha256"] = digest
                data["artifacts"]["diagram"]["sha256"] = digest
            self.mutate(base, refresh_raw_hash)
            self.assertTrue(any("可读 UTF-8" in item for item in verify_package_dir(base)))

    def test_success_rejects_non_svg_renderer_output_even_with_matching_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build_package(base)
            svg_path = base / "diagram.svg"
            svg_path.write_text("not an svg\n", encoding="utf-8")
            digest = compute_sha256(str(svg_path))
            def refresh_hash(data):
                data["svg_sha256"] = digest
                data["artifacts"]["svg"]["sha256"] = digest
            self.mutate(base, refresh_hash)
            self.assertTrue(any("合法且非错误的 SVG 根文档" in item for item in verify_package_dir(base)))


if __name__ == "__main__":
    unittest.main()
