#!/usr/bin/env python3
"""比较细节丢失、来源伪造与补帧不覆盖旧证据的回归。"""
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
from review_summary import review


class SummaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "extraction_manifest.json"
        self.summary = self.root / "summary.md"
        self.coverage = self.root / "summary_coverage.json"
        self.source = "建议PUR封边。用胶量少、胶线细、封边较牢。价格比EVA略高，需要专业设备。"
        m = cm.new_manifest("https://example.invalid/video", "bilibili", "video")
        text = self.root / "asr.txt"
        text.write_text(self.source)
        cm.artifact(m, self.root, "asr", "asr", text, {"type": "time_range", "start_seconds": 0})
        cm.channel(m, "asr", "complete")
        cm.finish(m, self.root)
        self.summary.write_text(self.source)
        self.rows = {"schema": "feipi-summary-coverage-v1", "reviewed_artifact_ids": ["asr"],
                     "source_review": "full_available_text_and_images", "summary_review": "all_units_checked",
                     "units": [{"id": str(i), "topic": title, "category": category,
                                "evidence": [{"artifact_id": "asr", "quote": quote}], "summary_quote": quote}
                               for i, (title, category, quote) in enumerate([
                                   ("建议", "recommendation", "建议PUR封边"),
                                   ("理由", "reason", "用胶量少、胶线细、封边较牢"),
                                   ("代价与条件", "condition", "价格比EVA略高，需要专业设备")])]}

    def check(self):
        self.coverage.write_text(json.dumps(self.rows, ensure_ascii=False))
        return review(self.manifest, self.summary, self.coverage)

    def test_complete_comparison_and_current_hashes(self):
        result = self.check()
        self.assertEqual(result["unit_count"], 3)
        self.assertEqual(result["semantic_review"], "host_declared")
        self.summary.write_text(self.source + "\n待核验现场条件。")
        self.assertNotEqual(result["summary_sha256"], self.check()["summary_sha256"])

    def test_short_recommendation_loses_reason_and_condition(self):
        self.summary.write_text("建议PUR封边。")
        with self.assertRaisesRegex(ValueError, "summary_unit_missing:1"):
            self.check()

    def test_fake_source_quote_is_rejected(self):
        self.rows["units"][0]["evidence"][0]["quote"] = "防火等级已经认证"
        with self.assertRaisesRegex(ValueError, "summary_evidence_not_in_source"):
            self.check()

    def test_unreviewed_content_file_is_rejected(self):
        self.rows["reviewed_artifact_ids"] = []
        with self.assertRaisesRegex(ValueError, "all_content_artifacts"):
            self.check()

    def test_missing_actual_host_review_is_rejected(self):
        self.rows["summary_review"] = "pending"
        with self.assertRaisesRegex(ValueError, "host_semantic_review_required"):
            self.check()

    def test_additional_frames_preserve_read_old_frames(self):
        m = json.loads(self.manifest.read_text())
        old = self.root / "frames/001-0.000s.jpg"
        old.parent.mkdir()
        old.write_bytes(b"old-frame")
        cm.artifact(m, self.root, "frame-001", "frame", old, {"type": "time", "seconds": 0})
        m["artifacts"][-1]["read_status"] = "read"
        cm.channel(m, "frames", "complete", sampling={"strategy": "uniform", "requested_times_seconds": [0]})
        def fake_run(args, log, **kwargs):
            Path(args[-1]).write_bytes(b"new-frame")
            return 0, b""
        info = {"duration": 200, "url": "https://example.invalid/media.mp4", "vcodec": "h264", "ext": "mp4"}
        with patch.object(frames.shutil, "which", return_value="ffmpeg"), patch.object(frames, "check_seekable", return_value="http_range"), patch.object(frames, "run_logged", side_effect=fake_run):
            frames.extract_frames(m["original_url"], self.root, m, SCRIPTS, info=info, times=[145])
        self.assertEqual(old.read_bytes(), b"old-frame")
        self.assertEqual([a["id"] for a in m["artifacts"] if a["kind"] == "frame"], ["frame-001", "frame-002"])
        self.assertEqual(m["channels"]["frames"]["sampling"]["previous_sampling"]["strategy"], "uniform")
        self.assertEqual(m["artifacts"][1]["read_status"], "read")

    def test_base_copy_uses_saved_url_without_host_copying_signature(self):
        m = json.loads(self.manifest.read_text())
        m["original_url"] += "?xsec_token=actual-public-signature"
        self.manifest.write_text(json.dumps(m))
        output = self.root / "new-extraction"
        before = (self.root / "asr.txt").read_bytes()
        with patch.object(sys, "argv", ["extract_frames.py", "-", str(output), "--base-dir", str(self.root), "--times", "145"]), patch.object(frames, "extract_frames") as extract:
            frames.main()
        self.assertEqual(extract.call_args.args[0], m["original_url"])
        self.assertEqual((output / "asr.txt").read_bytes(), before)
        self.assertEqual((self.root / "asr.txt").read_bytes(), before)

    def test_wrong_base_source_fails_before_creating_output(self):
        output = self.root / "new-extraction"
        with patch.object(sys, "argv", ["extract_frames.py", "https://wrong.invalid/", str(output), "--base-dir", str(self.root), "--times", "145"]):
            with self.assertRaisesRegex(ValueError, "base_source_url_mismatch"):
                frames.main()
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
