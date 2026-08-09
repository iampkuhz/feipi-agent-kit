#!/usr/bin/env python3
"""为行为测试生成自包含的合成交付包。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_puml(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def diagram_specs(variant: str) -> list[dict[str, Any]]:
    component = """@startuml
rectangle "业务入口" as A
rectangle "策略协调域" as B
rectangle "可信执行端点" as C
A --> B : E1
B --> C : E2
@enduml
"""
    if variant == "implementation_top":
        component = component.replace("业务入口", "RequestHandler")
    if variant == "implementation_table_field":
        component = component.replace("业务入口", "alarm_record.status")
    if variant == "implementation_alias_only":
        component = component.replace("as A", "as request_system").replace("A --> B", "request_system --> B")

    activity = """@startuml
start
:S1 接收请求;
:S2 校验边界;
:S3 生成计划;
:S4 执行机制;
:S5 固化结果;
stop
@enduml
"""
    if variant == "flow_mr":
        for number in range(1, 6):
            activity = activity.replace(f"S{number}", f"M{number}")
    if variant == "flow_jump":
        activity = activity.replace(":S4 执行机制;", ":S6 执行机制;")
    if variant == "flow_missing_parent":
        activity = activity.replace(":S5 固化结果;", ":S5 固化结果;\n:S9.1 子调用;")
    if variant == "flow_long_label":
        activity = activity.replace(":S4 执行机制;", ":S4 执行具有非常非常冗长参数与异常说明的核心机制;")

    specs = [
        {
            "id": "D1",
            "role": "component_overview",
            "profile": "component",
            "purpose": "说明业务边界与可信执行端点的结构关系",
            "path": "diagrams/D1-component-overview",
            "puml": component,
            "metrics": {"node_count": 3, "edge_count": 2, "max_degree": 2},
        },
        {
            "id": "D2",
            "role": "main_flow",
            "profile": "activity",
            "purpose": "说明最常见请求的端到端处理步骤",
            "path": "diagrams/D2-main-flow",
            "puml": activity,
            "metrics": {"node_count": 5, "edge_count": 4, "max_degree": 2},
        },
    ]
    if variant == "complex_deployment":
        specs.append(
            {
                "id": "D3",
                "role": "deployment_boundary",
                "profile": "deployment",
                "purpose": "说明跨网传递与离线执行的物理边界",
                "path": "diagrams/D3-deployment-boundary",
                "puml": """@startuml
