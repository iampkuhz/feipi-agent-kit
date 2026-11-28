"""校验源码维护资料与运行资源的边界。"""

from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_resources import validate_resources


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.skill = Path(self.tmp.name) / "feipi-example-review-rules"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text("执行业务。\n", encoding="utf-8")

    def test_legacy_layout_allowed_until_governed(self):
        validate_resources(self.skill)
        with self.assertRaisesRegex(ValueError, "缺少非空源码维护资料"):
            validate_resources(self.skill, require_maintenance=True)

    def test_maintenance_pair_required_and_source_contents_ignored(self):
        maintenance = self.skill / "maintenance"
        maintenance.mkdir()
        (maintenance / "README.md").write_text("读取 maintenance/terminology.md\n")
        with self.assertRaisesRegex(ValueError, "terminology.md"):
            validate_resources(self.skill)
        (maintenance / "terminology.md").write_text("术语与对象。\n")
        validate_resources(self.skill, require_maintenance=True)
        (maintenance / "terminology.md").write_text(" \n")
        with self.assertRaisesRegex(ValueError, "缺少非空源码维护资料"):
            validate_resources(self.skill)

    def test_runtime_resources_cannot_depend_on_maintenance(self):
        for relative, text in (
            ("SKILL.md", "读取 maintenance/README.md"),
            ("references/rules.md", "读取 ../maintenance/terminology.md"),
            ("scripts/run.py", 'open("../maintenance/config.json")'),
            ("templates/output.md", "[设计](../maintenance/design.md)"),
            ("runtime.json", '{"source":"./maintenance/data.json"}'),
            ("scripts/run.js", 'const file = "maintenance\\\\data.json";'),
        ):
            with self.subTest(relative=relative):
                path = self.skill / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                with self.assertRaisesRegex(ValueError, "运行内容引用源码维护目录"):
                    validate_resources(self.skill)
                path.unlink()

    def test_nested_source_documents_are_not_runtime_dependencies(self):
        path = self.skill / "references/examples/maintenance/design.md"
        path.parent.mkdir(parents=True)
        path.write_text("维护时读取 maintenance/README.md\n")
        validate_resources(self.skill)

    def test_runtime_link_cannot_alias_maintenance(self):
        maintenance = self.skill / "maintenance"
        maintenance.mkdir()
        (maintenance / "README.md").write_text("维护说明")
        (maintenance / "terminology.md").write_text("术语")
        (self.skill / "source-notes").symlink_to(maintenance)
        with self.assertRaisesRegex(ValueError, "运行内容引用源码维护目录"):
            validate_resources(self.skill)

    def test_governor_reads_target_source_not_its_own_maintenance(self):
        governor = self.skill.with_name("feipi-skill-govern")
        self.skill.rename(governor)
        entry = governor / "SKILL.md"
        entry.write_text("先读 `<target_skill>/maintenance/README.md` 和 `<target_skill>/maintenance/terminology.md`。\n")
        validate_resources(governor)
        for text in ("[维护](maintenance/README.md)", '读取 "$SKILL_DIR/maintenance/terminology.md"'):
            entry.write_text(text)
            with self.assertRaisesRegex(ValueError, "运行内容引用源码维护目录"):
                validate_resources(governor)


if __name__ == "__main__":
    unittest.main()
