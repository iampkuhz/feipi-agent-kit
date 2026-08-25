#!/usr/bin/env python3
"""Focused regression tests for the compact stage handoff chain."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "stage_handoff.py"
D1_SHA256 = "a" * 64
D2_SHA256 = "b" * 64
DOC_SHA256 = "c" * 64
STALE_SHA256 = "d" * 64
D1_OUTPUT_DIR = "disclosure-workspace/diagrams/D1-component-overview"
D2_OUTPUT_DIR = "disclosure-workspace/diagrams/D2-main-flow"
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


def task_packet(input_name: str, judgment: str) -> str:
    return (
        "# Task\n\n"
        f"## 输入\n\n- {input_name}\n\n"
        f"## 需要判断\n\n- {judgment}\n\n"
        "## 返回\n\n- compact rows\n"
    )


def diagram_plan(*diagram_ids: str) -> str:
    purposes = {
        "D1": "component-overview",
        "D2": "main-flow",
    }
    diagrams = []
    for diagram_id in diagram_ids:
        purpose = purposes.get(diagram_id, f"detail-{diagram_id.lower()}")
        diagrams.append(
            {
                "diagram_id": diagram_id,
                "purpose": purpose,
                "output_dir": f"disclosure-workspace/diagrams/{diagram_id}-{purpose}",
            }
        )
    return json.dumps({"diagrams": diagrams}, ensure_ascii=False) + "\n"


def populate(working: Path) -> None:
    stage_root = working / "stages"
    write(
        stage_root / "shared/material-index.tsv",
        "source_id\tsource_type\tpath_or_locator\tsha256\trelevant_anchors\n"
        "SF1\tuser_file\tinput.md\tabcd\tL1-L3\n",
    )
    write(stage_root / "shared/evidence-cards.md", "# Evidence\n\n- SF1: compact fact\n")
    write(stage_root / "agents/subject-boundary-task.md", task_packet("SF1", "boundary"))
    write(stage_root / "agents/prior-art-object-task.md", task_packet("object terms", "relevance"))
    write(stage_root / "agents/prior-art-mechanism-task.md", task_packet("mechanism terms", "relevance"))
    write(stage_root / "agents/innovation-value-task.md", task_packet("joined facts", "value chain"))
    write(stage_root / "phase-1/analysis-plan.json", '{"status":"ready"}\n')
    write(stage_root / "phase-1/delivery-goals.md", "# Delivery goals\n\n- external + internal\n")
    write(
        stage_root / "phase-1/subject-boundary.tsv",
        "subject_id\ttechnical_object\tuse_scenario\tbusiness_domain\tsystem_owner\tphysical_boundary\timplemented_scope\textension_scope\tcore_mechanism\n"
        "SUB1\tobject\tscene\tdomain\towner\tboundary\tSF1\tIE1\tmechanism\n",
    )
    research_header = "lane\tquery_id\tsource_id\tevidence_status\tlocator\tconclusion\n"
    write(
        stage_root / "phase-1/research-object.tsv",
        research_header + "object\tQ1\tEM1\tevidence_found\thttps://example.com/object\tbaseline\n",
    )
    write(
        stage_root / "phase-1/research-mechanism.tsv",
        research_header + "mechanism\tQ2\tEM2\tevidence_found\thttps://example.com/mechanism\tbaseline\n",
    )
    write(
        stage_root / "phase-1/innovation-candidates.tsv",
        "candidate_id\tsource_fact_ids\textension_ids\tproblem\tmechanism\tconstraint\tbaseline\tdifference_hypothesis\tvalue_chain\teffect\tvalidation_status\tdiagram_landing\n"
        "I1\tSF1\tIE1\tproblem\tmechanism\tconstraint\tbaseline\tdifference\tvalue\tT1\tprovisional\tD1\n",
    )
    write(stage_root / "phase-1/model.md", "# Model\n\n- I1 -> T1\n")
    write(
        stage_root / "phase-1/research.tsv",
        research_header + "object\tQ1\tEM1\tevidence_found\thttps://example.com\tbaseline\n",
    )
    write(stage_root / "phase-2/decision.md", "# Decision\n\nconfirmed\n")
    write(stage_root / "phase-3/content-core.json", '{"status":"frozen"}\n')
    write(stage_root / "phase-3/diagram-plan.json", diagram_plan("D1", "D2"))
    for diagram_id in ("D1", "D2"):
        write(
            stage_root / f"agents/diagram-{diagram_id}-task.md",
            task_packet(diagram_id, "diagram package"),
        )
        write(
            stage_root / f"phase-3/diagrams/{diagram_id}-result.tsv",
            "artifact_id\tpath\tsha256\towner\tstatus\n"
            f"{diagram_id}\t{D1_OUTPUT_DIR if diagram_id == 'D1' else D2_OUTPUT_DIR}\t"
            f"{D1_SHA256 if diagram_id == 'D1' else D2_SHA256}\tpatent_diagram_engineer\tready\n",
        )
    write(
        stage_root / "phase-3/diagram-result.tsv",
        "artifact_id\tpath\tsha256\towner\tstatus\n"
        f"D1\t{D1_OUTPUT_DIR}\t{D1_SHA256}\tpatent_diagram_engineer\tready\n"
        f"D2\t{D2_OUTPUT_DIR}\t{D2_SHA256}\tpatent_diagram_engineer\tready\n",
    )
    write(
        stage_root / "phase-3/build-map.tsv",
        "artifact_id\tpath\tsha256\towner\tstatus\n"
        f"D1\t{D1_OUTPUT_DIR}\t{D1_SHA256}\tpatent_diagram_engineer\tready\n"
        f"D2\t{D2_OUTPUT_DIR}\t{D2_SHA256}\tpatent_diagram_engineer\tready\n",
    )
    write(stage_root / "agents/semantic-review-task.md", task_packet("phase-3", "semantic quality"))
    write(
        stage_root / "phase-4/review-plan.json",
        '{"diagrams":["D1","D2"],"artifacts":["DOC"]}\n',
    )
    for diagram_id in ("D1", "D2"):
        write(
            stage_root / f"agents/visual-review-{diagram_id}-task.md",
            task_packet(diagram_id, "visual quality"),
        )
        write(
            stage_root / f"phase-4/visual/{diagram_id}-review.tsv",
            "artifact_id\treview_type\tstatus\tbound_sha256\tconclusion\n"
            f"{diagram_id}\tvisual\tpass\t"
            f"{D1_SHA256 if diagram_id == 'D1' else D2_SHA256}\tclear\n",
        )
    write(
        stage_root / "phase-4/semantic-review.tsv",
        "artifact_id\treview_type\tstatus\tbound_sha256\tconclusion\n"
        f"DOC\tsemantic\tpass\t{DOC_SHA256}\tcoherent\n",
    )
    write(
        stage_root / "phase-4/review.tsv",
        "artifact_id\treview_type\tstatus\tbound_sha256\tconclusion\n"
        f"DOC\tsemantic\tpass\t{DOC_SHA256}\tcoherent\n"
        f"D1\tvisual\tpass\t{D1_SHA256}\tclear\n"
        f"D2\tvisual\tpass\t{D2_SHA256}\tclear\n",
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
        path.write_text(
            path.read_text(encoding="utf-8")
            + "DOC\tdisclosure.md\tbead\tmain_agent\tready\n",
            encoding="utf-8",
        )
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


def test_rewind_truncates_state_and_allows_current_stage_noop() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        seal_all(working)
        cached = working / "stages/phase-3/build-map.tsv"
        cached_before = cached.read_bytes()

        result = run(working, "rewind", "--stage", STAGES[1][0])
        assert f"rewound={STAGES[1][0]}" in result.stdout
        assert (
            "invalidated="
            "phase_2_idea_confirmation,phase_3_final_drafting,phase_4_review_delivery"
        ) in result.stdout
        assert "valid_stages=1" in result.stdout
        assert f"next_stage={STAGES[1][0]}" in result.stdout
        assert cached.read_bytes() == cached_before

        status = run(working, "status")
        assert f"next_stage={STAGES[1][0]}" in status.stdout
        assert "next_input=stages/phase-1/handoff.md" in status.stdout

        state_before = (working / "stages/stage-state.tsv").read_bytes()
        result = run(working, "rewind", "--stage", STAGES[1][0])
        assert "invalidated=none" in result.stdout
        assert "valid_stages=1" in result.stdout
        assert (working / "stages/stage-state.tsv").read_bytes() == state_before


def test_rewind_allows_damaged_downstream_and_preserves_cache() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        seal_all(working)
        damaged = working / "stages/phase-3/build-map.tsv"
        damaged.write_text(damaged.read_text(encoding="utf-8") + "damaged\n", encoding="utf-8")

        result = run(working, "rewind", "--stage", STAGES[1][0])
        assert f"rewound={STAGES[1][0]}" in result.stdout
        assert "valid_stages=1" in result.stdout
        assert damaged.read_text(encoding="utf-8").endswith("damaged\n")
        result = run(working, "validate")
        assert "valid_stages=1" in result.stdout


def test_rewind_rejects_unreachable_future_stage() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        run(working, "seal", "--stage", STAGES[0][0])
        state_path = working / "stages/stage-state.tsv"
        state_before = state_path.read_bytes()

        result = run(working, "rewind", "--stage", STAGES[2][0], expected=1)
        assert f"回退阶段尚不可达：{STAGES[2][0]}" in result.stderr
        assert state_path.read_bytes() == state_before
        status = run(working, "status")
        assert f"next_stage={STAGES[1][0]}" in status.stdout


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


def test_invalid_json_plan_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        write(working / "stages/phase-3/diagram-plan.json", "[]\n")
        run(working, "seal", "--stage", STAGES[0][0])
        run(working, "seal", "--stage", STAGES[1][0])
        result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
        assert "顶层必须是对象" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        write(working / "stages/phase-3/diagram-plan.json", "{\n")
        run(working, "seal", "--stage", STAGES[0][0])
        run(working, "seal", "--stage", STAGES[1][0])
        result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
        assert "无法解析" in result.stderr


def test_phase3_requires_every_planned_task_and_result() -> None:
    for missing, expected_message in (
        ("stages/agents/diagram-D2-task.md", "逐图任务集合"),
        ("stages/phase-3/diagrams/D2-result.tsv", "逐图结果集合"),
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            (working / missing).unlink()
            run(working, "seal", "--stage", STAGES[0][0])
            run(working, "seal", "--stage", STAGES[1][0])
            result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
            assert expected_message in result.stderr
            assert "missing=D2" in result.stderr


def test_phase3_rejects_duplicate_or_discontinuous_plan_ids() -> None:
    for plan, expected_message in (
        (diagram_plan("D1", "D1"), "图示编号重复"),
        (diagram_plan("D1", "D3"), "不得断号"),
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            write(working / "stages/phase-3/diagram-plan.json", plan)
            run(working, "seal", "--stage", STAGES[0][0])
            run(working, "seal", "--stage", STAGES[1][0])
            result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
            assert expected_message in result.stderr


def test_phase3_rejects_aggregate_mismatch_unsafe_path_and_symlink() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        write(
            working / "stages/phase-3/diagram-result.tsv",
            "artifact_id\tpath\tsha256\towner\tstatus\n"
            f"D1\t{D1_OUTPUT_DIR}\t{D1_SHA256}\tpatent_diagram_engineer\tready\n",
        )
        run(working, "seal", "--stage", STAGES[0][0])
        run(working, "seal", "--stage", STAGES[1][0])
        result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
        assert "聚合图示结果集合" in result.stderr
        assert "missing=D2" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        path = working / "stages/phase-3/diagrams/D2-result.tsv"
        path.write_text(
            path.read_text(encoding="utf-8").replace(D2_OUTPUT_DIR, "../outside"),
            encoding="utf-8",
        )
        run(working, "seal", "--stage", STAGES[0][0])
        run(working, "seal", "--stage", STAGES[1][0])
        result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
        assert "包内相对路径" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        working = base / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        result_file = working / "stages/phase-3/diagrams/D2-result.tsv"
        external = base / "D2-result.tsv"
        external.write_text(result_file.read_text(encoding="utf-8"), encoding="utf-8")
        result_file.unlink()
        result_file.symlink_to(external)
        run(working, "seal", "--stage", STAGES[0][0])
        run(working, "seal", "--stage", STAGES[1][0])
        result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
        assert "符号链接" in result.stderr or "越界" in result.stderr


def test_phase4_requires_exact_visual_sets() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        (working / "stages/phase-4/visual/D2-review.tsv").unlink()
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "逐图视觉复核结果集合" in result.stderr
        assert "missing=D2" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        write(working / "stages/phase-4/review-plan.json", '{"diagrams":["D1","D3"]}\n')
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "终审计划图示集合" in result.stderr
        assert "missing=D2" in result.stderr and "extra=D3" in result.stderr


def test_phase4_rejects_build_map_or_result_id_misalignment() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        write(
            working / "stages/phase-3/build-map.tsv",
            "artifact_id\tpath\tsha256\towner\tstatus\n"
            f"D1\t{D1_OUTPUT_DIR}\t{D1_SHA256}\tpatent_diagram_engineer\tready\n",
        )
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "build map 图示集合" in result.stderr
        assert "missing=D2" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        review = working / "stages/phase-4/visual/D2-review.tsv"
        review.write_text(
            review.read_text(encoding="utf-8").replace("D2\tvisual", "D1\tvisual"),
            encoding="utf-8",
        )
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "必须且只能包含 D2" in result.stderr


def test_phase3_and_phase4_reject_stale_hash_bindings() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        result_file = working / "stages/phase-3/diagrams/D2-result.tsv"
        result_file.write_text(
            result_file.read_text(encoding="utf-8").replace(D2_SHA256, STALE_SHA256),
            encoding="utf-8",
        )
        run(working, "seal", "--stage", STAGES[0][0])
        run(working, "seal", "--stage", STAGES[1][0])
        result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
        assert "逐图、聚合结果与 build map 的 hash 不一致：D2" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        visual = working / "stages/phase-4/visual/D2-review.tsv"
        visual.write_text(
            visual.read_text(encoding="utf-8").replace(D2_SHA256, STALE_SHA256),
            encoding="utf-8",
        )
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "逐图视觉复核 hash 未绑定当前 build map：D2" in result.stderr


def test_phase3_rejects_invalid_diagram_row_fields() -> None:
    mutations = (
        (D2_SHA256, "notsha", "sha256 必须是 64 位"),
        (D2_OUTPUT_DIR, ".", "D 行 path 必须落入对应图示独占目录"),
        (
            D2_OUTPUT_DIR,
            "disclosure-workspace/diagrams/D2-wrong-purpose",
            "path 未绑定 diagram plan",
        ),
        ("patent_diagram_engineer", "wrong_owner", "D 行 owner 不符合制图职责"),
        ("\tready\n", "\tblocked\n", "D 行 status 必须为 ready"),
    )
    relatives = (
        "stages/phase-3/diagrams/D2-result.tsv",
        "stages/phase-3/diagram-result.tsv",
        "stages/phase-3/build-map.tsv",
    )
    for old, new, expected_message in mutations:
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            for relative in relatives:
                path = working / relative
                path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
            run(working, "seal", "--stage", STAGES[0][0])
            run(working, "seal", "--stage", STAGES[1][0])
            result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
            assert expected_message in result.stderr


def test_phase4_requires_semantic_join_and_successful_review_rows() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        review = working / "stages/phase-4/review.tsv"
        review.write_text(
            "artifact_id\treview_type\tstatus\tbound_sha256\tconclusion\n"
            f"D1\tvisual\tpass\t{D1_SHA256}\tclear\n"
            f"D2\tvisual\tpass\t{D2_SHA256}\tclear\n",
            encoding="utf-8",
        )
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "未完整汇合 semantic-review.tsv" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        for relative in (
            "stages/phase-4/semantic-review.tsv",
            "stages/phase-4/review.tsv",
        ):
            path = working / relative
            path.write_text(
                path.read_text(encoding="utf-8").replace("semantic\tpass", "semantic\tblocked"),
                encoding="utf-8",
            )
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "语义复核 status 必须为 pass" in result.stderr

    for old, new, expected_message in (
        (D2_SHA256, "notsha", "bound_sha256 必须是 64 位"),
        ("visual\tpass", "visual\tblocked", "逐图复核 status 必须为 pass"),
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            for stage, _, _, _ in STAGES[:3]:
                run(working, "seal", "--stage", stage)
            for relative in (
                "stages/phase-4/visual/D2-review.tsv",
                "stages/phase-4/review.tsv",
            ):
                path = working / relative
                path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
            result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
            assert expected_message in result.stderr


def main() -> None:
    tests = (
        test_complete_chain_and_status,
        test_tamper_and_header_failure,
        test_upstream_change_invalidates_downstream,
        test_rewind_truncates_state_and_allows_current_stage_noop,
        test_rewind_allows_damaged_downstream_and_preserves_cache,
        test_rewind_rejects_unreachable_future_stage,
        test_symlink_escape_is_rejected,
        test_nested_json_cell_is_rejected,
        test_invalid_json_plan_is_rejected,
        test_phase3_requires_every_planned_task_and_result,
        test_phase3_rejects_duplicate_or_discontinuous_plan_ids,
        test_phase3_rejects_aggregate_mismatch_unsafe_path_and_symlink,
        test_phase4_requires_exact_visual_sets,
        test_phase4_rejects_build_map_or_result_id_misalignment,
        test_phase3_and_phase4_reject_stale_hash_bindings,
        test_phase3_rejects_invalid_diagram_row_fields,
        test_phase4_requires_semantic_join_and_successful_review_rows,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"stage handoff tests passed: {len(tests)}")


if __name__ == "__main__":
    main()