node "在线网络区" as Online
node "隔离交换区" as Relay
node "离线执行区" as Offline
Online --> Relay : E1
Relay --> Offline : E2
@enduml
""",
                "metrics": {"node_count": 3, "edge_count": 2, "max_degree": 2},
            }
        )
    return specs


def build_manifest(specs: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "patent": {
            "title": "一种基于约束编排的可信处理方法/系统",
            "use_case": "在隔离边界内处理策略请求并固化可核验结果",
        },
        "input_completeness": {
            "technical_objects": ["策略请求"],
            "core_mechanisms": ["约束编排", "证据绑定"],
            "necessary_constraints": ["隔离边界"],
            "existing_problem_facts": ["跨边界处理结果无法与执行条件稳定关联"],
        },
        "boundaries": {
            "business_domains": [{"id": "BD1", "name": "策略处理域", "scope": "约束解析与结果核验"}],
            "system_ownership": [
                {
                    "id": "SYS1",
                    "name": "可信处理系统",
                    "owner": "策略处理域",
                    "boundary": "仅处理已确认边界内的策略请求",
                }
            ],
            "physical_boundaries": [],
            "deployment_triggers": [],
        },
        "sources": {
            "source_facts": [
                {
                    "id": "SF1",
                    "statement": "现有流程无法证明结果对应的约束版本",
                    "source_locator": "用户输入：现有问题第 1 条",
                }
            ],
            "invention_extensions": [
                {
                    "id": "IE1",
                    "statement": "将约束摘要与执行结果一并固化",
                    "basis_source_ids": ["SF1"],
                }
            ],
            "external_materials": [
                {
                    "id": "EM1",
                    "title": "公开技术说明样例",
                    "locator": "https://example.org/public-technology",
                    "retrieved_at": "2026-08-09",
                    "evidence_type": "public_fact",
                }
            ],
            "term_generalizations": [
                {"original": "InternalPolicyJob", "generalized": "策略请求", "reason": "移除内部产品标识"}
            ],
            "abbreviation_allowlist": [],
        },
        "keywords": {
            "technical_objects": [{"term": "策略请求", "anchor": "详细描述/技术对象"}],
            "core_mechanisms": [
                {"term": "约束编排", "anchor": "I1/S3"},
                {"term": "证据绑定", "anchor": "I2/S5"},
            ],
            "key_constraints": [
                {"term": "隔离边界", "anchor": "D1"},
                {"term": "哈希同源", "anchor": "I2"},
            ],
        },
        "core_invention_claim": "在隔离边界内按确定约束生成执行计划，并将约束摘要与结果绑定为可核验记录。",
        "innovations": [
            {
                "id": "I1",
                "core_mechanism": "约束驱动的执行计划编排",
                "necessary_constraint": "计划只能引用当前边界内已确认的约束",
                "substantive_difference": "不是固定流程调用，而是先解析约束再形成可执行计划",
                "anchors": ["D2", "S3"],
            },
            {
                "id": "I2",
                "core_mechanism": "约束摘要与结果的联合证据绑定",
                "necessary_constraint": "摘要和结果必须在同一处理上下文固化",
                "substantive_difference": "结果不再脱离其适用约束独立存储",
                "anchors": ["D1", "S5"],
            },
        ],
        "effects": [
            {
                "id": "T1",
                "innovation_id": "I1",
                "original_problem": "固定流程不能反映请求的边界约束",
                "mechanism": "按已确认约束生成执行计划",
                "observable_result": "可逐步核对每个计划动作引用的约束",
                "verification_status": "expected_observable",
                "evidence_source_ids": [],
            },
            {
                "id": "T2",
                "innovation_id": "I2",
                "original_problem": "结果与约束版本无法稳定对应",
                "mechanism": "联合固化约束摘要和执行结果",
                "observable_result": "可通过摘要复算确认结果适用的约束集合",
                "verification_status": "expected_observable",
                "evidence_source_ids": [],
            },
        ],
        "competitors": {
            "status": "ready",
            "evidence": [
                {
                    "id": "C1",
                    "name": "公开方案甲",
                    "product_or_business": "约束处理公开说明",
                    "locator": "https://example.org/competitor-a",
                    "retrieved_at": "2026-08-09",
                    "evidence_type": "public_fact",
                }
            ],
        },
        "diagrams": [
            {"id": spec["id"], "role": spec["role"], "package_path": spec["path"], "purpose": spec["purpose"]}
            for spec in specs
        ],
        "reviews": {
            "generalization_test": {
                "status": "pass",
                "reviewer": "synthetic-reviewer",
                "notes": "替换领域名词后核心约束与机制不再自然成立。",
            },
            "causal_deletion_tests": [
                {
                    "innovation_id": "I1",
                    "status": "pass",
                    "reviewer": "synthetic-reviewer",
                    "notes": "删除约束编排后 T1 的可核对结果不成立。",
                },
                {
                    "innovation_id": "I2",
                    "status": "pass",
                    "reviewer": "synthetic-reviewer",
                    "notes": "删除证据绑定后 T2 的摘要复算关系不成立。",
                },
            ],
            "visual_reviews": [],
        },
    }

    if variant in {"complex_deployment", "deployment_missing"}:
        manifest["boundaries"]["physical_boundaries"] = [
            {"id": "PB1", "type": "online", "description": "在线网络区"},
            {"id": "PB2", "type": "offline", "description": "离线执行区"},
        ]
        manifest["boundaries"]["deployment_triggers"] = ["cross_network", "online_offline"]
    if variant == "deployment_trigger_omitted":
        manifest["sources"]["source_facts"][0]["statement"] += "；任务还需进入 HSM 执行。"
    if variant in {"pending_retrieval", "competitor_pending_bare"}:
        manifest["competitors"] = {"status": "pending_retrieval", "evidence": []}
    if variant == "keyword_generic":
        manifest["keywords"]["key_constraints"][0]["term"] = "系统"
    if variant == "innovation_missing":
        del manifest["innovations"][0]["necessary_constraint"]
    if variant == "effect_mismatch":
        manifest["effects"][0]["innovation_id"] = "I9"
    if variant == "effect_missing":
        del manifest["effects"][0]["observable_result"]
    if variant == "effect_verified_unbound":
        manifest["effects"][0]["verification_status"] = "verified"
    if variant == "source_invalid":
        manifest["sources"]["invention_extensions"][0]["basis_source_ids"] = ["SF9"]
    if variant == "competitor_bare":
        del manifest["competitors"]["evidence"][0]["locator"]
    if variant == "semantic_pending":
        manifest["reviews"]["generalization_test"] = {
            "status": "pending",
            "reviewer": "待指定",
            "notes": "等待完成泛化替换复核",
        }
    if variant == "path_traversal":
        manifest["diagrams"][0]["package_path"] = "../outside"
    if variant == "schema_alias":
        manifest["sources"]["allowlist"] = manifest["sources"].pop("abbreviation_allowlist")
    return manifest


def write_diagram(root: Path, spec: dict[str, Any], blocked: bool) -> str:
    directory = root / spec["path"]
    directory.mkdir(parents=True, exist_ok=True)
    brief = (
        f"diagram_id: {spec['id']}\n"
        f"diagram_type: {spec['profile']}\n"
        f"purpose: {spec['purpose']}\n"
    ).encode("utf-8")
    puml = spec["puml"].encode("utf-8")
    svg = f'<svg xmlns="http://www.w3.org/2000/svg"><text>{spec["id"]}</text></svg>\n'.encode("utf-8")
    (directory / "brief.normalized.yaml").write_bytes(brief)
    (directory / "diagram.puml").write_bytes(puml)
    (directory / "diagram.svg").write_bytes(svg)
    validation = {
        "schema_version": "1.1",
        "skill_name": "feipi-plantuml-generate-diagram",
        "diagram_id": spec["id"],
        "diagram_type": spec["profile"],
        "profile": spec["profile"],
        "profile_version": "2",
        "brief_check": "ok",
        "coverage_check": "ok",
        "layout_check": "ok",
        "brief_path": "brief.normalized.yaml",
        "diagram_path": "diagram.puml",
        "svg_path": "diagram.svg",
        "brief_sha256": sha256(brief),
        "puml_sha256": sha256(puml),
        "normalized_puml_sha256": sha256(normalize_puml(spec["puml"]).encode("utf-8")),
        "svg_sha256": sha256(svg),
        "artifacts": {
            "brief": {"path": "brief.normalized.yaml", "sha256": sha256(brief)},
            "diagram": {"path": "diagram.puml", "sha256": sha256(puml)},
            "svg": {"path": "diagram.svg", "sha256": sha256(svg)},
        },
        "metrics": spec["metrics"],
        "render_result": "ok",
        "render_server": "synthetic_fixture",
        "final_status": "blocked" if blocked else "success",
        "blocked_reason": "synthetic_failure" if blocked else "",
    }
    (directory / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return sha256(svg)


def build(output: Path, variant: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    specs = diagram_specs(variant)
    manifest = build_manifest(specs, variant)
    visual_reviews = []
    for spec in specs:
        svg_hash = write_diagram(output, spec, blocked=(variant == "diagram_blocked" and spec["id"] == "D1"))
        visual_reviews.append(
            {
                "diagram_id": spec["id"],
                "svg_sha256": "0" * 64 if variant == "visual_stale" and spec["id"] == "D1" else svg_hash,
                "status": "pending" if variant == "visual_pending" and spec["id"] == "D1" else "pass",
                "reviewer": "synthetic-reviewer",
                "notes": "已确认 SVG 无文字遮挡与非预期交叉。",
            }
        )
    manifest["reviews"]["visual_reviews"] = visual_reviews

    keyword_values = [
        item["term"]
        for field in ("technical_objects", "core_mechanisms", "key_constraints")
        for item in manifest["keywords"][field]
    ]
    if manifest["competitors"]["status"] == "pending_retrieval":
        competitor_lines = ["某竞品已具备自动闭环能力。"] if variant == "competitor_pending_bare" else ["待检索。"]
    else:
        competitor_lines = [
            "；".join(
                str(item.get(field, "未提供"))
                for field in ("id", "name", "product_or_business", "locator", "retrieved_at", "evidence_type")
            )
            for item in manifest["competitors"]["evidence"]
        ]
    document_lines = [
        f"# {manifest['patent']['title']}",
        "",
        "## 基本信息",
        "",
        "### 申请说明",
        "",
        manifest["patent"]["use_case"],
        "",
        "## 提案内容",
        "",
        "### 术语解释",
        "",
        "策略请求：进入约束编排流程的技术对象。",
        "",
        "### 关键词",
        "",
        "、".join(keyword_values),
        "",
        "### 应用本方案的产品",
        "",
        "当前为合成回归场景，不绑定未授权产品名。",
        "",
        "### 本方案的背景是什么",
        "",
        manifest["input_completeness"]["existing_problem_facts"][0],
        "",
        "### 行业内哪些竞争对手的业务、产品和本方案相关？请列出竞争对手的名称和相关业务、产品的名称（如有多个请一并列出）",
        "",
        *competitor_lines,
        "",
        "### 本方案是否有敏感的部分不适合作为专利申请公开？",
        "",
        "当前输入未声明敏感内容。",
        "",
        "### 详细介绍与本方案相似的方案及其缺点",
        "",
        manifest["sources"]["source_facts"][0]["statement"],
        "",
        "### 详细描述本方案，包括组合部分、步骤",
        "",
        "#### 核心发明主张",
        "",
        manifest["core_invention_claim"],
        "",
    ]
    for spec in specs:
        document_lines.extend(
            [
                f"<!-- diagram-id: {spec['id']} -->",
                "```plantuml",
                spec["puml"].rstrip("\n"),
                "```",
                "",
            ]
        )
        if spec["role"] == "main_flow":
            final_step = "5. S6 固化结果。" if variant == "flow_text_mismatch" else "5. S5 固化结果。"
            document_lines.extend(
                [
                    "主流程说明：",
                    "1. S1 接收请求。",
                    "2. S2 校验边界。",
                    "3. S3 生成计划。",
                    "4. S4 执行机制。",
                    final_step,
                    "",
                ]
            )
    document_lines.extend(
        [
            "### 是否还有其他解决方案，如有，请详细说明",
            "",
            "可替换具体执行端点，但不得改变约束先行和证据绑定机制。",
            "",
            "### 技术效果总结",
            "",
        ]
    )
    for effect in manifest["effects"]:
        document_lines.extend(
            [
                f"#### {effect['id']}（对应 {effect['innovation_id']}）",
                "",
                f"原问题：{effect.get('original_problem', '未提供')}",
                f"采用机制：{effect.get('mechanism', '未提供')}",
                f"可观察结果：{effect.get('observable_result', '未提供')}",
                f"验证状态：{effect.get('verification_status', '未提供')}",
                "",
            ]
        )
    document_lines.extend(["### 提炼本方案的关键技术创新点", ""])
    for innovation in manifest["innovations"]:
        document_lines.extend(
            [
                f"#### {innovation['id']}",
                "",
                f"核心机制：{innovation.get('core_mechanism', '未提供')}",
                f"必要约束：{innovation.get('necessary_constraint', '未提供')}",
                f"实质差异：{innovation.get('substantive_difference', '未提供')}",
                f"正文与图示落点：{'、'.join(innovation.get('anchors', []))}",
                "",
            ]
        )
    if variant == "document_structure_missing":
        document_lines = [
            f"# {manifest['patent']['title']}",
            "",
            "## 基本信息",
            "",
            "仅保留两个二级标题的旧式假绿文档。",
            "",
            "## 提案内容",
            "",
        ]
        for spec in specs:
            document_lines.extend(
                [
                    f"<!-- diagram-id: {spec['id']} -->",
                    "```plantuml",
                    spec["puml"].rstrip("\n"),
                    "```",
                    "",
                ]
            )
            if spec["role"] == "main_flow":
                document_lines.extend([f"{step}。" for step in ("S1 接收请求", "S2 校验边界", "S3 生成计划", "S4 执行机制", "S5 固化结果")])
    if variant == "document_title_mismatch":
        document_lines[0] = "# 一种量子调度方法/系统"
    (output / "disclosure.md").write_text("\n".join(document_lines), encoding="utf-8")
    (output / "disclosure-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if variant == "hash_tamper":
        target = output / "diagrams/D1-component-overview/diagram.puml"
        target.write_text(target.read_text(encoding="utf-8") + "' tampered\n", encoding="utf-8")
    if variant == "artifact_path_missing":
        target = output / "diagrams/D1-component-overview/validation.json"
        validation = json.loads(target.read_text(encoding="utf-8"))
        validation["brief_path"] = "missing/brief.normalized.yaml"
        validation["diagram_path"] = "missing/diagram.puml"
        validation["svg_path"] = "missing/diagram.svg"
        validation["artifacts"]["brief"]["path"] = "missing/brief.normalized.yaml"
        validation["artifacts"]["diagram"]["path"] = "missing/diagram.puml"
        validation["artifacts"]["svg"]["path"] = "missing/diagram.svg"
        target.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if variant == "diagram_check_failed":
        target = output / "diagrams/D1-component-overview/validation.json"
        validation = json.loads(target.read_text(encoding="utf-8"))
        validation["coverage_check"] = "failed"
        target.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if variant == "diagram_metrics_forged":
        target = output / "diagrams/D2-main-flow/validation.json"
        validation = json.loads(target.read_text(encoding="utf-8"))
        validation["metrics"] = {"node_count": 5, "edge_count": 0, "max_degree": 0}
        target.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if variant == "non_utf8_puml":
        target = output / "diagrams/D1-component-overview/diagram.puml"
        target.write_bytes(b"\xff\xfe\x00broken")
    if variant == "artifact_symlink_escape":
        target = output / "diagrams/D1-component-overview/diagram.puml"
        outside = output.parent / f".{output.name}-outside.puml"
        outside.write_text("@startuml\n@enduml\n", encoding="utf-8")
        target.unlink()
        target.symlink_to(outside)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--variant",
        default="happy",
        choices=(
            "happy",
            "complex_deployment",
            "pending_retrieval",
            "competitor_pending_bare",
            "deployment_missing",
            "deployment_trigger_omitted",
            "keyword_generic",
            "implementation_top",
            "implementation_table_field",
            "implementation_alias_only",
            "flow_mr",
            "flow_jump",
            "flow_missing_parent",
            "flow_long_label",
            "flow_text_mismatch",
            "innovation_missing",
            "effect_mismatch",
            "effect_missing",
            "source_invalid",
            "competitor_bare",
            "diagram_blocked",
            "hash_tamper",
            "visual_stale",
            "visual_pending",
            "semantic_pending",
            "path_traversal",
            "schema_alias",
            "document_structure_missing",
            "document_title_mismatch",
            "artifact_path_missing",
            "diagram_check_failed",
            "diagram_metrics_forged",
            "effect_verified_unbound",
            "non_utf8_puml",
            "artifact_symlink_escape",
        ),
    )
    args = parser.parse_args()
    build(args.output.resolve(), args.variant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
