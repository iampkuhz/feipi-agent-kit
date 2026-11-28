"""校验宿主调用策略、徽章和图标。"""

import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from validate_host_metadata import validate_host_metadata


def register_default(library):
    record = {"code": {"name": "代码", "description": "通用代码图稿。", "aliases": ["脚手架", "code"]}}
    (library / "catalog.json").write_text(json.dumps(record), encoding="utf-8")


class HostMetadataTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        templates = Path(__file__).resolve().parents[1] / "templates"
        self.skill = Path(tmp.name) / "feipi-example-review-rules"
        (self.skill / "assets").mkdir(parents=True)
        (self.skill / "agents").mkdir()
        shutil.copy2(templates / "code.png", self.skill / "assets")
        self.entry = self.skill / "SKILL.md"
        self.config = self.skill / "agents/openai.yaml"
        self.entry_text = """---
name: feipi-example-review-rules
description: 检查仓库规则。
disable-model-invocation: false
icon: shield
color: purple
---
"""
        self.config_text = """interface:
  icon_small: "./assets/code.png"
  icon_large: "./assets/code.png"
policy:
  allow_implicit_invocation: true
"""

    def validate(self, entry=None, config=None):
        self.entry.write_text(self.entry_text if entry is None else entry, encoding="utf-8")
        self.config.write_text(self.config_text if config is None else config, encoding="utf-8")
        validate_host_metadata(self.skill)

    def test_both_invocation_policies_and_quoted_color(self):
        self.validate()
        self.validate(
            self.entry_text.replace("disable-model-invocation: false", '"disable-model-invocation": true # 手动'),
            self.config_text.replace("allow_implicit_invocation: true", "allow_implicit_invocation: false")
            .replace("interface:", 'interface: # 展示\n  brand_color: "#3B82F6" # 主题色'),
        )

    def test_invalid_shared_fields(self):
        for field, current, replacement in (
            ("disable-model-invocation", "false", ""),
            ("disable-model-invocation", "false", '"false"'),
            ("disable-model-invocation", "false", "yes"),
            ("disable-model-invocation", "false", "false\n  continued"),
            ("disable-model-invocation", "false", "false\ndisable-model-invocation: true"),
            ("color", "purple", ""),
            ("color", "purple", "ultraviolet"),
            ("icon", "shield", "unknown-icon"),
        ):
            with self.subTest(field=field, replacement=replacement):
                line = f"{field}: {current}\n"
                invalid = self.entry_text.replace(line, f"{field}: {replacement}\n" if replacement else "")
                with self.assertRaisesRegex(ValueError, field):
                    self.validate(entry=invalid)

    def test_invalid_codex_metadata(self):
        for current, replacement, error in (
            ("policy:\n  allow_implicit_invocation: true", "", "policy"),
            ("allow_implicit_invocation: true", 'allow_implicit_invocation: "true"', "YAML 布尔值"),
            ("allow_implicit_invocation: true", "allow_implicit_invocation: false", "互为相反"),
            ("allow_implicit_invocation: true", "allow_implicit_invocation: true\n  allow_implicit_invocation: false",
             "必须有且只有一个"),
            ("interface:", 'interface:\n  brand_color: "purple"', "brand_color"),
            ('icon_small: "./assets/code.png"', 'icon_small: "./assets/small.png"', "须引用同一个"),
        ):
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(ValueError, error):
                    self.validate(config=self.config_text.replace(current, replacement))

    def test_cli_requires_icons_in_each_hosts_configuration(self):
        command = [sys.executable, str(SCRIPTS / "validate_resources.py"), str(self.skill)]
        self.validate()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        cases = (
            (self.entry, "icon:", "", "SKILL.md", "icon"),
            (self.entry, "icon:", "icon:shield", "SKILL.md", "icon"),
            (self.config, "  icon_small:", "", "agents/openai.yaml", "icon_small"),
            (self.config, "  icon_large:", "", "agents/openai.yaml", "icon_large"),
            (self.config, "  icon_large:", "  icon_large:./assets/code.png",
             "agents/openai.yaml", "icon_large"),
        )
        for path, prefix, replacement, source, field in cases:
            with self.subTest(field=field, replacement=replacement):
                self.validate()
                lines = path.read_text(encoding="utf-8").splitlines()
                edited = [replacement if line.startswith(prefix) else line for line in lines]
                path.write_text("\n".join(edited) + "\n", encoding="utf-8")
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(source, result.stderr)
                self.assertIn(field, result.stderr)

    def test_mode_requires_manual_invocation(self):
        mode = self.skill.with_name("feipi-engineering-collaborate-mode")
        self.validate()
        self.skill.rename(mode)
        with self.assertRaisesRegex(ValueError, "工作模式须声明"):
            validate_host_metadata(mode)

    def test_source_requires_portable_catalog_binding(self):
        self.validate()
        repo = self.skill.parent / "repo"
        skill = repo / "skills/content" / self.skill.name
        skill.parent.mkdir(parents=True)
        (repo / "workbench").touch()
        (repo / "skills/registry.yaml").touch()
        self.skill.rename(skill)
        with self.assertRaisesRegex(ValueError, "相对链接"):
            validate_host_metadata(skill)

        icon = skill / "assets/code.png"
        catalog_icon = repo / "assets/skill-icons/code.png"
        catalog_icon.parent.mkdir(parents=True)
        shutil.copy2(icon, catalog_icon)
        register_default(catalog_icon.parent)
        icon.unlink()
        icon.symlink_to(catalog_icon)
        with self.assertRaisesRegex(ValueError, "相对链接"):
            validate_host_metadata(skill)
        icon.unlink()
        icon.symlink_to(os.path.relpath(catalog_icon, icon.parent))
        validate_host_metadata(skill)
        other = catalog_icon.parent / "other.png"
        shutil.copy2(catalog_icon, other)
        icon.unlink()
        icon.symlink_to(os.path.relpath(other, icon.parent))
        with self.assertRaisesRegex(ValueError, "文件名须与图库母版同名"):
            validate_host_metadata(skill)
        icon.unlink()
        icon.symlink_to(os.path.relpath(catalog_icon, icon.parent))
        catalog_icon.unlink()
        with self.assertRaisesRegex(ValueError, "资源缺失"):
            validate_host_metadata(skill)

    def test_initializer_binds_new_repository_skill_to_default_catalog_icon(self):
        repo = self.skill.parent / "repo"
        library = repo / "assets/skill-icons"
        library.mkdir(parents=True)
        (repo / "skills").mkdir()
        (repo / "skills/registry.yaml").touch()
        (repo / "workbench").touch()
        shutil.copy2(self.skill / "assets/code.png", library / "code.png")
        register_default(library)
        command = ["bash", str(SCRIPTS / "init_skill.sh"), "report-generate-brief", "--domain", "content",
                   "--target", str(repo / "skills")]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        created = repo / "skills/content/feipi-report-generate-brief"
        icon = created / "assets/code.png"
        self.assertTrue(icon.is_symlink())
        self.assertEqual(icon.resolve(), (library / "code.png").resolve())
        validate_host_metadata(created)

    def test_manual_skill_retains_user_invocation_in_claude(self):
        entry = self.entry_text.replace("disable-model-invocation: false",
                                        "disable-model-invocation: true\nuser-invocable: false")
        config = self.config_text.replace("allow_implicit_invocation: true", "allow_implicit_invocation: false")
        with self.assertRaisesRegex(ValueError, "user-invocable: true"):
            self.validate(entry, config)


if __name__ == "__main__":
    unittest.main()
