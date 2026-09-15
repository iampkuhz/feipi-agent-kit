#!/usr/bin/env python3
"""checkpoint.py 的端到端合同测试。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "scripts/checkpoint.py"
CATALOG = SCRIPT.parents[1] / "agents/subagents/checkpoint-task-catalog.json"
CATALOG_DATA = json.loads(CATALOG.read_text(encoding="utf-8"))["stages"]
CHECKPOINT = Path("disclosure-workspace/working/CHECKPOINT.md")
PHASE_1 = "phase_1_material_modeling"
PHASE_2 = "phase_2_idea_confirmation"
PHASE_3 = "phase_3_final_drafting"
PHASE_4 = "phase_4_review_delivery"


class CheckpointTests(unittest.TestCase):
    def run_raw(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *args, "--root", str(root)],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )

    def run_cli(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        completed = self.run_raw(root, *args)
        if completed.returncode != 0:
            self.fail(
                f"CLI failed ({completed.returncode}): {' '.join(args)}\n"
                f"stdout={completed.stdout}\nstderr={completed.stderr}"
            )
        return completed

    def start(
        self,
        root: Path,
        *tasks: tuple[str, str, str, str, str],
        stage: str = PHASE_1,
        inputs: tuple[str, ...] = ("用户材料索引",),
    ) -> subprocess.CompletedProcess[str]:
        arguments = ["start-stage", "--stage", stage]
        for value in inputs:
            arguments.extend(("--input", value))
        arguments.extend(self.catalog_task_arguments(stage))
        for task in tasks:
            arguments.extend(("--task", *task))
        started = self.run_cli(root, *arguments)
        self.complete_catalog_tasks(root, stage)
        return started

    @staticmethod
    def dynamic_task(template_id: str, instance_number: int) -> tuple[str, str, str, str, str]:
        instance = f"D{instance_number}"
        if template_id == "phase-3-diagram":
            return (
                f"phase-3-diagram-{instance}", f"生成并校验图包 {instance}",
                "patent_diagram_engineer",
                f"disclosure-workspace/working/stages/phase-3/diagrams/{instance}-result.tsv",
                "tsv",
            )
        if template_id == "phase-4-visual-review":
            return (
                f"phase-4-visual-review-{instance}", f"复核图示 {instance}",
                "patent_visual_reviewer",
                f"disclosure-workspace/working/stages/phase-4/visual/{instance}-review.tsv",
                "tsv",
            )
        raise AssertionError(f"unknown template fixture: {template_id}")

    @classmethod
    def catalog_tasks(
        cls,
        stage: str,
        template_counts: dict[str, int] | None = None,
    ) -> list[tuple[str, str, str, str, str]]:
        counts = template_counts or {}
        tasks: list[tuple[str, str, str, str, str]] = []
        for node in CATALOG_DATA[stage]:
            if node["type"] == "fixed":
                tasks.append(
                    (
                        node["task_id"], node["title"], node["allowed_owners"][0],
                        node["result"], node["minimum_check"],
                    )
                )
                continue
            count = counts.get(node["template_id"], node["min_instances"])
            tasks.extend(cls.dynamic_task(node["template_id"], index) for index in range(1, count + 1))
        return tasks

    @staticmethod
    def task_arguments(tasks: list[tuple[str, str, str, str, str]]) -> list[str]:
        arguments: list[str] = []
        for task in tasks:
            arguments.extend(("--task", *task))
        return arguments

    @classmethod
    def catalog_task_arguments(
        cls,
        stage: str,
        template_counts: dict[str, int] | None = None,
    ) -> list[str]:
        return cls.task_arguments(cls.catalog_tasks(stage, template_counts))

    def complete_catalog_tasks(self, root: Path, stage: str) -> None:
        for task_id, _, _, result, check in self.catalog_tasks(stage):
            if check == "json":
                data = b"{}\n"
            elif check == "tsv":
                data = b"id\tstatus\nfixture\tready\n"
            else:
                data = b"# fixture\n"
            self.write(root, result, data)
            self.run_cli(root, "complete-task", "--task", task_id)

    def advance_before(self, root: Path, target_stage: str) -> None:
        for index, stage in enumerate((PHASE_1, PHASE_2, PHASE_3, PHASE_4)):
            if stage == target_stage:
                return
            self.start(root, stage=stage, inputs=(f"阶段 {index + 1} 输入",))

    @staticmethod
    def write(root: Path, relative: str, data: str | bytes) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    @staticmethod
    def checkpoint(root: Path) -> Path:
        return root / CHECKPOINT

    def test_happy_path_all_checks_order_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tasks = (
                ("T1", "保存文本", "main_agent", "outputs/note.txt", "nonempty"),
                ("T2", "保存 JSON", "main_agent", "outputs/model.json", "json"),
                ("T3", "保存 Markdown", "main_agent", "outputs/review.md", "markdown"),
                ("T4", "保存 TSV", "main_agent", "outputs/map.tsv", "tsv"),
            )
            started = self.start(root, *tasks, inputs=("输入 A", "输入 B"))
            self.assertIn("checkpoint=started", started.stdout)
            self.assertIn("next_task=phase-1-material-index", started.stdout)
            checkpoint = self.checkpoint(root)
            content = checkpoint.read_text(encoding="utf-8")
            for heading in (
                "## 当前阶段", "## 本阶段输入", "## 本阶段任务",
                "## 当前阶段已交付", "## 下一步", "## 阻塞项",
            ):
                self.assertIn(heading, content)
            self.assertIn(
                "| 顺序 | ID | 标题 | owner | 结果文件 | 最低检查 | 状态 | SHA-256 |",
                content,
            )
            checkpoint_before_repeat = checkpoint.read_bytes()
            checkpoint_mtime = checkpoint.stat().st_mtime_ns
            repeated_start = self.start(root, *tasks, inputs=("输入 A", "输入 B"))
            self.assertIn("checkpoint=unchanged", repeated_start.stdout)
            self.assertEqual(checkpoint_before_repeat, checkpoint.read_bytes())
            self.assertEqual(checkpoint_mtime, checkpoint.stat().st_mtime_ns)
            self.assertIn("| json |", content)
            self.assertIn("| markdown |", content)
            self.assertIn("| tsv |", content)

            resumed = self.run_cli(root, "resume")
            self.assertIn("status=ready", resumed.stdout)
            self.assertIn("task_id=T1", resumed.stdout)

            fixtures = (
                ("T1", "outputs/note.txt", b"ready\n"),
                ("T2", "outputs/model.json", b'{"ok": true}\n'),
                ("T3", "outputs/review.md", "# 复核\n\n通过。\n".encode()),
                ("T4", "outputs/map.tsv", b"id\tstatus\nI1\tready\n"),
            )
            for index, (task_id, relative, data) in enumerate(fixtures):
                self.write(root, relative, data)
                completed = self.run_cli(root, "complete-task", "--task", task_id)
                digest = hashlib.sha256(data).hexdigest()
                self.assertIn(f"task_id={task_id}", completed.stdout)
                self.assertIn(f"sha256={digest}", completed.stdout)
                if index + 1 < len(fixtures):
                    resumed = self.run_cli(root, "resume")
                    self.assertIn(f"task_id={fixtures[index + 1][0]}", resumed.stdout)

            completed = self.run_cli(root, "resume")
            self.assertIn("status=complete", completed.stdout)
            validated = self.run_cli(root, "validate")
            self.assertIn("checkpoint=valid", validated.stdout)
            self.assertIn(f"completed_tasks={len(CATALOG_DATA[PHASE_1]) + 4}", validated.stdout)
            final_content = checkpoint.read_text(encoding="utf-8")
            for _, _, data in fixtures:
                self.assertIn(hashlib.sha256(data).hexdigest(), final_content)

    def test_catalog_v2_fixed_sequences_and_template_contracts(self) -> None:
        raw = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual("2.0", raw["schema_version"])
        self.assertFalse((SCRIPT.parents[1] / "references/checkpoint-task-catalog.json").exists())

        def node_ids(stage: str) -> list[str]:
            return [node.get("task_id", node.get("template_id")) for node in CATALOG_DATA[stage]]

        self.assertEqual(
            [
                "phase-1-material-index", "phase-1-evidence-cards", "phase-1-analysis-plan",
                "phase-1-delivery-goals", "phase-1-subject-boundary", "phase-1-research-object",
                "phase-1-research-mechanism", "phase-1-research-join",
                "phase-1-innovation-candidates", "phase-1-material-model", "phase-1-handoff",
            ],
            node_ids(PHASE_1),
        )
        self.assertEqual(["phase-2-decision", "phase-2-handoff"], node_ids(PHASE_2))
        self.assertEqual(
            [
                "phase-3-content-core", "phase-3-diagram-plan", "phase-3-public-draft",
                "phase-3-diagram", "phase-3-diagram-join", "phase-3-manifest",
                "phase-3-internal-draft", "phase-3-build-map", "phase-3-handoff",
            ],
            node_ids(PHASE_3),
        )
        self.assertEqual(
            [
                "phase-4-review-plan", "phase-4-semantic-review", "phase-4-visual-review",
                "phase-4-review-join", "phase-4-validation", "phase-4-timing-summary",
                "phase-4-handoff",
            ],
            node_ids(PHASE_4),
        )
        templates = {
            node["template_id"]: node
            for stage in (PHASE_3, PHASE_4)
            for node in CATALOG_DATA[stage]
            if node["type"] == "template"
        }
        self.assertEqual({"phase-3-diagram", "phase-4-visual-review"}, set(templates))
        for node in templates.values():
            self.assertEqual(2, node["min_instances"])
            self.assertEqual(8, node["max_instances"])
            self.assertEqual("tsv", node["minimum_check"])
            self.assertIn("(?P<instance>", node["task_id_regex"])
            self.assertIn("(?P<instance>", node["result_regex"])
        self.assertEqual(
            ["patent_diagram_engineer", "main_agent"],
            templates["phase-3-diagram"]["allowed_owners"],
        )
        self.assertEqual(
            ["patent_visual_reviewer", "main_agent"],
            templates["phase-4-visual-review"]["allowed_owners"],
        )

    def test_dynamic_templates_accept_consecutive_instances_and_trailing_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.advance_before(root, PHASE_3)
            tasks = self.catalog_tasks(PHASE_3, {"phase-3-diagram": 3})
            tasks.append(("custom-after-phase-3", "普通追加任务", "main_agent", "outputs/extra.txt", "nonempty"))
            started = self.run_cli(
                root,
                "start-stage", "--stage", PHASE_3, "--input", "阶段二 handoff",
                *self.task_arguments(tasks),
            )
            self.assertIn("checkpoint=started", started.stdout)
            checkpoint = self.checkpoint(root).read_text(encoding="utf-8")
            ordered_ids = (
                "phase-3-public-draft", "phase-3-diagram-D1", "phase-3-diagram-D2",
                "phase-3-diagram-D3", "phase-3-diagram-join", "phase-3-manifest",
                "phase-3-internal-draft", "phase-3-build-map", "phase-3-handoff",
                "custom-after-phase-3",
            )
            positions = [checkpoint.index(task_id) for task_id in ordered_ids]
            self.assertEqual(sorted(positions), positions)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.advance_before(root, PHASE_4)
            tasks = self.catalog_tasks(PHASE_4, {"phase-4-visual-review": 2})
            tasks.append(("custom-after-phase-4", "普通追加任务", "main_agent", "outputs/final-extra.txt", "nonempty"))
            started = self.run_cli(
                root,
                "start-stage", "--stage", PHASE_4, "--input", "阶段三 handoff",
                *self.task_arguments(tasks),
            )
            self.assertIn("checkpoint=started", started.stdout)
            checkpoint = self.checkpoint(root).read_text(encoding="utf-8")
            ordered_ids = (
                "phase-4-semantic-review", "phase-4-visual-review-D1",
                "phase-4-visual-review-D2", "phase-4-review-join", "phase-4-validation",
                "phase-4-timing-summary", "phase-4-handoff", "custom-after-phase-4",
            )
            positions = [checkpoint.index(task_id) for task_id in ordered_ids]
            self.assertEqual(sorted(positions), positions)

    def test_trailing_custom_tasks_reject_other_stage_catalog_identities(self) -> None:
        phase_2_fixed = next(
            node for node in CATALOG_DATA[PHASE_2] if node["type"] == "fixed"
        )
        phase_3_template_task = self.dynamic_task("phase-3-diagram", 7)
        phase_4_template_task = self.dynamic_task("phase-4-visual-review", 7)
        cases = (
            (
                (
                    phase_2_fixed["task_id"], "伪装其他阶段固定 ID", "main_agent",
                    "outputs/custom-fixed-id.txt", "nonempty",
                ),
                "追加任务不得复用其他阶段固定任务 ID",
            ),
            (
                (
                    "custom-fixed-result", "伪装其他阶段固定结果", "main_agent",
                    phase_2_fixed["result"], "markdown",
                ),
                "追加任务不得复用其他阶段固定任务结果",
            ),
            (
                (
                    phase_3_template_task[0], "伪装其他阶段模板 ID", "main_agent",
                    "outputs/custom-template-id.txt", "nonempty",
                ),
                "追加任务不得匹配其他阶段模板任务 ID",
            ),
            (
                (
                    "custom-template-result", "伪装其他阶段模板结果", "main_agent",
                    phase_4_template_task[3], "tsv",
                ),
                "追加任务不得匹配其他阶段模板任务结果",
            ),
        )
        for task, expected_message in cases:
            with self.subTest(task_id=task[0]), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                rejected = self.run_raw(
                    root,
                    "start-stage", "--stage", PHASE_1, "--input", "阶段一输入",
                    *self.catalog_task_arguments(PHASE_1), "--task", *task,
                )
                self.assertEqual(1, rejected.returncode, rejected.stderr)
                self.assertIn(expected_message, rejected.stderr)
                self.assertFalse(self.checkpoint(root).exists())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            accepted = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "阶段一输入",
                *self.catalog_task_arguments(PHASE_1),
                "--task", "custom-phase-1-tail", "真正的阶段尾部任务", "main_agent",
                "outputs/custom-phase-1-tail.txt", "nonempty",
            )
            self.assertEqual(0, accepted.returncode, accepted.stderr)
            self.assertIn("checkpoint=started", accepted.stdout)

    def test_dynamic_template_rejects_count_order_instance_owner_check_and_position(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.advance_before(root, PHASE_3)
            valid_tasks = self.catalog_tasks(PHASE_3)
            self.run_cli(
                root,
                "start-stage", "--stage", PHASE_3, "--input", "阶段二 handoff",
                *self.task_arguments(valid_tasks),
            )
            checkpoint = self.checkpoint(root)
            unchanged = checkpoint.read_bytes()

            def rejected(tasks: list[tuple[str, str, str, str, str]], message: str) -> None:
                completed = self.run_raw(
                    root,
                    "rollback-stage", "--stage", PHASE_3, "--reason", "模板反例",
                    "--input", "阶段二 handoff", *self.task_arguments(tasks),
                )
                self.assertEqual(1, completed.returncode, completed.stderr)
                self.assertIn(message, completed.stderr)
                self.assertEqual(unchanged, checkpoint.read_bytes())

            rejected(
                self.catalog_tasks(PHASE_3, {"phase-3-diagram": 1}),
                "模板任务实例不足",
            )
            rejected(
                self.catalog_tasks(PHASE_3, {"phase-3-diagram": 9}),
                "模板任务实例超过上限",
            )

            starts_at_d2 = self.catalog_tasks(PHASE_3)
            diagram_index = next(
                index for index, task in enumerate(starts_at_d2)
                if task[0] == "phase-3-diagram-D1"
            )
            starts_at_d2[diagram_index] = self.dynamic_task("phase-3-diagram", 2)
            starts_at_d2[diagram_index + 1] = self.dynamic_task("phase-3-diagram", 3)
            rejected(starts_at_d2, "必须从 D1 连续编号")

            gap = self.catalog_tasks(PHASE_3)
            gap[diagram_index + 1] = self.dynamic_task("phase-3-diagram", 3)
            rejected(gap, "必须从 D1 连续编号")

            mismatched_instance = self.catalog_tasks(PHASE_3)
            first = list(mismatched_instance[diagram_index])
            first[3] = "disclosure-workspace/working/stages/phase-3/diagrams/D8-result.tsv"
            mismatched_instance[diagram_index] = tuple(first)
            rejected(mismatched_instance, "task_id/result instance 不一致")

            wrong_owner = self.catalog_tasks(PHASE_3)
            first = list(wrong_owner[diagram_index])
            first[2] = "patent_visual_reviewer"
            wrong_owner[diagram_index] = tuple(first)
            rejected(wrong_owner, "模板任务 owner 不允许")

            wrong_check = self.catalog_tasks(PHASE_3)
            first = list(wrong_check[diagram_index])
            first[4] = "markdown"
            wrong_check[diagram_index] = tuple(first)
            rejected(wrong_check, "模板任务最低检查不匹配")

            misplaced = self.catalog_tasks(PHASE_3)
            misplaced.append(self.dynamic_task("phase-3-diagram", 3))
            rejected(misplaced, "模板任务只能在 catalog 固定位置连续出现")

    def test_complete_task_allows_parallel_order_and_requires_valid_regular_nonempty_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.start(
                root,
                ("T1", "先完成", "main_agent", "outputs/first.txt", "nonempty"),
                ("T2", "后完成", "main_agent", "outputs/second.txt", "nonempty"),
            )
            checkpoint = self.checkpoint(root)
            self.write(root, "outputs/second.txt", b"parallel-result\n")
            out_of_order = self.run_cli(root, "complete-task", "--task", "T2")
            self.assertIn("checkpoint=task_completed", out_of_order.stdout)
            self.assertIn("task_id=T2", out_of_order.stdout)
            before = checkpoint.read_bytes()
            self.assertIn(
                f"| {len(CATALOG_DATA[PHASE_1]) + 2} | T2 |",
                checkpoint.read_text(encoding="utf-8"),
            )
            resume = self.run_cli(root, "resume")
            self.assertIn("status=ready", resume.stdout)
            self.assertIn("task_id=T1", resume.stdout)

            self.write(root, "outputs/first.txt", b"")
            empty = self.run_raw(root, "complete-task", "--task", "T1")
            self.assertEqual(1, empty.returncode)
            self.assertIn("check_failed:nonempty", empty.stderr)
            self.assertEqual(before, checkpoint.read_bytes())

            directory = root / "outputs/first.txt"
            directory.unlink()
            directory.mkdir()
            nonregular = self.run_raw(root, "complete-task", "--task", "T1")
            self.assertEqual(1, nonregular.returncode)
            self.assertIn("unsafe_or_nonregular_result", nonregular.stderr)
            self.assertEqual(before, checkpoint.read_bytes())
            directory.rmdir()
            os.mkfifo(directory)
            fifo = self.run_raw(root, "complete-task", "--task", "T1")
            self.assertEqual(1, fifo.returncode)
            self.assertIn("unsafe_or_nonregular_result", fifo.stderr)
            self.assertEqual(before, checkpoint.read_bytes())
            self.assertEqual([], list(checkpoint.parent.glob(".CHECKPOINT.*")))

    def test_invalid_json_markdown_and_tsv_are_rejected(self) -> None:
        cases = (
            ("json", "outputs/value.json", b'{"broken":}'),
            ("markdown", "outputs/value.md", b"   \n"),
            ("tsv", "outputs/value.tsv", b"id\tstatus\nI1\n"),
        )
        for check, relative, data in cases:
            with self.subTest(check=check), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.start(root, ("T1", "格式检查", "main_agent", relative, check))
                self.write(root, relative, data)
                rejected = self.run_raw(root, "complete-task", "--task", "T1")
                self.assertEqual(1, rejected.returncode)
                self.assertIn(f"check_failed:{check}", rejected.stderr)

    def test_resume_is_read_only_and_redoes_missing_or_changed_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.start(
                root,
                ("T1", "第一个结果", "main_agent", "outputs/first.txt", "nonempty"),
                ("T2", "第二个结果", "main_agent", "outputs/second.txt", "nonempty"),
            )
            first = self.write(root, "outputs/first.txt", b"first-v1\n")
            self.run_cli(root, "complete-task", "--task", "T1")
            checkpoint = self.checkpoint(root)
            before = checkpoint.read_bytes()
            before_mtime = checkpoint.stat().st_mtime_ns
            repeated = self.run_cli(root, "complete-task", "--task", "T1")
            self.assertIn("checkpoint=already_complete", repeated.stdout)
            self.assertIn("next_task=T2", repeated.stdout)
            self.assertEqual(before, checkpoint.read_bytes())
            self.assertEqual(before_mtime, checkpoint.stat().st_mtime_ns)

            ready = self.run_cli(root, "resume")
            self.assertIn("status=ready", ready.stdout)
            self.assertIn("task_id=T2", ready.stdout)
            self.assertEqual(before, checkpoint.read_bytes())
            self.assertEqual(before_mtime, checkpoint.stat().st_mtime_ns)

            first.write_bytes(b"first-v2\n")
            changed = self.run_cli(root, "resume")
            self.assertIn("status=redo", changed.stdout)
            self.assertIn("task_id=T1", changed.stdout)
            self.assertIn("reason=sha256_changed", changed.stdout)
            self.assertEqual(before, checkpoint.read_bytes())
            failed_validate = self.run_raw(root, "validate")
            self.assertEqual(1, failed_validate.returncode)
            self.assertIn("sha256_changed", failed_validate.stderr)
            self.assertEqual(before, checkpoint.read_bytes())

            first.unlink()
            missing = self.run_cli(root, "resume")
            self.assertIn("status=redo", missing.stdout)
            self.assertIn("task_id=T1", missing.stdout)
            self.assertIn("reason=result_missing", missing.stdout)
            self.assertEqual(before, checkpoint.read_bytes())

            outside = root / "outputs/linked-target.txt"
            outside.write_text("outside\n", encoding="utf-8")
            first.symlink_to(outside)
            linked = self.run_cli(root, "resume")
            self.assertIn("status=redo", linked.stdout)
            self.assertIn("task_id=T1", linked.stdout)
            self.assertIn("reason=unsafe_or_nonregular_result", linked.stdout)
            self.assertEqual(before, checkpoint.read_bytes())

    def test_wait_user_and_block_are_persistent_and_resume_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tasks = (
                ("T1", "已交付结果", "main_agent", "outputs/delivered.txt", "nonempty"),
                ("T2", "等待后继续", "main_agent", "outputs/result.txt", "nonempty"),
            )
            self.start(root, *tasks)
            delivered = self.write(root, "outputs/delivered.txt", b"delivered\n")
            self.run_cli(root, "complete-task", "--task", "T1")
            waited = self.run_cli(root, "wait-user", "--reason", "确认保护边界")
            self.assertIn("status=waiting_user", waited.stdout)
            checkpoint = self.checkpoint(root)
            waiting_content = checkpoint.read_bytes()
            waiting_text = checkpoint.read_text(encoding="utf-8")
            self.assertIn("- 等待用户：确认保护边界", waiting_text.split("## 下一步", 1)[1])
            self.assertIn("- 无", waiting_text.split("## 阻塞项", 1)[1])
            waiting_mtime = checkpoint.stat().st_mtime_ns
            resumed = self.run_cli(root, "resume")
            self.assertIn("status=waiting_user", resumed.stdout)
            self.assertIn("reason=确认保护边界", resumed.stdout)
            self.assertEqual(waiting_content, checkpoint.read_bytes())
            self.assertEqual(waiting_mtime, checkpoint.stat().st_mtime_ns)

            repeated_wait = self.run_cli(root, "wait-user", "--reason", "确认保护边界")
            self.assertIn("checkpoint=unchanged", repeated_wait.stdout)
            self.assertEqual(waiting_content, checkpoint.read_bytes())
            self.assertEqual(waiting_mtime, checkpoint.stat().st_mtime_ns)

            delivered.unlink()
            invalid_delivery = self.run_cli(root, "resume")
            self.assertIn("status=redo", invalid_delivery.stdout)
            self.assertIn("task_id=T1", invalid_delivery.stdout)
            self.assertIn("reason=result_missing", invalid_delivery.stdout)
            self.assertEqual(waiting_content, checkpoint.read_bytes())
            invalid_block = self.run_cli(root, "block", "--reason", "已交付文件丢失")
            self.assertIn("status=blocked", invalid_block.stdout)
            blocked_after_loss = checkpoint.read_text(encoding="utf-8")
            self.assertIn(
                f"| {len(CATALOG_DATA[PHASE_1]) + 1} | T1 | 已交付结果 | main_agent | outputs/delivered.txt | nonempty | pending | - |",
                blocked_after_loss,
            )
            delivered_section = blocked_after_loss.split("## 当前阶段已交付", 1)[1].split("## 下一步", 1)[0]
            self.assertNotIn("| 1 | T1 | 已交付结果 |", delivered_section)
            delivered.write_text("delivered\n", encoding="utf-8")

            self.start(root, *tasks)
            active = self.run_cli(root, "resume")
            self.assertIn("status=ready", active.stdout)
            blocked = self.run_cli(root, "block", "--reason", "缺少检索能力")
            self.assertIn("status=blocked", blocked.stdout)
            blocked_content = checkpoint.read_bytes()
            resumed = self.run_cli(root, "resume")
            self.assertIn("status=blocked", resumed.stdout)
            self.assertIn("reason=缺少检索能力", resumed.stdout)
            self.assertEqual(blocked_content, checkpoint.read_bytes())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.start(
                root,
                ("A", "顺序在前的待办", "main_agent", "outputs/a.txt", "nonempty"),
                ("B", "并行先完成", "main_agent", "outputs/b.txt", "nonempty"),
            )
            completed_later = self.write(root, "outputs/b.txt", b"parallel\n")
            self.run_cli(root, "complete-task", "--task", "B")
            self.run_cli(root, "wait-user", "--reason", "等待确认")
            completed_later.unlink()
            paused = self.run_cli(root, "resume")
            self.assertIn("status=waiting_user", paused.stdout)
            self.assertNotIn("status=redo", paused.stdout)

    def test_rollback_requires_explicit_reason_and_does_not_infer_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fresh_late = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_3, "--input", "跳过前序阶段",
                *self.catalog_task_arguments(PHASE_3),
                "--task", "T3", "阶段三结果", "main_agent", "outputs/phase-3.txt", "nonempty",
            )
            self.assertEqual(1, fresh_late.returncode)
            self.assertIn("首次 start-stage 必须从 phase_1_material_modeling 开始", fresh_late.stderr)

            self.start(
                root,
                ("T1", "阶段一结果", "main_agent", "outputs/phase-1-current.txt", "nonempty"),
            )
            self.write(root, "outputs/phase-1-current.txt", b"phase-1\n")
            self.run_cli(root, "complete-task", "--task", "T1")
            skipped = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_3, "--input", "跳过阶段二",
                *self.catalog_task_arguments(PHASE_3),
                "--task", "T3", "阶段三结果", "main_agent", "outputs/phase-3.txt", "nonempty",
            )
            self.assertEqual(1, skipped.returncode)
            self.assertIn("固定顺序逐阶段开始", skipped.stderr)
            self.start(
                root,
                ("T2", "阶段二结果", "main_agent", "outputs/phase-2.txt", "nonempty"),
                stage=PHASE_2,
                inputs=("阶段一 handoff",),
            )
            self.write(root, "outputs/phase-2.txt", b"phase-2\n")
            self.run_cli(root, "complete-task", "--task", "T2")
            self.start(
                root,
                ("T3", "阶段三结果", "main_agent", "outputs/phase-3.txt", "nonempty"),
                stage=PHASE_3,
                inputs=("阶段二 handoff",),
            )
            checkpoint = self.checkpoint(root)
            before = checkpoint.read_bytes()
            missing_reason = self.run_raw(
                root,
                "rollback-stage", "--stage", PHASE_1,
                "--input", "新增用户事实",
                "--task", "T1", "重建模型", "main_agent", "outputs/phase-1.txt", "nonempty",
            )
            self.assertEqual(2, missing_reason.returncode)
            self.assertEqual(before, checkpoint.read_bytes())

            rolled_back = self.run_cli(
                root,
                "rollback-stage", "--stage", PHASE_1,
                "--reason", "主 agent 判定来源事实已改变",
                "--input", "新增用户事实",
                *self.catalog_task_arguments(PHASE_1),
                "--task", "T1", "重建模型", "main_agent", "outputs/phase-1.txt", "nonempty",
            )
            self.assertIn("checkpoint=rolled_back", rolled_back.stdout)
            self.assertIn("stage=phase_1_material_modeling", rolled_back.stdout)
            content = checkpoint.read_text(encoding="utf-8")
            self.assertIn("主 agent 判定来源事实已改变", content)
            self.assertNotIn("阶段三结果", content)

            rollback_bytes = checkpoint.read_bytes()
            rollback_mtime = checkpoint.stat().st_mtime_ns
            repeated_rollback = self.run_cli(
                root,
                "rollback-stage", "--stage", PHASE_1,
                "--reason", "主 agent 判定来源事实已改变",
                "--input", "新增用户事实",
                *self.catalog_task_arguments(PHASE_1),
                "--task", "T1", "重建模型", "main_agent", "outputs/phase-1.txt", "nonempty",
            )
            self.assertIn("checkpoint=unchanged", repeated_rollback.stdout)
            self.assertEqual(rollback_bytes, checkpoint.read_bytes())
            self.assertEqual(rollback_mtime, checkpoint.stat().st_mtime_ns)

            future = self.run_raw(
                root,
                "rollback-stage", "--stage", PHASE_3,
                "--reason", "非法前进",
                "--input", "输入",
                "--task", "T3", "阶段三结果", "main_agent", "outputs/phase-3.txt", "nonempty",
            )
            self.assertEqual(1, future.returncode)
            self.assertIn("不能前进到更后阶段", future.stderr)

            changed_start = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1,
                "--input", "被修改的输入",
                *self.catalog_task_arguments(PHASE_1),
                "--task", "T1", "重建模型", "main_agent", "outputs/phase-1.txt", "nonempty",
            )
            self.assertEqual(1, changed_start.returncode)
            self.assertIn("输入或任务定义变化必须使用 rollback-stage", changed_start.stderr)

    def test_path_traversal_absolute_and_symlink_escape_are_rejected(self) -> None:
        bad_paths = ("../outside.txt", "/tmp/outside.txt", "outputs/../outside.txt", "..\\outside.txt")
        for relative in bad_paths:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                rejected = self.run_raw(
                    root,
                    "start-stage", "--stage", PHASE_1, "--input", "input",
                    "--task", "T1", "非法路径", "main_agent", relative, "nonempty",
                )
                self.assertEqual(1, rejected.returncode)
                self.assertFalse(self.checkpoint(root).exists())

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "disclosure"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "linked").symlink_to(outside, target_is_directory=True)
            escaped = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                *self.catalog_task_arguments(PHASE_1),
                "--task", "T1", "符号链接逃逸", "main_agent", "linked/result.txt", "nonempty",
            )
            self.assertEqual(1, escaped.returncode)
            self.assertIn("符号链接", escaped.stderr)
            self.assertFalse(self.checkpoint(root).exists())

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "disclosure"
            root.mkdir()
            target = self.write(root, "real.txt", b"real\n")
            (root / "result.txt").symlink_to(target)
            linked_result = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                *self.catalog_task_arguments(PHASE_1),
                "--task", "T1", "符号链接结果", "main_agent", "result.txt", "nonempty",
            )
            self.assertEqual(1, linked_result.returncode)
            self.assertIn("符号链接", linked_result.stderr)

    def test_unknown_check_duplicate_ids_and_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_fixed = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                "--task", "T1", "仅额外任务", "main_agent", "outputs/result.txt", "nonempty",
            )
            self.assertEqual(1, missing_fixed.returncode)
            self.assertIn("阶段固定任务不完整", missing_fixed.stderr)

            inserted = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                "--task", "T1", "错误插入", "main_agent", "outputs/result.txt", "nonempty",
                *self.catalog_task_arguments(PHASE_1),
            )
            self.assertEqual(1, inserted.returncode)
            self.assertIn("必须按 catalog 顺序且只能追加", inserted.stderr)

            mismatched = self.catalog_task_arguments(PHASE_1)
            expected_result = CATALOG_DATA[PHASE_1][0]["result"]
            mismatched[mismatched.index(expected_result)] = "outputs/wrong.tsv"
            wrong_definition = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                *mismatched,
            )
            self.assertEqual(1, wrong_definition.returncode)
            self.assertIn("结果路径不匹配", wrong_definition.stderr)

            wrong_title_tasks = self.catalog_tasks(PHASE_1)
            first_fixed = list(wrong_title_tasks[0])
            first_fixed[1] = "被篡改的固定标题"
            wrong_title_tasks[0] = tuple(first_fixed)
            wrong_title = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                *self.task_arguments(wrong_title_tasks),
            )
            self.assertEqual(1, wrong_title.returncode)
            self.assertIn("固定任务标题不匹配", wrong_title.stderr)

            missing_owner = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                "--task", "T1", "缺 owner", "outputs/result.txt", "nonempty",
            )
            self.assertEqual(2, missing_owner.returncode)
            empty_owner = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                "--task", "T1", "空 owner", "", "outputs/result.txt", "nonempty",
            )
            self.assertEqual(1, empty_owner.returncode)
            self.assertIn("owner 不得为空", empty_owner.stderr)
            self.assertFalse(self.checkpoint(root).exists())

            unknown = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                "--task", "T1", "未知检查", "main_agent", "outputs/result.txt", "yaml",
            )
            self.assertEqual(1, unknown.returncode)
            self.assertIn("不支持的最低检查", unknown.stderr)

            duplicate = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                "--task", "T1", "任务一", "main_agent", "outputs/one.txt", "nonempty",
                "--task", "T1", "任务二", "main_agent", "outputs/two.txt", "nonempty",
            )
            self.assertEqual(1, duplicate.returncode)
            self.assertIn("任务 ID 重复", duplicate.stderr)

            self.start(root, ("T1", "正常任务", "main_agent", "outputs/result.txt", "nonempty"))
            checkpoint = self.checkpoint(root)
            checkpoint.write_text(
                checkpoint.read_text(encoding="utf-8").replace("# 执行检查点", "# 手工篡改"),
                encoding="utf-8",
            )
            tampered = self.run_raw(root, "validate")
            self.assertEqual(1, tampered.returncode)
            self.assertIn("规范渲染", tampered.stderr)

    def test_checkpoint_path_symlink_and_read_only_commands_do_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "disclosure"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "disclosure-workspace").symlink_to(outside, target_is_directory=True)
            rejected = self.run_raw(
                root,
                "start-stage", "--stage", PHASE_1, "--input", "input",
                *self.catalog_task_arguments(PHASE_1),
                "--task", "T1", "任务", "main_agent", "result.txt", "nonempty",
            )
            self.assertEqual(1, rejected.returncode)
            self.assertIn("符号链接", rejected.stderr)
            self.assertEqual([], list(outside.iterdir()))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_resume = self.run_raw(root, "resume")
            missing_validate = self.run_raw(root, "validate")
            self.assertEqual(1, missing_resume.returncode)
            self.assertEqual(1, missing_validate.returncode)
            self.assertFalse((root / "disclosure-workspace").exists())


if __name__ == "__main__":
    unittest.main()
