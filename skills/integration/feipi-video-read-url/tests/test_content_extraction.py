#!/usr/bin/env python3
"""证据隔离、远程 Range 抽帧、宿主读图登记与下载边界回归。"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "lib")]
import content_manifest as cm
import extract_content as content
import extract_frames as frames
import record_observations as observations
from validate_extraction import validate


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_output_rejects_skill_directory_and_reuse(self):
        with self.assertRaisesRegex(ValueError, "inside_skill"):
            cm.prepare_output(SCRIPTS.parent / "generated")
        (self.root / "existing").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "not_empty"):
            cm.prepare_output(self.root)

    def test_pending_visual_is_not_complete_and_records_separately(self):
        m = cm.new_manifest("https://example.invalid", "xiaohongshu", "image_note")
        for k in ("source", "body", "images"):
            cm.channel(m, k, "complete")
        body = self.root / "body.txt"; body.write_text("文案")
        cm.artifact(m, self.root, "body", "body", body, {"type": "note"})
        image = self.root / "one.png"; image.write_bytes(b"image-test")
        cm.artifact(m, self.root, "image-001", "image", image, {"type": "image", "index": 1})
        cm.visual_pending(m)
        self.assertEqual(cm.finish(m, self.root), 2)
        self.assertIn("visual_reading_pending", m["reasons"])
        code, result = observations.record(self.root, [{"source_artifact_id": "image-001", "ocr_text": "示例文字",
                            "observation": "示例测试观察", "uncertainties": ["尺寸模糊"]}])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "complete")
        self.assertEqual([a["kind"] for a in result["artifacts"]], ["body", "image", "ocr", "visual_observation"])
        validate(self.root)
        with self.assertRaises(ValueError):
            observations.record(self.root, [{"source_artifact_id": "not-read"}])

    def test_metadata_and_caption_cannot_count_as_video_transcript(self):
        m = cm.new_manifest("url", "xiaohongshu", "video_note")
        for k in ("source", "body", "frames"):
            cm.channel(m, k, "complete")
        path = self.root / "body.txt"; path.write_text("长文案也不是语音")
        cm.artifact(m, self.root, "body", "body", path, {"type": "note"})
        cm.finish(m, self.root)
        self.assertEqual(m["status"], "partial")
        self.assertIn("video_text_unavailable", m["reasons"])

    def test_manifest_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            cm.safe_path(self.root, "../private.txt")

    def test_public_environment_disables_browser_cookies(self):
        with patch.dict("os.environ", {"AGENT_CHROME_PROFILE": "chrome", "AGENT_YOUTUBE_COOKIE_FILE": "/private"}):
            env = cm.public_env()
        self.assertEqual(env["AGENT_CHROME_PROFILE"], "")
        self.assertEqual(env["AGENT_YOUTUBE_COOKIE_FILE"], "")
        self.assertEqual(env["AGENT_VIDEO_CONTENT_EXTRACTION"], "1")

    def test_audio_only_mode_never_falls_back_to_muxed_video(self):
        code = '\n'.join(['source "$1"',
            'yt_common_run_with_success_log() { printf "%s\\n" "$*"; return 1; }',
            'export AGENT_VIDEO_CONTENT_EXTRACTION=1',
            'yt_common_mode_whisper_audio url || true',
            'yt_common_mode_whisper_audio_with_format_fallback url || true'])
        r = subprocess.run(["bash", "-c", code, "test", str(SCRIPTS / "lib/yt_dlp_common.sh")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("--format 18", r.stdout)
        for line in r.stdout.splitlines():
            self.assertIn("--format bestaudio[abr<=96]/bestaudio --extract-audio", line)

    def test_subtitle_and_asr_provenance_from_entrypoint_output(self):
        text_dir = self.root / "text"; text_dir.mkdir()
        text = text_dir / "voice.txt"; text.write_text("[00:00:01.000 --> 00:00:02.000] 转写证据")
        def run(args, log, timeout):
            return 0, f"mode=whisper\ntext_path={text}\n".encode()
        m = cm.new_manifest("https://www.bilibili.com/video/BVexample", "bilibili", "video")
        with patch.object(content, "resolve_media", return_value={"id": "BVexample", "title": "元数据", "duration": 2}), \
                patch.object(content, "run_logged", side_effect=run), patch.object(content, "extract_frames"):
            content.collect_video(m["original_url"], self.root, m)
        self.assertEqual(m["channels"]["asr"]["status"], "complete")
        self.assertEqual([a["kind"] for a in m["artifacts"]], ["source", "asr"])
        self.assertIn("00:00:01", (self.root / "asr.txt").read_text())


class FrameTests(unittest.TestCase):
    def test_time_plan_and_input_seek(self):
        self.assertEqual(frames.frame_times(60), [0, 10, 20, 30, 40, 50])
        self.assertEqual(frames.frame_times(None), [0])
        for invalid in (["nan"], ["inf"], ["-1"], ["60"]):
            with self.assertRaises(ValueError): frames.frame_times(60, invalid)
        args = frames.ffmpeg_args({"url": "https://example.invalid/video"}, {}, 12, Path("frame.jpg"))
        self.assertLess(args.index("-ss"), args.index("-i"))
        self.assertEqual(args[args.index("-frames:v") + 1], "1")

    def test_reject_non_range_response_without_reading_body(self):
        class Response:
            status = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, n): raise AssertionError("must not read whole video")
        with self.assertRaisesRegex(ValueError, "http_range_not_supported"):
            frames.check_seekable({"url": "https://example.invalid/a.mp4"}, {}, lambda *a, **k: Response())

    def test_candidate_excludes_audio_and_private_protocol(self):
        with self.assertRaises(ValueError):
            frames.media_candidate({"formats": [{"url": "file:///private", "ext": "mp4"}]})
        with self.assertRaises(ValueError):
            frames.media_candidate({"formats": [{"url": "https://example.invalid/audio", "ext": "mp4", "vcodec": "none"}]})

    @unittest.skipUnless(shutil.which("ffmpeg"), "需要 ffmpeg")
    def test_real_ffmpeg_remote_range_outputs_frames_only(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            fixture = base / "fixture.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                            "testsrc2=duration=4:size=320x240:rate=10", "-c:v", "libx264", "-movflags", "+faststart",
                            str(fixture)], check=True)
            data = fixture.read_bytes(); ranges = []
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *a): pass
                def do_GET(self):
                    value = self.headers.get("Range", "")
                    ranges.append(value)
                    match = re.fullmatch(r"bytes=(\d+)-(\d*)", value)
                    start = int(match[1]) if match else 0
                    end = min(int(match[2]) if match and match[2] else len(data)-1, len(data)-1)
                    self.send_response(206 if match else 200)
                    if match: self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                    self.send_header("Content-Length", str(end-start+1)); self.end_headers()
                    self.wfile.write(data[start:end+1])
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                out = base / "out"; out.mkdir()
                url = f"http://127.0.0.1:{server.server_port}/video.mp4"
                m = cm.new_manifest(url, "bilibili", "video")
                info = {"duration": 4, "formats": [{"url": url, "ext": "mp4", "vcodec": "h264", "height": 240}]}
                saved = frames.extract_frames(url, out, m, SCRIPTS, info=info, times=[0, 2])
                self.assertEqual(saved, [0, 2])
                self.assertEqual(m["channels"]["frames"]["status"], "complete")
                self.assertEqual(len(list(out.glob("frames/*.jpg"))), 2)
                self.assertFalse(list(out.rglob("*.mp4")))
                self.assertTrue(ranges and all(r.startswith("bytes=") for r in ranges))
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
