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
from summary_packet import build, prepare


class SummaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "extraction_manifest.json"
        self.summary = self.root / "summary.md"
        self.coverage = self.root / "summary_coverage.json"
        self.source = "建议方案A。操作步骤少、执行时间短。需要额外工具，仅在具备工具时适用。"
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
                                   ("建议", "recommendation", "建议方案A"),
                                   ("理由", "reason", "操作步骤少、执行时间短"),
                                   ("代价与条件", "condition", "需要额外工具，仅在具备工具时适用")])]}

    def check(self):
        self.coverage.write_text(json.dumps(self.rows, ensure_ascii=False))
        return review(self.manifest, self.summary, self.coverage)

    def test_complete_comparison_and_current_hashes(self):
        result = self.check()
        self.assertEqual(result["unit_count"], 3)
        self.assertEqual(result["semantic_review"], "host_declared")
        self.summary.write_text(self.source + "\n待核验使用条件。")
        self.assertNotEqual(result["summary_sha256"], self.check()["summary_sha256"])

    def test_short_recommendation_loses_reason_and_condition(self):
        self.summary.write_text("建议方案A。")
        with self.assertRaisesRegex(ValueError, "summary_unit_missing:1"):
            self.check()

    def test_fake_source_quote_is_rejected(self):
        self.rows["units"][0]["evidence"][0]["quote"] = "已在全部环境验证通过"
        with self.assertRaisesRegex(ValueError, "summary_evidence_not_in_source"):
            self.check()

    def test_reports_all_mismatches_in_one_pass(self):
        self.summary.write_text("完全不同的摘要文本")
        self.rows["units"][2]["evidence"][0]["quote"] = "虚构的来源片段"
        with self.assertRaises(ValueError) as failure:
            self.check()
        self.assertIn("summary_unit_missing:0", str(failure.exception))
        self.assertIn("summary_unit_missing:2", str(failure.exception))
        self.assertIn("summary_evidence_not_in_source:2", str(failure.exception))

    def draft(self):
        packet = prepare(self.root)
        value = {"schema": "feipi-summary-draft-v1", "source_digest": packet["source_digest"],
                 "reviewed_artifact_ids": ["asr"], "semantic_review": "all_units_checked",
                 "overview": "作者比较方案及执行条件。", "sections": [{"title": "方案取舍", "items": [
                     {"id": "choice", "category": "condition", "text": '选择 **方案A**，保留 "工具" 条件及 20 分钟间隔。',
                      "evidence": ["asr:0001"]}]}]}
        path = self.root / "draft.json"
        path.write_text(json.dumps(value, ensure_ascii=False))
        return path, value

    def test_packet_build_preserves_quotes_and_markdown_without_manual_copy(self):
        path, value = self.draft()
        result = build(self.root, path)
        self.assertEqual(result["status"], "traceability_checked")
        coverage = json.loads(self.coverage.read_text())
        self.assertEqual(coverage["units"][0]["summary_quote"], value["sections"][0]["items"][0]["text"])
        self.assertEqual(coverage["units"][0]["evidence"][0]["quote"], self.source)
        self.assertEqual(review(self.manifest, self.summary, self.coverage)["unit_count"], 1)

    def test_packet_rejects_stale_evidence_and_preserves_previous_summary(self):
        path, _ = self.draft()
        build(self.root, path)
        before = self.summary.read_bytes()
        (self.root / "asr.txt").write_text("来源内容已经改变，旧编号不得沿用。")
        with self.assertRaisesRegex(ValueError, "source_changed"):
            build(self.root, path)
        self.assertEqual(self.summary.read_bytes(), before)

    def test_packet_rejects_invented_reference_and_missing_review(self):
        path, value = self.draft()
        value["semantic_review"] = "pending"
        value["sections"][0]["items"][0]["evidence"] = ["asr:9999"]
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError) as failure:
            build(self.root, path)
        self.assertIn("host_semantic_review_required", str(failure.exception))
        self.assertIn("unknown_evidence_id:choice", str(failure.exception))

    def test_unreviewed_content_file_is_rejected(self):
        self.rows["reviewed_artifact_ids"] = []
        with self.assertRaisesRegex(ValueError, "all_content_artifacts"):
            self.check()

    def test_missing_actual_host_review_is_rejected(self):
        self.rows["summary_review"] = "pending"
        with self.assertRaisesRegex(ValueError, "host_semantic_review_required"):
            self.check()

    def frame_plan(self, manifest, second=None):
        from frame_plan import source_hashes
        rows = []
        if second is not None:
            text = "[00:02:20] " + (self.root / "asr.txt").read_text()
            (self.root / "asr.txt").write_text(text)
            manifest["metadata"]["duration_seconds"] = 200
            rows = [{"seconds": second, "title": "术语核验", "reason": "核对字幕提示", "evidence": {"artifact_id": "asr", "quote": text}}]
        return {"schema": "feipi-frame-plan-v1", "transcript_sha256": source_hashes(self.root, manifest), "decision": "阅读全文后选择", "frames": rows}

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
            frames.extract_frames(m["original_url"], self.root, m, SCRIPTS, info=info, plan=self.frame_plan(m, 145))
        self.assertEqual(old.read_bytes(), b"old-frame")
        self.assertEqual([a["id"] for a in m["artifacts"] if a["kind"] == "frame"], ["frame-001", "frame-002"])
        self.assertEqual(m["channels"]["frames"]["sampling"]["strategy"], "opening_plus_transcript_v1")
        self.assertEqual(m["artifacts"][1]["read_status"], "read")

    def test_base_copy_uses_saved_url_without_host_copying_signature(self):
        m = json.loads(self.manifest.read_text())
        m["original_url"] += "?xsec_token=actual-public-signature"
        self.manifest.write_text(json.dumps(m))
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(self.frame_plan(m)))
        output = self.root / "new-extraction"
        before = (self.root / "asr.txt").read_bytes()
        with patch.object(sys, "argv", ["extract_frames.py", "-", str(output), "--base-dir", str(self.root), "--plan", str(plan_path)]), patch.object(frames, "extract_frames") as extract:
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
