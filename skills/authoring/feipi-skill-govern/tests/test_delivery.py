"""正式交接的正反例，以及真实测试入口的中途失败传递。"""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("delivery", SKILL / "scripts/check_delivery.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.request = self.root / "request.txt"
        self.request.write_text("修复报告遗漏具体问题与未解决原因。", encoding="utf-8")
        (self.root / "source.json").write_text('{"problem":"缺少证据"}', encoding="utf-8")
        (self.root / "report.md").write_text("P1：缺少证据，尚未修复。", encoding="utf-8")
        (self.root / "test.log").write_text("实际调用完成。", encoding="utf-8")
        self.record = self.root / "record.json"
        self.data = {
            "schema_version": 1, "target_skill": "feipi-report-build-summary",
            "request_sha256": delivery.digest(self.request),
            "inputs": [{"id": "source", **self.file("source.json")}],
            "problems": [{
                "id": "P1", "source_ids": ["request", "source"],
                "observation": "原始问题在报告中丢失，影响后续修复。", "expected": "报告保留具体问题和不足。",
                "failure_case": "两条不同问题不能合并为一个目标名称。", "owner": "脚本处理",
                "status": "open", "outcome": "尚未修复；需要继续定位处理逻辑。", "check_ids": ["T1"],
            }],
            "checks": [
                {"id": "T1", "kind": "technical", "status": "passed", "method": "实际调用", "result": "仅技术通过", "evidence": ["test.log"]},
                {"id": "S1", "kind": "semantic", "status": "not_run", "method": "原始材料审阅", "result": "未执行 Agent 评估", "evidence": []},
                {"id": "I1", "kind": "integration", "status": "not_applicable", "method": "能力边界审阅", "result": "无外部发送能力", "evidence": []},
            ],
            "artifacts": [self.file("report.md"), self.file("test.log")],
            "report": {"path": "report.md", "problem_ids": ["P1"]},
            "notification": {"status": "prepared", "text": "P1 尚未修复，语义效果未验证。", "problem_ids": ["P1"], "evidence": []},
        }

    def file(self, name):
        return {"path": name, "sha256": delivery.digest(self.root / name)}

    def validate(self, final=True):
        self.record.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        return delivery.validate(self.record, self.request, final)

    def test_partial_final_report_preserves_open_and_unverified(self):
        result = self.validate()
        self.assertEqual(result["problems"][0]["status"], "open")
        self.assertEqual(result["checks"][1]["status"], "not_run")

    def test_resume_rejects_changed_request_or_input(self):
        self.request.write_text("这轮用户请求已更换。", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "当前请求"):
            self.validate()
        self.data["request_sha256"] = delivery.digest(self.request)
        (self.root / "source.json").write_text("新的来源材料", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "指纹不符"):
            self.validate()

    def test_detects_missing_or_changed_delivery(self):
        report = self.root / "report.md"
        report.unlink()
        with self.assertRaisesRegex(ValueError, "缺少交接文件"):
            self.validate()
        report.write_text("不同报告", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "指纹不符"):
            self.validate()

    def test_rejects_lost_problem_in_report_or_notification(self):
        for key in ("report", "notification"):
            with self.subTest(key=key):
                self.data[key]["problem_ids"] = []
                with self.assertRaisesRegex(ValueError, "未覆盖全部问题"):
                    self.validate()
                self.data[key]["problem_ids"] = ["P1"]

    def test_rejects_unknown_duplicate_or_missing_references(self):
        original = copy.deepcopy(self.data)
        for change in (
            lambda d: d["problems"].append(copy.deepcopy(d["problems"][0])),
            lambda d: d["problems"][0].update(source_ids=["unknown"]),
            lambda d: d["problems"][0].update(check_ids=["unknown"]),
            lambda d: d["checks"][0].update(evidence=["missing.log"]),
        ):
            self.data = copy.deepcopy(original)
            change(self.data)
            with self.assertRaises(ValueError):
                self.validate()

    def test_rejects_fixed_without_passed_evidence(self):
        self.data["problems"][0].update(status="fixed", check_ids=["S1"])
        with self.assertRaisesRegex(ValueError, "已修复项缺少通过证据"):
            self.validate()
        self.data["problems"][0]["check_ids"] = ["T1"]
        self.validate()

    def test_rejects_execution_or_delivery_claim_without_evidence(self):
        self.data["checks"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "必须引用证据"):
            self.validate()
        self.data["checks"][0]["evidence"] = ["test.log"]
        self.data["notification"]["status"] = "delivered"
        with self.assertRaisesRegex(ValueError, "缺少接收证据"):
            self.validate()

    def test_final_requires_all_three_verification_declarations(self):
        self.data["checks"].pop()
        with self.assertRaisesRegex(ValueError, "三类验证"):
            self.validate()
        self.data["report"] = None
        self.validate(final=False)
        with self.assertRaisesRegex(ValueError, "缺少报告"):
            self.validate()

    def test_technical_checker_does_not_pretend_to_judge_meaning(self):
        # 格式及引用齐全仍可能语义漏项，须由真实 Agent 产物审阅发现。
        (self.root / "report.md").write_text("只有目标名称，没有具体问题。", encoding="utf-8")
        self.data["artifacts"][0] = self.file("report.md")
        self.validate()

    def test_cli_reports_technical_boundary_and_rejects_malformed_json(self):
        self.validate()
        command = ["python3", str(SKILL / "scripts/check_delivery.py"), str(self.record), "--request-file", str(self.request), "--final"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("业务正确性", result.stdout)
        self.record.write_text("[]", encoding="utf-8")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)


class HarnessTests(unittest.TestCase):
    def test_generated_scaffold_rejects_placeholder_and_missing_maintenance(self):
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run(["bash", str(SKILL / "scripts/init_skill.sh"), "report-build-summary", "--target", temp], check=True, capture_output=True)
            skill = Path(temp) / "feipi-report-build-summary"
            entry = ["bash", str(skill / "tests/run.sh")]
            result = subprocess.run(entry, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("尚未验证", result.stdout)
            original = (skill / "SKILL.md").read_text(encoding="utf-8")
            (skill / "SKILL.md").write_text(original + "\n" + "{{" + "SKILL_NAME}}", encoding="utf-8")
            self.assertNotEqual(subprocess.run(entry, capture_output=True).returncode, 0)
            (skill / "SKILL.md").write_text(original, encoding="utf-8")
            (skill / "maintenance/terminology.md").write_text("", encoding="utf-8")
            self.assertNotEqual(subprocess.run(entry, capture_output=True).returncode, 0)

    def test_real_entry_rejects_success_exit_with_error_message(self):
        # 旧入口把整个 run_case 放在 if 中，[[ code != 0 ]] 失败后仍会继续 grep 并假通过。
        with tempfile.TemporaryDirectory() as temp:
            skill = Path(temp) / "skills/authoring/feipi-skill-govern"
            skill.parent.mkdir(parents=True)
            shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("__pycache__"))
            validator = skill / "scripts/validate.sh"
            validator.write_text('#!/usr/bin/env bash\necho "未替换模板占位符"\nexit 0\n', encoding="utf-8")
            result = subprocess.run(["bash", str(skill / "tests/run.sh"), "--case", "validate-detects-placeholder"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, "错误的零退出码被测试入口误报成功")


class EvaluationFixtureTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("fixture", SKILL / "evals/prepare_fixture.py")
        self.fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.fixture)

    def test_constructor_preserves_existing_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            existing = root / "keep.txt"
            existing.write_text("原有资料", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "必须为空"):
                self.fixture.prepare(root)
            self.assertEqual(existing.read_text(encoding="utf-8"), "原有资料")
            self.assertEqual(list(root.iterdir()), [existing])

    def test_resume_fixture_contains_real_input_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture.prepare(root, "stale-handoff")
            with self.assertRaisesRegex(ValueError, "当前请求"):
                delivery.validate(root / "governance-record.json", root / "request.txt")
            record = json.loads((root / "governance-record.json").read_text(encoding="utf-8"))
            record["request_sha256"] = delivery.digest(root / "request.txt")
            (root / "governance-record.json").write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "指纹不符"):
                delivery.validate(root / "governance-record.json", root / "request.txt")


if __name__ == "__main__":
    unittest.main()
