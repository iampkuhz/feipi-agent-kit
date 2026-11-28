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
        self.health = "skills/health/feipi-health-maintain-records"
        self.writing = "skills/content/writing/feipi-writing-refine-copy"
        for path in (self.health, self.writing):
            self.create(path)
        self.write(self.health, self.writing)

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

    def test_two_directory_depths(self):
        health, writing = parse_registry(self.root)
        self.assertEqual((health["domain"], health["subdomain"]), ("health", None))
        self.assertEqual((writing["domain"], writing["subdomain"]), ("content", "writing"))
        self.assertEqual(health["name"], Path(self.health).name)
        self.assertEqual(writing["description"], "示例")

    def test_duplicate_id_and_path_are_separate_errors(self):
        self.write(self.health, self.health)
        with self.assertRaisesRegex(ValueError, "重复路径"):
            parse_registry(self.root)
        extra = "skills/another/" + Path(self.health).name
        self.create(extra)
        self.write(self.health, self.writing, extra)
        with self.assertRaisesRegex(ValueError, "Skill ID 重复"):
            parse_registry(self.root)

    def test_registry_and_disk_must_agree(self):
        self.write(self.health)
        with self.assertRaisesRegex(ValueError, "未注册"):
            parse_registry(self.root)
        self.write(self.health, self.writing, "skills/media/feipi-media-read-fixture")
        with self.assertRaisesRegex(ValueError, "不存在"):
            parse_registry(self.root)

    def test_only_safe_classified_paths(self):
        for bad in ("../escape", "/tmp/bad", "skills/content/writing/verification/feipi-content-review-copy",
                    "skills/content/verification/feipi-content-review-copy"):
            with self.subTest(bad=bad):
                self.write(self.health, self.writing, bad)
                with self.assertRaisesRegex(ValueError, "路径须为|须为领域"):
                    parse_registry(self.root)

    def test_symlink_escaping_entry_is_rejected(self):
        file = self.root / self.health / "SKILL.md"
        outside_skills = self.root / "other.md"
        file.rename(outside_skills)
        file.symlink_to(outside_skills)
        with self.assertRaisesRegex(ValueError, "越界"):
            parse_registry(self.root)


if __name__ == "__main__":
    unittest.main()
