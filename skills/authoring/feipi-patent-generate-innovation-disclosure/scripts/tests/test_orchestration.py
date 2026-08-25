#!/usr/bin/env python3
"""subagent 配置和阶段并行图的回归测试。"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
VALIDATOR = SKILL_DIR / "scripts/validate_orchestration.py"
CONFIG_RELATIVE = Path("agents/subagents")


class OrchestrationTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory(prefix="patent-orchestration-")
        root = Path(temporary.name)
        shutil.copytree(SKILL_DIR / CONFIG_RELATIVE, root / CONFIG_RELATIVE)
        return temporary, root

    def run_validator(
        self,
        root: Path,
        expected: int,
        error_contains: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["python3", str(VALIDATOR), str(root)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        if expected:
            self.assertIn("ORCH-001", result.stderr)
            if error_contains:
                self.assertIn(error_contains, result.stderr)
        return result

    @staticmethod
    def mutate_json(root: Path, relative: str, callback) -> None:
        path = root / CONFIG_RELATIVE / relative
        data = json.loads(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_valid_configuration_matches_stage_barriers_and_joins(self) -> None:
        self.run_validator(SKILL_DIR, 0)
        config = SKILL_DIR / CONFIG_RELATIVE

        phase_1 = json.loads((config / "stages/phase-1.json").read_text(encoding="utf-8"))
        nodes_1 = {node["id"]: node for node in phase_1["nodes"]}
        self.assertEqual(
            ["research-object", "research-mechanism"],
            nodes_1["research-join"]["depends_on"],
        )
        self.assertEqual(
            {"delivery-goals", "subject-boundary", "research-join"},
            set(nodes_1["innovation-value"]["depends_on"]),
        )

        phase_3 = json.loads((config / "stages/phase-3.json").read_text(encoding="utf-8"))
        nodes_3 = {node["id"]: node for node in phase_3["nodes"]}
        self.assertEqual(
            {"content-core", "diagram-plan"},
            set(nodes_3["diagram-worker"]["depends_on"]),
        )
        self.assertEqual("frozen_diagram_plan", nodes_3["diagram-worker"]["fan_out"]["source"])

        phase_4 = json.loads((config / "stages/phase-4.json").read_text(encoding="utf-8"))
        nodes_4 = {node["id"]: node for node in phase_4["nodes"]}
        self.assertEqual("build_map_diagrams", nodes_4["visual-review"]["fan_out"]["source"])
        self.assertEqual("all_instances", nodes_4["review-join"]["join"])

    def test_configuration_does_not_copy_checkpoint_result_paths(self) -> None:
        config = SKILL_DIR / CONFIG_RELATIVE
        for stage_path in sorted((config / "stages").glob("*.json")):
            stage = json.loads(stage_path.read_text(encoding="utf-8"))
            for node in stage["nodes"]:
                self.assertNotIn("result", node)
                self.assertNotIn("result_path", node)

    def test_role_json_is_runtime_source_but_schema_is_enforced(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        self.mutate_json(
            root,
            "roles/patent-visual-reviewer.json",
            lambda data: data.update(model="future-compatible-model"),
        )
        self.run_validator(root, 0)

        for field, value, expected_error in (
            ("reasoning_effort", "extreme", "reasoning_effort 非法"),
            ("permission", "root", "permission 非法"),
            ("max_instances", 0, "max_instances 必须在"),
        ):
            with self.subTest(field=field):
                nested_temporary, nested_root = self.fixture()
                try:
                    self.mutate_json(
                        nested_root,
                        "roles/patent-visual-reviewer.json",
                        lambda data, field=field, value=value: data.update({field: value}),
                    )
                    self.run_validator(nested_root, 1, expected_error)
                finally:
                    nested_temporary.cleanup()

    def test_stage_role_capability_responsibility_is_enforced(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)

        def change(data):
            node = next(item for item in data["nodes"] if item["id"] == "subject-boundary")
            node["role_ref"] = "patent_prior_art_researcher"

        self.mutate_json(root, "stages/phase-1.json", change)
        self.run_validator(root, 1, "阶段职责不匹配")

    def test_cycle_is_rejected(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        self.mutate_json(
            root,
            "stages/phase-1.json",
            lambda data: data["nodes"][0].update(depends_on=["phase-1-handoff"]),
        )
        self.run_validator(root, 1, "存在环")

    def test_phase_2_subagent_is_rejected(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)

        def change(data):
            node = data["nodes"][0]
            node["executor"] = "subagent"
            node["role_ref"] = "patent_subject_boundary_analyst"
            node["task_packet"] = {
                "template_ref": "default",
                "path": "disclosure-workspace/working/stages/agents/invalid.md",
            }
            node["allowed_writes"] = []

        self.mutate_json(root, "stages/phase-2.json", change)
        self.run_validator(root, 1, "阶段 2 禁止 subagent")

    def test_requires_upstream_chain_is_rejected_when_broken(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        self.mutate_json(
            root,
            "stages/phase-3.json",
            lambda data: data.update(requires_upstream=["phase-1-handoff"]),
        )
        self.run_validator(root, 1, "requires_upstream 链不正确")

    def test_phase_1_research_join_and_innovation_dependencies_are_enforced(self) -> None:
        mutations = (
            (
                "research join",
                lambda data: next(item for item in data["nodes"] if item["id"] == "research-join").update(join="all_instances"),
                "all_instances 必须直接依赖 fan_out",
            ),
            (
                "innovation dependency",
                lambda data: next(item for item in data["nodes"] if item["id"] == "innovation-value").update(
                    depends_on=["delivery-goals", "subject-boundary", "research-object", "research-mechanism"]
                ),
                "innovation-value 必须等待",
            ),
        )
        for name, change, expected_error in mutations:
            with self.subTest(name=name):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, "stages/phase-1.json", change)
                    self.run_validator(root, 1, expected_error)
                finally:
                    temporary.cleanup()

    def test_phase_3_freeze_barrier_and_fan_out_source_are_enforced(self) -> None:
        mutations = (
            (
                "barrier",
                lambda data: next(item for item in data["nodes"] if item["id"] == "diagram-worker").update(
                    depends_on=["diagram-plan"]
                ),
                "diagram-worker 必须等待 content-core",
            ),
            (
                "source",
                lambda data: next(item for item in data["nodes"] if item["id"] == "diagram-worker")["fan_out"].update(
                    source="mutable_diagram_plan"
                ),
                "frozen_diagram_plan",
            ),
        )
        for name, change, expected_error in mutations:
            with self.subTest(name=name):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, "stages/phase-3.json", change)
                    self.run_validator(root, 1, expected_error)
                finally:
                    temporary.cleanup()

    def test_phase_4_fan_out_source_and_join_are_enforced(self) -> None:
        mutations = (
            (
                "source",
                lambda data: next(item for item in data["nodes"] if item["id"] == "visual-review")["fan_out"].update(
                    source="review_plan_diagrams"
                ),
                "build_map_diagrams",
            ),
            (
                "join",
                lambda data: next(item for item in data["nodes"] if item["id"] == "review-join").update(
                    join="all_dependencies"
                ),
                "fan_out 必须且只能由一个 all_instances",
            ),
        )
        for name, change, expected_error in mutations:
            with self.subTest(name=name):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, "stages/phase-4.json", change)
                    self.run_validator(root, 1, expected_error)
                finally:
                    temporary.cleanup()

    def test_user_confirmation_and_stage_terminal_chains_are_enforced(self) -> None:
        mutations = (
            (
                "phase 2 gate",
                "stages/phase-2.json",
                lambda data: next(item for item in data["nodes"] if item["id"] == "user-confirmation").update(
                    gate="implicit_confirmation"
                ),
                "显式确认屏障",
            ),
            (
                "phase 2 bypass",
                "stages/phase-2.json",
                lambda data: next(item for item in data["nodes"] if item["id"] == "phase-2-handoff").update(
                    depends_on=["idea-decision"]
                ),
                "不得绕过显式用户确认",
            ),
            (
                "phase 1 terminal",
                "stages/phase-1.json",
                lambda data: next(item for item in data["nodes"] if item["id"] == "phase-1-handoff").update(
                    depends_on=[]
                ),
                "phase-1-handoff 必须是",
            ),
            (
                "phase 3 terminal",
                "stages/phase-3.json",
                lambda data: next(item for item in data["nodes"] if item["id"] == "phase-3-handoff").update(
                    depends_on=[]
                ),
                "phase-3-handoff 必须是",
            ),
            (
                "phase 4 terminal",
                "stages/phase-4.json",
                lambda data: next(item for item in data["nodes"] if item["id"] == "phase-4-handoff").update(
                    depends_on=[]
                ),
                "phase-4-handoff 必须是",
            ),
        )
        for name, stage_file, change, expected_error in mutations:
            with self.subTest(name=name):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, stage_file, change)
                    self.run_validator(root, 1, expected_error)
                finally:
                    temporary.cleanup()

    def test_checkpoint_binding_is_unique_and_complete_per_stage(self) -> None:
        def duplicate_fixed(data):
            nodes = {item["id"]: item for item in data["nodes"]}
            nodes["material-model"]["checkpoint_ref"] = nodes["innovation-value"]["checkpoint_ref"]

        def duplicate_template(data):
            node = next(item for item in data["nodes"] if item["id"] == "public-draft")
            node.pop("checkpoint_ref")
            node["checkpoint_template_ref"] = "phase-3-diagram"

        for stage_file, change, expected_error in (
            ("stages/phase-1.json", duplicate_fixed, "checkpoint_ref 在阶段内重复绑定"),
            ("stages/phase-3.json", duplicate_template, "checkpoint_template_ref 在阶段内重复绑定"),
        ):
            with self.subTest(stage_file=stage_file):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, stage_file, change)
                    self.run_validator(root, 1, expected_error)
                finally:
                    temporary.cleanup()

    def test_cross_stage_checkpoint_reference_is_rejected(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)

        def change(data):
            node = next(item for item in data["nodes"] if item["id"] == "validation")
            node["checkpoint_ref"] = "phase-1-material-index"

        self.mutate_json(root, "stages/phase-4.json", change)
        self.run_validator(root, 1, "不属于当前阶段")

    def test_checkpoint_catalog_order_must_follow_dag_topology(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)

        def change(data):
            tasks = data["stages"]["phase_1_material_modeling"]
            join_index = next(index for index, task in enumerate(tasks) if task.get("task_id") == "phase-1-research-join")
            innovation_index = next(index for index, task in enumerate(tasks) if task.get("task_id") == "phase-1-innovation-candidates")
            tasks[join_index], tasks[innovation_index] = tasks[innovation_index], tasks[join_index]

        self.mutate_json(root, "checkpoint-task-catalog.json", change)
        self.run_validator(root, 1, "checkpoint catalog 顺序与 DAG 反向")

    def test_dag_derived_peak_cannot_be_hidden_by_parallel_group(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)

        def change(data):
            node = next(item for item in data["nodes"] if item["id"] == "innovation-value")
            node["depends_on"] = ["analysis-plan"]
            node["parallel_group"] = "looks-serial-but-is-not"

        self.mutate_json(root, "stages/phase-1.json", change)
        self.run_validator(root, 1, "DAG 推导并发超过 max_active_subagents")

    def test_role_pool_limit_is_read_from_role_json(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        self.mutate_json(
            root,
            "roles/patent-prior-art-researcher.json",
            lambda data: data.update(max_instances=1),
        )
        self.run_validator(root, 1, "DAG 推导并发超过 role pool")

    def test_total_spawn_budget_over_limit_is_rejected(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        self.mutate_json(
            root,
            "roles/patent-diagram-engineer.json",
            lambda data: data.update(max_instances=3),
        )

        def change(data):
            node = next(item for item in data["nodes"] if item["id"] == "diagram-worker")
            node["fan_out"]["max_parallel"] = 3

        self.mutate_json(root, "stages/phase-3.json", change)
        self.run_validator(root, 1, "累计 subagent 预算超过")

    def test_busy_wait_and_event_contract_mutations_are_rejected(self) -> None:
        mutations = (
            (lambda data: data["wait_policy"].update(busy_wait=True), "禁止等待策略"),
            (lambda data: data["event_reporting"].update(deduplicate=False), "关键事件必须去重"),
        )
        for change, expected_error in mutations:
            with self.subTest(expected_error=expected_error):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, "runtime.json", change)
                    self.run_validator(root, 1, expected_error)
                finally:
                    temporary.cleanup()

    def test_missing_task_packet_section_is_rejected(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = root / CONFIG_RELATIVE / "task-packet.template.md"
        content = path.read_text(encoding="utf-8").replace("## 返回", "### 返回")
        path.write_text(content, encoding="utf-8")
        self.run_validator(root, 1, "只能包含输入/需要判断/返回三节")

    def test_nonisolated_diagram_write_path_is_rejected(self) -> None:
        temporary, root = self.fixture()
        self.addCleanup(temporary.cleanup)

        def change_role(data):
            data["allowed_write_templates"] = ["disclosure-workspace/diagrams/shared/"]

        def change_stage(data):
            node = next(item for item in data["nodes"] if item["id"] == "diagram-worker")
            node["allowed_writes"] = ["disclosure-workspace/diagrams/shared/"]

        self.mutate_json(root, "roles/patent-diagram-engineer.json", change_role)
        self.mutate_json(root, "stages/phase-3.json", change_stage)
        self.run_validator(root, 1, "动态图写路径必须按 diagram_id 隔离")

    def test_unknown_role_and_checkpoint_references_are_rejected(self) -> None:
        mutations = (
            (
                lambda data: next(item for item in data["nodes"] if item["id"] == "diagram-worker").update(role_ref="missing_role"),
                "role_ref 不存在",
            ),
            (
                lambda data: next(item for item in data["nodes"] if item["id"] == "diagram-worker").update(
                    checkpoint_template_ref="missing_template"
                ),
                "checkpoint_template_ref 不属于当前阶段",
            ),
        )
        for change, expected_error in mutations:
            with self.subTest(expected_error=expected_error):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, "stages/phase-3.json", change)
                    self.run_validator(root, 1, expected_error)
                finally:
                    temporary.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
