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


class OmlxTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.audio, self.prefix = self.root / "input.wav", self.root / "transcript"
        self.make_audio(31)
        self.models = ["mlx-community/SenseVoiceSmall", "Qwen3-ASR-1.7B-bf16"]
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

    def run_client(self, profile="auto", language="zh", extra=()):
        return subprocess.run([sys.executable, str(CLIENT), str(self.audio), str(self.prefix), language, profile, *extra],
                              env=self.env, capture_output=True, text=True, timeout=15)

    def successful(self, profile="auto", language="zh"):
        result = self.run_client(profile, language)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def record(self):
        return json.loads(self.prefix.with_suffix(".asr.json").read_text())

    def test_auto_fast_complete_chunks_and_multipart(self):
        result = self.successful()
        self.assertIn("asr_model=mlx-community/SenseVoiceSmall", result.stdout)
        self.assertEqual(len(self.posts), 2)
        for expected_frames, (path, headers, body) in zip((480000, 16000), self.posts):
            self.assertEqual(path, "/v1/audio/transcriptions")
            self.assertIn(b"mlx-community/SenseVoiceSmall", body)
            self.assertIn(b'name="language"\r\n\r\nzh', body)
            start = body.index(b"RIFF")
            end = body.index(b"\r\n--feipi", start)
            with wave.open(io.BytesIO(body[start:end]), "rb") as audio:
                self.assertEqual(audio.getnframes(), expected_frames)
        self.assertIn("00:00:30,000 --> 00:00:31,000", self.prefix.with_suffix(".srt").read_text())
        self.assertIn("[00:00:30] 块2原文", self.prefix.with_suffix(".txt").read_text())
        self.assertEqual(self.record()["timestamp_source"], "audio_chunk")
        self.assertEqual(self.record()["duration_seconds"], 31)

    def test_accurate_uses_qwen_and_auto_language_omits_hint(self):
        self.successful("accurate", "auto")
        self.assertIn(b"Qwen3-ASR-1.7B-bf16", self.posts[0][2])
        self.assertNotIn(b'name="language"', self.posts[0][2])

    def test_fast_never_falls_back_to_accurate(self):
        self.models = ["Qwen3-ASR-1.7B-bf16"]
        result = self.run_client("fast")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("omlx_model_missing", result.stderr)
        self.assertFalse(self.posts)

    def test_accurate_never_falls_back_to_fast(self):
        self.models = ["SenseVoiceSmall"]
        self.assertNotEqual(self.run_client("accurate").returncode, 0)
        self.assertFalse(self.posts)

    def test_ambiguous_models_rejected(self):
        self.models += ["SenseVoiceSmall"]
        self.assertIn("omlx_model_ambiguous", self.run_client().stderr)
        self.assertFalse(self.posts)

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

    def test_silence_chunk_and_control_tags(self):
        self.responses = [{"text": ""}, {"text": "<|zh|><|NEUTRAL|>原文<|Speech|>"}]
        self.successful()
        self.assertEqual(self.prefix.with_suffix(".txt").read_text(), "- [00:00:30] 原文\n")
        self.assertEqual(len(self.record()["chunks"]), 2)

    def test_matching_cache_does_not_call_service(self):
        self.successful()
        self.models = []
        result = self.successful("fast")
        self.assertIn("cache_reused=1", result.stdout)
        self.assertIn("asr_auth=not_requested_cache", result.stdout)
        self.assertEqual(len(self.gets), 1)
        self.assertEqual(len(self.posts), 2)

    def test_cache_does_not_cross_profile_audio_or_language(self):
        self.successful()
        self.successful("accurate")
        self.assertEqual(self.record()["model"], "Qwen3-ASR-1.7B-bf16")
        self.successful("fast", "en")
        self.make_audio(31, value=b"\x01\x00")
        self.successful("fast", "en")
        self.assertEqual(len(self.posts), 8)

    def test_old_whisper_cache_not_reused(self):
        self.prefix.with_suffix(".meta").write_text("profile=accurate\nmodel=ggml-large-v3-q5_0.bin\n")
        self.prefix.with_suffix(".srt").write_text("old whisper")
        self.successful("accurate")
        self.assertEqual(len(self.posts), 2)

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

    def test_check_models_and_api_key(self):
        self.env["OMLX_API_KEY"] = "test-private-key"
        result = subprocess.run([sys.executable, str(CLIENT), "--check", "accurate"], env=self.env,
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
        self.assertTrue(self.get_headers)
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
        self.successful("accurate")
        result = subprocess.run(["bash", str(SKILL / "scripts/render_summary_prompt.sh"),
                                 "https://www.youtube.com/watch?v=test", "测试视频",
                                 "31", str(self.prefix.with_suffix(".txt"))], env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"model": "Qwen3-ASR-1.7B-bf16"', result.stdout)
        self.assertIn('"timestamp_source": "audio_chunk"', result.stdout)
        self.assertIn("不能声称逐句或逐字对齐", result.stdout)

    def test_site_pipeline_never_reuses_fast_for_accurate(self):
        # 实际执行站点公共流程、ffmpeg 和客户端，仅把平台下载替换成本地音频。
        import shutil
        mp3 = self.root / "site.mp3"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-i", str(self.audio), str(mp3)], check=True)
        command = '''source "$1"
yt_common_mode_whisper_audio() { echo "[download] $OMLX_TEST_MP3 has already been downloaded"; }
yt_common_run_whisper_mode_from_url "$3" "$4" "$5" zh "$6"
'''
        args = ["bash", "-c", command, "test", str(SKILL / "scripts/lib/yt_dlp_common.sh"),
                str(mp3), "https://youtube.com/watch?v=test", str(self.root),
                str(SKILL / "scripts/lib/omlx_transcribe.sh")]
        env = dict(self.env, OMLX_TEST_MP3=str(mp3))
        for profile, model in (("fast", "SenseVoiceSmall"), ("accurate", "Qwen3-ASR-1.7B-bf16")):
            result = subprocess.run(args + [profile], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("asr_model=", result.stdout)
            self.assertIn(model, result.stdout)
        self.assertEqual(len(self.posts), 4)


if __name__ == "__main__":
    unittest.main()
