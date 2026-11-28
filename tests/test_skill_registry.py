"""Registry validation and classified source paths without PyYAML."""

from pathlib import Path
from runpy import run_path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
parse_registry = run_path(str(ROOT / "scripts/harness/validate_registry.py"))["parse_registry"]


class RegistryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="feipi registry ")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.mode = "skills/engineering/feipi-engineering-junction-mode"
        self.writing = "skills/content/writing/feipi-writing-refine-copy"
        for path in (self.mode, self.writing):
            self.create(path)
        self.write(self.mode, self.writing)

    def create(self, relative):
        directory = self.root / relative
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {directory.name}\ndescription: 示例\n---\n", encoding="utf-8"
        )

    def write(self, *paths):
        (self.root / "skills/registry.yaml").write_text(
            "skills:\n" + "".join(f"  - {path}\n" for path in paths), encoding="utf-8"
        )

    def test_modes_and_two_directory_depths(self):
        mode, writing = parse_registry(self.root)
        self.assertEqual((mode["domain"], mode["subdomain"]), ("engineering", None))
        self.assertEqual((writing["domain"], writing["subdomain"]), ("content", "writing"))
        self.assertEqual(mode["name"], Path(self.mode).name)
        self.assertEqual(writing["description"], "示例")

    def test_index_reads_required_fields_without_consuming_extension_values(self):
        path = self.root / self.mode / "SKILL.md"
        extensions = "disable-model-invocation: true\nicon: crown\ncolor: yellow\nmetadata:\n  name: ignored\n"
        text = path.read_text().replace("\n---\n", "\n" + extensions + "---\n", 1)
        path.write_text(text)
        mode = parse_registry(self.root)[0]
        self.assertEqual(mode["name"], Path(self.mode).name)
        self.assertEqual(mode["description"], "示例")
        self.assertNotIn("metadata", mode)
        self.assertEqual(path.read_text(), text)
        path.write_text(text.replace("icon: crown", "name: duplicate"))
        with self.assertRaisesRegex(ValueError, "字段重复"):
            parse_registry(self.root)

    def test_duplicate_id_and_path_are_separate_errors(self):
        self.write(self.mode, self.mode)
        with self.assertRaisesRegex(ValueError, "重复路径"):
            parse_registry(self.root)
        extra = "skills/another/" + Path(self.mode).name
        self.create(extra)
        self.write(self.mode, self.writing, extra)
        with self.assertRaisesRegex(ValueError, "Skill ID 重复"):
            parse_registry(self.root)

    def test_registry_and_disk_must_agree(self):
        self.write(self.mode)
        with self.assertRaisesRegex(ValueError, "未注册"):
            parse_registry(self.root)
        self.write(self.mode, self.writing, "skills/media/feipi-media-read-fixture")
        with self.assertRaisesRegex(ValueError, "不存在"):
            parse_registry(self.root)

    def test_only_safe_classified_paths(self):
        for bad in ("../escape", "/tmp/bad", "skills/content/writing/verification/feipi-content-review-copy",
                    "skills/content/verification/feipi-content-review-copy"):
            with self.subTest(bad=bad):
                self.write(self.mode, self.writing, bad)
                with self.assertRaisesRegex(ValueError, "路径须为|须为领域"):
                    parse_registry(self.root)

    def test_symlink_escaping_entry_is_rejected(self):
        file = self.root / self.mode / "SKILL.md"
        outside_skills = self.root / "other.md"
        file.rename(outside_skills)
        file.symlink_to(outside_skills)
        with self.assertRaisesRegex(ValueError, "越界"):
            parse_registry(self.root)


if __name__ == "__main__":
    unittest.main()
