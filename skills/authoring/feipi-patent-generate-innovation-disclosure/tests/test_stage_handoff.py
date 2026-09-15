#!/usr/bin/env python3
"""Focused regression tests for the compact stage handoff chain."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/stage_handoff.py"
D1_SVG = "<svg><title>D1</title></svg>\n"
D2_SVG = "<svg><title>D2</title></svg>\n"
D1_SHA256 = hashlib.sha256(D1_SVG.encode("utf-8")).hexdigest()
D2_SHA256 = hashlib.sha256(D2_SVG.encode("utf-8")).hexdigest()
STALE_SHA256 = "d" * 64
D1_OUTPUT_DIR = "disclosure-workspace/diagrams/D1-component-overview"
D2_OUTPUT_DIR = "disclosure-workspace/diagrams/D2-main-flow"
STAGES = (
    ("phase_1_material_modeling", "phase_2_idea_confirmation", "ready", "phase-1"),
    ("phase_2_idea_confirmation", "phase_3_final_drafting", "confirmed", "phase-2"),
    ("phase_3_final_drafting", "phase_4_review_delivery", "built", "phase-3"),
    ("phase_4_review_delivery", "delivery", "reviewed", "phase-4"),
)
SEMANTIC_CHECK_IDS = (
    "SEM-IMPLEMENTATION",
    "SEM-SYSTEM-BOUNDARY",
    "SEM-INNOVATION-VALUE",
    "SEM-GENERALIZATION",
    "SEM-CAUSALITY",
    "SEM-FLOW",
    "SEM-KEYWORDS",
    "SEM-EVIDENCE",
    "SEM-PUBLIC-LEAK",
)
TASK_TIMING_PATH = "disclosure-workspace/working/session-timing.jsonl"
TASK_EVENT_CONTRACT = "MILESTONE|DECISION|BLOCKED|COMPLETE；仅一行；最多 240 字符"
TASK_FORBIDDEN_ACTIONS = "读取未列输入|写入未授权路径|返回日志或推理过程"
TASK_DENY_LINES = (
    "- 只读取上述动态输入；禁止读取完整阶段缓存、原始材料、未列出的会话文件或其他任务的输入切片。",
    "- 除“本 Skill 资源”所列文件外，禁止读取本 Skill 其他资源。",
    "- 除“依赖 Skill”所列 Skill 外，禁止加载其他 Skill。",
)
TASK_CONTRACT_IDS = {
    "subject-boundary": ("JUDGMENT-SUBJECT-BOUNDARY-V1", "RETURN-SUBJECT-BOUNDARY-TSV-V1"),
    "prior-art-object": ("JUDGMENT-PRIOR-ART-OBJECT-V1", "RETURN-PRIOR-ART-OBJECT-TSV-V1"),
    "prior-art-mechanism": (
        "JUDGMENT-PRIOR-ART-MECHANISM-V1", "RETURN-PRIOR-ART-MECHANISM-TSV-V1",
    ),
    "innovation-value": ("JUDGMENT-INNOVATION-VALUE-V1", "RETURN-INNOVATION-VALUE-TSV-V1"),
    "semantic-review": ("JUDGMENT-SEMANTIC-REVIEW-V1", "RETURN-SEMANTIC-REVIEW-TSV-V1"),
}
PHASE_1_SOURCE_SETS = {
    "subject-boundary": (
        "disclosure-workspace/working/stages/shared/material-index.tsv",
        "disclosure-workspace/working/stages/shared/evidence-cards.md",
        "disclosure-workspace/working/stages/phase-1/analysis-plan.json",
    ),
    "prior-art-object": (
        "disclosure-workspace/working/stages/shared/material-index.tsv",
        "disclosure-workspace/working/stages/shared/evidence-cards.md",
        "disclosure-workspace/working/stages/phase-1/analysis-plan.json",
    ),
    "prior-art-mechanism": (
        "disclosure-workspace/working/stages/shared/material-index.tsv",
        "disclosure-workspace/working/stages/shared/evidence-cards.md",
        "disclosure-workspace/working/stages/phase-1/analysis-plan.json",
    ),
    "innovation-value": (
        "disclosure-workspace/working/stages/shared/evidence-cards.md",
        "disclosure-workspace/working/stages/phase-1/delivery-goals.md",
        "disclosure-workspace/working/stages/phase-1/subject-boundary.tsv",
        "disclosure-workspace/working/stages/phase-1/research.tsv",
    ),
}


def run(
    working: Path,
    *args: str,
    expected: int = 0,
    hash_seed: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = None if hash_seed is None else {**os.environ, "PYTHONHASHSEED": hash_seed}
    result = subprocess.run(
        ["python3", str(SCRIPT), *args, "--working", str(working)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_file_set_digest(disclosure_dir: Path, paths: tuple[str, ...] | list[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(paths):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(disclosure_dir / value).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


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


def task_packet(
    working: Path,
    task_type: str,
    _judgment: str,
    *,
    diagram_id: str | None = None,
    purpose: str | None = None,
) -> str:
    fixed = {
        "subject-boundary": (
            "patent_subject_boundary_analyst", "phase-1-subject-boundary",
            "disclosure-workspace/working/stages/phase-1/subject-boundary.tsv", "无",
            "references/roles/subject-boundary.md", "无",
        ),
        "prior-art-object": (
            "patent_prior_art_researcher", "phase-1-research-object",
            "disclosure-workspace/working/stages/phase-1/research-object.tsv", "无",
            "references/roles/prior-art-research.md", "无",
        ),
        "prior-art-mechanism": (
            "patent_prior_art_researcher", "phase-1-research-mechanism",
            "disclosure-workspace/working/stages/phase-1/research-mechanism.tsv", "无",
            "references/roles/prior-art-research.md", "无",
        ),
        "innovation-value": (
            "patent_innovation_value_analyst", "phase-1-innovation-candidates",
            "disclosure-workspace/working/stages/phase-1/innovation-candidates.tsv", "无",
            "references/roles/innovation-value.md", "无",
        ),
        "semantic-review": (
            "patent_semantic_reviewer", "phase-4-semantic-review",
            "disclosure-workspace/working/stages/phase-4/semantic-review.tsv", "无",
            "references/reviews/semantic-review.md", "无",
        ),
    }
    if task_type == "diagram":
        assert diagram_id and purpose
        role = "patent_diagram_engineer"
        checkpoint = f"phase-3-diagram-{diagram_id}"
        result = f"disclosure-workspace/working/stages/phase-3/diagrams/{diagram_id}-result.tsv"
        allowed_writes = f"disclosure-workspace/diagrams/{diagram_id}-{purpose}/"
        resources = "references/roles/diagram-engineer.md"
        dependencies = "feipi-plantuml-generate-diagram"
        judgment_contract_id = f"JUDGMENT-DIAGRAM-{diagram_id}-V1"
        return_contract_id = f"RETURN-DIAGRAM-{diagram_id}-TSV-V1"
    elif task_type == "visual-review":
        assert diagram_id and purpose
        role = "patent_visual_reviewer"
        checkpoint = f"phase-4-visual-review-{diagram_id}"
        result = f"disclosure-workspace/working/stages/phase-4/visual/{diagram_id}-review.tsv"
        allowed_writes = "无"
        resources = "references/reviews/visual-review.md"
        dependencies = "无"
        judgment_contract_id = f"JUDGMENT-VISUAL-REVIEW-{diagram_id}-V1"
        return_contract_id = f"RETURN-VISUAL-REVIEW-{diagram_id}-TSV-V1"
    else:
        role, checkpoint, result, allowed_writes, resources, dependencies = fixed[task_type]
        judgment_contract_id, return_contract_id = TASK_CONTRACT_IDS[task_type]

    if task_type in {"subject-boundary", "prior-art-object", "prior-art-mechanism", "innovation-value"}:
        dynamic_paths = [
            f"disclosure-workspace/working/stages/agents/inputs/{task_type}-input.json"
        ]
    elif task_type == "diagram":
        dynamic_paths = [
            f"disclosure-workspace/working/stages/agents/inputs/diagram-{diagram_id}-input.json"
        ]
    elif task_type == "semantic-review":
        dynamic_paths = [
            "disclosure.md",
            "disclosure-workspace/disclosure-internal.md",
            "disclosure-workspace/disclosure-manifest.json",
            "disclosure-workspace/working/stages/phase-3/handoff.md",
        ]
    else:
        output_dir = f"disclosure-workspace/diagrams/{diagram_id}-{purpose}"
        dynamic_paths = [
            f"{output_dir}/{name}"
            for name in ("brief.normalized.yaml", "diagram.puml", "diagram.svg", "validation.json")
        ]

    disclosure_dir = working.parent.parent
    dynamic_lines = "\n".join(
        f"- path：`{path}`；sha256：`{sha256(disclosure_dir / path)}`"
        for path in dynamic_paths
    )
    return (
        "# Subagent 任务包\n\n"
        "- contract_version: `2`\n"
        f"- task_type: `{task_type}`\n"
        f"- role: `{role}`\n"
        f"- checkpoint: `{checkpoint}`\n"
        f"- result: `{result}`\n"
        "- result_owner: `main_agent`\n"
        "- minimum_check: `tsv`\n"
        f"- timing: `{TASK_TIMING_PATH}`\n"
        f"- 关键事件: `{TASK_EVENT_CONTRACT}`\n"
        f"- 允许写入: `{allowed_writes}`\n"
        f"- 本 Skill 资源: `{resources}`\n"
        f"- 依赖 Skill: `{dependencies}`\n"
        f"- 禁止动作: `{TASK_FORBIDDEN_ACTIONS}`\n\n"
        "## 输入\n\n"
        "### 动态输入\n\n"
        f"{dynamic_lines}\n\n"
        f"{TASK_DENY_LINES[0]}\n{TASK_DENY_LINES[1]}\n{TASK_DENY_LINES[2]}\n\n"
        f"## 需要判断\n\n- contract_id: `{judgment_contract_id}`\n\n"
        f"## 返回\n\n- contract_id: `{return_contract_id}`\n"
        "- `result_owner=main_agent` 时，subagent 只返回符合 `minimum_check` 的结构化内容，由主 agent 校验后写入 `result`。\n"
        "- 只返回结构化结果与一行终态关键事件，不返回日志、正文副本或推理过程。\n"
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


def slice_envelope(
    working: Path,
    task_type: str,
    role: str,
    checkpoint: str,
    source_paths: tuple[str, ...],
    payload: dict[str, object],
    **extra: object,
) -> str:
    value = {
        "slice_version": 1,
        "task_type": task_type,
        "role": role,
        "checkpoint": checkpoint,
        "source_set_sha256": normalized_file_set_digest(working.parent.parent, source_paths),
        "payload": payload,
        **extra,
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"


def populate(working: Path) -> None:
    stage_root = working / "stages"
    disclosure_dir = working.parent.parent
    for stage, next_stage, status, folder in STAGES:
        write(stage_root / folder / "handoff.md", handoff(stage, next_stage, status))
    write(
        stage_root / "shared/material-index.tsv",
        "source_id\tsource_type\tpath_or_locator\tsha256\trelevant_anchors\n"
        "SF1\tuser_file\tinput.md\tabcd\tL1-L3\n",
    )
    write(stage_root / "shared/evidence-cards.md", "# Evidence\n\n- SF1: compact fact\n")
    write(stage_root / "phase-1/analysis-plan.json", '{"status":"ready"}\n')
    write(stage_root / "phase-1/delivery-goals.md", "# Delivery goals\n\n- external + internal\n")
    write(
        stage_root / "phase-1/subject-boundary.tsv",
        "subject_id\ttechnical_object\tuse_scenario\tbusiness_domain\tsystem_owner\tphysical_boundary\timplemented_scope\textension_scope\tcore_mechanism\n"
        "SUB1\tobject\tscene\tdomain\towner\tboundary\tSF1\tIE1\tmechanism\n",
    )
    research_header = "lane\tquery_id\tsource_id\tevidence_status\tlocator\tconclusion\n"
    write(
        stage_root / "phase-1/research.tsv",
        research_header + "object\tQ1\tEM1\tevidence_found\thttps://example.com\tbaseline\n",
    )
    phase_1_specs = {
        "subject-boundary": ("patent_subject_boundary_analyst", "phase-1-subject-boundary"),
        "prior-art-object": ("patent_prior_art_researcher", "phase-1-research-object"),
        "prior-art-mechanism": ("patent_prior_art_researcher", "phase-1-research-mechanism"),
        "innovation-value": ("patent_innovation_value_analyst", "phase-1-innovation-candidates"),
    }
    for task_type, (role, checkpoint) in phase_1_specs.items():
        payload: dict[str, object] = {"fact_ids": ["SF1"], "scope": task_type}
        if task_type.startswith("prior-art-"):
            payload["research_url"] = "https://example.com/research-only-in-payload"
        write(
            stage_root / f"agents/inputs/{task_type}-input.json",
            slice_envelope(
                working,
                task_type,
                role,
                checkpoint,
                PHASE_1_SOURCE_SETS[task_type],
                payload,
            ),
        )
    write(
        stage_root / "agents/subject-boundary-task.md",
        task_packet(working, "subject-boundary", "boundary"),
    )
    write(
        stage_root / "agents/prior-art-object-task.md",
        task_packet(working, "prior-art-object", "relevance"),
    )
    write(
        stage_root / "agents/prior-art-mechanism-task.md",
        task_packet(working, "prior-art-mechanism", "relevance"),
    )
    write(
        stage_root / "agents/innovation-value-task.md",
        task_packet(working, "innovation-value", "value chain"),
    )
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
    renderer_preflight = stage_root / "phase-3/renderer-preflight.json"
    write(
        renderer_preflight,
        json.dumps(
            {
                "schema_version": "1",
                "final_status": "success",
                "renderer_url": "http://127.0.0.1:8199",
                "blocked_reason": "",
                "startup_policy": "podman_once",
                "process_management_allowed": False,
            },
            ensure_ascii=False,
        ) + "\n",
    )
    write(disclosure_dir / "disclosure.md", "# Disclosure\n\nPublic frozen draft.\n")
    write(
        disclosure_dir / "disclosure-workspace/disclosure-internal.md",
        "# Disclosure\n\nPublic frozen draft.\n\n# Internal\n\nTrace.\n",
    )
    write(
        disclosure_dir / "disclosure-workspace/disclosure-manifest.json",
        '{"status":"frozen"}\n',
    )
    for diagram_id in ("D1", "D2"):
        purpose = "component-overview" if diagram_id == "D1" else "main-flow"
        output_dir = disclosure_dir / f"disclosure-workspace/diagrams/{diagram_id}-{purpose}"
        write(
            stage_root / f"agents/inputs/diagram-{diagram_id}-input.json",
            slice_envelope(
                working,
                "diagram",
                "patent_diagram_engineer",
                f"phase-3-diagram-{diagram_id}",
                (
                    "disclosure-workspace/working/stages/phase-3/content-core.json",
                    "disclosure-workspace/working/stages/phase-3/diagram-plan.json",
                ),
                {
                    "implemented_ids": ["SF1"],
                    "output_dir": f"disclosure-workspace/diagrams/{diagram_id}-{purpose}",
                    "renderer_url": "http://127.0.0.1:8199",
                    "renderer_preflight_sha256": sha256(renderer_preflight),
                },
                diagram_id=diagram_id,
                purpose=purpose,
                diagram_plan_sha256=sha256(stage_root / "phase-3/diagram-plan.json"),
            ),
        )
        write(output_dir / "brief.normalized.yaml", f"diagram_id: {diagram_id}\n")
        write(output_dir / "diagram.puml", f"@startuml\ntitle {diagram_id}\n@enduml\n")
        write(output_dir / "diagram.svg", D1_SVG if diagram_id == "D1" else D2_SVG)
        write(output_dir / "validation.json", '{"final_status":"success"}\n')
        write(
            stage_root / f"agents/diagram-{diagram_id}-task.md",
            task_packet(
                working,
                "diagram",
                "diagram package",
                diagram_id=diagram_id,
                purpose=purpose,
            ),
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
    write(
        stage_root / "agents/semantic-review-task.md",
        task_packet(working, "semantic-review", "semantic quality"),
    )
    write(
        stage_root / "phase-4/review-plan.json",
        '{"diagrams":["D1","D2"],"artifacts":["DOC"]}\n',
    )
    for diagram_id in ("D1", "D2"):
        purpose = "component-overview" if diagram_id == "D1" else "main-flow"
        write(
            stage_root / f"agents/visual-review-{diagram_id}-task.md",
            task_packet(
                working,
                "visual-review",
                "visual quality",
                diagram_id=diagram_id,
                purpose=purpose,
            ),
        )
        write(
            stage_root / f"phase-4/visual/{diagram_id}-review.tsv",
            "artifact_id\treview_type\tstatus\tbound_sha256\tconclusion\n"
            f"{diagram_id}\tvisual\tpass\t"
            f"{D1_SHA256 if diagram_id == 'D1' else D2_SHA256}\tclear\n",
        )
    semantic_inputs = (
        "disclosure.md",
        "disclosure-workspace/disclosure-internal.md",
        "disclosure-workspace/disclosure-manifest.json",
        "disclosure-workspace/working/stages/phase-3/handoff.md",
    )
    semantic_bound_sha256 = normalized_file_set_digest(disclosure_dir, semantic_inputs)
    semantic_rows = "".join(
        f"{check_id}\tsemantic\tpass\t{semantic_bound_sha256}\tcoherent\n"
        for check_id in SEMANTIC_CHECK_IDS
    )
    write(
        stage_root / "phase-4/semantic-review.tsv",
        "artifact_id\treview_type\tstatus\tbound_sha256\tconclusion\n" + semantic_rows,
    )
    write(
        stage_root / "phase-4/review.tsv",
        "artifact_id\treview_type\tstatus\tbound_sha256\tconclusion\n"
        + semantic_rows
        +
        f"D1\tvisual\tpass\t{D1_SHA256}\tclear\n"
        f"D2\tvisual\tpass\t{D2_SHA256}\tclear\n",
    )
    task_paths = [
        "stages/agents/subject-boundary-task.md",
        "stages/agents/prior-art-object-task.md",
        "stages/agents/prior-art-mechanism-task.md",
        "stages/agents/innovation-value-task.md",
        "stages/agents/diagram-D1-task.md",
        "stages/agents/diagram-D2-task.md",
        "stages/agents/semantic-review-task.md",
        "stages/agents/visual-review-D1-task.md",
        "stages/agents/visual-review-D2-task.md",
    ]
    for relative in task_paths:
        result = run(working, "validate-task", "--task", relative)
        assert "dispatch_receipt=" in result.stdout


def seal_all(working: Path) -> None:
    for stage, _, _, _ in STAGES:
        run(working, "seal", "--stage", stage)


def add_task_input(task: Path, value: str) -> None:
    text = task.read_text(encoding="utf-8")
    task.write_text(
        text.replace("\n## 需要判断", f"\n- 额外输入：{value}\n\n## 需要判断"),
        encoding="utf-8",
    )


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
        path = working / "stages/phase-1/research-object.tsv"
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


def validate_task(working: Path, relative: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    return run(working, "validate-task", "--task", relative, expected=expected)


def replace_task_text(working: Path, relative: str, old: str, new: str) -> None:
    path = working / relative
    text = path.read_text(encoding="utf-8")
    assert old in text, (relative, old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def refresh_task_input_hash(working: Path, task_relative: str, input_relative: str) -> None:
    task = working / task_relative
    lines = task.read_text(encoding="utf-8").splitlines()
    prefix = f"- path：`{input_relative}`；sha256：`"
    matches = [line for line in lines if line.startswith(prefix)]
    assert len(matches) == 1
    replacement = f"{prefix}{sha256(working.parent.parent / input_relative)}`"
    replace_task_text(working, task_relative, matches[0], replacement)


def receipt_path(working: Path, task_relative: str) -> Path:
    return working / "stages/agents/receipts" / f"{Path(task_relative).stem}.dispatch.json"


def test_validate_task_dispatch_entry_and_legal_diagram_write_dir() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for relative in (
            "stages/agents/subject-boundary-task.md",
            "stages/agents/diagram-D2-task.md",
            "stages/agents/semantic-review-task.md",
            "stages/agents/visual-review-D2-task.md",
        ):
            result = validate_task(working, relative)
            assert f"task_valid={relative}" in result.stdout
        result = validate_task(working, "stages/agents/not-registered-task.md", expected=1)
        assert "[TASK-001]" in result.stderr


def test_diagram_dispatch_requires_successful_renderer_preflight() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        preflight = working / "stages/phase-3/renderer-preflight.json"
        data = json.loads(preflight.read_text(encoding="utf-8"))
        data["final_status"] = "blocked"
        data["renderer_url"] = ""
        preflight.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
        result = validate_task(working, "stages/agents/diagram-D2-task.md", expected=1)
        assert "[TASK-004]" in result.stderr and "preflight" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        relative = "stages/agents/subject-boundary-task.md"
        replace_task_text(
            working,
            relative,
            "- role: `patent_subject_boundary_analyst`",
            "- role: `patent_prior_art_researcher`",
        )
        assert "[TASK-002]" in validate_task(working, relative, expected=1).stderr
        sealed = run(working, "seal", "--stage", STAGES[0][0], expected=1)
        assert "[TASK-002]" in sealed.stderr


def test_task_packets_bind_role_checkpoint_result_owner_and_minimum_check() -> None:
    cases = (
        ("- task_type: `subject-boundary`", "- task_type: `prior-art-object`", "TASK-002"),
        ("- role: `patent_subject_boundary_analyst`", "- role: `patent_prior_art_researcher`", "TASK-002"),
        ("- checkpoint: `phase-1-subject-boundary`", "- checkpoint: `phase-1-research-object`", "TASK-002"),
        (
            "- result: `disclosure-workspace/working/stages/phase-1/subject-boundary.tsv`",
            "- result: `disclosure-workspace/working/stages/phase-1/research-object.tsv`",
            "TASK-002",
        ),
        ("- result_owner: `main_agent`", "- result_owner: `patent_subject_boundary_analyst`", "TASK-002"),
        ("- minimum_check: `tsv`", "- minimum_check: `markdown`", "TASK-002"),
    )
    for old, new, rule_id in cases:
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            relative = "stages/agents/subject-boundary-task.md"
            replace_task_text(working, relative, old, new)
            result = validate_task(working, relative, expected=1)
            assert f"[{rule_id}]" in result.stderr


def test_task_packets_separate_instruction_refs_dependencies_and_writes() -> None:
    cases = (
        (
            "stages/agents/diagram-D2-task.md",
            "- 本 Skill 资源: `references/roles/diagram-engineer.md`",
            "- 本 Skill 资源: `feipi-plantuml-generate-diagram`",
        ),
        (
            "stages/agents/diagram-D2-task.md",
            "- 依赖 Skill: `feipi-plantuml-generate-diagram`",
            "- 依赖 Skill: `feipi-plantuml-render-proxy`",
        ),
        (
            "stages/agents/diagram-D2-task.md",
            f"- 允许写入: `{D2_OUTPUT_DIR}/`",
            f"- 允许写入: `{D1_OUTPUT_DIR}/`",
        ),
        (
            "stages/agents/semantic-review-task.md",
            "- 依赖 Skill: `无`",
            "- 依赖 Skill: `feipi-plantuml-generate-diagram`",
        ),
        (
            "stages/agents/subject-boundary-task.md",
            "- 允许写入: `无`",
            f"- 允许写入: `{D1_OUTPUT_DIR}/`",
        ),
        (
            "stages/agents/subject-boundary-task.md",
            "- 本 Skill 资源: `references/roles/subject-boundary.md`",
            "- 本 Skill 资源: `无`",
        ),
        (
            "stages/agents/prior-art-object-task.md",
            "- 本 Skill 资源: `references/roles/prior-art-research.md`",
            "- 本 Skill 资源: `references/roles/subject-boundary.md`",
        ),
        (
            "stages/agents/innovation-value-task.md",
            "- 本 Skill 资源: `references/roles/innovation-value.md`",
            "- 本 Skill 资源: `无`",
        ),
    )
    for relative, old, new in cases:
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            replace_task_text(working, relative, old, new)
            result = validate_task(working, relative, expected=1)
            assert "[TASK-003]" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        relative = "stages/agents/subject-boundary-task.md"
        replace_task_text(working, relative, TASK_DENY_LINES[0], TASK_DENY_LINES[0].replace("禁止", "允许"))
        result = validate_task(working, relative, expected=1)
        assert "[TASK-003]" in result.stderr


def test_task_packets_reject_unsafe_path_references() -> None:
    cases = (
        ("/tmp/raw.md", "禁止绝对路径"),
        ("`../raw.md`", "禁止路径越界"),
        ("`stages/shared/*.md`", "禁止通配符"),
        ("`stages/shared`", "禁止目录级宽泛引用"),
        ("`file:/tmp/raw.md`", "禁止 file URI"),
        ("`file:///tmp/raw.md`", "禁止 file URI"),
        ("`stages／shared／raw.md`", "禁止全角斜杠"),
    )
    for reference, expected_message in cases:
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            add_task_input(working / "stages/agents/subject-boundary-task.md", reference)
            result = validate_task(working, "stages/agents/subject-boundary-task.md", expected=1)
            assert "[TASK-005]" in result.stderr
            assert expected_message in result.stderr


def test_task_packets_reject_unapproved_skill_resources() -> None:
    forbidden = (
        "SKILL.md",
        "`references/stages/phase-1.md`",
        "`agents/subagents/stages/phase-1.json`",
        "`agents/subagents/roles/subject-modeler.json`",
        "`references/stage-delivery-contract.md`",
        "`references/content-quality-gates.md`",
        "`handbook/workflow-and-parallelism.md`",
        "`MAINTAINER_HISTORY.md`",
        "`cases/happy/disclosure.md`",
        "`schemas/disclosure-manifest.schema.json`",
        "`agents/subagents/checkpoint-task-catalog.json`",
        "`scripts/stage_handoff.py`",
        "`disclosure-workspace/working/stages/shared/evidence-cards.md`",
        "`disclosure-workspace/working/stages/phase-3/content-core.json`",
        "`disclosure-workspace/working/stages/phase-3/diagram-plan.json`",
    )
    for reference in forbidden:
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            add_task_input(working / "stages/agents/subject-boundary-task.md", reference)
            result = validate_task(working, "stages/agents/subject-boundary-task.md", expected=1)
            assert "[TASK-003]" in result.stderr


def test_dynamic_inputs_reject_cross_role_and_cross_diagram_access() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        subject = "disclosure-workspace/working/stages/agents/inputs/subject-boundary-input.json"
        other = "disclosure-workspace/working/stages/agents/inputs/prior-art-object-input.json"
        replace_task_text(
            working,
            "stages/agents/subject-boundary-task.md",
            f"- path：`{subject}`；sha256：`{sha256(working.parent.parent / subject)}`",
            f"- path：`{other}`；sha256：`{sha256(working.parent.parent / other)}`",
        )
        result = validate_task(working, "stages/agents/subject-boundary-task.md", expected=1)
        assert "[TASK-004]" in result.stderr and "本 task_type" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        d2 = "disclosure-workspace/working/stages/agents/inputs/diagram-D2-input.json"
        d1 = "disclosure-workspace/working/stages/agents/inputs/diagram-D1-input.json"
        replace_task_text(
            working,
            "stages/agents/diagram-D2-task.md",
            f"- path：`{d2}`；sha256：`{sha256(working.parent.parent / d2)}`",
            f"- path：`{d1}`；sha256：`{sha256(working.parent.parent / d1)}`",
        )
        result = validate_task(working, "stages/agents/diagram-D2-task.md", expected=1)
        assert "[TASK-004]" in result.stderr and "task_type/D" in result.stderr


def test_dynamic_inputs_reject_hash_size_and_symlink() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        relative = "stages/agents/subject-boundary-task.md"
        path = "disclosure-workspace/working/stages/agents/inputs/subject-boundary-input.json"
        replace_task_text(working, relative, sha256(working.parent.parent / path), "0" * 64)
        result = validate_task(working, relative, expected=1)
        assert "[TASK-004]" in result.stderr and "sha256 不匹配" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        input_path = working / "stages/agents/inputs/subject-boundary-input.json"
        input_path.write_text("x" * (13 * 1024), encoding="utf-8")
        relative = "stages/agents/subject-boundary-task.md"
        old_hash = next(
            line.split("`")[-2]
            for line in (working / relative).read_text(encoding="utf-8").splitlines()
            if "subject-boundary-input.json" in line
        )
        replace_task_text(working, relative, old_hash, sha256(input_path))
        result = validate_task(working, relative, expected=1)
        assert "[TASK-004]" in result.stderr and "超过 12 KiB" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        working = base / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        input_path = working / "stages/agents/inputs/subject-boundary-input.json"
        external = input_path.parent / "real-input.json"
        external.write_text(input_path.read_text(encoding="utf-8"), encoding="utf-8")
        input_path.unlink()
        input_path.symlink_to("real-input.json")
        result = validate_task(working, "stages/agents/subject-boundary-task.md", expected=1)
        assert "[TASK-004]" in result.stderr and "符号链接" in result.stderr


def test_semantic_review_requires_exact_nine_checks() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        for relative in ("stages/phase-4/semantic-review.tsv", "stages/phase-4/review.tsv"):
            path = working / relative
            path.write_text(
                path.read_text(encoding="utf-8").replace("SEM-FLOW", "SEM-OTHER"),
                encoding="utf-8",
            )
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "[TASK-005]" in result.stderr and "9 个 check id" in result.stderr


def test_task_packets_keep_three_sections_and_size_limit() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        task = working / "stages/agents/subject-boundary-task.md"
        task.write_text(task.read_text(encoding="utf-8") + "\n## 日志\n\n- debug\n", encoding="utf-8")
        result = validate_task(working, "stages/agents/subject-boundary-task.md", expected=1)
        assert "[TASK-001]" in result.stderr and "章节不符合合同" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        add_task_input(
            working / "stages/agents/subject-boundary-task.md",
            "x" * (13 * 1024),
        )
        result = validate_task(working, "stages/agents/subject-boundary-task.md", expected=1)
        assert "[TASK-001]" in result.stderr and "超过 12 KiB" in result.stderr


def test_seal_requires_current_dispatch_receipts() -> None:
    task_relative = "stages/agents/subject-boundary-task.md"
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        receipt_path(working, task_relative).unlink()
        result = run(working, "seal", "--stage", STAGES[0][0], expected=1)
        assert "[TASK-006]" in result.stderr and "缺少 dispatch receipt" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        task = working / task_relative
        task.write_text(task.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = run(working, "seal", "--stage", STAGES[0][0], expected=1)
        assert "[TASK-006]" in result.stderr and "失效" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        input_relative = (
            "disclosure-workspace/working/stages/agents/inputs/subject-boundary-input.json"
        )
        input_path = working.parent.parent / input_relative
        envelope = json.loads(input_path.read_text(encoding="utf-8"))
        envelope["payload"]["scope"] = "changed-after-validation"
        input_path.write_text(json.dumps(envelope, sort_keys=True) + "\n", encoding="utf-8")
        refresh_task_input_hash(working, task_relative, input_relative)
        result = run(working, "seal", "--stage", STAGES[0][0], expected=1)
        assert "[TASK-006]" in result.stderr and "失效" in result.stderr


def test_slice_envelopes_reject_cross_role_cross_diagram_and_hardlink() -> None:
    cases = (
        (
            "stages/agents/subject-boundary-task.md",
            "disclosure-workspace/working/stages/agents/inputs/subject-boundary-input.json",
            "disclosure-workspace/working/stages/agents/inputs/prior-art-object-input.json",
        ),
        (
            "stages/agents/diagram-D2-task.md",
            "disclosure-workspace/working/stages/agents/inputs/diagram-D2-input.json",
            "disclosure-workspace/working/stages/agents/inputs/diagram-D1-input.json",
        ),
    )
    for task_relative, target_relative, source_relative in cases:
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            disclosure_dir = working.parent.parent
            (disclosure_dir / target_relative).write_bytes((disclosure_dir / source_relative).read_bytes())
            refresh_task_input_hash(working, task_relative, target_relative)
            result = validate_task(working, task_relative, expected=1)
            assert "[TASK-004]" in result.stderr and "JSON envelope" in result.stderr

    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        task_relative = "stages/agents/subject-boundary-task.md"
        input_relative = (
            "disclosure-workspace/working/stages/agents/inputs/subject-boundary-input.json"
        )
        input_path = working.parent.parent / input_relative
        original = input_path.with_name("subject-boundary-source.json")
        input_path.replace(original)
        os.link(original, input_path)
        result = validate_task(working, task_relative, expected=1)
        assert "[TASK-004]" in result.stderr and "硬链接" in result.stderr


def test_task_contract_sections_reject_inline_blob_url_and_path() -> None:
    inserts = (
        ('- {"inline":"blob"}', "TASK-001"),
        ("- https://example.com/inline", "TASK-003"),
        ("- `disclosure-workspace/working/stages/shared/evidence-cards.md`", "TASK-003"),
    )
    for injected, rule_id in inserts:
        with tempfile.TemporaryDirectory() as temp_dir:
            working = Path(temp_dir) / "disclosure-workspace/working"
            run(working, "init")
            populate(working)
            relative = "stages/agents/prior-art-object-task.md"
            replace_task_text(
                working,
                relative,
                "## 需要判断\n\n",
                f"## 需要判断\n\n{injected}\n",
            )
            result = validate_task(working, relative, expected=1)
            assert f"[{rule_id}]" in result.stderr


def test_semantic_bound_digest_rejects_arbitrary_64hex() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        semantic = working / "stages/phase-4/semantic-review.tsv"
        actual = semantic.read_text(encoding="utf-8").splitlines()[1].split("\t")[3]
        bogus = "e" * 64
        for relative in ("stages/phase-4/semantic-review.tsv", "stages/phase-4/review.tsv"):
            path = working / relative
            path.write_text(path.read_text(encoding="utf-8").replace(actual, bogus), encoding="utf-8")
        for stage, _, _, _ in STAGES[:3]:
            run(working, "seal", "--stage", stage)
        result = run(working, "seal", "--stage", STAGES[3][0], expected=1)
        assert "[TASK-005]" in result.stderr and "规范化集合" in result.stderr


def test_diagram_rows_bind_actual_svg_hash() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        forged = "f" * 64
        for relative in (
            "stages/phase-3/diagrams/D2-result.tsv",
            "stages/phase-3/diagram-result.tsv",
            "stages/phase-3/build-map.tsv",
        ):
            path = working / relative
            path.write_text(path.read_text(encoding="utf-8").replace(D2_SHA256, forged), encoding="utf-8")
        for stage, _, _, _ in STAGES[:2]:
            run(working, "seal", "--stage", stage)
        result = run(working, "seal", "--stage", STAGES[2][0], expected=1)
        assert "hash 未绑定实际 diagram.svg：D2" in result.stderr


def test_normalized_digests_are_pythonhashseed_stable() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        working = Path(temp_dir) / "disclosure-workspace/working"
        run(working, "init")
        populate(working)
        relative = "stages/agents/semantic-review-task.md"
        digests = []
        for seed in ("1", "7", "999"):
            run(working, "validate-task", "--task", relative, hash_seed=seed)
            receipt = json.loads(receipt_path(working, relative).read_text(encoding="utf-8"))
            digests.append(receipt["dynamic_input_set_sha256"])
        assert len(set(digests)) == 1


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
        test_validate_task_dispatch_entry_and_legal_diagram_write_dir,
        test_diagram_dispatch_requires_successful_renderer_preflight,
        test_task_packets_bind_role_checkpoint_result_owner_and_minimum_check,
        test_task_packets_separate_instruction_refs_dependencies_and_writes,
        test_task_packets_reject_unsafe_path_references,
        test_task_packets_reject_unapproved_skill_resources,
        test_dynamic_inputs_reject_cross_role_and_cross_diagram_access,
        test_dynamic_inputs_reject_hash_size_and_symlink,
        test_semantic_review_requires_exact_nine_checks,
        test_task_packets_keep_three_sections_and_size_limit,
        test_seal_requires_current_dispatch_receipts,
        test_slice_envelopes_reject_cross_role_cross_diagram_and_hardlink,
        test_task_contract_sections_reject_inline_blob_url_and_path,
        test_semantic_bound_digest_rejects_arbitrary_64hex,
        test_diagram_rows_bind_actual_svg_hash,
        test_normalized_digests_are_pythonhashseed_stable,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"stage handoff tests passed: {len(tests)}")


if __name__ == "__main__":
    main()
