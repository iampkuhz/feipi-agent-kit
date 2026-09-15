#!/usr/bin/env python3
"""subagent 配置和阶段并行图的回归测试。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
VALIDATOR = SKILL_DIR / "scripts/validate_orchestration.py"
CONFIG_RELATIVE = Path("agents/subagents")


class OrchestrationTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory(prefix="patent-orchestration-")
        root = Path(temporary.name)
        shutil.copytree(SKILL_DIR, root, dirs_exist_ok=True)
        return temporary, root

    def run_validator(
        self,
        root: Path,
        expected: int,
        error_contains: str | None = None,
        rule_id: str = "ORCH-001",
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["python3", str(VALIDATOR), str(root)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        if expected:
            self.assertIn(rule_id, result.stderr)
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

        index = json.loads((config / "index.json").read_text(encoding="utf-8"))
        self.assertEqual("loading-policy.json", index["loading_policy"])
        policy = json.loads((config / "loading-policy.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "path": "references/session-timing.md",
                "audience": "main_agent",
                "load_at": "session_init_or_resume",
                "cardinality": "once_per_task",
            },
            policy["on_demand"]["session_timing"],
        )
        for context_name in ("subagent_context", "fallback_context"):
            self.assertIn(
                "task_packet.dynamic_inputs",
                policy["just_in_time"][context_name]["selectors"],
            )

        phase_1 = json.loads((config / "stages/phase-1.json").read_text(encoding="utf-8"))
        self.assertEqual(
            "references/stages/phase-1-material-modeling.md",
            phase_1["instruction_ref"],
        )
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
        self.assertEqual(["assets/proposal_template.md"], nodes_3["public-draft"]["resource_refs"])
        self.assertEqual(
            ["assets/disclosure-manifest.template.json"],
            nodes_3["manifest"]["resource_refs"],
        )
        self.assertEqual(
            ["assets/internal_trace_appendix_template.md"],
            nodes_3["internal-draft"]["resource_refs"],
        )
        self.assertEqual(
            {"content-core", "diagram-plan"},
            set(nodes_3["diagram-worker"]["depends_on"]),
        )
        self.assertEqual("frozen_diagram_plan", nodes_3["diagram-worker"]["fan_out"]["source"])

        phase_4 = json.loads((config / "stages/phase-4.json").read_text(encoding="utf-8"))
        nodes_4 = {node["id"]: node for node in phase_4["nodes"]}
        self.assertEqual("build_map_diagrams", nodes_4["visual-review"]["fan_out"]["source"])
        self.assertEqual("all_instances", nodes_4["review-join"]["join"])

        expected_role_guides = {
            "patent-subject-boundary-analyst.json": ["references/roles/subject-boundary.md"],
            "patent-prior-art-researcher.json": ["references/roles/prior-art-research.md"],
            "patent-innovation-value-analyst.json": ["references/roles/innovation-value.md"],
        }
        for role_file, instruction_refs in expected_role_guides.items():
            role = json.loads((config / f"roles/{role_file}").read_text(encoding="utf-8"))
            self.assertEqual(instruction_refs, role["instruction_refs"])

        diagram_role = json.loads(
            (config / "roles/patent-diagram-engineer.json").read_text(encoding="utf-8")
        )
        self.assertEqual(["references/roles/diagram-engineer.md"], diagram_role["instruction_refs"])
        self.assertEqual(["feipi-plantuml-generate-diagram"], diagram_role["skill_dependencies"])

    def test_loading_policy_keeps_bootstrap_small_and_jit(self) -> None:
        mutations = (
            (
                lambda data: data["bootstrap"]["paths"].append("references/content-quality-gates.md"),
                "bootstrap 必须保持最小固定集合",
            ),
            (
                lambda data: data["just_in_time"]["role_config"].update(load_at="stage_start"),
                "just_in_time 必须保持阶段/角色即时加载合同",
            ),
            (
                lambda data: data["just_in_time"]["subagent_context"].update(audience="main_agent"),
                "just_in_time 必须保持阶段/角色即时加载合同",
            ),
            (
                lambda data: data["just_in_time"]["subagent_context"]["selectors"].remove(
                    "task_packet.dynamic_inputs"
                ),
                "just_in_time 必须保持阶段/角色即时加载合同",
            ),
            (
                lambda data: data["just_in_time"]["fallback_context"]["selectors"].remove(
                    "task_packet.dynamic_inputs"
                ),
                "just_in_time 必须保持阶段/角色即时加载合同",
            ),
            (
                lambda data: data["on_demand"]["session_timing"].update(audience="subagent"),
                "session timing 必须由 main_agent",
            ),
            (
                lambda data: data["on_demand"]["session_timing"].update(trigger="timing_enabled"),
                "session timing 必须由 main_agent",
            ),
            (
                lambda data: data["limits"].update(stage_instruction_max_bytes=65536),
                "体积上限不得被放宽",
            ),
        )
        for change, expected_error in mutations:
            with self.subTest(expected_error=expected_error):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, "loading-policy.json", change)
                    self.run_validator(root, 1, expected_error, "LOAD-001")
                finally:
                    temporary.cleanup()

    def test_stage_instruction_refs_are_unique_safe_and_present(self) -> None:
        temporary, root = self.fixture()
        try:
            self.mutate_json(
                root,
                "stages/phase-2.json",
                lambda data: data.update(instruction_ref="references/stages/phase-1-material-modeling.md"),
            )
            self.run_validator(root, 1, "每个阶段必须使用独立", "LOAD-003")
        finally:
            temporary.cleanup()

        temporary, root = self.fixture()
        try:
            self.mutate_json(
                root,
                "stages/phase-2.json",
                lambda data: data.update(instruction_ref="../outside.md"),
            )
            self.run_validator(root, 1, "路径越界", "LOAD-002")
        finally:
            temporary.cleanup()

        for mode in ("missing", "symlink"):
            with self.subTest(mode=mode):
                temporary, root = self.fixture()
                try:
                    path = root / "references/stages/phase-2-idea-confirmation.md"
                    path.unlink()
                    if mode == "symlink":
                        path.symlink_to("phase-1-material-modeling.md")
                    expected_error = "缺少资源" if mode == "missing" else "禁止软链接"
                    self.run_validator(root, 1, expected_error, "LOAD-002")
                finally:
                    temporary.cleanup()

    def test_stage_and_role_guides_reject_hardlinks_and_copied_content(self) -> None:
        cases = (
            (
                "stage",
                "references/stages/phase-1-material-modeling.md",
                "references/stages/phase-2-idea-confirmation.md",
                "LOAD-003",
            ),
            (
                "role",
                "references/reviews/semantic-review.md",
                "references/reviews/visual-review.md",
                "LOAD-005",
            ),
        )
        for family, source_relative, target_relative, rule_id in cases:
            for reuse_mode in ("hardlink", "copied-content"):
                with self.subTest(family=family, reuse_mode=reuse_mode):
                    temporary, root = self.fixture()
                    try:
                        source = root / source_relative
                        target = root / target_relative
                        if reuse_mode == "hardlink":
                            target.unlink()
                            os.link(source, target)
                            expected_error = "hardlink"
                        else:
                            target.write_bytes(source.read_bytes())
                            expected_error = "复制相同内容"
                        self.run_validator(root, 1, expected_error, rule_id)
                    finally:
                        temporary.cleanup()

    def test_node_resources_are_bound_only_at_their_node(self) -> None:
        temporary, root = self.fixture()
        try:
            def change_template(data):
                node = next(item for item in data["nodes"] if item["id"] == "manifest")
                node["resource_refs"] = ["assets/proposal_template.md"]

            self.mutate_json(root, "stages/phase-3.json", change_template)
            self.run_validator(root, 1, "条件模板绑定不正确", "LOAD-004")
        finally:
            temporary.cleanup()

        temporary, root = self.fixture()
        try:
            def load_maintainer_doc(data):
                node = next(item for item in data["nodes"] if item["id"] == "content-core")
                node["resource_refs"] = ["references/content-quality-gates.md"]

            self.mutate_json(root, "stages/phase-3.json", load_maintainer_doc)
            self.run_validator(root, 1, "包含非运行时资源", "LOAD-006")
        finally:
            temporary.cleanup()

    def test_role_instructions_and_dependencies_do_not_cross(self) -> None:
        temporary, root = self.fixture()
        try:
            self.mutate_json(
                root,
                "roles/patent-semantic-reviewer.json",
                lambda data: data.update(instruction_refs=["references/reviews/visual-review.md"]),
            )
            self.run_validator(root, 1, "角色专页不得交叉复用", "LOAD-005")
        finally:
            temporary.cleanup()

        temporary, root = self.fixture()
        try:
            self.mutate_json(
                root,
                "roles/patent-diagram-engineer.json",
                lambda data: data.update(skill_dependencies=[]),
            )
            self.run_validator(root, 1, "skill_dependencies 与职责不一致", "LOAD-005")
        finally:
            temporary.cleanup()

    def test_entry_and_guides_have_hard_size_limits(self) -> None:
        for relative, expected_label in (
            ("SKILL.md", "SKILL.md"),
            ("references/stages/phase-1-material-modeling.md", "stage instruction_ref"),
            ("references/roles/diagram-engineer.md", "role instruction_ref"),
        ):
            with self.subTest(relative=relative):
                temporary, root = self.fixture()
                try:
                    path = root / relative
                    path.write_text("x" * 13000, encoding="utf-8")
                    self.run_validator(root, 1, expected_label, "LOAD-007")
                finally:
                    temporary.cleanup()

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

    def test_role_permissions_cannot_be_escalated_or_downgraded(self) -> None:
        cases = (
            (
                "roles/patent-semantic-reviewer.json",
                lambda data: data.update(
                    permission="workspace_write",
                    allowed_write_templates=["disclosure-workspace/reviews/semantic/"],
                ),
            ),
            (
                "roles/patent-diagram-engineer.json",
                lambda data: data.update(permission="read_only", allowed_write_templates=[]),
            ),
        )
        for relative, mutation in cases:
            with self.subTest(relative=relative):
                temporary, root = self.fixture()
                try:
                    self.mutate_json(root, relative, mutation)
                    self.run_validator(root, 1, "role permission 与职责不一致")
                finally:
                    temporary.cleanup()

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
        self.run_validator(root, 1, "只能包含输入/需要判断/返回三节", "LOAD-008")

    def test_task_packet_progressive_loading_contract_cannot_be_weakened(self) -> None:
        mutations = (
            ("{{dynamic_inputs}}", "", "缺少占位字段"),
            ("{{result_owner}}", "", "缺少占位字段"),
            (
                "{{dynamic_inputs}}",
                "{{dynamic_inputs}}\n{{input_references}}",
                "占位字段集合必须固定",
            ),
            (
                "禁止读取完整阶段缓存",
                "可以读取完整阶段缓存",
                "语义反转",
            ),
            (
                "禁止读取本 Skill 其他资源",
                "可以读取本 Skill 其他资源",
                "语义反转",
            ),
            (
                "禁止加载其他 Skill",
                "可以加载其他 Skill",
                "语义反转",
            ),
        )
        for original, replacement, expected_error in mutations:
            with self.subTest(original=original):
                temporary, root = self.fixture()
                try:
                    path = root / CONFIG_RELATIVE / "task-packet.template.md"
                    content = path.read_text(encoding="utf-8")
                    self.assertIn(original, content)
                    path.write_text(content.replace(original, replacement, 1), encoding="utf-8")
                    self.run_validator(root, 1, expected_error, "LOAD-008")
                finally:
                    temporary.cleanup()

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
        self.run_validator(root, 1, "role allowed_write_templates 与职责不一致")

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
