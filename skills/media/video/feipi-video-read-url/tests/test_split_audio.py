#!/usr/bin/env python3
"""真实 PCM 与 ffmpeg 验证连续讲话、长静音、片尾和分块上限；不评价人工听感。"""

from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lib"))
from split_audio import plan_audio


class SplitAudioTests(unittest.TestCase):
    def plan(self, blocks, maximum=30):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "input.wav"
            pcm = b"".join(value * round(seconds * 16000) for seconds, value in blocks)
            with wave.open(str(audio), "wb") as target:
                target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                target.writeframes(pcm)
            rate, frames, pieces = plan_audio(audio, maximum)
        self.assertEqual(pieces[0]["start_frame"], 0)
        self.assertEqual(pieces[-1]["end_frame"], frames)
        self.assertEqual(b"".join(pcm[p["start_frame"] * 2:p["end_frame"] * 2] for p in pieces), pcm)
        self.assertTrue(all(0 < p["end_frame"] - p["start_frame"] <= int(maximum * rate) for p in pieces))
        self.assertTrue(all(a["end_frame"] == b["start_frame"] for a, b in zip(pieces, pieces[1:])))
        return pieces

    def test_continuous_signal_forces_cut_and_preserves_one_sample_tail(self):
        for maximum in (1, 1.25, 20, 30, 60):
            pieces = self.plan([(maximum * 2 + 1 / 16000, b"\x10\x27")], maximum)
            self.assertEqual([p["cut_reason"] for p in pieces], ["forced", "forced", "end"])
            self.assertEqual(pieces[-1]["end_frame"] - pieces[-1]["start_frame"], 1)

    def test_long_silence_and_final_speech_are_preserved(self):
        pieces = self.plan([(22, b"\x10\x27"), (73, b"\x00\x00"), (2.125, b"\x10\x27")])
        self.assertTrue(all(p["cut_reason"] == "pause" for p in pieces[:-1]))
        self.assertEqual(pieces[-1]["cut_reason"], "end")
        self.assertGreater(pieces[-1]["end_frame"], 95 * 16000)

    def test_entirely_silent_input_is_partitioned_without_dropping_samples(self):
        pieces = self.plan([(91.125, b"\x00\x00")])
        self.assertEqual(len(pieces), 4)
        self.assertTrue(all(p["cut_reason"] == "pause" for p in pieces[:-1]))

    def test_pause_near_limit_stays_inside_silence_and_limit(self):
        pieces = self.plan([(29.8, b"\x10\x27"), (1, b"\x00\x00"), (1, b"\x10\x27")])
        self.assertEqual(pieces[0]["cut_reason"], "pause")
        self.assertEqual(pieces[0]["end_frame"], 30 * 16000)

    def test_short_clip_and_exact_limit_use_single_complete_chunk(self):
        for seconds in (0.1, 30):
            pieces = self.plan([(seconds, b"\x10\x27")])
            self.assertEqual(len(pieces), 1)
            self.assertEqual(pieces[0]["cut_reason"], "end")


if __name__ == "__main__":
    unittest.main()
