#!/usr/bin/env python3
"""为行为测试生成自包含的合成交付包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


WORKSPACE_DIR_NAME = "disclosure-workspace"


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
    if variant == "puml_trace_leak":
        component = component.replace("@enduml", "' SF1\n@enduml")
    if variant == "puml_extension_leak":
        component = component.replace("策略协调域", "策略协调域\\n将单一约束集合扩展为可组合的分层约束集合")

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
    if variant == "svg_term_leak":
        specs[0]["svg_label"] = "InternalPolicyJob"
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
        "schema_version": "1.2",
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
                },
                {
                    "id": "SF2",
                    "statement": "当前实现会解析已确认约束并据此生成逐项执行计划",
                    "source_locator": "用户输入：已实现路径第 1 条",
                },
                {
                    "id": "SF3",
                    "statement": "当前实现会在同一处理上下文固化约束摘要与执行结果",
                    "source_locator": "用户输入：已实现路径第 2 条",
                },
            ],
            "invention_extensions": [
                {
                    "id": "IE1",
                    "statement": "将单一约束集合扩展为可组合的分层约束集合",
                    "basis_source_ids": ["SF2"],
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
                "implementation_basis": {
                    "technical_object": "策略请求",
                    "trigger_or_input": "接收已通过边界校验的策略请求与约束集合",
                    "processing": "解析已确认约束并按约束顺序形成逐项执行计划",
                    "constraint": "计划动作只能引用当前处理边界内的已确认约束",
                    "output_or_state": "输出带约束引用的可执行计划",
                    "source_fact_ids": ["SF2"],
                },
                "protection_extensions": [
                    {
                        "extension_id": "IE1",
                        "scope": "将单一约束集合扩展为可组合的分层约束集合",
                        "rationale": "扩展后仍以约束解析先于计划生成作为核心机制",
                    }
                ],
                "comparison_baseline": "现有做法按固定流程依次执行预设动作",
                "core_mechanism": "约束驱动的执行计划编排",
                "necessary_constraint": "计划只能引用当前边界内已确认的约束",
                "substantive_difference": "不是固定流程调用，而是先解析约束再形成可执行计划",
                "value_link": "由于每个计划动作显式引用已确认约束，因此可以逐步核对动作与约束是否一致",
                "effect_id": "T1",
                "anchors": ["D2", "S3"],
            },
            {
                "id": "I2",
                "implementation_basis": {
                    "technical_object": "执行结果记录",
                    "trigger_or_input": "执行计划完成并产生处理结果",
                    "processing": "计算当前约束集合摘要并与执行结果在同一上下文固化",
                    "constraint": "摘要与结果必须使用同一处理上下文标识",
                    "output_or_state": "形成可复算约束摘要的结果记录",
                    "source_fact_ids": ["SF3"],
                },
                "protection_extensions": [],
                "comparison_baseline": "现有做法将处理结果与适用约束分别存储",
                "core_mechanism": "约束摘要与结果的联合证据绑定",
                "necessary_constraint": "摘要和结果必须在同一处理上下文固化",
                "substantive_difference": "结果不再脱离其适用约束独立存储",
                "value_link": "由于结果携带同一上下文中的约束摘要，因此可以复算并核对结果对应的约束版本",
                "effect_id": "T2",
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
            "status": "evidence_found",
            "research_summary": "公开资料显示相关方案提供约束处理能力，可作为本方案的行业对比对象。",
            "search_records": [
                {
                    "focus": "technical_object",
                    "basis_terms": ["策略请求"],
                    "context_terms": ["约束编排"],
                    "query": "策略请求 约束编排 公开方案",
                    "searched_at": "2026-08-09",
                    "consulted_locators": ["https://example.org/competitor-a"],
                    "result_summary": "查阅到公开方案甲的约束处理说明。",
                },
                {
                    "focus": "core_mechanism",
                    "basis_terms": ["约束编排", "证据绑定"],
                    "context_terms": ["策略请求"],
                    "query": "约束编排 证据绑定 策略请求 公开实现",
                    "searched_at": "2026-08-09",
                    "consulted_locators": [
                        "https://example.org/competitor-a",
                        "https://example.org/constraint-processing",
                    ],
                    "result_summary": "查阅页面涉及约束处理，但未公开与结果联合固化的完整机制。",
                },
            ],
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
    if variant in {
        "searched_no_evidence",
        "competitor_no_evidence_bare",
        "competitor_no_evidence_named_claim",
        "competitor_placeholder",
    }:
        manifest["competitors"] = {
            "status": "searched_no_usable_evidence",
            "research_summary": "已完成公开资料检索，但未发现足以形成具名对比的可靠证据；本节不对具体产品能力作断言。",
            "search_records": manifest["competitors"]["search_records"],
            "evidence": [],
        }
    if variant == "competitor_legacy_pending":
        manifest["competitors"] = {"status": "pending_retrieval", "evidence": []}
    if variant == "competitor_search_missing":
        del manifest["competitors"]["search_records"]
    if variant == "competitor_search_focus_missing":
        manifest["competitors"]["search_records"][1]["focus"] = "technical_object"
    if variant == "competitor_search_duplicate":
        manifest["competitors"]["search_records"][1]["query"] = manifest["competitors"]["search_records"][0]["query"]
    if variant == "competitor_search_zero_width_duplicate":
        manifest["competitors"]["search_records"][1]["query"] = manifest["competitors"]["search_records"][0]["query"].replace(" ", "\u200b ", 1)
    if variant == "competitor_search_unrelated":
        manifest["competitors"]["search_records"][0]["query"] = "coffee maker price comparison"
        manifest["competitors"]["search_records"][1]["query"] = "tomorrow weather forecast"
    if variant == "competitor_basis_stuffed_unrelated":
        manifest["competitors"]["search_records"][0]["query"] = "策略请求 coffee maker price comparison"
        manifest["competitors"]["search_records"][1]["query"] = "约束编排 证据绑定 tomorrow weather forecast"
    if variant == "competitor_basis_html_entity":
        manifest["competitors"]["search_records"][0]["query"] = "&#31574;&#30053;&#35831;&#27714; 约束编排 公开方案"
    if variant == "competitor_basis_self_poisoned":
        manifest["input_completeness"]["technical_objects"] = ["coffee maker"]
        manifest["input_completeness"]["core_mechanisms"] = ["weather forecast"]
        manifest["competitors"]["search_records"][0]["basis_terms"] = ["coffee maker"]
        manifest["competitors"]["search_records"][0]["query"] = "coffee maker 约束编排 公开产品"
        manifest["competitors"]["search_records"][1]["basis_terms"] = ["weather forecast"]
        manifest["competitors"]["search_records"][1]["query"] = "weather forecast 策略请求 官方产品"
    if variant == "competitor_basis_zero_width":
        manifest["input_completeness"]["technical_objects"] = ["\u200b"]
        manifest["input_completeness"]["core_mechanisms"] = ["\u200b"]
        manifest["competitors"]["search_records"][0]["basis_terms"] = ["\u200b"]
        manifest["competitors"]["search_records"][1]["basis_terms"] = ["\u200b"]
    if variant == "competitor_search_locator_invalid":
        manifest["competitors"]["search_records"][0]["consulted_locators"] = ["https://localhost/research"]
    if variant == "competitor_summary_placeholder":
        manifest["competitors"]["research_summary"] = "待检索：当前输入未包含竞品材料，后续再补充完整行业分析。"
    if variant == "competitor_summary_english_placeholder":
        manifest["competitors"]["research_summary"] = "Research is incomplete and competitor evidence will be added later."
    if variant == "competitor_summary_zero_width":
        manifest["competitors"]["research_summary"] = "\u200b" * 24
    if variant == "competitor_no_evidence_named_claim":
        manifest["competitors"]["research_summary"] = "FabricatedVendor AutoLoop 已具备全自动端到端闭环能力，可以直接替代人工处理。"
    if variant == "competitor_fake_url":
        fake_locator = "https://fabricated.vendor.invalid/nonexistent-product"
        for record in manifest["competitors"]["search_records"]:
            record["consulted_locators"] = [fake_locator]
        manifest["competitors"]["evidence"][0]["locator"] = fake_locator
    if variant == "keyword_generic":
        manifest["keywords"]["key_constraints"][0]["term"] = "系统"
    if variant == "innovation_missing":
        del manifest["innovations"][0]["necessary_constraint"]
    if variant == "implementation_basis_missing":
        del manifest["innovations"][0]["implementation_basis"]
    if variant == "implementation_source_invalid":
        manifest["innovations"][0]["implementation_basis"]["source_fact_ids"] = ["SF9"]
    if variant == "implementation_internal_identifier":
        manifest["innovations"][0]["implementation_basis"]["processing"] = "调用 InternalPolicyJob.run_plan() 生成计划"
    if variant == "implementation_internal_identifier_casefold":
        manifest["innovations"][0]["implementation_basis"]["processing"] = "调用 internalpolicyjob 生成计划"
    if variant == "protection_extension_field_missing":
        del manifest["innovations"][0]["protection_extensions"][0]["rationale"]
    if variant == "protection_extension_id_missing":
        del manifest["innovations"][0]["protection_extensions"][0]["extension_id"]
    if variant == "protection_extension_unknown_id":
        manifest["innovations"][0]["protection_extensions"][0]["extension_id"] = "IE9"
    if variant == "protection_extension_duplicate_id":
        manifest["innovations"][1]["protection_extensions"] = [
            {
                "extension_id": "IE1",
                "scope": "将证据绑定扩展到多个连续处理上下文",
                "rationale": "扩展后仍以约束摘要与结果的联合绑定为核心机制",
            }
        ]
    if variant == "protection_extension_orphan_ledger":
        manifest["sources"]["invention_extensions"].append(
            {
                "id": "IE2",
                "statement": "将证据绑定扩展到多个连续处理上下文",
                "basis_source_ids": ["SF3"],
            }
        )
    if variant == "protection_extension_ledger_missing":
        manifest["sources"]["invention_extensions"] = []
    if variant == "protection_internal_identifier_casefold":
        manifest["innovations"][0]["protection_extensions"][0]["scope"] = "将 internalpolicyjob 扩展到分层约束集合"
    if variant == "innovation_comparison_missing":
        del manifest["innovations"][0]["comparison_baseline"]
    if variant == "innovation_value_missing":
        del manifest["innovations"][0]["value_link"]
    if variant == "innovation_value_generic":
        manifest["innovations"][0]["value_link"] = "提升效率"
    if variant == "innovation_effect_link_mismatch":
        manifest["innovations"][0]["effect_id"] = "T9"
    if variant == "effect_mismatch":
        manifest["effects"][0]["innovation_id"] = "I9"
    if variant == "effect_missing":
        del manifest["effects"][0]["observable_result"]
    if variant == "effect_verified_unbound":
        manifest["effects"][0]["verification_status"] = "verified"
    if variant == "source_invalid":
        manifest["sources"]["invention_extensions"][0]["basis_source_ids"] = ["SF9"]
    if variant == "multiline_source_fact":
        manifest["sources"]["source_facts"][0]["statement"] = "现有流程无法证明结果\n对应的约束版本"
        manifest["sources"]["source_facts"][0]["source_locator"] = "用户输入：现有问题\n第 1 条"
    if variant == "competitor_bare":
        del manifest["competitors"]["evidence"][0]["locator"]
    if variant == "competitor_evidence_unlinked":
        manifest["competitors"]["evidence"][0]["locator"] = "https://example.org/not-consulted"
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
    svg_label = spec.get("svg_label", spec["id"])
    svg = f'<svg xmlns="http://www.w3.org/2000/svg"><text>{svg_label}</text></svg>\n'.encode("utf-8")
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


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def trace_value(value: Any) -> str:
    normalized = re.sub(r"\s+", " ", str(value) if value is not None else "").strip()
    return normalized or "未提供"


def internal_appendix_lines(manifest: dict[str, Any]) -> list[str]:
    sources = manifest.get("sources") if isinstance(manifest.get("sources"), dict) else {}
    lines = [
        "## 内部追溯附录（禁止对外）",
        "",
        "> 本附录仅供内部评审、事实核对和校验使用。对外发送时只使用交底书目录根部的 disclosure.md，不得包含本附录。",
        "",
        "### 来源事实台账",
        "",
    ]
    source_facts = [item for item in sources.get("source_facts", []) if isinstance(item, dict)]
    if source_facts:
        for item in source_facts:
            lines.append(
                f"- {trace_value(item.get('id'))}｜陈述：{trace_value(item.get('statement'))}｜"
                f"输入定位：{trace_value(item.get('source_locator'))}"
            )
    else:
        lines.append("- 来源事实：无")

    lines.extend(["", "### 发明扩展台账", ""])
    extensions = [item for item in sources.get("invention_extensions", []) if isinstance(item, dict)]
    if extensions:
        for item in extensions:
            basis_ids = "、".join(string_list(item.get("basis_source_ids"))) or "无"
            lines.append(
                f"- {trace_value(item.get('id'))}｜扩展内容：{trace_value(item.get('statement'))}｜依据：{basis_ids}"
            )
    else:
        lines.append("- 发明扩展：无")

    lines.extend(["", "### 外部资料台账", ""])
    external_materials = [item for item in sources.get("external_materials", []) if isinstance(item, dict)]
    if external_materials:
        for item in external_materials:
            lines.append(
                f"- {trace_value(item.get('id'))}｜标题：{trace_value(item.get('title'))}｜"
                f"定位：{trace_value(item.get('locator'))}｜检索日期：{trace_value(item.get('retrieved_at'))}｜"
                f"证据属性：{trace_value(item.get('evidence_type'))}"
            )
    else:
        lines.append("- 外部资料：无")

    lines.extend(["", "### 创新与效果映射", ""])
    for item in manifest.get("innovations", []):
        if not isinstance(item, dict):
            continue
        implementation = item.get("implementation_basis") if isinstance(item.get("implementation_basis"), dict) else {}
        source_ids = "、".join(string_list(implementation.get("source_fact_ids"))) or "无"
        extension_ids = "、".join(
            str(extension.get("extension_id"))
            for extension in item.get("protection_extensions", [])
            if isinstance(extension, dict) and isinstance(extension.get("extension_id"), str)
        ) or "无"
        lines.append(
            f"- {trace_value(item.get('id'))}｜已实现依据：{source_ids}｜"
            f"拟扩展：{extension_ids}｜效果：{trace_value(item.get('effect_id'))}"
        )

    lines.extend(["", "### 效果证据", ""])
    for item in manifest.get("effects", []):
        if not isinstance(item, dict):
            continue
        evidence_ids = "、".join(string_list(item.get("evidence_source_ids"))) or "无"
        lines.append(
            f"- {trace_value(item.get('id'))}｜验证状态：{trace_value(item.get('verification_status'))}｜"
            f"证据：{evidence_ids}"
        )

    lines.extend(["", "### 竞品证据", ""])
    competitors = manifest.get("competitors") if isinstance(manifest.get("competitors"), dict) else {}
    lines.append(
        f"- 检索状态：{trace_value(competitors.get('status'))}｜"
        f"检索结论：{trace_value(competitors.get('research_summary'))}"
    )
    for index, item in enumerate(
        [entry for entry in competitors.get("search_records", []) if isinstance(entry, dict)],
        start=1,
    ):
        consulted = "、".join(string_list(item.get("consulted_locators"))) or "无"
        basis_terms = "、".join(string_list(item.get("basis_terms"))) or "无"
        context_terms = "、".join(string_list(item.get("context_terms"))) or "无"
        lines.append(
            f"- 检索记录 {index}｜焦点：{trace_value(item.get('focus'))}｜"
            f"依据词：{basis_terms}｜上下文词：{context_terms}｜检索式：{trace_value(item.get('query'))}｜"
            f"检索日期：{trace_value(item.get('searched_at'))}｜"
            f"查阅：{consulted}｜结果：{trace_value(item.get('result_summary'))}"
        )
    evidence = [item for item in competitors.get("evidence", []) if isinstance(item, dict)]
    if evidence:
        for item in evidence:
            lines.append(
                f"- {trace_value(item.get('id'))}｜名称：{trace_value(item.get('name'))}｜"
                f"相关业务或产品：{trace_value(item.get('product_or_business'))}｜"
                f"定位：{trace_value(item.get('locator'))}｜检索日期：{trace_value(item.get('retrieved_at'))}｜"
                f"证据属性：{trace_value(item.get('evidence_type'))}"
            )
    else:
        lines.append("- 竞品证据：无")
    return lines


def build(output: Path, variant: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    workspace = output if variant == "legacy_flat_layout" else output / WORKSPACE_DIR_NAME
    workspace.mkdir(parents=True, exist_ok=True)
    specs = diagram_specs(variant)
    manifest = build_manifest(specs, variant)
    visual_reviews = []
    for spec in specs:
        svg_hash = write_diagram(workspace, spec, blocked=(variant == "diagram_blocked" and spec["id"] == "D1"))
        visual_reviews.append(
            {
                "diagram_id": spec["id"],
                "svg_sha256": "0" * 64 if variant == "visual_stale" and spec["id"] == "D1" else svg_hash,
                "status": "pending" if variant == "visual_pending" and spec["id"] == "D1" else "pass",
                "reviewer": "synthetic-reviewer",
                "notes": (
                    "已确认 SVG 无文字遮挡与非预期交叉。"
                    if variant == "diagram_scope_review_missing" and spec["id"] == "D1"
                    else "已确认 SVG 无文字遮挡与非预期交叉，并确认仅呈现已实现路径。"
                ),
            }
        )
    manifest["reviews"]["visual_reviews"] = visual_reviews

    keyword_values = [
        item["term"]
        for field in ("technical_objects", "core_mechanisms", "key_constraints")
        for item in manifest["keywords"][field]
    ]
    competitors = manifest["competitors"]
    search_records = [item for item in competitors.get("search_records", []) if isinstance(item, dict)]
    queries = "；".join(str(item.get("query", "未提供")) for item in search_records)
    search_dates = "、".join(
        dict.fromkeys(str(item.get("searched_at", "未提供")) for item in search_records)
    )
    competitor_lines = [
        f"检索范围：{queries}",
        f"检索日期：{search_dates}",
        f"检索结论：{competitors.get('research_summary', '未提供')}",
    ]
    public_evidence_type = {"public_fact": "公开事实", "reasonable_inference": "合理推断"}
    competitor_lines.extend(
        f"- 名称：{item.get('name', '未提供')}；相关业务或产品：{item.get('product_or_business', '未提供')}；"
        f"来源：{item.get('locator', '未提供')}；检索日期：{item.get('retrieved_at', '未提供')}；"
        f"证据属性：{public_evidence_type.get(str(item.get('evidence_type')), '未提供')}"
        for item in competitors.get("evidence", [])
        if isinstance(item, dict)
    )
    if variant == "competitor_no_evidence_bare":
        competitor_lines.append("某竞品已具备自动闭环能力。")
    if variant in {"competitor_placeholder", "competitor_legacy_pending"}:
        competitor_lines = ["待检索。"]
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
            (
                "拟扩展保护已在对应创新点下高亮列出，本节不重复。"
                if any(
                    innovation.get("protection_extensions")
                    for innovation in manifest.get("innovations", [])
                    if isinstance(innovation, dict)
                )
                else "无。"
            ),
            "",
            "### 技术效果总结",
            "",
        ]
    )
    for effect in manifest["effects"]:
        public_status = {
            "expected_observable": "预期可观察",
            "verified": "已有证据支持",
        }.get(str(effect.get("verification_status")), "未提供")
        document_lines.extend(
            [
                f"#### {effect['id']}（对应 {effect['innovation_id']}）",
                "",
                f"原问题：{effect.get('original_problem', '未提供')}",
                f"采用机制：{effect.get('mechanism', '未提供')}",
                f"可观察结果：{effect.get('observable_result', '未提供')}",
                f"验证状态：{public_status}",
                "",
            ]
        )
    document_lines.extend(["### 提炼本方案的关键技术创新点", ""])
    effects_by_id = {effect["id"]: effect for effect in manifest["effects"] if isinstance(effect, dict) and "id" in effect}
    for innovation in manifest["innovations"]:
        effect = effects_by_id.get(innovation.get("effect_id"), {})
        implementation = innovation.get("implementation_basis", {})
        document_lines.extend(
            [
                f"#### {innovation['id']}",
                "",
                "- **已实现基础**",
                f"  - 技术对象：{implementation.get('technical_object', '未提供')}",
                f"  - 触发或输入：{implementation.get('trigger_or_input', '未提供')}",
                f"  - 实际处理：{implementation.get('processing', '未提供')}",
                f"  - 必要边界：{implementation.get('constraint', '未提供')}",
                f"  - 输出或状态：{implementation.get('output_or_state', '未提供')}",
                f"对比基线：{innovation.get('comparison_baseline', '未提供')}",
                f"本方案处理方式：{innovation.get('core_mechanism', '未提供')}",
                f"必要约束：{innovation.get('necessary_constraint', '未提供')}",
                f"实质差异：{innovation.get('substantive_difference', '未提供')}",
                f"价值关联（{innovation.get('effect_id', '未提供')}）：{innovation.get('value_link', '未提供')}",
                f"对应可观察结果：{effect.get('observable_result', '未提供')}",
                f"正文与图示落点：{'、'.join(innovation.get('anchors', []))}",
                "",
            ]
        )
        protection_extensions = innovation.get("protection_extensions", [])
        if protection_extensions:
            for extension in protection_extensions:
                document_lines.extend(
                    [
                        "> **拟扩展保护**",
                        ">",
                        f"> - 保护范围：{extension.get('scope', '未提供')}",
                        f"> - 扩展理由：{extension.get('rationale', '未提供')}",
                        "",
                    ]
                )
    if variant == "innovation_value_scattered":
        value_line = f"价值关联（T1）：{manifest['innovations'][0]['value_link']}"
        document_lines.remove(value_line)
        document_lines.extend(["", value_line])
    if variant == "protection_extension_unhighlighted":
        marker_index = document_lines.index("> **拟扩展保护**")
        document_lines[marker_index] = "拟扩展保护"
    if variant == "protection_extension_body_unquoted":
        extension = manifest["innovations"][0]["protection_extensions"][0]
        for label, field in (("保护范围", "scope"), ("扩展理由", "rationale")):
            line = f"> - {label}：{extension.get(field, '未提供')}"
            document_lines[document_lines.index(line)] = line[2:]
    if variant == "implementation_fields_quoted":
        implementation = manifest["innovations"][0]["implementation_basis"]
        for label, field in (
            ("技术对象", "technical_object"),
            ("触发或输入", "trigger_or_input"),
            ("实际处理", "processing"),
            ("必要边界", "constraint"),
            ("输出或状态", "output_or_state"),
        ):
            line = f"  - {label}：{implementation[field]}"
            document_lines[document_lines.index(line)] = f"> {line}"
    if variant == "implementation_field_before_label":
        marker_index = document_lines.index("- **已实现基础**")
        document_lines[marker_index], document_lines[marker_index + 1] = (
            document_lines[marker_index + 1],
            document_lines[marker_index],
        )
    if variant == "external_unexpected_no_extension_marker":
        document_lines.extend(["", "> **拟扩展保护：无**"])
    if variant == "alternative_extension_unhighlighted":
        reference_index = document_lines.index("拟扩展保护已在对应创新点下高亮列出，本节不重复。")
        document_lines[reference_index] = manifest["innovations"][0]["protection_extensions"][0]["scope"]
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
    if variant == "public_trace_ids_leak":
        document_lines.extend(["", "内部编号：SF1、IE1、EM1、C1、BD1、SYS1、PB1。"])
    if variant == "public_source_locator_leak":
        document_lines.extend(["", manifest["sources"]["source_facts"][0]["source_locator"]])
    if variant == "public_term_original_leak":
        document_lines.extend(["", manifest["sources"]["term_generalizations"][0]["original"]])
    if variant == "public_raw_enum_leak":
        document_lines.extend(
            ["", "expected_observable verified public_fact reasonable_inference pending_retrieval evidence_found searched_no_usable_evidence"]
        )
    if variant == "public_html_comment_leak":
        document_lines.extend(["", "<!-- internal-note: do-not-publish -->"])
    if variant == "public_entity_leak":
        document_lines.extend(
            [
                "",
                "S&#70;1 expected&#95;observable InternalPolicy&#74;ob 用户输入：现有问题第 &#49; 条",
            ]
        )
    if variant == "public_encoded_comment_leak":
        document_lines.extend(["", "&lt;!-- internal-note: do-not-publish --&gt;"])

    internal_lines = [*document_lines]
    if variant != "internal_appendix_missing":
        internal_lines.extend(["", *internal_appendix_lines(manifest)])
    if variant == "public_body_drift":
        body_index = internal_lines.index(manifest["patent"]["use_case"])
        internal_lines[body_index] = f"{internal_lines[body_index]}（内部改写）"
    if variant == "internal_trace_mapping_missing":
        mapping_index = next(
            index for index, line in enumerate(internal_lines) if line.startswith("- I1｜已实现依据：")
        )
        internal_lines.pop(mapping_index)
    if variant == "internal_appendix_commented":
        appendix_index = internal_lines.index("## 内部追溯附录（禁止对外）")
        internal_lines.insert(appendix_index + 1, "<!--")
        internal_lines.append("-->")
    if variant == "internal_extra_trace":
        internal_lines.append("- SF999｜陈述：伪造事实｜输入定位：伪造材料")

    (output / "disclosure.md").write_text("\n".join(document_lines), encoding="utf-8")
    if variant != "internal_missing":
        (workspace / "disclosure-internal.md").write_text("\n".join(internal_lines), encoding="utf-8")
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (workspace / "disclosure-manifest.json").write_text(
        manifest_text, encoding="utf-8"
    )
    if variant == "ambiguous_layout":
        (output / "disclosure-manifest.json").write_text(manifest_text, encoding="utf-8")
    if variant == "workspace_duplicate_public":
        (workspace / "disclosure.md").write_text("\n".join(document_lines), encoding="utf-8")
    if variant == "workspace_root_internal_leak":
        (output / "disclosure-internal.md").write_text("\n".join(internal_lines), encoding="utf-8")
    if variant == "workspace_symlink_escape":
        outside_workspace = output.parent / f".{output.name}-outside-workspace"
        workspace.rename(outside_workspace)
        workspace.symlink_to(outside_workspace, target_is_directory=True)

    if variant == "hash_tamper":
        target = workspace / "diagrams/D1-component-overview/diagram.puml"
        target.write_text(target.read_text(encoding="utf-8") + "' tampered\n", encoding="utf-8")
    if variant == "artifact_path_missing":
        target = workspace / "diagrams/D1-component-overview/validation.json"
        validation = json.loads(target.read_text(encoding="utf-8"))
        validation["brief_path"] = "missing/brief.normalized.yaml"
        validation["diagram_path"] = "missing/diagram.puml"
        validation["svg_path"] = "missing/diagram.svg"
        validation["artifacts"]["brief"]["path"] = "missing/brief.normalized.yaml"
        validation["artifacts"]["diagram"]["path"] = "missing/diagram.puml"
        validation["artifacts"]["svg"]["path"] = "missing/diagram.svg"
        target.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if variant == "diagram_check_failed":
        target = workspace / "diagrams/D1-component-overview/validation.json"
        validation = json.loads(target.read_text(encoding="utf-8"))
        validation["coverage_check"] = "failed"
        target.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if variant == "diagram_metrics_forged":
        target = workspace / "diagrams/D2-main-flow/validation.json"
        validation = json.loads(target.read_text(encoding="utf-8"))
        validation["metrics"] = {"node_count": 5, "edge_count": 0, "max_degree": 0}
        target.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if variant == "non_utf8_puml":
        target = workspace / "diagrams/D1-component-overview/diagram.puml"
        target.write_bytes(b"\xff\xfe\x00broken")
    if variant == "artifact_symlink_escape":
        target = workspace / "diagrams/D1-component-overview/diagram.puml"
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
            "legacy_flat_layout",
            "ambiguous_layout",
            "workspace_duplicate_public",
            "workspace_root_internal_leak",
            "workspace_symlink_escape",
            "complex_deployment",
            "searched_no_evidence",
            "competitor_no_evidence_bare",
            "competitor_placeholder",
            "competitor_legacy_pending",
            "competitor_search_missing",
            "competitor_search_focus_missing",
            "competitor_search_duplicate",
            "competitor_search_zero_width_duplicate",
            "competitor_search_unrelated",
            "competitor_basis_stuffed_unrelated",
            "competitor_basis_html_entity",
            "competitor_basis_self_poisoned",
            "competitor_basis_zero_width",
            "competitor_search_locator_invalid",
            "competitor_summary_placeholder",
            "competitor_summary_english_placeholder",
            "competitor_summary_zero_width",
            "competitor_no_evidence_named_claim",
            "competitor_fake_url",
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
            "implementation_basis_missing",
            "implementation_source_invalid",
            "implementation_internal_identifier",
            "implementation_internal_identifier_casefold",
            "implementation_fields_quoted",
            "implementation_field_before_label",
            "protection_extension_field_missing",
            "protection_extension_id_missing",
            "protection_extension_unknown_id",
            "protection_extension_duplicate_id",
            "protection_extension_orphan_ledger",
            "protection_extension_ledger_missing",
            "protection_internal_identifier_casefold",
            "protection_extension_unhighlighted",
            "protection_extension_body_unquoted",
            "external_unexpected_no_extension_marker",
            "alternative_extension_unhighlighted",
            "innovation_comparison_missing",
            "innovation_value_missing",
            "innovation_value_generic",
            "innovation_value_scattered",
            "innovation_effect_link_mismatch",
            "effect_mismatch",
            "effect_missing",
            "source_invalid",
            "multiline_source_fact",
            "competitor_bare",
            "competitor_evidence_unlinked",
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
            "internal_missing",
            "internal_appendix_missing",
            "public_body_drift",
            "internal_trace_mapping_missing",
            "internal_appendix_commented",
            "internal_extra_trace",
            "public_trace_ids_leak",
            "public_source_locator_leak",
            "public_term_original_leak",
            "public_raw_enum_leak",
            "public_html_comment_leak",
            "public_entity_leak",
            "public_encoded_comment_leak",
            "puml_trace_leak",
            "puml_extension_leak",
            "svg_term_leak",
            "diagram_scope_review_missing",
        ),
    )
    args = parser.parse_args()
    build(args.output.resolve(), args.variant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
