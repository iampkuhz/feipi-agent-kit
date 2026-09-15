#!/usr/bin/env python3
"""运行真实公共函数；外部程序用隔离替身，不访问站点。"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parent
LIB = SCRIPTS / "lib/yt_dlp_common.sh"


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.formula = self.root / "formula"
        (self.formula / "bin").mkdir(parents=True)
        self.env = dict(os.environ, PATH=str(self.bin) + ":/usr/bin:/bin",
                        AGENT_CHROME_PROFILE="", AGENT_YOUTUBE_COOKIE_FILE="")
        for name in ("python3", "rg"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.program(self.bin / "brew", 'echo "{}"'.format(self.formula))

    def program(self, path, body):
        path.write_text("#!/bin/bash\n" + body + "\n")
        path.chmod(0o755)

    def shell(self, command, *args, env=None):
        return subprocess.run(["/bin/bash", "-c", 'source "$1"; shift; ' + command,
                               "test", str(LIB)] + [str(a) for a in args],
                              env=env or self.env, capture_output=True, text=True,
                              errors="replace", timeout=30)

    def select(self):
        return self.shell('yt_common_select_ytdlp || exit 1; echo "$YT_DLP_BIN|$YT_DLP_VERSION"')

    def test_skip_broken_and_unrecognized_candidates(self):
        good = self.formula / "bin/yt-dlp"
        self.program(good, "echo 2026.08.19")
        for body in ("echo custom-build", "echo 2027.01.01; exit 1", "exit 127",
                     "echo '2027.01.01 extra output'"):
            with self.subTest(body=body):
                self.program(self.bin / "yt-dlp", body)
                result = self.select()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(str(good) + "|2026.08.19", result.stdout)

    def test_equal_version_keeps_path_priority(self):
        for path in (self.bin / "yt-dlp", self.formula / "bin/yt-dlp"):
            self.program(path, "echo 2026.08.19")
        self.assertIn(str(self.bin / "yt-dlp") + "|", self.select().stdout)

    def test_nightly_and_packaging_suffix(self):
        self.program(self.bin / "yt-dlp", "echo 2026.08.19+package99")
        self.program(self.formula / "bin/yt-dlp", "echo 2026.08.19.120000")
        self.assertIn("|2026.08.19.120000", self.select().stdout)

    def test_only_invalid_candidates_fail_and_clear_state(self):
        self.program(self.bin / "yt-dlp", "exit 127")
        result = self.shell('YT_DLP_BIN=previous; if yt_common_select_ytdlp; then exit 9; fi; '
                            'test -z "$YT_DLP_BIN"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.select().returncode, 0)

    def test_dependency_check_uses_formula_without_path_command(self):
        self.program(self.formula / "bin/yt-dlp", "echo 2026.08.19")
        result = subprocess.run(["/bin/bash", str(SCRIPTS / "install_deps.sh"), "--check"],
                                env=self.env, capture_output=True, text=True, timeout=30)
        # 不依赖宿主转写模型是否存在，只核对 yt-dlp 的依赖结果。
        self.assertIn("[OK] yt-dlp", result.stdout)
        self.assertNotIn("[MISS] yt-dlp", result.stdout)
        self.assertIn("yt_dlp_path=" + str(self.formula / "bin/yt-dlp"), result.stderr)

    def convert(self, content):
        source, target = self.root / "source.srt", self.root / "target.txt"
        source.write_bytes(content)
        result = self.shell('yt_common_subtitle_to_text "$1" "$2"', source, target)
        return result, target

    def test_bad_utf8_keeps_last_cue(self):
        result, target = self.convert(
            b"1\n00:00:00,000 --> 00:00:01,000\nfirst\n\n"
            b"2\n00:53:01,000 --> 00:53:02,000\nbad \xff byte\n\n"
            b"3\n02:33:38,620 --> 02:33:39,180\nlast\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("\ufffd", target.read_text())
        self.assertIn("[02:33:38] last", target.read_text())
        self.assertIn("subtitle_encoding_replaced_bytes=1", result.stderr)
        self.assertIn("subtitle_cue_count=3", result.stderr)

    def test_malformed_last_cue_preserves_existing_target(self):
        target = self.root / "target.txt"
        target.write_text("previous complete result")
        result, _ = self.convert(b"1\n00:00:00,000 --> 00:00:01,000\nfirst\n\n"
                                 b"2\nbroken --> timestamp\nlast\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), "previous complete result")
        self.assertFalse(list(self.root.glob(".subtitle-text-*")))

    def test_empty_transcript_does_not_publish(self):
        result, target = self.convert(b"WEBVTT\n\nNOTE no subtitles\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())

    def test_vtt_ids_tags_and_numeric_body(self):
        result, target = self.convert(
            b"WEBVTT\n\nNOTE ignore me\n\ncue-id\n00:01.000 --> 00:02.000 align:start\n"
            b"<c>hello</c>\n42\n\nsecond-id\n00:02.000 --> 00:03.000\nlast\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(), "- [00:01] hello\n  42\n- [00:02] last\n")

    def test_reuse_rebuilds_partial_text_and_propagates_failure(self):
        self.program(self.bin / "uname", "echo Darwin")
        helper = self.root / "helper"
        self.program(helper, "exit 99")
        (self.root / "video.whisper.wav").touch()
        (self.root / "video.meta").write_text("profile=fast\nmodel=mock\n")
        srt = self.root / "video.srt"
        srt.write_bytes(b"1\n02:33:38,620 --> 02:33:39,180\nlast \xff\n")
        target = self.root / "video.txt"
        target.write_text("old partial result")
        call = 'yt_common_run_whisper_mode_from_url url "$1" "$2" zh fast'
        result = self.shell(call, self.root, helper)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[02:33:38]", target.read_text())
        srt.write_text("no timestamp")
        result = self.shell(call, self.root, helper)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("text_file=", result.stdout)

    def test_recovered_download_then_transcription_failure(self):
        self.program(self.bin / "uname", "echo Darwin")
        helper = self.root / "helper"
        self.program(helper, 'echo "missing model"; exit 1')
        log = self.root / "attempt.log"
        result = self.shell('''
            download() { echo 'ERROR: HTTP Error 403: Forbidden'; touch "$TEST_ROOT/audio.mp3"; }
            ffmpeg() { touch "${!#}"; }
            TEST_ROOT="$1"
            if yt_common_run_whisper_mode_from_url url "$1" "$2" zh fast download >"$3" 2>&1; then exit 9; fi
            yt_common_report_youtube_failure "$3"
        ''', self.root, helper, log)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("failure_stage=transcription", result.stderr)
        self.assertNotIn("youtube_media_download_blocked", result.stderr)

    def test_unknown_freshness_is_not_zero(self):
        log = self.root / "last.log"
        log.write_text("pipeline_stage=media_download\nERROR: HTTP Error 403\n"
                       "WARNING: GVS PO Token\n")
        result = self.shell('yt_common_report_youtube_failure "$1"', log)
        self.assertIn("yt_dlp_stale=unknown", result.stderr)
        self.assertIn("gvs_po_token_observed=1", result.stderr)
        self.assertNotIn("gvs_po_token_required", result.stderr)

    def test_metadata_survives_bad_bytes_in_transcription_log(self):
        self.program(self.bin / "uname", "echo Darwin")
        helper = self.root / "helper"
        self.program(helper, '''
            printf '\\377\\n'
            printf 'profile=fast\\nmodel=test-model\\ndevice=test-device\\n'
            printf '1\\n00:00:00,000 --> 00:00:01,000\\nlast\\n' > "$2.srt"
        ''')
        result = self.shell('''
            download() { touch "$TEST_ROOT/audio.mp3"; }
            ffmpeg() { touch "${!#}"; }
            TEST_ROOT="$1"
            yt_common_run_whisper_mode_from_url url "$1" "$2" zh fast download
        ''', self.root, helper)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("model=test-model", result.stdout)
        self.assertNotIn("illegal byte sequence", result.stderr)
        self.assertIn("model=test-model", (self.root / "audio.meta").read_text())

    def test_fresh_conversion_failure_does_not_return_text_path(self):
        self.program(self.bin / "uname", "echo Darwin")
        helper = self.root / "helper"
        self.program(helper, 'echo malformed > "$2.srt"')
        result = self.shell('''
            download() { touch "$TEST_ROOT/audio.mp3"; }
            ffmpeg() { touch "${!#}"; }
            TEST_ROOT="$1"
            if yt_common_run_whisper_mode_from_url url "$1" "$2" zh fast download; then exit 9; else exit 7; fi
        ''', self.root, helper)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertNotIn("text_file=", result.stdout)
        self.assertFalse((self.root / "audio.txt").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
