#!/usr/bin/env python3
"""隔离缓存与解码参数验证，不运行实际识别模型或访问站点。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

SKILL = Path(__file__).resolve().parents[1]
HELPER = SKILL / 'scripts/lib/verify_cached_audio.py'


class CachedAudioTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.video, self.audio = self.root/'video.mp4', self.root/'audio.wav'
        self.video.write_bytes(b'fake video')
        self.pcm = b'\x01\x00\x02\x00' * 160
        self.make_audio()
        self.output = self.root/'validation.json'
        bin_dir = self.root/'bin'
        bin_dir.mkdir()
        ffmpeg = bin_dir/'ffmpeg'
        ffmpeg.write_text(f'#!{sys.executable}\nimport os,sys\n'
            "sys.stdout.buffer.write(bytes.fromhex(os.environ['CACHE_TEST_PCM']))\n"
            "sys.exit(int(os.environ.get('CACHE_TEST_EXIT','0')))\n")
        ffmpeg.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],
                        CACHE_TEST_PCM=self.pcm.hex())

    def make_audio(self, channels=1):
        with wave.open(str(self.audio), 'wb') as target:
            target.setparams((channels, 2, 16000, 0, 'NONE', 'not compressed'))
            target.writeframes(self.pcm)

    def run_helper(self):
        return subprocess.run([sys.executable, str(HELPER), str(self.video),
            str(self.audio), str(self.output)], env=self.env, capture_output=True,
            text=True, timeout=10)

    def test_valid_pcm_does_not_modify_media(self):
        before = (self.audio.read_bytes(), self.video.read_bytes(), self.audio.stat().st_mtime_ns)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, (self.audio.read_bytes(), self.video.read_bytes(),
                                  self.audio.stat().st_mtime_ns))
        record = json.loads(self.output.read_text())
        self.assertTrue(record['decoded_pcm_identical'])
        self.assertEqual(record['pcm_bytes'], len(self.pcm))
        self.assertFalse(record['media_payload_files_created'])

    def test_mismatch_preserves_media_and_previous_report(self):
        self.env['CACHE_TEST_PCM'] = '0000'
        self.output.write_text('previous')
        before = self.audio.read_bytes()
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('drvoice_audio_cache_mismatch', result.stderr)
        self.assertEqual(self.output.read_text(), 'previous')
        self.assertEqual(self.audio.read_bytes(), before)

    def test_decoder_failure_rejects_even_matching_pcm(self):
        self.env['CACHE_TEST_EXIT'] = '7'
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_wrong_parameters_rejected(self):
        self.make_audio(channels=2)
        self.assertNotEqual(self.run_helper().returncode, 0)

    def test_truncated_wav_rejected_even_if_actual_bytes_match(self):
        self.audio.write_bytes(self.audio.read_bytes()[:-8])
        self.env['CACHE_TEST_PCM'] = self.pcm[:-8].hex()
        self.assertNotEqual(self.run_helper().returncode, 0)

    def test_empty_audio_rejected(self):
        self.pcm = b''
        self.make_audio()
        self.env['CACHE_TEST_PCM'] = ''
        self.assertNotEqual(self.run_helper().returncode, 0)


if __name__ == '__main__':
    unittest.main()
