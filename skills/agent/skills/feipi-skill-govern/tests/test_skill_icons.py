"""图标候选、名称刷新、应用和统一画法的回归。"""

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from discover_cursor_icons import NAME_MARKERS, discover
from render_skill_icon import draw
from skill_icon_catalog import bind, cursor_names, find_candidates, load_codex_catalog, search_cursor


class SkillIconTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        repo = Path(scratch.name).resolve()
        self.skill = repo / "skills/content/feipi-example-review-rules"
        self.library = repo / "assets/skill-icons"
        self.library.mkdir(parents=True)
        (self.skill / "assets").mkdir(parents=True)
        (self.skill / "agents").mkdir()
        (repo / "workbench").touch()
        (repo / "skills/registry.yaml").touch()
        self.entry = self.skill / "SKILL.md"
        self.entry.write_text('---\nname: feipi-example-review-rules\ndescription: 读取家庭健康档案与健康随访。\n'
                              'disable-model-invocation: false\n"icon": code # keep\ncolor: default\n---\n正文\n',
                              encoding="utf-8")
        self.metadata = self.skill / "agents/openai.yaml"
        self.metadata.write_text('interface:\n  icon_small: "./assets/code.png"\n'
                                 '  icon_large: "./assets/code.png"\npolicy:\n  allow_implicit_invocation: true\n'
                                 'metadata:\n  icon_small: "./assets/other.png"\n',
                                 encoding="utf-8")
        self.icon = self.skill / "assets/code.png"
        self.icon.symlink_to(os.path.relpath(self.library / "code.png", self.icon.parent))
        for name in ("code", "health-card"):
            shutil.copy2(SCRIPTS.parent / "templates/code.png", self.library / f"{name}.png")
        self.catalog = self.library / "catalog.json"
        self.catalog.write_text(json.dumps({
            "code": dict(name="代码", description="初始化占位图。", aliases=["scaffold"]),
            "health-card": dict(name="家用档案", description="心形与随访图。", aliases=["健康随访", "health records"]),
        }, ensure_ascii=False), encoding="utf-8")

    def test_agent_can_find_and_bind_from_bilingual_purpose(self):
        candidates = find_candidates(self.skill, ["家庭健康", "health records"])
        self.assertEqual(candidates["cursor"][0]["id"], "cross-medical")
        self.assertEqual(candidates["codex"][0]["file"], str(self.library / "health-card.png"))
        self.assertIn("health records", candidates["codex"][0]["matched"])
        old_metadata = self.metadata.read_bytes()
        bind(self.skill, "cross-medical", "health-card", "green")
        self.assertFalse(self.icon.is_symlink())
        self.assertEqual((self.icon.parent / "health-card.png").resolve(), self.library / "health-card.png")
        self.assertIn('"icon": cross-medical # keep\ncolor: green\n---\n正文\n', self.entry.read_text())
        self.assertEqual(self.metadata.read_bytes(), old_metadata.replace(b"./assets/code.png", b"./assets/health-card.png"))

    def test_codex_pngs_and_semantic_records_stay_in_sync(self):
        (self.library / "health-card.png").unlink()
        with self.assertRaisesRegex(ValueError, "缺图"):
            load_codex_catalog(self.library)
        shutil.copy2(self.library / "code.png", self.library / "health-card.png")
        self.catalog.write_text(self.catalog.read_text().replace('["健康随访", "health records"]', '[]'))
        with self.assertRaisesRegex(ValueError, "同义词"):
            load_codex_catalog(self.library)

    def test_discovery_tracks_actual_badge_consumers_in_both_layouts(self):
        names = sorted(NAME_MARKERS | {f"fixture-{index}" for index in range(35)} | {"latency-watch"})
        packed = " ".join("0" + name for name in names)
        glyphs = f'"cursor-icons.ts";data="{packed}",list=decode(data);'
        legacy = glyphs + 'badge=list;function accepts(e){return badge.includes(e)}'
        self.assertEqual(discover(legacy.encode()), names)
        host = ('import{CURSOR_ICON_NAMES$x as glyphs}from"./workbench.anysphere-ui.js";'
                'badges=new Set(glyphs);function accepts(e){return badges.has(e)}').encode()
        exported = (glyphs + 'export{list as CURSOR_ICON_NAMES$x}').encode()
        self.assertEqual(discover(host, exported), names)
        additions = set(names) - set(cursor_names())
        self.assertEqual(search_cursor(sorted(additions), ["latency watch"])[0]["id"], "latency-watch")
        with self.assertRaisesRegex(ValueError, "无法确认"):
            discover(host.replace(b"badges.has(e)", b"true"), exported)

    def test_style_uses_the_common_canvas_and_white_primary_stroke(self):
        svg = ET.fromstring(draw("M7 8h18v16H7Z", "M9 16h14", "blue"))
        self.assertEqual(svg.get("viewBox"), "0 0 32 32")
        self.assertEqual(svg[0].get("rx"), "8")
        self.assertEqual(svg[1].get("stroke-width"), "2.15")
        self.assertEqual(svg[1][0].get("stroke"), "#fff")
        self.assertEqual(len(svg[1]), 2)


if __name__ == "__main__":
    unittest.main()
