import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_migration import validate
from review_skill import digest, fingerprint, inventory, verify_approval


class MigrationReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.root = root
        self.upstream = root / "upstream"
        self.upstream.mkdir()
        (self.upstream / "playbook.md").write_text("call a driver\n", encoding="utf-8")
        self.install = root / "install"
        self.caller = "feipi-code-repair-bug"
        self.target = "feipi-code-verify-behavior"
        self.skills = []
        for name in (self.caller, self.target):
            source = Path("skills/engineering") / name
            self.skills.append({"name": name, "path": str(source)})
            for destination in (root / source, self.install / name):
                destination.mkdir(parents=True)
                (destination / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: Same words near both titles\n---\n# Skill\n",
                    encoding="utf-8",
                )
        self.dep = {
            "id": "driver", "caller": self.caller, "source": "playbook.md#L1",
            "kind": "skill", "behavior": "Run original path", "disposition": "adapt",
            "target": self.target, "missing": "Report live verification blocked",
            "verification": "Exercise the fixture in isolated install",
        }
        self.manifest = {"schema_version": 1, "upstream_revision": "a" * 40,
                         "skills": self.skills, "dependencies": [self.dep]}

    def inspect(self):
        return validate(self.manifest, self.root, self.install, self.upstream)

    def test_exact_bindings_with_similar_description(self):
        other = self.install / "feipi-code-verify-alternative"
        other.mkdir()
        (other / "SKILL.md").write_bytes((self.install / self.target / "SKILL.md").read_bytes())
        self.assertIn("driver", self.inspect())
        (self.install / self.target / "SKILL.md").unlink()
        with self.assertRaisesRegex(ValueError, "安装入口"):
            self.inspect()

    def test_cycle_and_unknown_project_reference(self):
        self.manifest["dependencies"].append(
            dict(self.dep, id="back", caller=self.target, target=self.caller))
        with self.assertRaisesRegex(ValueError, "调用有循环"):
            self.inspect()
        self.manifest["dependencies"].pop()
        self.dep.update(kind="project", target="missing")
        with self.assertRaisesRegex(ValueError, "未知项目入口"):
            self.inspect()
        self.dep.update(target="verification")
        self.assertIn("driver", self.inspect())

    def test_blocked_driver_stays_visible(self):
        self.dep.update(kind="host", disposition="blocked", target="live browser")
        self.assertEqual(self.inspect()["driver"]["disposition"], "blocked")

    def test_rejects_paths_in_source_even_before_install(self):
        caller = self.root / self.skills[0]["path"]
        config = caller / "runtime.yml"
        for location, issue in (
            ("~/.cursor/projects/project", "依赖 IDE"),
            ("./.cursor/rules/models.mdc", "依赖 IDE"),
            ("$PROJECT/.vscode/tasks.json", "依赖 IDE"),
            (r"$PROJECT\.idea\workspace.xml", "依赖 IDE"),
            ("$HOME/Downloads/plugins/control-ui", "个人上游目录"),
            ("project.code-workspace", "依赖 IDE"),
            ("/" + "Users/alice/work/repo", "固定机器"),
            ("D:" + r"\scratch\repo", "Windows 盘符"),
            ("D:" + r"\\scratch\\repo", "Windows 盘符"),
            ("file:" + "//localhost/data/notes", "本机 URI"),
            (r"\\share\workspace\notes", "固定网络共享"),
        ):
            with self.subTest(location=location):
                config.write_text(f'root: "{location}"\n', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, issue):
                    validate(self.manifest, self.root, upstream_root=self.upstream)

    def test_rejects_installed_path_and_manifest_host_target(self):
        caller = self.install / self.caller
        extensionless = caller / "use-driver"
        extensionless.write_text("Open ~/.codex/sessions/ first.", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "use-driver:1"):
            self.inspect()
        extensionless.unlink()
        self.dep.update(kind="sibling", target="Downloads/plugins/control-ui")
        with self.assertRaisesRegex(ValueError, "driver 的目标入口"):
            self.inspect()

    def test_allows_anchored_paths_and_upstream_only_evidence(self):
        for caller in (self.root / self.skills[0]["path"], self.install / self.caller):
            (caller / "references").mkdir()
            (caller / "references/driver.md").write_text(
                'Read the project binding for docs/verify.md.\n'
                'Read "${PROJECT_ROOT}/opt/drivers/start".\n'
                'See https://example.org/.vscode/task for upstream context.\n',
                encoding="utf-8",
            )
        source_maintenance = self.root / self.skills[0]["path"] / "maintenance"
        source_maintenance.mkdir()
        (source_maintenance / "audit.md").write_text("Original: ~/.cursor/projects", encoding="utf-8")
        (self.upstream / "playbook.md").write_text("Original: ~/.cursor/projects", encoding="utf-8")
        (self.install / self.caller / ".feipi-agent-kit-source").write_text(
            "/" + "Users/author/kit/skills", encoding="utf-8",
        )
        self.dep.update(kind="bundled", target="references/driver.md")
        self.assertIn("driver", self.inspect())

    def test_rejects_missing_bundled_resource(self):
        self.dep.update(kind="bundled", target="references/driver.md")
        with self.assertRaisesRegex(ValueError, "不存在"):
            self.inspect()

    def test_rejects_symlink_to_machine_local_resource(self):
        path = self.root / "external-driver"
        path.mkdir()
        caller = self.root / self.skills[0]["path"]
        link = caller / "driver"
        link.symlink_to(path, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "超出 Skill 根目录"):
            validate(self.manifest, self.root, upstream_root=self.upstream)
        link.unlink()
        link.symlink_to(caller / "SKILL.md")
        with self.assertRaisesRegex(ValueError, "绝对符号链接"):
            validate(self.manifest, self.root, upstream_root=self.upstream)

    def test_approval_bound_to_candidate_and_review_context(self):
        skill = self.root / self.skills[0]["path"]
        context = self.root / "context.json"
        context.write_text('{"verification":[]}', encoding="utf-8")
        approval = self.root / "approval.json"
        confirmed = fingerprint(inventory(skill), digest(context))
        receipt = {"status": "approved", "skill": skill.name,
                   "fingerprint": confirmed, "evidence": "test fixture confirmation"}
        approval.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertEqual(verify_approval(skill, context, approval), confirmed)
        context.write_text('{"verification":["new evidence"]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "重新确认"):
            verify_approval(skill, context, approval)
        context.write_text('{"verification":[]}', encoding="utf-8")
        (skill / "SKILL.md").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "重新确认"):
            verify_approval(skill, context, approval)

    def test_approval_rejects_changed_shared_file(self):
        skill = self.root / self.skills[0]["path"]
        shared = self.root / "installer.py"
        shared.write_text("published", encoding="utf-8")
        context = self.root / "context.json"
        context.write_text(json.dumps({"shared_diff": "+published",
                                       "shared_files": {"installer.py": digest(shared)}}), encoding="utf-8")
        approval = self.root / "approval.json"
        confirmed = fingerprint(inventory(skill), digest(context))
        approval.write_text(json.dumps({"status": "approved", "skill": skill.name,
                                        "fingerprint": confirmed, "evidence": "test fixture"}), encoding="utf-8")
        self.assertEqual(verify_approval(skill, context, approval, self.root), confirmed)
        shared.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "共享文件已变"):
            verify_approval(skill, context, approval, self.root)


if __name__ == "__main__":
    unittest.main()
