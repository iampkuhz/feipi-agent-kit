#!/usr/bin/env python3
"""目标身份、正文缺失、图片失败、浏览器取证与视频复用回归。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("extract_note", SKILL / "scripts/extract_note.py")
note = importlib.util.module_from_spec(spec); spec.loader.exec_module(note)
note.load_video_skill()
import extract_content
from validate_extraction import validate

NOTE_ID = "6adc39ca000000002a0381a5"
URL = "https://www.xiaohongshu.com/explore/" + NOTE_ID
PNG = b"\x89PNG\r\n\x1a\nfixture-original"

def html(data):
    return '<script>window.__INITIAL_STATE__=' + json.dumps({"note": {"noteDetailMap": {NOTE_ID: {"note": data}}}}, ensure_ascii=False) + '</script>'

class NoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.base = {"noteId": NOTE_ID, "type": "normal", "title": "测试笔记", "desc": "独立文案",
                     "user": {"nickname": "测试作者"}, "time": 1792800000000, "imageList": []}

    def run_note(self, data, fetch_image=None):
        def fetch(url, limit, image=False):
            if image and fetch_image: return fetch_image(url)
            return html(data).encode(), URL, "text/html"
        with patch.object(note, "fetch", side_effect=fetch):
            return note.extract(URL, self.root)

    def test_parser_undefined_preserves_strings(self):
        source = html(self.base).replace('"imageList": []', '"imageList": undefined')
        self.assertEqual(note.parse_note(source, NOTE_ID)["desc"], "独立文案")
        self.base["desc"] = "undefined : undefined"
        self.assertEqual(note.parse_note(html(self.base), NOTE_ID)["desc"], "undefined : undefined")

    def test_wrong_identity_and_title_only_rejected(self):
        self.base["noteId"] = "other"
        self.assertIsNone(note.parse_note(html(self.base), NOTE_ID))
        self.assertIsNone(note.parse_note('<title>标题不是内容</title>', NOTE_ID))

    def test_confirmed_empty_body(self):
        self.base["desc"] = ""
        code, m = self.run_note(self.base)
        self.assertEqual(code, 0)
        self.assertEqual(m["channels"]["body"]["status"], "complete")
        self.assertEqual((self.root / "body.txt").read_text(), "")
        validate(self.root)

    def test_missing_body_not_asserted_empty(self):
        self.base.pop("desc")
        code, m = self.run_note(self.base)
        self.assertNotEqual(code, 0)
        self.assertEqual(m["channels"]["body"]["reasons"], ["body_not_exposed"])
        self.assertFalse((self.root / "body.txt").exists())

    def test_partial_images_preserve_original_bytes_and_indices(self):
        self.base["imageList"] = [{"urlDefault": f"https://sns-webpic-qc.xhscdn.com/{i}"} for i in (1,2,3)]
        def fetch_image(url):
            if url.endswith("/2"): raise note.FetchError("network_request_failed")
            return PNG, url, "image/png"
        code, m = self.run_note(self.base, fetch_image)
        self.assertEqual(code, 2)
        images = [a for a in m["artifacts"] if a["kind"] == "image"]
        self.assertEqual([a["anchor"]["index"] for a in images], [1,3])
        self.assertEqual((self.root / images[0]["path"]).read_bytes(), PNG)
        self.assertEqual(m["channels"]["images"]["failures"], [{"index":2,"reason":"network_request_failed"}])
        self.assertEqual(m["channels"]["ocr"]["status"], "pending")
        validate(self.root)

    def test_video_caption_separate_and_delegates(self):
        self.base["type"] = "video"
        with patch.object(extract_content, "collect_video") as collect:
            code, m = self.run_note(self.base)
        collect.assert_called_once()
        self.assertEqual(m["content_type"], "video_note")
        self.assertIn("video_text_unavailable", m["reasons"])
        self.assertEqual([a["kind"] for a in m["artifacts"] if a["kind"] in ("body","asr")], ["body"])

    def test_login_captcha_deleted_app_shell_distinguished(self):
        for page, final, reason in [("", "https://www.xiaohongshu.com/login", "login_required"),
                ("<title>安全验证</title>", URL, "verification_required"),
                ("笔记不存在", URL, "note_unavailable"), ("<title>首页</title>", URL, "note_data_unavailable")]:
            self.assertEqual(note.missing_note_reason(page, final), reason)

    def test_blocked_preserves_source_without_fake_body(self):
        with patch.object(note, "fetch", return_value=(b"<title>app</title>", "https://www.xiaohongshu.com/login", "text/html")):
            code, m = note.extract(URL, self.root)
        self.assertEqual(code, 1)
        self.assertEqual(m["status"], "blocked")
        self.assertEqual(m["reasons"], ["login_required"])
        self.assertFalse((self.root / "body.txt").exists())
        validate(self.root)

    def test_platform_image_boundary_and_invalid_payload(self):
        for url in ("https://example.invalid/private", "https://xhscdn.com.evil.invalid/a", "file:///private", "https://u:p@xhscdn.com/a"):
            with self.assertRaises(ValueError): note.public_url(url, image=True)
        with self.assertRaises(note.FetchError): note.image_extension(b"<html>login</html>")

    def test_rendered_package_keeps_visible_body_provenance(self):
        rendered = {"schema":"feipi-xiaohongshu-rendered-note-v1","source_url":URL,"note":self.base}
        with patch.object(note, "fetch", side_effect=AssertionError("must not fetch login shell")):
            code, m = note.extract(URL, self.root, rendered=rendered)
        self.assertEqual(code, 0)
        self.assertEqual(m["artifacts"][0]["provenance"], "browser_dom")
        self.assertEqual((self.root / "body.txt").read_text(), "独立文案")

    def test_rendered_package_wrong_note_rejected(self):
        rendered = {"schema":"feipi-xiaohongshu-rendered-note-v1","source_url":URL.replace(NOTE_ID,"f"*24),"note":self.base}
        code, m = note.extract(URL, self.root, rendered=rendered)
        self.assertEqual(code, 1)
        self.assertIn("rendered_note_identity_mismatch", m["reasons"])

if __name__ == "__main__":
    unittest.main()
