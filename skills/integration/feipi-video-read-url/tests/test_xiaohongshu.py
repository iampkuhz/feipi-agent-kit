#!/usr/bin/env python3
"""短链边界、分享参数、真实统一入口与内容来源隔离回归。"""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.request import Request


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
spec = importlib.util.spec_from_file_location("xhs_url", SCRIPTS / "lib/xiaohongshu_url.py")
xhs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xhs)
NOTE_ID = "6adc39ca000000002a0381a5"
NOTE = "https://www.xiaohongshu.com/explore/" + NOTE_ID
SHARE = "https://xhslink.cn/o/4fVBDGJn6Rk"


class UrlTests(unittest.TestCase):
    def test_direct_url_keeps_share_query_without_network(self):
        for prefix in ("explore", "discovery/item"):
            url = f"http://www.xiaohongshu.com/{prefix}/{NOTE_ID}?xsec_token=a%2Bb%3D&xsec_source=app_share"
            self.assertEqual(xhs.resolve(url), NOTE + "?xsec_token=a%2Bb%3D&xsec_source=app_share")

    def test_redirect_stops_before_note_and_upgrades_https(self):
        redirect = xhs.ShareRedirects()
        with self.assertRaises(xhs.NoteFound) as found:
            redirect.redirect_request(Request(SHARE), None, 302, "", {},
                                      f"http://www.xiaohongshu.com/discovery/item/{NOTE_ID}?xsec_token=secret")
        self.assertEqual(found.exception.url, NOTE + "?xsec_token=secret")

    def test_other_hosts_credentials_ports_and_profiles_rejected(self):
        for url in ("https://xiaohongshu.com.evil.example/explore/" + NOTE_ID,
                    "https://evil.example/a", "file:///etc/passwd",
                    "https://user:pass@www.xiaohongshu.com/explore/" + NOTE_ID,
                    "https://www.xiaohongshu.com:444/explore/" + NOTE_ID,
                    "https://www.xiaohongshu.com/user/profile/example"):
            with self.subTest(url=url), self.assertRaises(xhs.SourceError):
                xhs.resolve(url)

    def test_redirect_to_login_has_explicit_diagnostic(self):
        with self.assertRaisesRegex(xhs.SourceError, "xiaohongshu_login_required"):
            xhs.ShareRedirects().redirect_request(Request(SHARE), None, 302, "", {},
                                                  "https://www.xiaohongshu.com/login?redirectPath=secret")

    def test_redirect_cannot_leave_site(self):
        with self.assertRaises(xhs.SourceError):
            xhs.ShareRedirects().redirect_request(Request(SHARE), None, 302, "", {},
                                                  "https://evil.example/private")

    def test_shortlink_resolution_and_missing_redirect(self):
        class Opener:
            def open(self, request, timeout):
                raise xhs.NoteFound(NOTE + "?xsec_token=preserved")
        self.assertEqual(xhs.resolve(SHARE, Opener()), NOTE + "?xsec_token=preserved")
        class Empty:
            def open(self, request, timeout):
                return tempfile.TemporaryFile()
        with self.assertRaisesRegex(xhs.SourceError, "xiaohongshu_share_unresolved"):
            xhs.resolve(SHARE, Empty())


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.scripts = self.root / "scripts"
        shutil.copytree(SCRIPTS, self.scripts, ignore=shutil.ignore_patterns("__pycache__"))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("python3", "rg", "ffmpeg"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.program("brew", "#!/bin/bash\nexit 1\n")
        self.program("yt-dlp", f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
a=sys.argv[1:]
if '--version' in a:
 print('2099.01.01'); sys.exit(0)
with open(os.environ['XHS_TEST_ARGS'], 'a') as f: f.write(json.dumps(a)+'\\n')
if os.environ.get('XHS_TEST_FAIL'):
 print('ERROR: Login required https://example.com/?xsec_token=secret', file=sys.stderr); sys.exit(3)
if '--print-to-file' in a:
 Path(a[a.index('--print-to-file')+2]).write_text(json.dumps({{"id":"{NOTE_ID}","title":"装修与家务"}})+'\\n')
if '--write-subs' in a and not os.environ.get('XHS_TEST_NO_SUBS'):
 out=Path(a[a.index('--output')+1]).parent
 (out/'fixture.zh.srt').write_text('1\\n00:00:00,000 --> 00:00:02,000\\n减少清洁死角。\\n\\n2\\n00:00:03,000 --> 00:00:05,000\\n物品就近收纳。\\n')
print('装修与家务')
''')
        # 网络边界独立测试；统一入口使用固定解析结果，不触碰线上服务。
        (self.scripts / "lib/xiaohongshu_url.py").write_text(f"print({NOTE!r})\n")
        self.args = self.root / "calls.jsonl"
        self.env = dict(os.environ, PATH=str(self.bin) + ":/usr/bin:/bin",
                        XHS_TEST_ARGS=str(self.args), AGENT_CHROME_PROFILE="")
        self.out = self.root / "output"

    def program(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def run_entry(self, script, *args):
        return subprocess.run(["bash", str(self.scripts / script), *map(str, args)],
                              env=self.env, text=True, capture_output=True, timeout=30)

    def test_download_shortlink_identity_and_no_browser_credentials(self):
        self.env["AGENT_CHROME_PROFILE"] = "chrome:personal"
        result = self.run_entry("download_video.sh", SHARE, self.out, "dryrun")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.out / "video_identity.json").read_text())
        self.assertEqual((data["platform"], data["video_id"], data["input_url"]),
                         ("小红书", NOTE_ID, SHARE))
        calls = [json.loads(line) for line in self.args.read_text().splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-1], NOTE)
        self.assertNotIn("--cookies-from-browser", calls[0])
        self.assertFalse(list(self.out.glob("*.mp4")))

    def test_auto_returns_timestamped_subtitles_from_real_converter(self):
        result = self.run_entry("extract_video_text.sh", NOTE, self.out, "auto", "--instruction", "总结视频")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("source=xiaohongshu", result.stdout)
        self.assertIn("mode=subtitle", result.stdout)
        text = next(self.out.glob("xiaohongshu-*/*.txt")).read_text()
        self.assertIn("[00:00:03] 物品就近收纳。", text)
        transcript = next(self.out.glob("xiaohongshu-*/*.txt"))
        prompt = self.run_entry("render_summary_prompt.sh", NOTE, "装修与家务", "5", transcript)
        self.assertEqual(prompt.returncode, 0, prompt.stderr)
        prompt_path = transcript.parent / "summary_request.md"
        prompt_path.write_text(prompt.stdout)
        lint = self.run_entry("lint_prompt_contract.sh", prompt_path)
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_auto_falls_back_to_builtin_whisper_contract(self):
        self.env["XHS_TEST_NO_SUBS"] = "1"
        # 转写引擎另有回归；此处隔离识别耗时，验证真实两阶段入口与文本交接。
        with (self.scripts / "lib/yt_dlp_common.sh").open("a") as target:
            target.write('''
yt_common_run_whisper_mode_from_url() {
  printf '%s\\n' '- [00:00:00] 实际转写替身。' > "$2/fixture-transcript.txt"
  printf 'text_file=%s/fixture-transcript.txt\\n' "$2"
}
''')
        result = self.run_entry("extract_video_text.sh", SHARE, self.out, "auto", "--instruction", "总结视频")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=whisper", result.stdout)
        self.assertIn("mode_calls=2", result.stdout)
        self.assertIn("whisper_profile=fast", result.stdout)

    def test_missing_subtitles_is_failure_and_not_note_description(self):
        self.env["XHS_TEST_NO_SUBS"] = "1"
        result = self.run_entry("download_video.sh", NOTE, self.out, "subtitle")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("xiaohongshu_subtitles_not_exposed", result.stderr)
        self.assertFalse(list(self.out.glob("*.txt")))

    def test_extraction_failure_produces_no_transcript_or_summary(self):
        self.env["XHS_TEST_FAIL"] = "1"
        result = self.run_entry("extract_video_text.sh", SHARE, self.out, "subtitle")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("text_path=", result.stdout)
        self.assertFalse(list(self.out.rglob("*.txt")))
        self.assertFalse(list(self.out.rglob("summary_result.md")))
        logs = "".join(p.read_text() for p in self.out.rglob("*.log"))
        self.assertIn("Login required", logs)
        self.assertNotIn("xsec_token=secret", logs)


if __name__ == "__main__":
    unittest.main()
