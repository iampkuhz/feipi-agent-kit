#!/usr/bin/env python3
"""使用真实本机 HTTP 接口验证模型选择、分块完整性、失败原子性与缓存隔离。"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import wave

SKILL = Path(__file__).resolve().parents[1]
CLIENT = SKILL / "scripts/lib/omlx_transcribe.py"
MODEL = "Qwen3-ASR-1.7B-8bit"


class OmlxTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.audio, self.prefix = self.root / "input.wav", self.root / "transcript"
        self.make_audio(31)
        self.models = [MODEL]
        self.posts, self.gets, self.get_headers = [], [], []
        self.responses = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_json(self, value, status=200):
                data = json.dumps(value, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                owner.gets.append(self.path)
                owner.get_headers.append(dict(self.headers))
                self.send_json({"data": [{"id": model} for model in owner.models]})

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                owner.posts.append((self.path, dict(self.headers), body))
                response = owner.responses.pop(0) if owner.responses else {"text": "块{}原文".format(len(owner.posts))}
                if isinstance(response, int):
                    self.send_json({"detail": "private error content"}, response)
                else:
                    self.send_json(response)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.env = dict(os.environ, AGENT_OMLX_BASE_URL="http://127.0.0.1:{}/v1".format(self.server.server_port),
                        HTTP_PROXY="http://127.0.0.1:1", HTTPS_PROXY="http://127.0.0.1:1", NO_PROXY="")
        self.env.pop("AGENT_OMLX_API_KEY", None)
        self.env.pop("OMLX_API_KEY", None)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def make_audio(self, seconds, rate=16000, value=b"\x00\x00"):
        with wave.open(str(self.audio), "wb") as target:
            target.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            target.writeframes(value * (rate * seconds))

    def run_client(self, language="zh", extra=()):
        return subprocess.run([sys.executable, str(CLIENT), str(self.audio), str(self.prefix), language, *extra],
                              env=self.env, capture_output=True, text=True, timeout=15)

    def successful(self, language="zh"):
        result = self.run_client(language)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def record(self):
        return json.loads(self.prefix.with_suffix(".asr.json").read_text())

    def test_fixed_model_complete_chunks_and_multipart(self):
        result = self.successful()
        self.assertIn(f"asr_model={MODEL}", result.stdout)
        self.assertEqual(len(self.posts), 2)
        self.assertFalse(self.gets)
        for expected_frames, (path, headers, body) in zip((480000, 16000), self.posts):
            self.assertEqual(path, "/v1/audio/transcriptions")
            self.assertIn(MODEL.encode(), body)
            self.assertIn(b'name="language"\r\n\r\nzh', body)
            start = body.index(b"RIFF")
            end = body.index(b"\r\n--feipi", start)
            with wave.open(io.BytesIO(body[start:end]), "rb") as audio:
                self.assertEqual(audio.getnframes(), expected_frames)
        self.assertIn("00:00:30,000 --> 00:00:31,000", self.prefix.with_suffix(".srt").read_text())
        self.assertIn("[00:00:30] 块2原文", self.prefix.with_suffix(".txt").read_text())
        self.assertEqual(self.record()["timestamp_source"], "audio_chunk")
        self.assertEqual(self.record()["duration_seconds"], 31)

    def test_auto_language_omits_hint(self):
        self.successful("auto")
        self.assertNotIn(b'name="language"', self.posts[0][2])

    def test_failed_later_chunk_never_publishes_partial_result(self):
        self.responses = [{"text": "first"}, 500]
        result = self.run_client()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP 500", result.stderr)
        self.assertNotIn("private error", result.stderr)
        self.assertFalse(list(self.root.glob("transcript.*")))

    def test_failure_preserves_previous_complete_result(self):
        self.successful()
        previous = {p: p.read_bytes() for p in self.root.glob("transcript.*")}
        self.make_audio(31, value=b"\x01\x00")
        self.responses = [500]
        self.assertNotEqual(self.run_client().returncode, 0)
        self.assertEqual(previous, {p: p.read_bytes() for p in previous})

    def test_empty_transcript_and_invalid_text_rejected(self):
        for response in ({"text": ""}, {"text": None}, {}):
            self.responses = [response, response]
            self.assertNotEqual(self.run_client().returncode, 0)
            self.assertFalse(self.prefix.with_suffix(".asr.json").exists())

    def test_silence_chunk(self):
        self.responses = [{"text": ""}, {"text": "原文"}]
        self.successful()
        self.assertEqual(self.prefix.with_suffix(".txt").read_text(), "- [00:00:30] 原文\n")
        self.assertEqual(len(self.record()["chunks"]), 2)

    def test_matching_cache_does_not_call_service(self):
        self.successful()
        self.models = []
        result = self.successful()
        self.assertIn("cache_reused=1", result.stdout)
        self.assertIn("asr_auth=not_requested_cache", result.stdout)
        self.assertFalse(self.gets)
        self.assertEqual(len(self.posts), 2)

    def test_cache_does_not_cross_audio_or_language(self):
        self.successful()
        self.successful("en")
        self.make_audio(31, value=b"\x01\x00")
        self.successful("en")
        self.assertEqual(len(self.posts), 6)

    def test_cached_partial_text_rebuilt_without_service(self):
        self.successful()
        original = self.prefix.with_suffix(".txt").read_bytes()
        self.prefix.with_suffix(".txt").write_text("partial")
        self.successful()
        self.assertEqual(original, self.prefix.with_suffix(".txt").read_bytes())
        self.assertEqual(len(self.posts), 2)

    def test_corrupt_srt_not_reused(self):
        self.successful()
        self.prefix.with_suffix(".srt").write_text("partial")
        self.successful()
        self.assertEqual(len(self.posts), 4)

    def test_truncated_wav_and_wrong_rate_rejected(self):
        self.audio.write_bytes(self.audio.read_bytes()[:-10])
        self.assertNotEqual(self.run_client().returncode, 0)
        self.assertFalse(self.prefix.with_suffix(".srt").exists())
        self.make_audio(1, rate=8000)
        self.assertNotEqual(self.run_client().returncode, 0)
        self.audio.write_bytes(b"invalid")
        self.assertNotEqual(self.run_client().returncode, 0)

    def test_check_fixed_model_and_api_key(self):
        self.env["OMLX_API_KEY"] = "test-private-key"
        result = subprocess.run([sys.executable, str(CLIENT), "--check"], env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        transcription = self.successful()
        self.assertIn("asr_auth=env:OMLX_API_KEY", result.stdout)
        self.assertIn("asr_auth=env:OMLX_API_KEY", transcription.stdout)
        self.assertTrue(self.get_headers)
        self.assertTrue(all(headers["Authorization"] == "Bearer test-private-key" for headers in self.get_headers))
        self.assertEqual(self.posts[0][1]["Authorization"], "Bearer test-private-key")
        self.assertNotIn("test-private-key", result.stdout + result.stderr + transcription.stdout + transcription.stderr)

    def test_missing_env_key_does_not_load_dotenv_or_shell_profile(self):
        home = self.root / "home"
        home.mkdir()
        for filename in (".env", ".zshrc", ".zprofile", ".zshenv"):
            (home / filename).write_text("export OMLX_API_KEY=file-only-private-key\n")
        self.env["HOME"] = str(home)
        self.env["AGENT_OMLX_API_KEY"] = "legacy-private-key"
        result = self.successful()
        self.assertIn("asr_auth=none", result.stdout)
        self.assertTrue(all("Authorization" not in headers for headers in self.get_headers))
        self.assertTrue(all("Authorization" not in headers for _, headers, _ in self.posts))
        self.assertNotIn("private-key", result.stdout + result.stderr)

    def test_unauthorized_response_names_env_var_without_exposing_key(self):
        self.env["OMLX_API_KEY"] = "invalid-private-key"
        self.responses = [401]
        result = self.run_client()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP 401", result.stderr)
        self.assertIn("OMLX_API_KEY", result.stderr)
        self.assertNotIn("invalid-private-key", result.stdout + result.stderr)
        self.assertNotIn("private error", result.stderr)
        self.assertFalse(self.prefix.with_suffix(".asr.json").exists())

    def test_nonlocal_service_rejected(self):
        self.env["AGENT_OMLX_BASE_URL"] = "https://example.com/v1"
        self.assertNotEqual(self.run_client().returncode, 0)
        self.assertFalse(self.posts)

    def test_summary_prompt_preserves_model_and_coarse_timestamp_status(self):
        self.successful()
        result = subprocess.run(["bash", str(SKILL / "scripts/render_summary_prompt.sh"),
                                 "https://www.youtube.com/watch?v=test", "测试视频",
                                 "31", str(self.prefix.with_suffix(".txt"))], env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"model": "Qwen3-ASR-1.7B-8bit"', result.stdout)
        self.assertIn('"timestamp_source": "audio_chunk"', result.stdout)
        self.assertIn("不能声称逐句或逐字对齐", result.stdout)

    def test_site_pipeline_reuses_fixed_model_transcript(self):
        # 实际执行站点公共流程、ffmpeg 和客户端，仅把平台下载替换成本地音频。
        import shutil
        mp3 = self.root / "site.mp3"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-i", str(self.audio), str(mp3)], check=True)
        command = '''source "$1"
yt_common_mode_whisper_audio() { echo "[download] $OMLX_TEST_MP3 has already been downloaded"; }
yt_common_run_whisper_mode_from_url "$2" "$3" zh
'''
        args = ["bash", "-c", command, "test", str(SKILL / "scripts/lib/yt_dlp_common.sh"),
                "https://youtube.com/watch?v=test", str(self.root)]
        env = dict(self.env, OMLX_TEST_MP3=str(mp3))
        for reused in (0, 1):
            result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(f"asr_model={MODEL}", result.stdout)
            self.assertIn(f"cache_reused={reused}", result.stdout)
        self.assertEqual(len(self.posts), 2)

    def speech_with_pause(self, seconds, pause_start, pause_end):
        with wave.open(str(self.audio), "wb") as target:
            target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            target.writeframes(b"\x10\x27" * (pause_start * 16000))
            target.writeframes(b"\x00\x00" * ((pause_end - pause_start) * 16000))
            target.writeframes(b"\x10\x27" * ((seconds - pause_end) * 16000))

    def posted_pcm(self):
        pieces = []
        for _, _, body in self.posts:
            start = body.index(b"RIFF")
            end = body.index(b"\r\n--feipi", start)
            with wave.open(io.BytesIO(body[start:end]), "rb") as audio:
                pieces.append(audio.readframes(audio.getnframes()))
        return b"".join(pieces)

    def test_pause_cut_and_forced_cut_upload_every_sample_once(self):
        self.speech_with_pause(70, 24, 25)
        result = self.successful()
        chunks = self.record()["chunks"]
        self.assertAlmostEqual(chunks[0]["end"], 24.5, places=2)
        self.assertEqual(chunks[0]["cut_reason"], "pause")
        self.assertTrue(any(chunk["cut_reason"] == "forced" for chunk in chunks))
        self.assertTrue(all(chunk["end"] - chunk["start"] <= 30 for chunk in chunks))
        with wave.open(str(self.audio), "rb") as original:
            self.assertEqual(self.posted_pcm(), original.readframes(original.getnframes()))
        self.assertIn("asr_chunk_start=1/3 start=0.000 end=24.500 cut=pause", result.stderr)

    def test_sixty_second_example_and_cache_parameter_isolation(self):
        self.speech_with_pause(80, 56, 63)
        result = self.run_client(extra=("--max-seconds", "60"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertAlmostEqual(self.record()["chunks"][0]["end"], 59.5, places=2)
        self.assertEqual(self.record()["chunk_seconds"], 60)
        self.assertIn("cache_reused=1", self.run_client(extra=("--max-seconds", "60")).stdout)
        self.assertEqual(len(self.posts), 2)
        self.assertIn("cache_reused=0", self.successful().stdout)
        self.assertEqual(len(self.posts), 5)

    def test_fixed_chunk_cache_is_not_reused_for_pause_chunking(self):
        self.successful()
        record = self.record()
        record["schema"] = "omlx-asr-v1"
        record.pop("chunk_policy")
        self.prefix.with_suffix(".asr.json").write_text(json.dumps(record))
        self.assertIn("cache_reused=0", self.successful().stdout)
        self.assertEqual(len(self.posts), 4)

    def test_changed_pause_policy_and_corrupt_chunk_trace_are_not_reused(self):
        for corrupt in ("policy", "range", "text", "model"):
            self.successful()
            record = self.record()
            if corrupt == "policy":
                record["chunk_policy"] = "pause-start-v1"
            elif corrupt == "range":
                record["chunks"][-1]["start_frame"] += 1
            elif corrupt == "text":
                record["chunks"][0]["text"] = "与SRT不符"
            else:
                record["model"] = "unrelated-model"
            self.prefix.with_suffix(".asr.json").write_text(json.dumps(record))
            before = len(self.posts)
            self.assertIn("cache_reused=0", self.successful().stdout)
            self.assertEqual(len(self.posts), before + 2)

    def test_summary_rejects_corrupt_asr_trace_without_modifying_text(self):
        self.successful()
        before = self.prefix.with_suffix(".txt").read_bytes()
        record = self.record()
        record["chunks"][0]["end_frame"] -= 1
        self.prefix.with_suffix(".asr.json").write_text(json.dumps(record))
        result = subprocess.run(["bash", str(SKILL / "scripts/render_summary_prompt.sh"),
                                 "https://youtube.com/watch?v=test", "测试", "31", str(self.prefix.with_suffix(".txt"))],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("oMLX 来源信息:", result.stdout)
        self.assertIn("ASR 来源校验未通过", result.stdout)
        self.assertEqual(self.prefix.with_suffix(".txt").read_bytes(), before)

    def test_summary_rejects_changed_extracted_audio(self):
        self.successful()
        self.prefix.with_suffix(".whisper.wav").write_bytes(b"broken extracted audio")
        result = subprocess.run(["bash", str(SKILL / "scripts/render_summary_prompt.sh"),
                                 "https://youtube.com/watch?v=test", "测试", "31", str(self.prefix.with_suffix(".txt"))],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("oMLX 来源信息:", result.stdout)
        self.assertIn("ASR 来源校验未通过", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_local_video_entrypoint_preserves_audio_and_cache_and_summary(self):
        video = self.root / "带 空格的视频.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=s=16x16:r=1",
                        "-i", str(self.audio), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                        "-c:a", "aac", "-shortest", str(video)], check=True)
        entry = SKILL / "scripts/extract_video_text.sh"
        command = ["bash", str(entry), str(video), str(self.root / "out"), "auto"]
        result = subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        self.assertEqual(fields["source"], "local")
        with wave.open(fields["audio_path"], "rb") as audio:
            self.assertEqual(self.posted_pcm(), audio.readframes(audio.getnframes()))
        prompt = subprocess.run(["bash", str(SKILL / "scripts/render_summary_prompt.sh"), str(video), "",
                                 fields["duration_sec"], fields["text_path"]], capture_output=True, text=True)
        self.assertEqual(prompt.returncode, 0, prompt.stderr)
        self.assertIn('"title_source": "local_filename"', prompt.stdout)
        self.assertIn('"model": "Qwen3-ASR-1.7B-8bit"', prompt.stdout)
        self.assertIn(str(video), prompt.stdout)
        self.assertIn("提取音频：" + fields["audio_path"], prompt.stdout)
        count = len(self.posts)
        result = subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cache_reused=1", result.stdout)
        self.assertIn("audio_reused=1", result.stdout)
        self.assertEqual(len(self.posts), count)
        # 源文件内容变化不能误用同路径旧结果。
        with video.open("ab") as output:
            output.write(b"\x00\x00\x00\x08free")
        result = subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cache_reused=0", result.stdout)
        self.assertGreater(len(self.posts), count)

    def test_invalid_chunk_limits_fail_before_any_service_request(self):
        for value in ("0", "nan", "inf"):
            self.assertNotEqual(self.run_client(extra=("--max-seconds", value)).returncode, 0)
        self.assertFalse(self.gets)
        self.assertFalse(self.posts)

    def test_splitter_only_exposes_max_seconds_setting(self):
        import re
        splitter = SKILL / "scripts/lib/split_audio.py"
        result = subprocess.run([sys.executable, str(splitter), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(re.findall(r"--[a-z-]+", result.stdout)), {"--help", "--max-seconds"})
        result = subprocess.run([sys.executable, str(splitter), str(self.audio), "--listen"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_splitter_cli_produces_lossless_wav_files(self):
        splitter = SKILL / "scripts/lib/split_audio.py"
        result = subprocess.run([sys.executable, str(splitter), str(self.audio)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = Path(next(line.split("=", 1)[1] for line in result.stdout.splitlines() if line.startswith("output_dir=")))
        pcm = bytearray()
        for path in sorted(output.glob("*.wav")):
            with wave.open(str(path), "rb") as chunk:
                self.assertLessEqual(chunk.getnframes(), 30 * 16000)
                pcm.extend(chunk.readframes(chunk.getnframes()))
        with wave.open(str(self.audio), "rb") as original:
            self.assertEqual(bytes(pcm), original.readframes(original.getnframes()))


if __name__ == "__main__":
    unittest.main()
