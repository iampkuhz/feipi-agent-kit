#!/usr/bin/env python3
"""验证字幕依据、零额外帧、重复复用及跨轮预算，使用临时来源文件。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "lib")]
import content_manifest as cm
import extract_frames as frames
from frame_plan import POLICY, validate_plan, source_hashes, check_policy


class FramePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.m = cm.new_manifest("https://example.invalid/video", "bilibili", "video")
        self.m["metadata"]["duration_seconds"] = 80
        self.text = self.root / "asr.txt"
        self.lines = [f"[00:00:{t:02d}] 字幕{t}：图中标注尺寸。" for t in range(0, 71, 10)]
        self.text.write_text("\n".join(self.lines))
        cm.artifact(self.m, self.root, "asr", "asr", self.text, {"type": "time_range", "start_seconds": 0, "end_seconds": 80})
        image = self.root / "opening.jpg"; image.write_bytes(b"opening")
        cm.artifact(self.m, self.root, "frame-001", "frame", image, {"type": "time", "seconds": 0})
        cm.channel(self.m, "frames", "complete", sampling={"strategy": POLICY, "selection_status": "pending"})

    def plan(self, times):
        return {"schema": "feipi-frame-plan-v1", "transcript_sha256": source_hashes(self.root, self.m),
            "decision": "读完字幕后核对尺寸，其他片段不需要截图。", "frames": [
                {"seconds": t, "title": "尺寸图", "reason": "核对画面上的尺寸", "evidence": {
                    "artifact_id": "asr", "quote": self.lines[int(t)//10]}} for t in times]}

    def test_empty_plan_reuses_opening_without_network(self):
        with patch.object(frames, "resolve_media", side_effect=AssertionError("must not request")):
            self.assertEqual(frames.extract_frames("url", self.root, self.m, SCRIPTS, plan=self.plan([])), [])
        check_policy(self.m, require_decision=True)
        self.assertEqual(len([a for a in self.m["artifacts"] if a["kind"] == "frame"]), 1)

    def test_five_allowed_six_rejected(self):
        self.assertEqual(len(validate_plan(self.root, self.m, self.plan([1,11,21,31,41]))), 5)
        with self.assertRaisesRegex(ValueError, "five"):
            validate_plan(self.root, self.m, self.plan([1,11,21,31,41,51]))

    def test_quote_hash_time_and_decision_are_checked(self):
        mutations = [("quote", "not_found"), ("hash", "changed"), ("time", "window"), ("decision", "decision_required")]
        for key, error in mutations:
            plan = self.plan([11])
            if key == "quote": plan["frames"][0]["evidence"]["quote"] = "编造字幕"
            if key == "hash": plan["transcript_sha256"]["asr"] = "old"
            if key == "time": plan["frames"][0]["seconds"] = 59
            if key == "decision": plan["decision"] = ""
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, error):
                validate_plan(self.root, self.m, plan)

    def test_failed_attempts_consume_cumulative_budget(self):
        self.m["channels"]["frames"]["sampling"]["attempted_extra_times_seconds"] = [1,11,21,31,41]
        validate_plan(self.root, self.m, self.plan([11]))
        with self.assertRaisesRegex(ValueError, "cumulative"):
            validate_plan(self.root, self.m, self.plan([51]))

    def test_raw_times_fail_before_network(self):
        with patch.object(frames, "resolve_media", side_effect=AssertionError("must not request")):
            with self.assertRaisesRegex(ValueError, "transcript_frame_plan"):
                frames.extract_frames("url", self.root, self.m, SCRIPTS, times=[1])

    def test_duplicate_times_and_missing_ai_decision_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_plan(self.root, self.m, self.plan([11,11]))
        with self.assertRaisesRegex(ValueError, "submit_frame_plan"):
            check_policy(self.m, require_decision=True)

    def test_same_selected_frame_is_reused_across_rounds(self):
        image = self.root / "extra.jpg"; image.write_bytes(b"extra")
        cm.artifact(self.m, self.root, "frame-002", "frame", image, {"type": "time", "seconds": 11})
        with patch.object(frames, "resolve_media", side_effect=AssertionError("must not request")):
            frames.extract_frames("url", self.root, self.m, SCRIPTS, plan=self.plan([11]))
        self.assertEqual(len([a for a in self.m["artifacts"] if a["kind"] == "frame"]), 2)


if __name__ == "__main__": unittest.main()
