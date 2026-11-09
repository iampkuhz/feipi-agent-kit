#!/usr/bin/env python3
"""固定短音频的程序检查；显式启用后逐字核对真实 oMLX，禁止模拟响应充当识别结果。"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unicodedata
import unittest
import wave

SKILL = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures/local_media"
sys.path.insert(0, str(SKILL / "scripts/lib"))
from split_audio import plan_audio


def characters(text):
    # 只忽略标点和空白；不改字、不替换同音字、不增删正文、不做繁简转换。
    return "".join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith("P"))


def fields(text):
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


class LocalMediaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_entry(self, media, mode="audio", root=None):
        return subprocess.run(["bash", str(SKILL / "scripts/download_video.sh"), str(media),
                               str(root or self.root / "out"), mode], capture_output=True, text=True, timeout=30)

    def make_video(self, root):
        video = root / "本地视频 样例.mp4"
        # 合成静态画面，音轨原样封装；fixture 是事先按参考稿生成的实际语音。
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=s=32x32:r=1",
                        "-i", str(FIXTURE / "speech.m4a"), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                        "-c:a", "copy", "-shortest", str(video)], check=True)
        return video

    def test_fixture_hashes_duration_and_lossless_partition_at_different_limits(self):
        metadata = json.loads((FIXTURE / "metadata.json").read_text())
        for name in ("reference.txt", "speech.m4a"):
            self.assertEqual(hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest(), metadata["sha256"][name])
        result = self.run_entry(FIXTURE / "speech.m4a")
        self.assertEqual(result.returncode, 0, result.stderr)
        audio = Path(fields(result.stdout)["audio_path"])
        with wave.open(str(audio), "rb") as source:
            pcm = source.readframes(source.getnframes())
        for maximum in (10, 20, 30, 45, 60):
            rate, frames, pieces = plan_audio(audio, maximum)
            self.assertGreaterEqual(frames / rate, 40)
            self.assertLess(frames / rate, 50)
            self.assertEqual(pieces[0]["start_frame"], 0)
            self.assertEqual(pieces[-1]["end_frame"], frames)
            self.assertEqual(b"".join(pcm[p["start_frame"] * 2:p["end_frame"] * 2] for p in pieces), pcm)
            self.assertTrue(all(0 < p["end_frame"] - p["start_frame"] <= maximum * rate for p in pieces))
            self.assertTrue(all(a["end_frame"] == b["start_frame"] for a, b in zip(pieces, pieces[1:])))
            if maximum == 30:
                self.assertEqual(len(pieces), 2)
                self.assertEqual(pieces[0]["cut_reason"], "pause")

    def test_local_video_extracts_complete_audio_and_repairs_changed_audio_cache(self):
        video = self.make_video(self.root)
        before = video.read_bytes()
        result = self.run_entry(video)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = fields(result.stdout)
        audio = Path(values["audio_path"])
        self.assertEqual(video.read_bytes(), before)
        expected = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-map", "0:a:0",
                                   "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
        with wave.open(str(audio), "rb") as source:
            self.assertEqual(source.readframes(source.getnframes()), expected)
        old = audio.read_bytes()
        audio.write_bytes(b"bad cache")
        result = self.run_entry(video)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("audio_reused=0", result.stdout)
        self.assertEqual(audio.read_bytes(), old)
        manifest = Path(values["source_manifest"])
        record = json.loads(manifest.read_text())
        record["duration_seconds"] = 99999
        manifest.write_text(json.dumps(record))
        result = self.run_entry(video)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("audio_reused=0", result.stdout)
        self.assertLess(json.loads(manifest.read_text())["duration_seconds"], 50)

    def test_dryrun_does_not_extract_audio_or_request_asr(self):
        result = self.run_entry(FIXTURE / "speech.m4a", "dryrun")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "out").exists())

    def test_no_audio_and_bad_input_fail_without_transcript(self):
        video = self.root / "silent.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=s=16x16:r=1",
                        "-t", "1", "-an", str(video)], check=True)
        for media in (video, self.root / "missing.mp4", self.root):
            result = self.run_entry(media, "whisper")
            self.assertNotEqual(result.returncode, 0)
        self.assertFalse(list(self.root.rglob("*.asr.json")))

    @unittest.skipUnless(os.environ.get("FEIPI_OMLX_LIVE_TEST") == "1", "需显式启用真实本地 oMLX 集成测试")
    def test_real_omlx_recovers_every_reference_character(self):
        configured_output = os.environ.get("FEIPI_OMLX_TEST_OUTPUT")
        root = Path(configured_output) if configured_output else Path(tempfile.mkdtemp(prefix="feipi-video-read-url-live-"))
        root.mkdir(parents=True, exist_ok=True)
        video = self.make_video(root)
        expected = characters((FIXTURE / "reference.txt").read_text())
        results = []
        for quality in ("fast", "accurate"):
            with self.subTest(quality=quality):
                command = ["bash", str(SKILL / "scripts/extract_video_text.sh"), str(video), str(root / quality),
                           "auto", "--quality", quality]
                completed = subprocess.run(command, capture_output=True, text=True, timeout=600)
                (root / f"{quality}-entrypoint.log").write_text(completed.stdout + completed.stderr)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                values = fields(completed.stdout)
                record = json.loads(Path(values["text_path"]).with_suffix(".asr.json").read_text())
                actual = characters("".join(piece["text"] for piece in record["chunks"]))
                item = {"quality": quality, "model": record["model"], "cache_reused": values["cache_reused"],
                        "expected_characters": len(expected), "actual_characters": len(actual),
                        "all_reference_characters_equal": actual == expected, "expected": expected, "actual": actual,
                        "audio_path": values["audio_path"], "text_path": values["text_path"],
                        "asr_elapsed_seconds": values["asr_elapsed_seconds"], "human_listening_performed": False}
                results.append(item)
                (root / "real-asr-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
                self.assertEqual(actual, expected, "实际 ASR 与事先参考稿逐字不符；不允许按参考稿修正文稿")
                self.assertEqual(len(record["chunks"]), 2)
                # 摘要请求包含真实转写、模型、文件来源与块级时间精度。
                prompt = subprocess.run(["bash", str(SKILL / "scripts/render_summary_prompt.sh"), str(video), "",
                                         values["duration_sec"], values["text_path"]], capture_output=True, text=True, check=True)
                (root / f"{quality}-summary_request.md").write_text(prompt.stdout)
                self.assertIn(record["model"], prompt.stdout)
                self.assertIn("local_filename", prompt.stdout)


if __name__ == "__main__":
    unittest.main()
