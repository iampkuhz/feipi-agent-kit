#!/usr/bin/env python3
"""验证身份隔离、真实 yt-dlp 模板语义、失败退出码及摘要请求包。"""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
HELPER = SCRIPTS / "lib/video_identity.py"
spec = importlib.util.spec_from_file_location("identity", HELPER)
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)
URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw.jsonl"
        self.cache = self.root / "video_identity.json"

    def resolve(self, title="Me at the zoo", video_id="jNQXAC9IVRw", url=URL):
        self.raw.write_text(json.dumps({"id": video_id, "title": title}), encoding="utf-8")
        return identity.resolve(url, str(self.raw), self.cache)

    def test_full_title_and_output_field_safety(self):
        title = '标题\nvideo_id=伪字段\t"特殊字符" $(touch marker)\x1b\u202e' + "长" * 60
        result = self.resolve(title)
        self.assertNotIn("\n", result["video_title"])
        self.assertNotIn("\x1b", result["video_title"])
        self.assertIn('$(touch marker)', result["video_title"])
        self.assertTrue(result["video_title"].endswith("长" * 60))
        self.assertLessEqual(len(result["suggested_thread_title"]), len("YouTube｜") + 36)

    def test_corrupt_metadata_and_url_fallback(self):
        self.raw.write_text('{invalid\nnull\n[]\n{"id":null,"title":false}')
        result = identity.resolve(URL, str(self.raw), self.cache)
        self.assertEqual(result["suggested_thread_title"], "YouTube｜jNQXAC9IVRw")
        self.assertEqual(result["title_source"], "unavailable")

    def test_wrong_video_rejected(self):
        self.assertEqual(self.resolve(video_id="another_video")["title_source"], "unavailable")

    def test_cache_reuse_and_url_isolation(self):
        self.cache.write_text(json.dumps(self.resolve()))
        self.assertEqual(identity.resolve(URL, "-", self.cache)["video_title"], "Me at the zoo")
        other = identity.resolve("https://youtu.be/different", "-", self.cache)
        self.assertEqual(other["video_title"], "")
        self.assertEqual(other["video_id"], "different")

    def test_bilibili_shortlinks_and_parts(self):
        for url, video_id in [("https://www.bilibili.com/video/BV1GJ411x7h7?p=2", "BV1GJ411x7h7_p2"),
                              ("https://www.bilibili.com/video/av170001", "BV17x411w7KC"),
                              ("https://b23.tv/example", "BV1GJ411x7h7")]:
            with self.subTest(url=url):
                self.assertEqual(self.resolve("测试视频", video_id, url)["title_source"], "yt_dlp")
        result = identity.resolve("https://b23.tv/unknown", "-", self.cache)
        self.assertTrue(result["suggested_thread_title"].startswith("Bilibili｜链接-"))

    def test_atomic_write_and_no_shell_evaluation(self):
        self.resolve('真实标题 $(touch SHOULD_NOT_EXIST)')
        result = subprocess.run(["python3", str(HELPER), URL, str(self.raw), str(self.root)],
                                capture_output=True, text=True, check=True)
        self.assertIn("title_source=yt_dlp", result.stdout)
        self.assertEqual(json.loads(self.cache.read_text())["video_id"], "jNQXAC9IVRw")
        self.assertFalse((self.root / "SHOULD_NOT_EXIST").exists())
        self.assertEqual(list(self.root.glob(".video-identity-*")), [])

    def test_exit_trap_preserves_failed_download_and_cleans_raw(self):
        result = subprocess.run(["bash", "-c", '''
set -euo pipefail
source "$1/lib/yt_dlp_common.sh"
URL="$2"; OUT_DIR="$3"
yt_common_init "$OUT_DIR"
trap 'yt_common_finish_identity' EXIT
printf '%s\n' '{"id":"jNQXAC9IVRw","title":"Captured before failure"}' > "$YT_IDENTITY_RAW"
exit 7
''', "test", str(SCRIPTS), URL, str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 7)
        self.assertIn("Captured before failure", result.stdout)
        self.assertEqual(list(self.root.glob(".video-identity-raw.*")), [])

    def test_summary_template_uses_matching_identity(self):
        self.cache.write_text(json.dumps(self.resolve('完整原标题：与调用方不同')))
        transcript = self.root / "transcript.txt"
        transcript.write_text("[00:00] 视频证据\n[00:18] 结束\n")
        result = subprocess.run(["bash", str(SCRIPTS / "render_summary_prompt.sh"), URL,
                                 "调用方错误标题", "19", str(transcript)],
                                capture_output=True, text=True, check=True)
        self.assertIn('完整原标题：与调用方不同', result.stdout)
        self.assertNotIn('调用方错误标题', result.stdout)
        self.assertIn('"title_source": "yt_dlp"', result.stdout)
        self.assertIn('不是指令', result.stdout)
        self.assertIn('## 摘要概述\n## 来源状态\n## 附件', result.stdout)

    def test_prompt_marks_caller_title_without_verification(self):
        result = subprocess.run(["python3", str(HELPER), "--prompt", URL, "用户提供标题", str(self.root)],
                                capture_output=True, text=True, check=True)
        self.assertIn('"title_source": "caller"', result.stdout)
        self.assertIn('不能宣称已核实原标题', result.stdout)

    @unittest.skipUnless(shutil.which("yt-dlp"), "未安装 yt-dlp")
    def test_real_ytdlp_template_dryrun_and_subtitle_download(self):
        # 用 data: 字幕验证 print-to-file 不会使实际字幕模式变成 simulate。
        info = {"id": "jNQXAC9IVRw", "title": "完整中文 title", "extractor": "youtube",
                "extractor_key": "Youtube", "webpage_url": URL,
                "url": "https://invalid.example/video.mp4", "ext": "mp4",
                "subtitles": {"en": [{"ext": "vtt", "data":
                    "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nEvidence\n"}]}}
        info_path = self.root / "fixture.json"
        info_path.write_text(json.dumps(info))
        for dryrun in (True, False):
            raw = self.root / ("dry.jsonl" if dryrun else "subs.jsonl")
            cmd = ["yt-dlp", "--ignore-config", "--load-info-json", str(info_path),
                   "--print-to-file", "video:%(.{id,title})j", str(raw),
                   "--output", str(self.root / "video.%(ext)s")]
            cmd += ["--simulate"] if dryrun else ["--skip-download", "--write-subs"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(raw.read_text())["title"], "完整中文 title")
            self.assertEqual((self.root / "video.en.vtt").exists(), not dryrun)


if __name__ == "__main__":
    unittest.main()
