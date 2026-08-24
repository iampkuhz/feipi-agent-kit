#!/usr/bin/env python3
"""Focused regression tests for the compact stage handoff chain."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "stage_handoff.py"
STAGES = (
    ("phase_1_material_modeling", "phase_2_idea_confirmation", "ready", "phase-1"),
    ("phase_2_idea_confirmation", "phase_3_final_drafting", "confirmed", "phase-2"),
    ("phase_3_final_drafting", "phase_4_review_delivery", "built", "phase-3"),
    ("phase_4_review_delivery", "delivery", "reviewed", "phase-4"),
)


def run(working: Path, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["python3", str(SCRIPT), *args, "--working", str(working)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"command={args} exit={result.returncode} expected={expected}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def handoff(stage: str, next_stage: str, status: str, marker: str = "v1") -> str:
    return (
        "handoff_version: 1\n"
        f"from_stage: {stage}\n"
        f"to_stage: {next_stage}\n"
        f"status: {status}\n\n"
        f"## 决策摘要\n\n- {marker}\n\n"
        "## 传递索引\n\n- cache: local\n\n"
        "## 未决项\n\n- 无\n"
    )


def populate(working: Path) -> None:
    stage_root = working / "stages"
    write(
        stage_root / "shared/material-index.tsv",
        "source_id\tsource_type\tpath_or_locator\tsha256\trelevant_anchors\n"
        "SF1\tuser_file\tinput.md\tabcd\tL1-L3\n",
    )
    write(stage_root / "shared/evidence-cards.md", "# Evidence\n\n- SF1: compact fact\n")
    write(stage_root / "agents/prior-art-task.md", "# Task\n\n## 输入\n\n- SF1\n\n## 需要判断\n\n- relevance\n\n## 返回\n\n- TSV rows\n")
    write(stage_root / "phase-1/model.md", "# Model\n\n- I1 -> T1\n")
    write(
        stage_root / "phase-1/research.tsv",
        "lane\tquery_id\tsource_id\tevidence_status\tlocator\tconclusion\n"
        "object\tQ1\tEM1\tevidence_found\thttps://example.com\tbaseline\n",
    )
    write(stage_root / "phase-2/decision.md", "# Decision\n\nconfirmed\n")
    write(stage_root / "agents/diagram-task.md", "# Task\n\n## 输入\n\n- phase-2\n\n## 需要判断\n\n- layout\n\n## 返回\n\n- TSV rows\n")
    write(
        stage_root / "phase-3/build-map.tsv",
        "artifact_id\tpath\tsha256\towner\tstatus\nD1\tdiagrams/D1\tdeadbeef\tdiagram_worker\tready\n",
    )
    write(stage_root / "agents/final-review-task.md", "# Task\n\n## 输入\n\n- phase-3\n\n## 需要判断\n\n- quality\n\n## 返回\n\n- TSV rows\n")
    write(
        stage_root / "phase-4/review.tsv",
        "artifact_id\treview_type\tstatus\tbound_sha256\tconclusion\nD1\tvisual\tpass\tdeadbeef\tclear\n",
    )
    for stage, next_stage, status, folder in STAGES:
        write(stage_root / folder / "handoff.md", handoff(stage, next_stage, status))


def seal_all(working: Path) -> None:
    for stage, _, _, _ in STAGES:
        run(working, "seal", "--stage", stage)


def test_complete_chain_and_status() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        seal_all(working)
        result = run(working, "validate", "--require-complete")
        assert "valid_stages=4" in result.stdout
        result = run(working, "status")
        assert "next_stage=delivery" in result.stdout
        assert "next_input=stages/phase-4/handoff.md" in result.stdout


def test_tamper_and_header_failure() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        seal_all(working)
        path = working / "stages/phase-3/handoff.md"
        path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
        result = run(working, "validate", expected=1)
        assert "hash 已变化" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        seal_all(working)
        path = working / "stages/phase-3/build-map.tsv"
        path.write_text(path.read_text(encoding="utf-8") + "D2\tdiagrams/D2\tbead\tdiagram_worker\tready\n", encoding="utf-8")
        result = run(working, "validate", expected=1)
        assert "阶段缓存 hash 已变化" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        path = working / "stages/phase-1/handoff.md"
        path.write_text(path.read_text(encoding="utf-8").replace("status: ready", "status: built"), encoding="utf-8")
        result = run(working, "seal", "--stage", STAGES[0][0], expected=1)
        assert "handoff 头不符合合同" in result.stderr


def test_upstream_change_invalidates_downstream() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        seal_all(working)
        path = working / "stages/phase-1/handoff.md"
        path.write_text(handoff(*STAGES[0][:3], marker="v2"), encoding="utf-8")
        result = run(working, "seal", "--stage", STAGES[0][0])
        assert "invalidated=phase_2_idea_confirmation,phase_3_final_drafting,phase_4_review_delivery" in result.stdout
        status = run(working, "status")
        assert "next_stage=phase_2_idea_confirmation" in status.stdout
        run(working, "validate", "--require-complete", expected=1)


def test_symlink_escape_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        working = base / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        external = base / "outside.md"
        external.write_text("outside\n", encoding="utf-8")
        cached = working / "stages/shared/evidence-cards.md"
        cached.unlink()
        cached.symlink_to(external)
        result = run(working, "seal", "--stage", STAGES[0][0], expected=1)
        assert "越界" in result.stderr or "符号链接" in result.stderr


def test_nested_json_cell_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        path = working / "stages/phase-1/research.tsv"
        path.write_text(
            "lane\tquery_id\tsource_id\tevidence_status\tlocator\tconclusion\n"
            'object\tQ1\tEM1\tevidence_found\thttps://example.com\t{"repeated":"payload"}\n',
            encoding="utf-8",
        )
        result = run(working, "seal", "--stage", STAGES[0][0], expected=1)
        assert "不得嵌套 JSON" in result.stderr


def main() -> None:
    tests = (
        test_complete_chain_and_status,
        test_tamper_and_header_failure,
        test_upstream_change_invalidates_downstream,
        test_symlink_escape_is_rejected,
        test_nested_json_cell_is_rejected,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"stage handoff tests passed: {len(tests)}")


if __name__ == "__main__":
    main()
