#!/usr/bin/env python3
"""专利创新交底书草稿与完整交付包校验器。

仅使用 Python 标准库。完整交付模式默认在交底书目录下的内部工作区写入
``disclosure-validation.json``，并以 0/1/2 分别表示
``success``/``blocked``/``review_required``。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlsplit


SKILL_NAME = "feipi-patent-generate-innovation-disclosure"
DISCLOSURE_WORKSPACE_DIR = "disclosure-workspace"
VALIDATION_SCHEMA_VERSION = "1.0"
EXIT_BY_STATUS = {"success": 0, "blocked": 1, "review_required": 2}
MANIFEST_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "assets" / "disclosure-manifest.schema.json"
GENERIC_PACKAGE_VERIFIER = (
    Path(__file__).resolve().parents[3]
    / "diagram"
    / "feipi-plantuml-generate-diagram"
    / "scripts"
    / "verify_package.py"
)

REQUIRED_DISCLOSURE_H3 = (
    "申请说明",
    "术语解释",
    "关键词",
    "应用本方案的产品",
    "本方案的背景是什么",
    "行业内哪些竞争对手的业务、产品和本方案相关？请列出竞争对手的名称和相关业务、产品的名称（如有多个请一并列出）",
    "本方案是否有敏感的部分不适合作为专利申请公开？",
    "详细介绍与本方案相似的方案及其缺点",
    "详细描述本方案，包括组合部分、步骤",
    "是否还有其他解决方案，如有，请详细说明",
    "技术效果总结",
    "提炼本方案的关键技术创新点",
)
COMPETITOR_SECTION_HEADING = REQUIRED_DISCLOSURE_H3[5]
ALTERNATIVE_SECTION_HEADING = REQUIRED_DISCLOSURE_H3[9]
EXTENSION_REFERENCE_TEXT = "拟扩展保护已在对应创新点下高亮列出，本节不重复。"
NO_USABLE_COMPETITOR_EVIDENCE_SUMMARY = "已完成公开资料检索，但未发现足以形成具名对比的可靠证据；本节不对具体产品能力作断言。"
COMPETITOR_RESEARCH_INTENT_PATTERN = re.compile(
    r"竞品|相似方案|行业方案|现有技术|公开(?:方案|实现|产品|资料)|官方|专利|论文|标准|产品|"
    r"prior[\s-]+art|competitor|alternative|official|patent|paper|standard|product|solution|"
    r"documentation|repository",
    re.IGNORECASE,
)

GENERIC_KEYWORDS = {
    "平台",
    "模块",
    "系统",
    "安全",
    "高效",
    "智能",
    "优化",
    "服务",
    "方案",
    "能力",
}
IMPLEMENTATION_PATTERN = re.compile(
    r"(?:\.jar\b|\b(?:class|function|method|field|table)\b|"
    r"(?:Handler|Processor|ServiceImpl|Controller|Repository|Dao)\b|"
    r"[A-Za-z_$][A-Za-z0-9_$]*\([^)]*\)|\b[a-z][a-z0-9]*_[a-z0-9_]+\b|"
    r"\b[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\b)",
    re.IGNORECASE,
)
INTERNAL_IDENTIFIER_PATTERN = re.compile(
    r"(?:\b[a-z][a-z0-9]*_[a-z0-9_]+\b|\b[A-Za-z_$][A-Za-z0-9_$]*\([^)]*\)|"
    r"\b[A-Za-z_$][A-Za-z0-9_$]*(?:Handler|Processor|ServiceImpl|Controller|Repository|Dao)\b|"
    r"\b[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\b)"
)
PUBLIC_PROTECTION_EXTENSION_MARKER = "> **拟扩展保护**"
INTERNAL_APPENDIX_HEADING = "## 内部追溯附录（禁止对外）"
INTERNAL_APPENDIX_NOTICE = "> 本附录仅供内部评审、事实核对和校验使用。对外发送时只使用交底书目录根部的 disclosure.md，不得包含本附录。"
REQUIRED_INTERNAL_APPENDIX_H3 = (
    "来源事实台账",
    "发明扩展台账",
    "外部资料台账",
    "创新与效果映射",
    "效果证据",
    "竞品证据",
)
INTERNAL_TRACE_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:SF|IE|EM|C|BD|SYS|PB)[1-9]\d*(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
PUBLIC_RAW_ENUM_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:expected_observable|verified|public_fact|reasonable_inference|"
    r"pending_retrieval|evidence_found|searched_no_usable_evidence)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
DIAGRAM_ID_COMMENT_PATTERN = re.compile(r"<!--\s*diagram-id:\s*D[1-9]\d*\s*-->", re.IGNORECASE)
PUBLIC_EFFECT_STATUS = {
    "expected_observable": "预期可观察",
    "verified": "已有证据支持",
}
PUBLIC_EVIDENCE_TYPE = {
    "public_fact": "公开事实",
    "reasonable_inference": "合理推断",
}
STRUCTURAL_DECLARATION_PATTERN = re.compile(
    r"^\s*(?P<kind>actor|boundary|control|entity|database|collections|queue|rectangle|component|node|"
    r"cloud|folder|frame|package|artifact|card|file|storage|agent|usecase|interface|class|object|enum|annotation)\s+"
    r"(?:\"(?P<quoted>(?:\\.|[^\"])*)\"|\[(?P<bracket>[^\]]+)\]|(?P<plain>[^\s{]+))",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEPLOYMENT_TRIGGERS = {
    "cross_network",
    "cross_chain",
    "online_offline",
    "hsm",
    "manual_transfer",
    "manual_handoff",
}
ID_PATTERNS = {
    "diagram": re.compile(r"^D([1-9]\d*)$"),
    "innovation": re.compile(r"^I([1-9]\d*)$"),
    "effect": re.compile(r"^T([1-9]\d*)$"),
    "source": re.compile(r"^[A-Z][A-Z0-9_-]*$"),
}


@dataclass(frozen=True)
class Diagnostic:
    rule_id: str
    severity: str
    message: str
    location: str = ""


class ValidationContext:
    def __init__(self, package_dir: Path | None = None) -> None:
        self.package_dir = package_dir
        self.diagnostics: list[Diagnostic] = []

    def add(self, rule_id: str, severity: str, message: str, location: str = "") -> None:
        self.diagnostics.append(Diagnostic(rule_id, severity, message, location))

    def error(self, rule_id: str, message: str, location: str = "") -> None:
        self.add(rule_id, "error", message, location)

    def warning(self, rule_id: str, message: str, location: str = "") -> None:
        self.add(rule_id, "warning", message, location)

    def review(self, rule_id: str, message: str, location: str = "") -> None:
        self.add(rule_id, "review", message, location)

    @property
    def final_status(self) -> str:
        if any(item.severity == "error" for item in self.diagnostics):
            return "blocked"
        if any(item.severity == "review" for item in self.diagnostics):
            return "review_required"
        return "success"

    def result(self, mode: str) -> dict[str, Any]:
        deterministic = "failed" if any(
            item.severity == "error" for item in self.diagnostics
        ) else "passed"
        semantic = _review_check_state(self.diagnostics, ("REV-001", "REV-002", "REV-003"))
        visual = _review_check_state(self.diagnostics, ("REV-004", "REV-005"))
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "skill_name": SKILL_NAME,
            "mode": mode,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "final_status": self.final_status,
            "checks": {
                "deterministic": deterministic,
                "semantic_review": semantic,
                "visual_review": visual,
            },
            "diagnostics": [asdict(item) for item in self.diagnostics],
            "limitations": [
                "本地校验不证明外部资料真实性、专利新颖性或法律可专利性。",
                "本地校验只检查竞品检索记录完整且自洽，不能证明网络检索动作真实发生。",
                "本地校验只确认检索式包含已绑定的技术依据、上下文和研究意图词，不判断其余自由文本的语义相关性。",
                "零交叉和零遮挡依赖人工 SVG 复核；脚本仅验证复核记录与当前哈希绑定。",
                "真实 Session 回归需在获得脱敏样本后另行完成。",
            ],
        }


def _review_check_state(diagnostics: list[Diagnostic], prefixes: tuple[str, ...]) -> str:
    scoped = [item for item in diagnostics if item.rule_id.startswith(prefixes)]
    if any(item.severity == "error" for item in scoped):
        return "failed"
    if any(item.severity == "review" for item in scoped):
        return "pending"
    return "passed"


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(_rendered_scan_text(value).strip())


def _is_nonempty_scalar(value: Any) -> bool:
    return (isinstance(value, str) and bool(value.strip())) or (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if _is_nonempty_string(item)]


def _is_iso_date(value: Any) -> bool:
    if not _is_nonempty_string(value) or not DATE_PATTERN.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_public_http_locator(value: Any) -> bool:
    if not _is_nonempty_string(value):
        return False
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return False
    hostname = parsed.hostname.casefold()
    if hostname == "localhost" or hostname.endswith((".local", ".invalid", ".test")):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return "." in hostname and " " not in hostname
    return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved)


def _schema_errors(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    pointer: str,
) -> list[tuple[str, str]]:
    """执行本 skill schema 使用到的 Draft 2020-12 子集。

    这里刻意只依赖标准库，并直接读取随 skill 分发的 schema，避免手写
    字段合同与 JSON Schema 再次漂移。
    """

    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return [(pointer, f"不支持的 schema 引用：{ref}")]
        resolved: Any = root_schema
        try:
            for part in ref[2:].split("/"):
                resolved = resolved[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            return [(pointer, f"schema 引用不存在：{ref}")]
        if not isinstance(resolved, dict):
            return [(pointer, f"schema 引用不是对象：{ref}")]
        return _schema_errors(value, resolved, root_schema, pointer)

    errors: list[tuple[str, str]] = []
    expected_type = schema.get("type")
    type_matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if isinstance(expected_type, str) and not type_matches.get(expected_type, False):
        return [(pointer, f"类型必须为 {expected_type}")]
    if "const" in schema and value != schema["const"]:
        errors.append((pointer, f"值必须为 {schema['const']!r}"))
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append((pointer, f"值不在允许集合 {enum!r} 中"))

    if isinstance(value, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append((pointer, f"字符串长度必须不少于 {minimum}"))
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                if re.search(pattern, value) is None:
                    errors.append((pointer, f"字符串不匹配 pattern={pattern}"))
            except re.error as exc:
                errors.append((pointer, f"schema 正则无效：{exc}"))
        if schema.get("format") == "date" and not _is_iso_date(value):
            errors.append((pointer, "日期必须为有效 YYYY-MM-DD"))

    if isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append((pointer, f"数组条目不得少于 {minimum}"))
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append((pointer, f"数组条目不得多于 {maximum}"))
        if schema.get("uniqueItems") is True:
            serialized = [
                json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                for item in value
            ]
            if len(serialized) != len(set(serialized)):
                errors.append((pointer, "数组条目必须唯一"))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_schema_errors(item, item_schema, root_schema, f"{pointer}/{index}"))

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for field in required:
                if field not in value:
                    errors.append((f"{pointer}/{field}", "缺少必填字段"))
        properties = schema.get("properties")
        if isinstance(properties, dict):
            if schema.get("additionalProperties") is False:
                for field in value.keys() - properties.keys():
                    errors.append((f"{pointer}/{field}", "字段未在 schema 中声明"))
            for field, field_schema in properties.items():
                if field in value and isinstance(field_schema, dict):
                    errors.extend(
                        _schema_errors(value[field], field_schema, root_schema, f"{pointer}/{field}")
                    )

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for sub_schema in all_of:
            if not isinstance(sub_schema, dict):
                continue
            condition = sub_schema.get("if")
            if isinstance(condition, dict):
                branch = sub_schema.get("then") if not _schema_errors(value, condition, root_schema, pointer) else sub_schema.get("else")
                if isinstance(branch, dict):
                    errors.extend(_schema_errors(value, branch, root_schema, pointer))
            else:
                errors.extend(_schema_errors(value, sub_schema, root_schema, pointer))
    return errors


def _validate_manifest_schema(ctx: ValidationContext, manifest: dict[str, Any]) -> None:
    schema = _read_json(ctx, MANIFEST_SCHEMA_PATH, "SCH-000")
    if schema is None:
        return
    errors = _schema_errors(manifest, schema, schema, "disclosure-manifest.json#")
    for pointer, message in errors[:40]:
        ctx.error("SCH-001", message, pointer)
    if len(errors) > 40:
        ctx.error("SCH-001", f"另有 {len(errors) - 40} 条 schema 诊断未展开", "disclosure-manifest.json")


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _contains_internal_identifier(text: str, internal_originals: Iterable[str]) -> bool:
    folded = text.casefold()
    return bool(IMPLEMENTATION_PATTERN.search(text)) or any(
        original.casefold() in folded for original in internal_originals if original
    )


def _collect_manifest_text(value: Any, *, skipped_key: str = "") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_collect_manifest_text(item, skipped_key=skipped_key) for item in value)
    if isinstance(value, dict):
        return " ".join(
            _collect_manifest_text(item, skipped_key=skipped_key)
            for key, item in value.items()
            if key != skipped_key
        )
    return ""


def _term_originals(manifest: dict[str, Any]) -> list[str]:
    sources = manifest.get("sources") if isinstance(manifest.get("sources"), dict) else {}
    return [
        str(item.get("original"))
        for item in _dict_list(sources.get("term_generalizations"))
        if _is_nonempty_string(item.get("original"))
    ]


def _rendered_scan_text(text: str) -> str:
    """近似浏览器可见文本，用于识别 entity、全角字符和零宽字符绕过。"""

    normalized = unicodedata.normalize("NFKC", html.unescape(text))
    return re.sub(r"[\u200b-\u200d\u2060\ufeff]", "", normalized)


def _competitor_plain_text(text: str) -> str:
    """竞品检索字段的纯文本视图；不把 HTML entity 解码成检索词。"""

    normalized = unicodedata.normalize("NFKC", text)
    return "".join(character for character in normalized if unicodedata.category(character) not in {"Cf", "Cc"})


def _has_competitor_encoding(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return html.unescape(value) != value or any(unicodedata.category(character) in {"Cf", "Cc"} for character in value)


def _contains_competitor_term(query: str, term: str) -> bool:
    normalized_query = _competitor_plain_text(query).casefold()
    normalized_term = _competitor_plain_text(term).strip().casefold()
    if not normalized_term:
        return False
    if normalized_term.isascii():
        return bool(re.search(rf"(?<![\w]){re.escape(normalized_term)}(?![\w])", normalized_query))
    return normalized_term in normalized_query


def _contains_term_original(text: str, original: str) -> bool:
    """按标识符边界匹配 ASCII 原名，避免单字符原名误伤普通单词。"""

    if not original:
        return False
    if re.fullmatch(r"[A-Za-z0-9_]+", original):
        return re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(original)}(?![A-Za-z0-9_])",
            text,
            flags=re.IGNORECASE,
        ) is not None
    return original.casefold() in text.casefold()


def _leaked_term_originals(text: str, manifest: dict[str, Any]) -> list[str]:
    return [original for original in _term_originals(manifest) if _contains_term_original(text, original)]


def _source_fact_locators(manifest: dict[str, Any]) -> list[str]:
    sources = manifest.get("sources") if isinstance(manifest.get("sources"), dict) else {}
    return [
        str(item.get("source_locator"))
        for item in _dict_list(sources.get("source_facts"))
        if _is_nonempty_string(item.get("source_locator"))
    ]


def _protection_extension_texts(manifest: dict[str, Any]) -> list[str]:
    sources = manifest.get("sources") if isinstance(manifest.get("sources"), dict) else {}
    values = [
        str(item.get("statement"))
        for item in _dict_list(sources.get("invention_extensions"))
        if _is_nonempty_string(item.get("statement"))
    ]
    for innovation in _dict_list(manifest.get("innovations")):
        for extension in _dict_list(innovation.get("protection_extensions")):
            for field in ("scope", "rationale"):
                if _is_nonempty_string(extension.get(field)):
                    values.append(str(extension[field]))
    return values


def _trace_value(value: Any) -> str:
    normalized = re.sub(r"\s+", " ", str(value) if value is not None else "").strip()
    return normalized or "未提供"


def _public_competitor_section_lines(competitors: dict[str, Any]) -> list[str]:
    search_records = _dict_list(competitors.get("search_records"))
    queries = "；".join(_trace_value(item.get("query")) for item in search_records)
    dates = list(
        dict.fromkeys(
            _trace_value(item.get("searched_at"))
            for item in search_records
        )
    )
    lines = [
        f"检索范围：{queries}",
        f"检索日期：{'、'.join(dates)}",
        f"检索结论：{_trace_value(competitors.get('research_summary'))}",
    ]
    for item in _dict_list(competitors.get("evidence")):
        evidence_label = PUBLIC_EVIDENCE_TYPE.get(str(item.get("evidence_type", "")), "未提供")
        lines.append(
            f"- 名称：{_trace_value(item.get('name'))}；"
            f"相关业务或产品：{_trace_value(item.get('product_or_business'))}；"
            f"来源：{_trace_value(item.get('locator'))}；"
            f"检索日期：{_trace_value(item.get('retrieved_at'))}；"
            f"证据属性：{evidence_label}"
        )
    return lines


def _expected_internal_trace_lines(manifest: dict[str, Any]) -> list[str]:
    """生成内部附录必须逐行覆盖的追溯合同。"""

    sources = manifest.get("sources") if isinstance(manifest.get("sources"), dict) else {}
    lines: list[str] = []
    source_facts = _dict_list(sources.get("source_facts"))
    if source_facts:
        for item in source_facts:
            lines.append(
                f"- {_trace_value(item.get('id'))}｜陈述：{_trace_value(item.get('statement'))}｜"
                f"输入定位：{_trace_value(item.get('source_locator'))}"
            )
    else:
        lines.append("- 来源事实：无")

    invention_extensions = _dict_list(sources.get("invention_extensions"))
    if invention_extensions:
        for item in invention_extensions:
            basis_ids = "、".join(_string_list(item.get("basis_source_ids"))) or "无"
            lines.append(
                f"- {_trace_value(item.get('id'))}｜扩展内容：{_trace_value(item.get('statement'))}｜依据：{basis_ids}"
            )
    else:
        lines.append("- 发明扩展：无")

    external_materials = _dict_list(sources.get("external_materials"))
    if external_materials:
        for item in external_materials:
            lines.append(
                f"- {_trace_value(item.get('id'))}｜标题：{_trace_value(item.get('title'))}｜"
                f"定位：{_trace_value(item.get('locator'))}｜检索日期：{_trace_value(item.get('retrieved_at'))}｜"
                f"证据属性：{_trace_value(item.get('evidence_type'))}"
            )
    else:
        lines.append("- 外部资料：无")

    for item in _dict_list(manifest.get("innovations")):
        implementation = item.get("implementation_basis") if isinstance(item.get("implementation_basis"), dict) else {}
        source_ids = "、".join(_string_list(implementation.get("source_fact_ids"))) or "无"
        extension_ids = "、".join(
            str(extension.get("extension_id"))
            for extension in _dict_list(item.get("protection_extensions"))
            if _is_nonempty_string(extension.get("extension_id"))
        ) or "无"
        lines.append(
            f"- {_trace_value(item.get('id'))}｜已实现依据：{source_ids}｜"
            f"拟扩展：{extension_ids}｜效果：{_trace_value(item.get('effect_id'))}"
        )

    for item in _dict_list(manifest.get("effects")):
        evidence_ids = "、".join(_string_list(item.get("evidence_source_ids"))) or "无"
        lines.append(
            f"- {_trace_value(item.get('id'))}｜验证状态：{_trace_value(item.get('verification_status'))}｜"
            f"证据：{evidence_ids}"
        )

    competitors = manifest.get("competitors") if isinstance(manifest.get("competitors"), dict) else {}
    lines.append(
        f"- 检索状态：{_trace_value(competitors.get('status'))}｜"
        f"检索结论：{_trace_value(competitors.get('research_summary'))}"
    )
    for index, item in enumerate(_dict_list(competitors.get("search_records")), start=1):
        consulted = "、".join(_string_list(item.get("consulted_locators"))) or "无"
        basis_terms = "、".join(_string_list(item.get("basis_terms"))) or "无"
        context_terms = "、".join(_string_list(item.get("context_terms"))) or "无"
        lines.append(
            f"- 检索记录 {index}｜焦点：{_trace_value(item.get('focus'))}｜"
            f"依据词：{basis_terms}｜上下文词：{context_terms}｜检索式：{_trace_value(item.get('query'))}｜"
            f"检索日期：{_trace_value(item.get('searched_at'))}｜"
            f"查阅：{consulted}｜结果：{_trace_value(item.get('result_summary'))}"
        )
    competitor_evidence = _dict_list(competitors.get("evidence"))
    if competitor_evidence:
        for item in competitor_evidence:
            lines.append(
                f"- {_trace_value(item.get('id'))}｜名称：{_trace_value(item.get('name'))}｜"
                f"相关业务或产品：{_trace_value(item.get('product_or_business'))}｜"
                f"定位：{_trace_value(item.get('locator'))}｜检索日期：{_trace_value(item.get('retrieved_at'))}｜"
                f"证据属性：{_trace_value(item.get('evidence_type'))}"
            )
    else:
        lines.append("- 竞品证据：无")
    return lines


def _visible_structural_labels(puml_text: str) -> str:
    """只提取结构图的可见节点标签，避免把 PlantUML alias 当作正文实现项。"""

    labels: list[str] = []
    implementation_kinds = {"class", "object", "enum", "annotation"}
    for line in puml_text.splitlines():
        match = STRUCTURAL_DECLARATION_PATTERN.match(line)
        if not match:
            continue
        label = match.group("quoted") or match.group("bracket") or match.group("plain") or ""
        kind = match.group("kind").casefold()
        labels.append(f"{kind} {label}" if kind in implementation_kinds else label)
    return "\n".join(labels)


def _read_json(ctx: ValidationContext, path: Path, rule_id: str) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        ctx.error(rule_id, f"缺少文件：{path.name}", path.name)
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        ctx.error(rule_id, f"无法读取 JSON：{exc}", path.name)
        return None
    if not isinstance(data, dict):
        ctx.error(rule_id, "JSON 根节点必须是对象", path.name)
        return None
    return data


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError:
        return ""


def _normalize_puml(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def _normalized_puml_sha256(text: str) -> str:
    return _sha256_bytes(_normalize_puml(text).encode("utf-8"))


def _safe_package_path(package_dir: Path, raw_path: Any) -> Path | None:
    if not _is_nonempty_string(raw_path):
        return None
    normalized = str(raw_path).replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        return None
    candidate = (package_dir / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(package_dir.resolve())
    except ValueError:
        return None
    return candidate


def _resolved_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def _require_object_fields(
    ctx: ValidationContext,
    item: dict[str, Any],
    fields: Iterable[str],
    rule_id: str,
    location: str,
) -> bool:
    missing = [field for field in fields if not _is_nonempty_string(item.get(field))]
    if missing:
        ctx.error(rule_id, f"缺少非空字段：{', '.join(missing)}", location)
        return False
    return True


def _require_id_pattern(
    ctx: ValidationContext,
    value: Any,
    pattern: str,
    rule_id: str,
    location: str,
) -> None:
    if _is_nonempty_string(value) and not re.fullmatch(pattern, value):
        ctx.error(rule_id, f"编号格式不正确：{value}", location)


def _check_sequential_ids(
    ctx: ValidationContext,
    ids: list[str],
    kind: str,
    rule_id: str,
    location: str,
) -> None:
    pattern = ID_PATTERNS[kind]
    numbers: list[int] = []
    for value in ids:
        match = pattern.fullmatch(value)
        if not match:
            ctx.error(rule_id, f"非法编号：{value}", location)
            continue
        numbers.append(int(match.group(1)))
    if len(set(ids)) != len(ids):
        ctx.error(rule_id, "编号不可重复", location)
    if numbers and sorted(numbers) != list(range(1, len(numbers) + 1)):
        ctx.error(rule_id, f"编号必须从 1 连续递增，当前={ids}", location)


def _validate_input_and_boundaries(ctx: ValidationContext, manifest: dict[str, Any]) -> None:
    patent = manifest.get("patent")
    if not isinstance(patent, dict) or not _is_nonempty_string(patent.get("title")) or not _is_nonempty_string(patent.get("use_case")):
        ctx.error("INP-001", "patent.title 与 patent.use_case 必须为非空字符串", "disclosure-manifest.json#/patent")

    completeness = manifest.get("input_completeness")
    required_lists = (
        "technical_objects",
        "core_mechanisms",
        "necessary_constraints",
        "existing_problem_facts",
    )
    if not isinstance(completeness, dict):
        ctx.error("INP-002", "缺少 input_completeness 对象", "disclosure-manifest.json#/input_completeness")
    else:
        for field in required_lists:
            values = _string_list(completeness.get(field))
            if not values or len(values) != len(completeness.get(field, [])):
                ctx.error("INP-002", f"input_completeness.{field} 必须是非空字符串数组且至少一项", f"disclosure-manifest.json#/input_completeness/{field}")
            elif len(set(values)) != len(values):
                ctx.error("INP-002", f"input_completeness.{field} 不得重复", f"disclosure-manifest.json#/input_completeness/{field}")

        keywords = manifest.get("keywords") if isinstance(manifest.get("keywords"), dict) else {}
        for field in ("technical_objects", "core_mechanisms"):
            input_terms = set(_string_list(completeness.get(field)))
            keyword_terms = {
                str(item.get("term")).strip()
                for item in _dict_list(keywords.get(field))
                if _is_nonempty_string(item.get("term"))
            }
            missing_anchors = sorted(input_terms - keyword_terms)
            if missing_anchors:
                ctx.error(
                    "INP-004",
                    f"input_completeness.{field} 必须在同类关键词中保留精确落点，缺少={missing_anchors}",
                    f"disclosure-manifest.json#/input_completeness/{field}",
                )

    boundaries = manifest.get("boundaries")
    if not isinstance(boundaries, dict):
        ctx.error("BND-001", "缺少 boundaries 对象", "disclosure-manifest.json#/boundaries")
        return
    requirements = {
        "business_domains": ("id", "name", "scope"),
        "system_ownership": ("id", "name", "owner", "boundary"),
        "physical_boundaries": ("id", "type", "description"),
    }
    for field, required in requirements.items():
        raw = boundaries.get(field)
        items = _dict_list(raw)
        if not isinstance(raw, list) or len(items) != len(raw):
            ctx.error("BND-001", f"boundaries.{field} 必须是对象数组", f"disclosure-manifest.json#/boundaries/{field}")
            continue
        if field != "physical_boundaries" and not items:
            ctx.error("BND-001", f"boundaries.{field} 至少一项", f"disclosure-manifest.json#/boundaries/{field}")
        for index, item in enumerate(items):
            item_location = f"disclosure-manifest.json#/boundaries/{field}/{index}"
            _require_object_fields(ctx, item, required, "BND-002", item_location)
            id_patterns = {
                "business_domains": r"BD[1-9]\d*",
                "system_ownership": r"SYS[1-9]\d*",
                "physical_boundaries": r"PB[1-9]\d*",
            }
            _require_id_pattern(ctx, item.get("id"), id_patterns[field], "BND-002", item_location)
            visible = " ".join(str(item.get(key, "")) for key in ("name", "owner", "type", "description"))
            if IMPLEMENTATION_PATTERN.search(visible):
                ctx.error("BND-003", "顶层边界不得使用类、函数、JAR、处理器或字段等内部实现项", f"disclosure-manifest.json#/boundaries/{field}/{index}")
        item_ids = [str(item.get("id")) for item in items if _is_nonempty_string(item.get("id"))]
        if len(item_ids) != len(set(item_ids)):
            ctx.error("BND-002", f"boundaries.{field} 的 id 不得重复", f"disclosure-manifest.json#/boundaries/{field}")
    triggers = boundaries.get("deployment_triggers")
    if not isinstance(triggers, list) or len(_string_list(triggers)) != len(triggers):
        ctx.error("BND-004", "boundaries.deployment_triggers 必须是字符串数组", "disclosure-manifest.json#/boundaries/deployment_triggers")
    elif len(set(triggers)) != len(triggers) or any(item not in DEPLOYMENT_TRIGGERS for item in triggers):
        ctx.error("BND-004", "deployment_triggers 含重复或未注册值", "disclosure-manifest.json#/boundaries/deployment_triggers")
    if _string_list(triggers) and not _dict_list(boundaries.get("physical_boundaries")):
        ctx.error("BND-005", "存在部署触发条件时必须给出物理边界", "disclosure-manifest.json#/boundaries/physical_boundaries")
    semantic_text = _collect_manifest_text(manifest, skipped_key="deployment_triggers")
    detected: set[str] = set()
    if re.search(r"跨网|跨网络|隔离网络", semantic_text, flags=re.IGNORECASE):
        detected.add("cross_network")
    if re.search(r"跨链|cross[-_ ]?chain", semantic_text, flags=re.IGNORECASE):
        detected.add("cross_chain")
    if ("在线" in semantic_text and "离线" in semantic_text) or re.search(r"online.{0,20}offline|offline.{0,20}online", semantic_text, flags=re.IGNORECASE | re.DOTALL):
        detected.add("online_offline")
    if re.search(r"\bHSM\b|硬件安全模块", semantic_text, flags=re.IGNORECASE):
        detected.add("hsm")
    if re.search(r"人工摆渡|人工带回|人工带入|人工搬运|人工转运", semantic_text):
        detected.add("manual_transfer")
    if re.search(r"人工交接|人工交付|人工接收", semantic_text):
        detected.add("manual_handoff")
    missing_triggers = sorted(detected - set(_string_list(triggers)))
    if missing_triggers:
        ctx.error("BND-006", f"内容已出现部署条件但 deployment_triggers 未声明：{missing_triggers}", "disclosure-manifest.json#/boundaries/deployment_triggers")


def _validate_sources(ctx: ValidationContext, manifest: dict[str, Any]) -> None:
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        ctx.error("EVD-001", "缺少 sources 三类来源台账", "disclosure-manifest.json#/sources")
        return
    facts_raw = sources.get("source_facts")
    extensions_raw = sources.get("invention_extensions")
    external_raw = sources.get("external_materials")
    mappings_raw = sources.get("term_generalizations")
    allowlist_raw = sources.get("abbreviation_allowlist")
    if not all(isinstance(value, list) for value in (facts_raw, extensions_raw, external_raw, mappings_raw, allowlist_raw)):
        ctx.error("EVD-001", "来源事实、发明扩展、外部资料、术语泛化及缩写白名单均必须是数组", "disclosure-manifest.json#/sources")
        return

    facts = _dict_list(facts_raw)
    if not facts or len(facts) != len(facts_raw):
        ctx.error("EVD-002", "source_facts 必须至少包含一条对象记录", "disclosure-manifest.json#/sources/source_facts")
    fact_ids: set[str] = set()
    for index, item in enumerate(facts):
        _require_object_fields(ctx, item, ("id", "statement", "source_locator"), "EVD-002", f"disclosure-manifest.json#/sources/source_facts/{index}")
        _require_id_pattern(ctx, item.get("id"), r"SF[1-9]\d*", "EVD-002", f"disclosure-manifest.json#/sources/source_facts/{index}")
        if _is_nonempty_string(item.get("id")):
            fact_ids.add(item["id"])
    if len(fact_ids) != len(facts):
        ctx.error("EVD-002", "source_facts 的 id 不得重复", "disclosure-manifest.json#/sources/source_facts")

    extensions = _dict_list(extensions_raw)
    external = _dict_list(external_raw)
    mappings = _dict_list(mappings_raw)
    if len(extensions) != len(extensions_raw) or len(external) != len(external_raw) or len(mappings) != len(mappings_raw):
        ctx.error("EVD-001", "来源台账数组只能包含对象", "disclosure-manifest.json#/sources")

    extension_ids: list[str] = []
    for index, item in enumerate(extensions):
        location = f"disclosure-manifest.json#/sources/invention_extensions/{index}"
        _require_object_fields(ctx, item, ("id", "statement"), "EVD-003", location)
        _require_id_pattern(ctx, item.get("id"), r"IE[1-9]\d*", "EVD-003", location)
        if _is_nonempty_string(item.get("id")):
            extension_ids.append(item["id"])
        basis = _string_list(item.get("basis_source_ids"))
        if not basis or len(basis) != len(set(basis)) or any(source_id not in fact_ids for source_id in basis):
            ctx.error("EVD-003", "发明扩展必须引用已存在的来源事实 id", location)
    if len(extension_ids) != len(set(extension_ids)):
        ctx.error("EVD-003", "invention_extensions 的 id 不得重复", "disclosure-manifest.json#/sources/invention_extensions")

    external_ids: list[str] = []
    for index, item in enumerate(external):
        location = f"disclosure-manifest.json#/sources/external_materials/{index}"
        _require_object_fields(ctx, item, ("id", "title", "locator", "retrieved_at", "evidence_type"), "EVD-004", location)
        _require_id_pattern(ctx, item.get("id"), r"EM[1-9]\d*", "EVD-004", location)
        if _is_nonempty_string(item.get("id")):
            external_ids.append(item["id"])
        if _is_nonempty_string(item.get("retrieved_at")) and not _is_iso_date(item["retrieved_at"]):
            ctx.error("EVD-004", "retrieved_at 必须为 YYYY-MM-DD", location)
        evidence_type = item.get("evidence_type")
        if not isinstance(evidence_type, str) or evidence_type not in {"public_fact", "reasonable_inference"}:
            ctx.error("EVD-004", "evidence_type 仅允许 public_fact 或 reasonable_inference", location)

    if len(external_ids) != len(set(external_ids)):
        ctx.error("EVD-004", "external_materials 的 id 不得重复", "disclosure-manifest.json#/sources/external_materials")

    for index, item in enumerate(mappings):
        _require_object_fields(ctx, item, ("original", "generalized", "reason"), "EVD-005", f"disclosure-manifest.json#/sources/term_generalizations/{index}")
    allowlist = _string_list(allowlist_raw)
    if len(allowlist) != len(allowlist_raw) or len(allowlist) != len(set(allowlist)):
        ctx.error("EVD-005", "abbreviation_allowlist 必须只包含非空字符串", "disclosure-manifest.json#/sources/abbreviation_allowlist")


def _validate_keywords(ctx: ValidationContext, manifest: dict[str, Any]) -> None:
    keywords = manifest.get("keywords")
    if not isinstance(keywords, dict):
        ctx.error("KWD-001", "缺少 keywords 分类对象", "disclosure-manifest.json#/keywords")
        return
    limits = {
        "technical_objects": (1, 2),
        "core_mechanisms": (2, 4),
        "key_constraints": (1, 2),
    }
    all_terms: list[tuple[str, str]] = []
    for field, (minimum, maximum) in limits.items():
        raw = keywords.get(field)
        items = _dict_list(raw)
        if not isinstance(raw, list) or len(items) != len(raw) or not minimum <= len(items) <= maximum:
            ctx.error("KWD-001", f"keywords.{field} 应为 {minimum}-{maximum} 条对象", f"disclosure-manifest.json#/keywords/{field}")
            continue
        for index, item in enumerate(items):
            location = f"disclosure-manifest.json#/keywords/{field}/{index}"
            _require_object_fields(ctx, item, ("term", "anchor"), "KWD-002", location)
            if _is_nonempty_string(item.get("term")):
                all_terms.append((item["term"].strip(), location))
    if not 5 <= len(all_terms) <= 8:
        ctx.error("KWD-001", f"关键词总数必须为 5-8，当前={len(all_terms)}", "disclosure-manifest.json#/keywords")
    normalized = [term.casefold() for term, _ in all_terms]
    if len(set(normalized)) != len(normalized):
        ctx.error("KWD-003", "三组关键词必须互斥且不得重复", "disclosure-manifest.json#/keywords")

    sources = manifest.get("sources") if isinstance(manifest.get("sources"), dict) else {}
    allowlist = {item.casefold() for item in _string_list(sources.get("abbreviation_allowlist"))}
    generalized_originals = {
        str(item.get("original", "")).casefold()
        for item in _dict_list(sources.get("term_generalizations"))
        if _is_nonempty_string(item.get("original"))
    }
    for term, location in all_terms:
        compact = term.strip()
        if compact in GENERIC_KEYWORDS:
            ctx.error("KWD-004", f"禁止单独使用低区分度泛词：{compact}", location)
        if INTERNAL_IDENTIFIER_PATTERN.search(compact) or compact.casefold() in generalized_originals:
            ctx.error("KWD-005", f"关键词不得使用内部标识或未泛化产品词：{compact}", location)
        if re.fullmatch(r"[A-Z][A-Z0-9-]{1,10}", compact) and compact.casefold() not in allowlist:
            ctx.error("KWD-005", f"缩写未进入 abbreviation_allowlist：{compact}", location)


def _validate_innovations_and_effects(ctx: ValidationContext, manifest: dict[str, Any]) -> None:
    claim = manifest.get("core_invention_claim")
    if not _is_nonempty_string(claim) or len(claim.strip()) < 20:
        ctx.error("INV-001", "必须提供不少于 20 字的唯一核心发明主张", "disclosure-manifest.json#/core_invention_claim")

    sources = manifest.get("sources") if isinstance(manifest.get("sources"), dict) else {}
    source_fact_ids = {
        str(item.get("id"))
        for item in _dict_list(sources.get("source_facts"))
        if _is_nonempty_string(item.get("id"))
    }
    internal_originals = [
        str(item.get("original"))
        for item in _dict_list(sources.get("term_generalizations"))
        if _is_nonempty_string(item.get("original"))
    ]
    invention_extension_ids = [
        str(item.get("id"))
        for item in _dict_list(sources.get("invention_extensions"))
        if _is_nonempty_string(item.get("id"))
    ]
    invention_extension_id_set = set(invention_extension_ids)
    innovations_raw = manifest.get("innovations")
    innovations = _dict_list(innovations_raw)
    if not isinstance(innovations_raw, list) or len(innovations) != len(innovations_raw) or not 2 <= len(innovations) <= 4:
        ctx.error("INV-002", f"innovations 必须包含 2-4 条对象，当前={len(innovations)}", "disclosure-manifest.json#/innovations")
    innovation_ids: list[str] = []
    innovation_effect_pairs: list[tuple[str, str]] = []
    bound_extension_ids: list[str] = []
    required_innovation_fields = (
        "id",
        "comparison_baseline",
        "core_mechanism",
        "necessary_constraint",
        "substantive_difference",
        "value_link",
        "effect_id",
    )
    for index, item in enumerate(innovations):
        location = f"disclosure-manifest.json#/innovations/{index}"
        _require_object_fields(ctx, item, required_innovation_fields, "INV-003", location)
        implementation = item.get("implementation_basis")
        if not isinstance(implementation, dict):
            ctx.error("INV-007", "创新点必须提供 implementation_basis 已实现基础对象", f"{location}/implementation_basis")
        else:
            _require_object_fields(
                ctx,
                implementation,
                ("technical_object", "trigger_or_input", "processing", "constraint", "output_or_state"),
                "INV-007",
                f"{location}/implementation_basis",
            )
            basis_source_raw = implementation.get("source_fact_ids")
            basis_source_ids = _string_list(basis_source_raw)
            if (
                not isinstance(basis_source_raw, list)
                or not basis_source_ids
                or len(basis_source_ids) != len(basis_source_raw)
                or len(basis_source_ids) != len(set(basis_source_ids))
                or any(source_id not in source_fact_ids for source_id in basis_source_ids)
            ):
                ctx.error("INV-007", "已实现基础必须引用至少一条已存在且不重复的 SF 来源事实", f"{location}/implementation_basis/source_fact_ids")
            implementation_text = " ".join(
                str(implementation.get(field, ""))
                for field in ("technical_object", "trigger_or_input", "processing", "constraint", "output_or_state")
            )
            if _contains_internal_identifier(implementation_text, internal_originals):
                ctx.error("INV-007", "已实现基础必须保留具体技术路径但泛化类名、函数、字段、表结构和内部产品标识", f"{location}/implementation_basis")
        protection_raw = item.get("protection_extensions")
        protection_extensions = _dict_list(protection_raw)
        if not isinstance(protection_raw, list) or len(protection_extensions) != len(protection_raw):
            ctx.error("INV-007", "protection_extensions 必须是对象数组，允许为空", f"{location}/protection_extensions")
        else:
            for extension_index, extension in enumerate(protection_extensions):
                _require_object_fields(
                    ctx,
                    extension,
                    ("extension_id", "scope", "rationale"),
                    "INV-007",
                    f"{location}/protection_extensions/{extension_index}",
                )
                extension_id = extension.get("extension_id")
                if _is_nonempty_string(extension_id):
                    bound_extension_ids.append(extension_id)
                    if extension_id not in invention_extension_id_set:
                        ctx.error(
                            "INV-007",
                            f"拟扩展保护引用了不存在的发明扩展台账编号：{extension_id}",
                            f"{location}/protection_extensions/{extension_index}/extension_id",
                        )
                extension_text = " ".join(
                    str(extension.get(field, "")) for field in ("scope", "rationale")
                )
                if _contains_internal_identifier(extension_text, internal_originals):
                    ctx.error(
                        "INV-007",
                        "拟扩展保护必须泛化类名、函数、字段、表结构和内部产品标识",
                        f"{location}/protection_extensions/{extension_index}",
                    )
        if _is_nonempty_string(item.get("id")):
            innovation_ids.append(item["id"])
        if _is_nonempty_string(item.get("id")) and _is_nonempty_string(item.get("effect_id")):
            innovation_effect_pairs.append((item["id"], item["effect_id"]))
        anchors = _string_list(item.get("anchors"))
        if not anchors or len(anchors) != len(item.get("anchors", [])):
            ctx.error("INV-004", "创新点必须提供至少一个正文或图示落点", location)
        baseline = str(item.get("comparison_baseline", "")).strip()
        mechanism = str(item.get("core_mechanism", "")).strip()
        difference = str(item.get("substantive_difference", "")).strip()
        value_link = str(item.get("value_link", "")).strip()
        if mechanism in {"模块拆分", "组件拆分", "模块组合", "组件组合"} or difference in {"结构不同", "模块不同", "实现不同"}:
            ctx.error("INV-005", "普通模块拆分或空泛差异不能作为创新机制", location)
        if (
            value_link in {"提升效率", "增强安全", "优化体验", "产生价值", "效果更好", "显著提升"}
            or value_link in {mechanism, difference}
            or baseline in {mechanism, difference}
        ):
            ctx.error("INV-006", "创新点必须区分对比基线、处理方式、实质差异和具体价值因果，不能只写做法或泛化好处", location)
    _check_sequential_ids(ctx, innovation_ids, "innovation", "INV-002", "disclosure-manifest.json#/innovations")
    duplicate_extension_ids = sorted(
        extension_id
        for extension_id in set(bound_extension_ids)
        if bound_extension_ids.count(extension_id) > 1
    )
    orphan_extension_ids = sorted(invention_extension_id_set - set(bound_extension_ids))
    if duplicate_extension_ids:
        ctx.error(
            "INV-007",
            f"每个 IE 发明扩展只能绑定一个创新点保护项，重复={duplicate_extension_ids}",
            "disclosure-manifest.json#/innovations",
        )
    if orphan_extension_ids:
        ctx.error(
            "INV-007",
            f"发明扩展台账不得存在未绑定到创新点的孤立项：{orphan_extension_ids}",
            "disclosure-manifest.json#/sources/invention_extensions",
        )

    effects_raw = manifest.get("effects")
    effects = _dict_list(effects_raw)
    if not isinstance(effects_raw, list) or len(effects) != len(effects_raw) or not 2 <= len(effects) <= 4:
        ctx.error("EFF-001", "effects 必须包含 2-4 条对象", "disclosure-manifest.json#/effects")
    effect_ids: list[str] = []
    effect_innovation_pairs: list[tuple[str, str]] = []
    evidence_source_ids = {
        str(item.get("id"))
        for field in ("source_facts", "external_materials")
        for item in _dict_list(sources.get(field))
        if _is_nonempty_string(item.get("id"))
    }
    for index, item in enumerate(effects):
        location = f"disclosure-manifest.json#/effects/{index}"
        required = ("id", "innovation_id", "original_problem", "mechanism", "observable_result", "verification_status")
        _require_object_fields(ctx, item, required, "EFF-002", location)
        if _is_nonempty_string(item.get("id")):
            effect_ids.append(item["id"])
        if _is_nonempty_string(item.get("id")) and _is_nonempty_string(item.get("innovation_id")):
            effect_innovation_pairs.append((item["innovation_id"], item["id"]))
        verification_status = item.get("verification_status")
        if not isinstance(verification_status, str) or verification_status not in {"verified", "expected_observable"}:
            ctx.error("EFF-002", "verification_status 仅允许 verified 或 expected_observable", location)
        support_raw = item.get("evidence_source_ids")
        support = _string_list(support_raw)
        if not isinstance(support_raw, list) or len(support) != len(support_raw) or len(support) != len(set(support)):
            ctx.error("EFF-005", "evidence_source_ids 必须是无重复的非空字符串数组", location)
        elif any(source_id not in evidence_source_ids for source_id in support):
            ctx.error("EFF-005", "evidence_source_ids 必须引用已存在的 SF/EM 来源记录", location)
        elif verification_status == "verified" and not support:
            ctx.error("EFF-005", "verified 技术效果必须绑定至少一条 SF/EM 验证证据；无证据应标为 expected_observable", location)
        result = str(item.get("observable_result", "")).strip()
        if result in {"提升效率", "增强安全", "优化体验", "显著提升", "全面提升"}:
            ctx.error("EFF-004", "可观察结果不得仅使用无法验证的泛化结论", location)
    _check_sequential_ids(ctx, effect_ids, "effect", "EFF-001", "disclosure-manifest.json#/effects")
    if (
        sorted(effect_innovation_pairs) != sorted(innovation_effect_pairs)
        or len(effect_innovation_pairs) != len(set(effect_innovation_pairs))
        or len(innovation_effect_pairs) != len(set(innovation_effect_pairs))
    ):
        ctx.error("EFF-003", "每个创新点与技术效果必须通过 effect_id/innovation_id 双向一致且唯一映射", "disclosure-manifest.json#/effects")


def _validate_competitors(ctx: ValidationContext, manifest: dict[str, Any]) -> None:
    competitors = manifest.get("competitors")
    if not isinstance(competitors, dict):
        ctx.error("CMP-001", "缺少 competitors 对象", "disclosure-manifest.json#/competitors")
        return
    status = competitors.get("status")
    research_summary = competitors.get("research_summary")
    search_records_raw = competitors.get("search_records")
    search_records = _dict_list(search_records_raw)
    evidence_raw = competitors.get("evidence")
    evidence = _dict_list(evidence_raw)
    allowed_statuses = {"evidence_found", "searched_no_usable_evidence"}
    if not isinstance(status, str) or status not in allowed_statuses:
        ctx.error(
            "CMP-001",
            "competitors.status 仅允许 evidence_found/searched_no_usable_evidence，旧 pending_retrieval 不再允许",
            "disclosure-manifest.json#/competitors/status",
        )
    if not isinstance(evidence_raw, list) or len(evidence) != len(evidence_raw):
        ctx.error("CMP-001", "competitors.evidence 必须为对象数组", "disclosure-manifest.json#/competitors/evidence")
        evidence = []
    if status == "evidence_found" and not 1 <= len(evidence) <= 3:
        ctx.error("CMP-001", f"evidence_found 必须有 1-3 条完整证据，当前={len(evidence)}", "disclosure-manifest.json#/competitors/evidence")
    if status == "searched_no_usable_evidence" and evidence:
        ctx.error("CMP-001", "searched_no_usable_evidence 不得混入具名竞品证据", "disclosure-manifest.json#/competitors/evidence")

    normalized_summary = re.sub(
        r"\s+",
        " ",
        _rendered_scan_text(str(research_summary) if research_summary is not None else ""),
    ).strip()
    placeholder_pattern = re.compile(
        r"待检索|待补充|后续补充|当前输入未包含|尚未检索|尚未完成|"
        r"\b(?:tbd|todo)\b|research\s+is\s+incomplete|(?:will\s+be|to\s+be)\s+added\s+later",
        re.IGNORECASE,
    )
    if len(normalized_summary) < 20 or placeholder_pattern.search(normalized_summary):
        ctx.error("CMP-003", "竞品研究必须提供不少于 20 字的具体检索结论，不得使用待检索占位", "disclosure-manifest.json#/competitors/research_summary")
    normalized_no_evidence_summary = re.sub(
        r"\s+",
        " ",
        _rendered_scan_text(NO_USABLE_COMPETITOR_EVIDENCE_SUMMARY),
    ).strip()
    if status == "searched_no_usable_evidence" and normalized_summary != normalized_no_evidence_summary:
        ctx.error(
            "CMP-003",
            "无可用证据状态必须使用固定无具名断言结论，详细检索发现仅写入 search_records",
            "disclosure-manifest.json#/competitors/research_summary",
        )
    if not isinstance(search_records_raw, list) or len(search_records) != len(search_records_raw):
        ctx.error("CMP-003", "search_records 必须为对象数组", "disclosure-manifest.json#/competitors/search_records")
        search_records = []
    if not 2 <= len(search_records) <= 6:
        ctx.error("CMP-003", f"竞品研究必须包含 2-6 组实际检索记录，当前={len(search_records)}", "disclosure-manifest.json#/competitors/search_records")

    focuses: set[str] = set()
    normalized_queries: list[str] = []
    consulted_dates: dict[str, set[str]] = {}
    input_completeness = manifest.get("input_completeness") if isinstance(manifest.get("input_completeness"), dict) else {}
    keywords = manifest.get("keywords") if isinstance(manifest.get("keywords"), dict) else {}
    input_terms = {
        "technical_object": set(_string_list(input_completeness.get("technical_objects"))),
        "core_mechanism": set(_string_list(input_completeness.get("core_mechanisms"))),
    }
    keyword_terms = {
        "technical_object": {
            str(item.get("term")).strip()
            for item in _dict_list(keywords.get("technical_objects"))
            if _is_nonempty_string(item.get("term"))
        },
        "core_mechanism": {
            str(item.get("term")).strip()
            for item in _dict_list(keywords.get("core_mechanisms"))
            if _is_nonempty_string(item.get("term"))
        },
    }
    grounded_terms = {
        focus: input_terms[focus] & keyword_terms[focus]
        for focus in ("technical_object", "core_mechanism")
    }
    use_case = str((manifest.get("patent") or {}).get("use_case", "")) if isinstance(manifest.get("patent"), dict) else ""
    for index, item in enumerate(search_records):
        location = f"disclosure-manifest.json#/competitors/search_records/{index}"
        _require_object_fields(
            ctx,
            item,
            ("focus", "query", "searched_at", "result_summary"),
            "CMP-003",
            location,
        )
        focus = item.get("focus")
        if not isinstance(focus, str) or focus not in {"technical_object", "core_mechanism"}:
            ctx.error("CMP-003", "focus 仅允许 technical_object 或 core_mechanism", location)
        else:
            focuses.add(focus)
        query = item.get("query")
        raw_query = query if isinstance(query, str) else ""
        normalized_query = re.sub(
            r"\s+",
            " ",
            _competitor_plain_text(raw_query),
        ).strip()
        if len(normalized_query) < 3 or placeholder_pattern.search(normalized_query):
            ctx.error("CMP-003", "检索式不得为空、过短或使用待检索占位", location)
        else:
            normalized_queries.append(normalized_query.casefold())
        if _has_competitor_encoding(query):
            ctx.error("CMP-005", "检索式必须记录实际纯文本，不得包含 HTML entity、零宽字符或控制字符", location)
        if normalized_query and not COMPETITOR_RESEARCH_INTENT_PATTERN.search(normalized_query):
            ctx.error("CMP-005", "检索式必须包含产品、官方、专利、论文、标准或相似方案等研究限定词", location)
        basis_raw = item.get("basis_terms")
        basis_terms = _string_list(basis_raw)
        if not isinstance(basis_raw, list) or len(basis_terms) != len(basis_raw) or not 1 <= len(basis_terms) <= 3:
            ctx.error("CMP-003", "每组检索必须绑定 1-3 个 manifest 技术依据词", location)
        allowed_terms = grounded_terms.get(str(focus), set())
        for basis_term in basis_terms:
            if _has_competitor_encoding(basis_term):
                ctx.error("CMP-005", "技术依据词不得包含 HTML entity、零宽字符或控制字符", location)
            if basis_term not in allowed_terms:
                ctx.error("CMP-005", "basis_terms 必须同时存在于对应的输入完整性与关键词分类", location)
            if not _contains_competitor_term(raw_query, basis_term):
                ctx.error("CMP-005", "每个 basis_terms 依据词必须以纯文本原样出现在实际检索式中", location)

        context_raw = item.get("context_terms")
        context_terms = _string_list(context_raw)
        if not isinstance(context_raw, list) or len(context_terms) != len(context_raw) or not 1 <= len(context_terms) <= 3:
            ctx.error("CMP-005", "每组检索必须绑定 1-3 个使用场景或跨分类上下文词", location)
        opposite_focus = "core_mechanism" if focus == "technical_object" else "technical_object"
        opposite_terms = grounded_terms.get(opposite_focus, set())
        for context_term in context_terms:
            if _has_competitor_encoding(context_term):
                ctx.error("CMP-005", "上下文词不得包含 HTML entity、零宽字符或控制字符", location)
            visible_context = _competitor_plain_text(context_term).strip()
            grounded_in_use_case = len(visible_context) >= 2 and _contains_competitor_term(use_case, context_term)
            if context_term not in opposite_terms and not grounded_in_use_case:
                ctx.error("CMP-005", "context_terms 必须来自另一技术分类或原样落入已确认使用场景", location)
            if not _contains_competitor_term(raw_query, context_term):
                ctx.error("CMP-005", "每个 context_terms 上下文词必须以纯文本原样出现在实际检索式中", location)
        searched_at = item.get("searched_at")
        if not _is_iso_date(searched_at):
            ctx.error("CMP-003", "searched_at 必须为有效 YYYY-MM-DD", location)
        locators_raw = item.get("consulted_locators")
        locators = _string_list(locators_raw)
        if not isinstance(locators_raw, list) or len(locators) != len(locators_raw) or not 1 <= len(locators) <= 5:
            ctx.error("CMP-003", "每组检索必须记录 1-5 个实际查阅页面", location)
        for locator in locators:
            if not _is_public_http_locator(locator):
                ctx.error("CMP-003", "实际查阅页面必须为可定位的 HTTP(S) 地址", location)
            if _is_iso_date(searched_at):
                consulted_dates.setdefault(locator, set()).add(str(searched_at))
        result_summary = item.get("result_summary")
        normalized_result = re.sub(
            r"\s+",
            " ",
            _rendered_scan_text(str(result_summary) if result_summary is not None else ""),
        ).strip()
        if len(normalized_result) < 10 or placeholder_pattern.search(normalized_result):
            ctx.error("CMP-003", "每组检索必须给出不少于 10 字的结果摘要，不得使用待检索占位", location)
    if focuses != {"technical_object", "core_mechanism"}:
        ctx.error("CMP-003", "检索记录必须同时覆盖技术对象和核心机制两类焦点", "disclosure-manifest.json#/competitors/search_records")
    if len(normalized_queries) != len(set(normalized_queries)):
        ctx.error("CMP-003", "多组检索式必须互不相同，不能复制同一查询凑数量", "disclosure-manifest.json#/competitors/search_records")

    evidence_ids: list[str] = []
    for index, item in enumerate(evidence):
        location = f"disclosure-manifest.json#/competitors/evidence/{index}"
        _require_object_fields(ctx, item, ("id", "name", "product_or_business", "locator", "retrieved_at", "evidence_type"), "CMP-002", location)
        _require_id_pattern(ctx, item.get("id"), r"C[1-9]\d*", "CMP-002", location)
        if _is_nonempty_string(item.get("id")):
            evidence_ids.append(str(item["id"]))
        locator = item.get("locator")
        if not _is_public_http_locator(locator):
            ctx.error("CMP-002", "竞品证据定位必须为实际公开页面的 HTTP(S) 地址", location)
        if _is_nonempty_string(item.get("retrieved_at")) and not _is_iso_date(item["retrieved_at"]):
            ctx.error("CMP-002", "retrieved_at 必须为 YYYY-MM-DD", location)
        evidence_type = item.get("evidence_type")
        if not isinstance(evidence_type, str) or evidence_type not in {"public_fact", "reasonable_inference"}:
            ctx.error("CMP-002", "evidence_type 仅允许 public_fact 或 reasonable_inference", location)
        if _is_public_http_locator(locator):
            matching_dates = consulted_dates.get(str(locator), set())
            if not matching_dates or str(item.get("retrieved_at", "")) not in matching_dates:
                ctx.error("CMP-002", "竞品证据的定位地址和检索日期必须回溯到 search_records", location)
    expected_ids = [f"C{index}" for index in range(1, len(evidence_ids) + 1)]
    if evidence_ids != expected_ids:
        ctx.error("CMP-002", f"竞品证据编号必须从 C1 连续且不重复，当前={evidence_ids}", "disclosure-manifest.json#/competitors/evidence")


def _extract_embedded_diagrams(markdown: str) -> tuple[dict[str, str], int]:
    block_pattern = re.compile(r"```(?:plantuml|puml)\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)
    marker_pattern = re.compile(r"<!--\s*diagram-id:\s*(D[1-9]\d*)\s*-->\s*$", re.IGNORECASE)
    lines = markdown.splitlines()
    result: dict[str, str] = {}
    block_count = 0
    offset = 0
    for block_match in block_pattern.finditer(markdown):
        block_count += 1
        prefix = markdown[: block_match.start()]
        previous_lines = prefix.splitlines()
        diagram_id = ""
        for line in reversed(previous_lines[-4:]):
            marker = marker_pattern.fullmatch(line.strip())
            if marker:
                diagram_id = marker.group(1).upper()
                break
            if line.strip():
                break
        if diagram_id and diagram_id not in result:
            result[diagram_id] = block_match.group(1)
        offset = block_match.end()
    _ = offset
    return result, block_count


def _validate_document(ctx: ValidationContext, package_dir: Path, manifest: dict[str, Any]) -> tuple[str, dict[str, str]]:
    doc_path = package_dir / "disclosure.md"
    try:
        text = doc_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        ctx.error("PKG-002", f"无法读取 disclosure.md：{exc}", "disclosure.md")
        return "", {}
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if not re.fullmatch(r"# 一种.+(?:方法/系统|方法|系统)", first):
        ctx.error("PKG-003", "文档标题必须为“# 一种XXX方法/系统”", "disclosure.md:1")
    patent = manifest.get("patent") if isinstance(manifest.get("patent"), dict) else {}
    expected_title = f"# {patent.get('title', '')}"
    if _is_nonempty_string(patent.get("title")) and first != expected_title:
        ctx.error("DOC-001", "disclosure.md 标题必须与 manifest.patent.title 完全一致", "disclosure.md:1")
    if "{{" in text or "XXX" in text:
        ctx.error("PKG-004", "文档仍包含模板占位符", "disclosure.md")
    headings = {line[4:].strip() for line in text.splitlines() if line.startswith("### ")}
    missing_headings = [heading for heading in REQUIRED_DISCLOSURE_H3 if heading not in headings]
    if missing_headings:
        ctx.error("DOC-002", f"完整交底书缺少固定三级章节：{', '.join(missing_headings)}", "disclosure.md")
    scan_text = _rendered_scan_text(text)
    leaked_trace_ids = sorted(set(INTERNAL_TRACE_ID_PATTERN.findall(scan_text)), key=str.casefold)
    if leaked_trace_ids:
        ctx.error("DOC-004", f"对外版不得出现内部追溯编号：{leaked_trace_ids}", "disclosure.md")
    leaked_locators = [
        locator
        for locator in _source_fact_locators(manifest)
        if _rendered_scan_text(locator) in scan_text
    ]
    if leaked_locators:
        ctx.error("DOC-004", "对外版不得出现来源事实的内部输入定位", "disclosure.md")
    leaked_originals = _leaked_term_originals(scan_text, manifest)
    if leaked_originals:
        ctx.error("DOC-004", "对外版不得出现术语泛化前的内部标识", "disclosure.md")
    if "来源依据" in scan_text:
        ctx.error("DOC-004", "对外版不得保留“来源依据”追溯标签", "disclosure.md")
    if INTERNAL_APPENDIX_HEADING in scan_text:
        ctx.error("DOC-004", "内部追溯附录不得出现在对外版", "disclosure.md")
    raw_enums = sorted(set(PUBLIC_RAW_ENUM_PATTERN.findall(scan_text)), key=str.casefold)
    if raw_enums:
        ctx.error("DOC-004", f"对外版不得出现机器枚举原值：{raw_enums}", "disclosure.md")
    if "待检索" in scan_text:
        ctx.error("CMP-004", "对外版不得使用“待检索”占位；竞品章节必须呈现已完成的检索范围、日期和结论", "disclosure.md")
    invalid_comments = [
        comment
        for comment in HTML_COMMENT_PATTERN.findall(text)
        if DIAGRAM_ID_COMMENT_PATTERN.fullmatch(comment) is None
    ]
    if invalid_comments:
        ctx.error("DOC-004", "对外版除规范 diagram-id 外不得保留 HTML 注释", "disclosure.md")
    scan_without_diagram_comments = DIAGRAM_ID_COMMENT_PATTERN.sub("", scan_text)
    if "<!--" in scan_without_diagram_comments:
        ctx.error("DOC-004", "对外版不得用编码或全角字符伪装 HTML 注释", "disclosure.md")
    required_content: list[tuple[str, str]] = []
    if _is_nonempty_string(patent.get("use_case")):
        required_content.append(("使用场景", patent["use_case"]))
    claim = manifest.get("core_invention_claim")
    if _is_nonempty_string(claim):
        required_content.append(("核心发明主张", claim))
    for field in ("technical_objects", "core_mechanisms", "key_constraints"):
        for item in _dict_list((manifest.get("keywords") or {}).get(field) if isinstance(manifest.get("keywords"), dict) else None):
            if _is_nonempty_string(item.get("term")):
                required_content.append(("关键词", item["term"]))
    for item in _dict_list(manifest.get("innovations")):
        implementation = item.get("implementation_basis") if isinstance(item.get("implementation_basis"), dict) else {}
        for field in ("technical_object", "trigger_or_input", "processing", "constraint", "output_or_state"):
            if _is_nonempty_string(implementation.get(field)):
                required_content.append((f"创新点 {item.get('id', '')} 已实现基础", implementation[field]))
        for extension in _dict_list(item.get("protection_extensions")):
            for field in ("scope", "rationale"):
                if _is_nonempty_string(extension.get(field)):
                    required_content.append((f"创新点 {item.get('id', '')} 拟扩展保护", extension[field]))
        for field in (
            "id",
            "comparison_baseline",
            "core_mechanism",
            "necessary_constraint",
            "substantive_difference",
            "value_link",
            "effect_id",
        ):
            if _is_nonempty_string(item.get(field)):
                required_content.append((f"创新点 {item.get('id', '')}", item[field]))
    for item in _dict_list(manifest.get("effects")):
        for field in ("id", "original_problem", "mechanism", "observable_result"):
            if _is_nonempty_string(item.get(field)):
                required_content.append((f"技术效果 {item.get('id', '')}", item[field]))
        public_status = PUBLIC_EFFECT_STATUS.get(str(item.get("verification_status", "")))
        if public_status:
            required_content.append((f"技术效果 {item.get('id', '')} 验证状态", public_status))
    effects_by_id = {
        item["id"]: item
        for item in _dict_list(manifest.get("effects"))
        if _is_nonempty_string(item.get("id"))
    }
    for item in _dict_list(manifest.get("innovations")):
        innovation_id = str(item.get("id", "")).strip()
        section_text = "\n".join(_markdown_h4_body(text, innovation_id)) if innovation_id else ""
        effect = effects_by_id.get(item.get("effect_id"), {})
        implementation = item.get("implementation_basis") if isinstance(item.get("implementation_basis"), dict) else {}
        protection_extensions = _dict_list(item.get("protection_extensions"))
        chain_values = [
            implementation.get("technical_object"),
            implementation.get("trigger_or_input"),
            implementation.get("processing"),
            implementation.get("constraint"),
            implementation.get("output_or_state"),
            item.get("comparison_baseline"),
            item.get("core_mechanism"),
            item.get("substantive_difference"),
            item.get("value_link"),
            item.get("effect_id"),
            effect.get("observable_result"),
            *(extension.get("scope") for extension in protection_extensions),
            *(extension.get("rationale") for extension in protection_extensions),
        ]
        if not section_text or any(_is_nonempty_string(value) and value not in section_text for value in chain_values):
            ctx.error(
                "INV-006",
                f"{innovation_id or '创新点'} 必须在同一小节连续呈现对比基线、处理方式、实质差异、价值关联和对应可观察效果",
                "disclosure.md",
            )
        section_lines = _markdown_h4_body(text, innovation_id) if innovation_id else []
        basis_markers = [
            index for index, line in enumerate(section_lines) if line == "- **已实现基础**"
        ]
        if len(basis_markers) != 1:
            ctx.error(
                "INV-007",
                f"{innovation_id or '创新点'} 必须且只能有一个未引用的已实现基础标签",
                "disclosure.md",
            )
        else:
            basis_index = basis_markers[0]
            implementation_fields = (
                ("技术对象", implementation.get("technical_object")),
                ("触发或输入", implementation.get("trigger_or_input")),
                ("实际处理", implementation.get("processing")),
                ("必要边界", implementation.get("constraint")),
                ("输出或状态", implementation.get("output_or_state")),
            )
            for field_label, field_value in implementation_fields:
                if _is_nonempty_string(field_value) and not _has_exact_unquoted_field_after(
                    section_lines, basis_index, field_label, field_value
                ):
                    ctx.error(
                        "INV-007",
                        f"{innovation_id or '创新点'} 的已实现基础字段必须位于标签后且处于扩展引用块外：{field_label}",
                        "disclosure.md",
                    )
        blocks = _public_protection_extension_blocks(section_lines)
        marker_like_lines = [line for line in section_lines if "拟扩展保护" in line]
        if protection_extensions:
            invalid_markers = [
                line
                for line in marker_like_lines
                if line != PUBLIC_PROTECTION_EXTENSION_MARKER
            ]
            if invalid_markers or len(blocks) != len(protection_extensions):
                ctx.error(
                    "INV-007",
                    f"{innovation_id or '创新点'} 必须为每个扩展使用无内部编号的 > **拟扩展保护** 高亮块",
                    "disclosure.md",
                )
            for extension, block in zip(protection_extensions, blocks):
                for field_label, field_name in (("保护范围", "scope"), ("扩展理由", "rationale")):
                    field_value = extension.get(field_name)
                    if _is_nonempty_string(field_value) and not _has_exact_quoted_field(
                        block, field_label, field_value
                    ):
                        ctx.error(
                            "INV-007",
                            f"{innovation_id or '创新点'} 的 {field_label}必须原样位于对应引用块内",
                            "disclosure.md",
                        )
        elif marker_like_lines:
            ctx.error("DOC-004", f"{innovation_id or '创新点'} 无扩展时对外版不得显示占位块", "disclosure.md")
    has_protection_extensions = any(
        _dict_list(item.get("protection_extensions"))
        for item in _dict_list(manifest.get("innovations"))
    )
    expected_alternative_body = [EXTENSION_REFERENCE_TEXT if has_protection_extensions else "无。"]
    if _markdown_h3_body(text, ALTERNATIVE_SECTION_HEADING) != expected_alternative_body:
        ctx.error(
            "INV-008",
            "其他解决方案章节不得重复裸写拟扩展内容；只能引用创新点高亮块，或在无扩展时写“无”",
            "disclosure.md",
        )
    competitors = manifest.get("competitors") if isinstance(manifest.get("competitors"), dict) else {}
    competitor_body = _markdown_h3_body(text, COMPETITOR_SECTION_HEADING)
    expected_competitor_body = _public_competitor_section_lines(competitors)
    if competitor_body != expected_competitor_body:
        ctx.error(
            "CMP-004",
            "竞品章节必须从 manifest 原样呈现检索范围、日期、结论及可用证据，且不得增加无来源断言",
            "disclosure.md",
        )
    for label, content in required_content:
        if content not in text:
            ctx.error("DOC-003", f"正文未原样呈现 manifest 内容：{label} / {content}", "disclosure.md")
    embedded, block_count = _extract_embedded_diagrams(text)
    marker_count = len(re.findall(r"<!--\s*diagram-id:\s*D[1-9]\d*\s*-->", text, flags=re.IGNORECASE))
    if block_count != marker_count or block_count != len(embedded):
        ctx.error("FIG-001", "每个 PlantUML 代码块前必须有唯一 diagram-id 标识", "disclosure.md")
    if re.search(r"\b[MR][1-9]\d*(?:\.\d+)?\b", text):
        ctx.error("FLOW-004", "专利文档不得出现 M/R 编号，只允许 E/S/I/T/D", "disclosure.md")
    return text, embedded


def _validate_internal_document(
    ctx: ValidationContext,
    package_dir: Path,
    manifest: dict[str, Any],
    public_text: str,
) -> None:
    internal_path = package_dir / "disclosure-internal.md"
    try:
        internal_text = internal_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        ctx.error("PKG-011", f"无法读取 disclosure-internal.md：{exc}", "disclosure-internal.md")
        return

    heading_count = sum(
        1 for line in internal_text.splitlines() if line.strip() == INTERNAL_APPENDIX_HEADING
    )
    if heading_count != 1:
        ctx.error("DOC-005", "内部版必须且只能包含一个内部追溯附录", "disclosure-internal.md")
        return
    public_part, _, appendix = internal_text.partition(INTERNAL_APPENDIX_HEADING)
    if public_part.rstrip() != public_text.rstrip():
        ctx.error("DOC-005", "内部版的公开正文必须与 disclosure.md 完全同源", "disclosure-internal.md")

    appendix_lines = [line.strip() for line in appendix.splitlines() if line.strip()]
    if HTML_COMMENT_PATTERN.search(appendix):
        ctx.error("DOC-005", "内部追溯附录不得把追溯记录隐藏在 HTML 注释中", "disclosure-internal.md")
    if appendix_lines.count(INTERNAL_APPENDIX_NOTICE) != 1:
        ctx.error("DOC-005", "内部追溯附录必须包含且只能包含一条禁止对外说明", "disclosure-internal.md")
    missing_headings = [
        heading
        for heading in REQUIRED_INTERNAL_APPENDIX_H3
        if appendix_lines.count(f"### {heading}") != 1
    ]
    if missing_headings:
        ctx.error(
            "DOC-005",
            f"内部追溯附录缺少或重复固定小节：{', '.join(missing_headings)}",
            "disclosure-internal.md",
        )
    missing_lines = [
        line
        for line in _expected_internal_trace_lines(manifest)
        if appendix_lines.count(line) != 1
    ]
    if missing_lines:
        preview = "；".join(missing_lines[:5])
        suffix = f"；另有 {len(missing_lines) - 5} 条" if len(missing_lines) > 5 else ""
        ctx.error("DOC-005", f"内部追溯附录缺少或重复追溯记录：{preview}{suffix}", "disclosure-internal.md")
    allowed_lines = {
        INTERNAL_APPENDIX_NOTICE,
        *(f"### {heading}" for heading in REQUIRED_INTERNAL_APPENDIX_H3),
        *_expected_internal_trace_lines(manifest),
    }
    unexpected_lines = [line for line in appendix_lines if line not in allowed_lines]
    if unexpected_lines:
        preview = "；".join(unexpected_lines[:5])
        suffix = f"；另有 {len(unexpected_lines) - 5} 条" if len(unexpected_lines) > 5 else ""
        ctx.error("DOC-005", f"内部追溯附录存在 manifest 之外的记录或结构：{preview}{suffix}", "disclosure-internal.md")


def _tokens(text: str, prefix: str) -> list[str]:
    return re.findall(rf"\b{re.escape(prefix)}[1-9]\d*(?:\.\d+)?\b", text)


def _without_fenced_blocks(text: str) -> str:
    return re.sub(r"```[^\n]*\n.*?```", "", text, flags=re.DOTALL)


def _markdown_h3_body(text: str, heading: str) -> list[str]:
    collecting = False
    lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.startswith("### "):
            current = raw_line[4:].strip()
            if collecting:
                break
            collecting = current == heading
            continue
        if collecting and raw_line.strip() and not raw_line.lstrip().startswith("<!--"):
            lines.append(raw_line.strip())
    return lines


def _markdown_h4_body(text: str, heading_id: str) -> list[str]:
    collecting = False
    lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.startswith("### "):
            if collecting:
                break
            continue
        if raw_line.startswith("#### "):
            current = raw_line[5:].strip()
            if collecting:
                break
            collecting = current == heading_id or current.startswith(f"{heading_id} ")
            continue
        if collecting and raw_line.strip() and not raw_line.lstrip().startswith("<!--"):
            lines.append(raw_line.strip())
    return lines


def _public_protection_extension_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    index = 0
    while index < len(lines):
        if lines[index] != PUBLIC_PROTECTION_EXTENSION_MARKER:
            index += 1
            continue
        block = [lines[index]]
        index += 1
        while index < len(lines) and lines[index].startswith(">"):
            if lines[index] == PUBLIC_PROTECTION_EXTENSION_MARKER:
                break
            block.append(lines[index])
            index += 1
        blocks.append(block)
    return blocks


def _has_exact_unquoted_field_after(
    lines: list[str],
    start_index: int,
    label: str,
    value: str,
) -> bool:
    expected = f"- {label}：{value}"
    return any(
        index > start_index and line == expected and not line.startswith(">")
        for index, line in enumerate(lines)
    )


def _has_exact_quoted_field(block: list[str], label: str, value: str) -> bool:
    return f"> - {label}：{value}" in block


def _validate_flow_numbers(ctx: ValidationContext, text: str, location: str) -> None:
    tokens = sorted(set(_tokens(text, "S")), key=lambda value: [int(part) for part in value[1:].split(".")])
    top = [value for value in tokens if "." not in value]
    expected = [f"S{number}" for number in range(1, len(top) + 1)]
    if not 5 <= len(top) <= 10:
        ctx.error("FLOW-001", f"主流程顶层步骤必须为 5-10 个，当前={len(top)}", location)
    if top != expected:
        ctx.error("FLOW-002", f"主流程顶层 S 编号必须从 S1 连续递增，当前={top}", location)
    top_set = set(top)
    for value in tokens:
        if "." in value and value.split(".", 1)[0] not in top_set:
            ctx.error("FLOW-003", f"子步骤缺少父步骤：{value}", location)
    for line in text.splitlines():
        match = re.search(r"\bS[1-9]\d*(?:\.\d+)?\b\s*([^\n;|]{1,80})", line)
        if not match:
            continue
        label = match.group(1).strip(" :[]()\t")
        if len(label) > 20 or re.search(r"[。；！？!?]", label):
            ctx.error("FLOW-005", f"流程标签应为不超过 20 字的单一动作短语：{label}", location)


def _validate_structural_labels(ctx: ValidationContext, text: str, location: str) -> None:
    e_tokens = sorted({int(value[1:]) for value in _tokens(text, "E") if "." not in value})
    if e_tokens and e_tokens != list(range(1, len(e_tokens) + 1)):
        ctx.error("FIG-004", f"结构关系 E 编号必须从 E1 连续递增，当前={e_tokens}", location)
    for line in text.splitlines():
        if not re.search(r"(?:--+>|<--+|\.\.+>|<\.\.+|-[^-]*-)", line) or ":" not in line:
            continue
        label = line.rsplit(":", 1)[1].strip()
        if label and not re.fullmatch(r"E[1-9]\d*", label):
            ctx.error("FIG-005", f"结构图边标签只允许 E 编号：{label}", location)


def _validate_artifact_entry(
    ctx: ValidationContext,
    validation: dict[str, Any],
    key: str,
    expected_name: str,
    expected_hash: str,
    location: str,
) -> None:
    artifacts = validation.get("artifacts")
    item = artifacts.get(key) if isinstance(artifacts, dict) else None
    if not isinstance(item, dict):
        ctx.error("PKG-008", f"artifacts.{key} 记录缺失", location)
        return
    path = item.get("path")
    if not _is_nonempty_string(path) or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
        ctx.error("PKG-008", f"artifacts.{key}.path 必须是安全相对路径", location)
    elif path != expected_name:
        ctx.error("PKG-008", f"artifacts.{key}.path 必须精确指向 {expected_name}", location)
    if item.get("sha256") != expected_hash:
        ctx.error("PKG-008", f"artifacts.{key}.sha256 与当前文件不一致", location)


def _validate_with_generic_verifier(ctx: ValidationContext, package_path: Path, location: str) -> None:
    if not GENERIC_PACKAGE_VERIFIER.is_file():
        ctx.error("PKG-010", f"缺少直接依赖图包复核器：{GENERIC_PACKAGE_VERIFIER}", location)
        return
    try:
        completed = subprocess.run(
            [sys.executable, str(GENERIC_PACKAGE_VERIFIER), str(package_path)],
            cwd=package_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        ctx.error("PKG-010", f"无法执行通用图包复核器：{exc}", location)
        return
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "无诊断").strip().replace("\n", " | ")[:800]
        ctx.error("PKG-010", f"通用图包 v1.1 复核失败：{detail}", location)


def _validate_diagrams(
    ctx: ValidationContext,
    package_dir: Path,
    manifest: dict[str, Any],
    embedded: dict[str, str],
    document_text: str,
) -> dict[str, str]:
    diagrams_raw = manifest.get("diagrams")
    diagrams = _dict_list(diagrams_raw)
    if not isinstance(diagrams_raw, list) or len(diagrams) != len(diagrams_raw):
        ctx.error("FIG-002", "diagrams 必须是对象数组", "disclosure-manifest.json#/diagrams")
        return {}
    ids: list[str] = []
    roles: list[str] = []
    purposes: list[str] = []
    svg_hashes: dict[str, str] = {}
    allowed_roles = {"component_overview", "main_flow", "deployment_boundary", "module_detail", "core_mechanism"}
    for index, item in enumerate(diagrams):
        location = f"disclosure-manifest.json#/diagrams/{index}"
        _require_object_fields(ctx, item, ("id", "role", "package_path", "purpose"), "FIG-002", location)
        diagram_id = str(item.get("id", ""))
        role = str(item.get("role", ""))
        if diagram_id:
            ids.append(diagram_id)
        if role:
            roles.append(role)
        purpose = str(item.get("purpose", "")).strip()
        if purpose:
            purposes.append(purpose.casefold())
        if not isinstance(role, str) or role not in allowed_roles:
            ctx.error("FIG-002", f"未知图示职责：{role}", location)
        package_path = _safe_package_path(package_dir, item.get("package_path"))
        if package_path is None:
            ctx.error("PKG-005", "diagram.package_path 必须是工作区内相对路径且不得包含 ..", location)
            continue
        if not package_path.is_dir():
            ctx.error("PKG-006", f"图包目录不存在：{item.get('package_path')}", location)
            continue
        required_files = {
            "brief": package_path / "brief.normalized.yaml",
            "puml": package_path / "diagram.puml",
            "svg": package_path / "diagram.svg",
            "validation": package_path / "validation.json",
        }
        missing = [path.name for path in required_files.values() if not path.is_file()]
        if missing:
            ctx.error("PKG-006", f"图包缺少文件：{', '.join(missing)}", str(item.get("package_path")))
            continue
        escaped = [path.name for path in required_files.values() if not _resolved_within(path, package_path)]
        if escaped:
            ctx.error("PKG-006", f"图包文件解析后越出图包目录：{', '.join(escaped)}", str(item.get("package_path")))
            continue
        validation = _read_json(ctx, required_files["validation"], "PKG-007")
        if validation is None:
            continue
        if str(validation.get("schema_version")) != "1.1":
            ctx.error("PKG-007", "图包 validation.json 必须使用 schema_version 1.1", str(required_files["validation"].relative_to(package_dir)))
        if validation.get("diagram_id") != diagram_id or not _is_nonempty_scalar(validation.get("profile_version")):
            ctx.error("PKG-007", "diagram_id 必须匹配 manifest，且 profile_version 不得为空", str(required_files["validation"].relative_to(package_dir)))
        if validation.get("final_status") != "success" or validation.get("render_result") != "ok":
            ctx.error("FIG-006", "图包必须 final_status=success 且 render_result=ok", str(required_files["validation"].relative_to(package_dir)))
        for check_field in ("brief_check", "coverage_check", "layout_check"):
            if validation.get(check_field) != "ok":
                ctx.error("FIG-006", f"图包 {check_field} 必须为 ok", str(required_files["validation"].relative_to(package_dir)))
        profile = validation.get("profile", validation.get("diagram_type"))
        allowed_profiles = {
            "component_overview": {"component"},
            "main_flow": {"activity", "sequence"},
            "deployment_boundary": {"deployment"},
            "module_detail": {"component"},
            "core_mechanism": {"component", "activity", "sequence"},
        }
        if not isinstance(profile, str) or profile not in allowed_profiles.get(role, set()):
            ctx.error("FIG-006", f"图示职责 {role} 不接受 profile={profile}", str(required_files["validation"].relative_to(package_dir)))

        try:
            brief_text = required_files["brief"].read_text(encoding="utf-8")
            puml_text = required_files["puml"].read_text(encoding="utf-8")
            svg_text = required_files["svg"].read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            ctx.error("PKG-006", f"图包文本工件必须为可读 UTF-8：{exc}", str(item.get("package_path")))
            continue
        public_artifact_text = _rendered_scan_text(f"{puml_text}\n{svg_text}")
        leaked_original = bool(_leaked_term_originals(public_artifact_text, manifest))
        leaked_extensions = [
            value
            for value in _protection_extension_texts(manifest)
            if _rendered_scan_text(value) in public_artifact_text
        ]
        if INTERNAL_TRACE_ID_PATTERN.search(public_artifact_text) or leaked_original or leaked_extensions:
            ctx.error(
                "FIG-010",
                "共享 PlantUML/SVG 只能呈现已实现路径，不得出现内部编号、原始术语或拟扩展内容",
                str(item.get("package_path")),
            )
        brief_hash = _sha256_file(required_files["brief"])
        normalized_hash = _normalized_puml_sha256(puml_text)
        svg_hash = _sha256_file(required_files["svg"])
        svg_hashes[diagram_id] = svg_hash
        validation_location = str(required_files["validation"].relative_to(package_dir))
        raw_puml_hash = _sha256_file(required_files["puml"])
        direct_hashes = {
            "brief_sha256": brief_hash,
            "puml_sha256": raw_puml_hash,
            "normalized_puml_sha256": normalized_hash,
            "svg_sha256": svg_hash,
        }
        for field, actual in direct_hashes.items():
            if validation.get(field) != actual:
                ctx.error("PKG-008", f"{field} 缺失或与当前文件不一致", validation_location)
        _validate_artifact_entry(ctx, validation, "brief", "brief.normalized.yaml", brief_hash, validation_location)
        _validate_artifact_entry(ctx, validation, "diagram", "diagram.puml", raw_puml_hash, validation_location)
        _validate_artifact_entry(ctx, validation, "svg", "diagram.svg", svg_hash, validation_location)
        top_level_paths = {
            "brief_path": "brief.normalized.yaml",
            "diagram_path": "diagram.puml",
            "svg_path": "diagram.svg",
        }
        for field, expected_name in top_level_paths.items():
            value = validation.get(field)
            if not _is_nonempty_string(value) or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
                ctx.error("PKG-008", f"{field} 必须是安全相对路径", validation_location)
            elif value != expected_name:
                ctx.error("PKG-008", f"{field} 必须精确指向 {expected_name}", validation_location)

        _validate_with_generic_verifier(ctx, package_path, validation_location)

        if diagram_id not in embedded:
            ctx.error("FIG-007", f"disclosure.md 缺少图 {diagram_id} 的内嵌 PlantUML", "disclosure.md")
        elif _normalized_puml_sha256(embedded[diagram_id]) != normalized_hash:
            ctx.error("PKG-009", f"图 {diagram_id} 的内嵌 PlantUML 与图包不同源", "disclosure.md")

        metrics = validation.get("metrics")
        if not isinstance(metrics, dict):
            ctx.error("FIG-008", "图包 v1.1 必须包含 metrics", str(required_files["validation"].relative_to(package_dir)))
        elif role in {"component_overview", "deployment_boundary", "module_detail"}:
            for field, maximum in (("node_count", 8), ("edge_count", 10), ("max_degree", 4)):
                value = metrics.get(field)
                if not isinstance(value, int):
                    ctx.error("FIG-008", f"metrics.{field} 必须是整数", str(required_files["validation"].relative_to(package_dir)))
                elif value > maximum:
                    ctx.error("FIG-008", f"{field}={value} 超过上限 {maximum}", str(required_files["validation"].relative_to(package_dir)))
        if role == "main_flow":
            _validate_flow_numbers(ctx, puml_text, str(required_files["puml"].relative_to(package_dir)))
            if re.search(r"^\s*autonumber\b", puml_text, flags=re.MULTILINE):
                ctx.error("FLOW-007", "专利主流程禁止 autonumber，避免与 S 编号重复", str(required_files["puml"].relative_to(package_dir)))
            if profile == "sequence":
                if not re.search(r"^\s*numbering_scheme\s*:\s*process_s\s*$", brief_text, flags=re.MULTILINE):
                    ctx.error("FLOW-007", "专利时序主流程必须声明 numbering_scheme: process_s", str(required_files["brief"].relative_to(package_dir)))
            puml_steps = set(_tokens(puml_text, "S"))
            narrative_steps = set(_tokens(_without_fenced_blocks(document_text), "S"))
            if puml_steps != narrative_steps:
                ctx.error(
                    "FLOW-006",
                    f"主流程图与图下正文的 S 步骤集合必须一致，图={sorted(puml_steps)}，正文={sorted(narrative_steps)}",
                    "disclosure.md",
                )
        elif role in {"component_overview", "deployment_boundary", "module_detail"}:
            _validate_structural_labels(ctx, puml_text, str(required_files["puml"].relative_to(package_dir)))
            if role == "component_overview" and IMPLEMENTATION_PATTERN.search(_visible_structural_labels(puml_text)):
                ctx.error("BND-003", "组件总览顶层出现内部实现项", str(required_files["puml"].relative_to(package_dir)))

    _check_sequential_ids(ctx, ids, "diagram", "FIG-002", "disclosure-manifest.json#/diagrams")
    if roles.count("component_overview") != 1:
        ctx.error("FIG-003", "component_overview 必须且只能有一张", "disclosure-manifest.json#/diagrams")
    if roles.count("main_flow") != 1:
        ctx.error("FIG-003", "main_flow 必须且只能有一张", "disclosure-manifest.json#/diagrams")
    triggers = []
    if isinstance(manifest.get("boundaries"), dict):
        triggers = _string_list(manifest["boundaries"].get("deployment_triggers"))
    if triggers and roles.count("deployment_boundary") != 1:
        ctx.error("FIG-003", "出现部署触发条件时 deployment_boundary 必须且只能有一张", "disclosure-manifest.json#/diagrams")
    if not triggers and roles.count("deployment_boundary") > 1:
        ctx.error("FIG-003", "deployment_boundary 不得重复", "disclosure-manifest.json#/diagrams")
    if len(set(purposes)) != len(purposes):
        ctx.error("FIG-009", "每张图必须声明不同的唯一目的", "disclosure-manifest.json#/diagrams")
    if set(embedded) != set(ids):
        ctx.error("FIG-007", "文档与 manifest 的 diagram-id 集合必须完全一致", "disclosure.md")
    return svg_hashes


def _validate_innovation_anchors(
    ctx: ValidationContext,
    manifest: dict[str, Any],
    document_text: str,
) -> None:
    available = set(re.findall(r"\b(?:D|E|S)[1-9]\d*(?:\.\d+)?\b", document_text))
    for index, item in enumerate(_dict_list(manifest.get("innovations"))):
        location = f"disclosure-manifest.json#/innovations/{index}/anchors"
        for anchor in _string_list(item.get("anchors")):
            if not re.fullmatch(r"(?:D|E|S)[1-9]\d*(?:\.\d+)?", anchor) or anchor not in available:
                ctx.error("INV-004", f"创新点落点不存在于当前文档：{anchor}", location)


def _validate_reviews(
    ctx: ValidationContext,
    manifest: dict[str, Any],
    svg_hashes: dict[str, str],
) -> None:
    reviews = manifest.get("reviews")
    if not isinstance(reviews, dict):
        ctx.error("REV-001", "缺少 reviews 对象", "disclosure-manifest.json#/reviews")
        return

    generalization = reviews.get("generalization_test")
    if not isinstance(generalization, dict):
        ctx.error("REV-001", "缺少泛化替换测试记录", "disclosure-manifest.json#/reviews/generalization_test")
    else:
        _validate_review_status(ctx, generalization, "REV-001", "disclosure-manifest.json#/reviews/generalization_test")

    innovation_ids = {
        str(item.get("id")) for item in _dict_list(manifest.get("innovations")) if _is_nonempty_string(item.get("id"))
    }
    causal_raw = reviews.get("causal_deletion_tests")
    causal = _dict_list(causal_raw)
    if not isinstance(causal_raw, list) or len(causal) != len(causal_raw):
        ctx.error("REV-002", "causal_deletion_tests 必须是对象数组", "disclosure-manifest.json#/reviews/causal_deletion_tests")
    else:
        seen: set[str] = set()
        for index, item in enumerate(causal):
            location = f"disclosure-manifest.json#/reviews/causal_deletion_tests/{index}"
            innovation_id = item.get("innovation_id")
            if not _is_nonempty_string(innovation_id):
                ctx.error("REV-002", "因果删除测试必须绑定 innovation_id", location)
            else:
                seen.add(innovation_id)
            _validate_review_status(ctx, item, "REV-003", location)
        if seen != innovation_ids or len(seen) != len(causal):
            ctx.error("REV-002", "每个创新点必须且只能有一条因果删除测试", "disclosure-manifest.json#/reviews/causal_deletion_tests")

    visual_raw = reviews.get("visual_reviews")
    visual = _dict_list(visual_raw)
    if not isinstance(visual_raw, list) or len(visual) != len(visual_raw):
        ctx.error("REV-004", "visual_reviews 必须是对象数组", "disclosure-manifest.json#/reviews/visual_reviews")
        return
    seen_diagrams: set[str] = set()
    for index, item in enumerate(visual):
        location = f"disclosure-manifest.json#/reviews/visual_reviews/{index}"
        diagram_id = item.get("diagram_id")
        if not _is_nonempty_string(diagram_id):
            ctx.error("REV-004", "视觉复核必须绑定 diagram_id", location)
        else:
            seen_diagrams.add(diagram_id)
        _validate_review_status(ctx, item, "REV-004", location)
        if "仅呈现已实现路径" not in str(item.get("notes", "")):
            ctx.error("FIG-010", "每张图的视觉复核记录必须确认仅呈现已实现路径", location)
        if diagram_id in svg_hashes and item.get("svg_sha256") != svg_hashes[diagram_id]:
            ctx.error("REV-005", "视觉复核记录未绑定当前 svg_sha256，旧复核已失效", location)
    if seen_diagrams != set(svg_hashes) or len(seen_diagrams) != len(visual):
        ctx.error("REV-004", "每张图必须且只能有一条 SVG 视觉复核", "disclosure-manifest.json#/reviews/visual_reviews")


def _validate_review_status(ctx: ValidationContext, item: dict[str, Any], rule_id: str, location: str) -> None:
    status = item.get("status")
    if not _is_nonempty_string(item.get("reviewer")) or not _is_nonempty_string(item.get("notes")):
        ctx.error(rule_id, "复核必须记录非空 reviewer 与 notes", location)
    if not isinstance(status, str) or status not in {"pass", "fail", "pending"}:
        ctx.error(rule_id, "复核 status 仅允许 pass/fail/pending", location)
        return
    if status == "fail":
        ctx.error(rule_id, "复核结论为 fail", location)
    elif status == "pending":
        ctx.review(rule_id, "复核尚未完成", location)


def validate_package(disclosure_dir: Path) -> tuple[ValidationContext, dict[str, Any]]:
    ctx = ValidationContext()
    if not disclosure_dir.is_dir():
        ctx.error("PKG-001", f"交底书目录不存在：{disclosure_dir}")
        return ctx, ctx.result("package")

    workspace_dir = disclosure_dir / DISCLOSURE_WORKSPACE_DIR
    nested_manifest = workspace_dir / "disclosure-manifest.json"
    legacy_manifest = disclosure_dir / "disclosure-manifest.json"
    workspace_exists = workspace_dir.exists() or workspace_dir.is_symlink()
    if workspace_exists and (workspace_dir.is_symlink() or not _resolved_within(workspace_dir, disclosure_dir)):
        ctx.error("PKG-012", f"{DISCLOSURE_WORKSPACE_DIR} 必须是交底书目录内的真实子目录", DISCLOSURE_WORKSPACE_DIR)
        return ctx, ctx.result("package")
    if nested_manifest.is_file() and legacy_manifest.is_file():
        ctx.package_dir = workspace_dir
        ctx.error("PKG-012", "新旧两套 manifest 同时存在，无法确定内部工作区", str(disclosure_dir))
        return ctx, ctx.result("package")
    if nested_manifest.is_file():
        ctx.package_dir = workspace_dir
        misplaced = [
            name
            for name in ("disclosure-internal.md", "disclosure-manifest.json", "disclosure-validation.json", "diagrams")
            if (disclosure_dir / name).exists()
        ]
        if misplaced:
            ctx.error("PKG-012", f"内部工件不得与外发稿并列：{misplaced}", str(disclosure_dir))
        if (workspace_dir / "disclosure.md").exists():
            ctx.error("PKG-012", "内部工作区不得复制 disclosure.md；目录根部外发稿是唯一公开版本", DISCLOSURE_WORKSPACE_DIR)
        package_dir = workspace_dir
    elif legacy_manifest.is_file() and not workspace_exists:
        ctx.package_dir = disclosure_dir
        package_dir = disclosure_dir
        ctx.warning("PKG-013", f"检测到旧版平铺布局；新产出必须迁移到 {DISCLOSURE_WORKSPACE_DIR}/", str(disclosure_dir))
    else:
        ctx.package_dir = workspace_dir
        if workspace_exists:
            ctx.error("PKG-002", f"{DISCLOSURE_WORKSPACE_DIR}/disclosure-manifest.json 不存在或不可读取", DISCLOSURE_WORKSPACE_DIR)
        else:
            ctx.error("PKG-012", f"缺少固定内部工作区 {DISCLOSURE_WORKSPACE_DIR}/", str(disclosure_dir))
        return ctx, ctx.result("package")

    manifest = _read_json(ctx, package_dir / "disclosure-manifest.json", "PKG-002")
    if manifest is None:
        return ctx, ctx.result("package")
    if str(manifest.get("schema_version")) != "1.2":
        ctx.error("PKG-003", "disclosure-manifest.json schema_version 必须为 1.2", "disclosure-manifest.json#/schema_version")
    if "{{" in json.dumps(manifest, ensure_ascii=False) or "XXX" in json.dumps(manifest, ensure_ascii=False):
        ctx.error("PKG-004", "disclosure-manifest.json 仍包含模板占位符", "disclosure-manifest.json")

    _validate_manifest_schema(ctx, manifest)
    _validate_input_and_boundaries(ctx, manifest)
    _validate_sources(ctx, manifest)
    _validate_keywords(ctx, manifest)
    _validate_innovations_and_effects(ctx, manifest)
    _validate_competitors(ctx, manifest)
    document_text, embedded = _validate_document(ctx, disclosure_dir, manifest)
    _validate_internal_document(ctx, package_dir, manifest, document_text)
    svg_hashes = _validate_diagrams(ctx, package_dir, manifest, embedded, document_text)
    _validate_innovation_anchors(ctx, manifest, document_text)
    _validate_reviews(ctx, manifest, svg_hashes)
    return ctx, ctx.result("package")


def validate_draft(doc_path: Path) -> tuple[ValidationContext, dict[str, Any]]:
    ctx = ValidationContext()
    try:
        text = doc_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        ctx.error("PKG-901", f"草稿不存在：{doc_path}")
        return ctx, ctx.result("draft")
    except (OSError, UnicodeError) as exc:
        ctx.error("PKG-901", f"无法读取草稿：{exc}", str(doc_path))
        return ctx, ctx.result("draft")
    lines = text.splitlines()
    first = lines[0].strip() if lines else ""
    if not re.fullmatch(r"# 一种.+(?:方法/系统|方法|系统)", first):
        ctx.error("PKG-902", "标题必须为“# 一种XXX方法/系统”", f"{doc_path}:1")
    if "{{" in text or "XXX" in text:
        ctx.error("PKG-903", "草稿仍包含模板占位符", str(doc_path))
    draft_scan_text = _rendered_scan_text(text)
    if (
        INTERNAL_TRACE_ID_PATTERN.search(draft_scan_text)
        or PUBLIC_RAW_ENUM_PATTERN.search(draft_scan_text)
        or "来源依据" in draft_scan_text
        or INTERNAL_APPENDIX_HEADING in draft_scan_text
    ):
        ctx.error("DOC-004", "对外草稿不得出现内部追溯编号、标签、附录或机器枚举", str(doc_path))
    invalid_comments = [
        comment
        for comment in HTML_COMMENT_PATTERN.findall(text)
        if DIAGRAM_ID_COMMENT_PATTERN.fullmatch(comment) is None
    ]
    if invalid_comments:
        ctx.error("DOC-004", "对外草稿除规范 diagram-id 外不得保留 HTML 注释", str(doc_path))
    competitor_body = _markdown_h3_body(text, COMPETITOR_SECTION_HEADING)
    if "待检索" in draft_scan_text:
        ctx.error("CMP-004", "对外草稿不得使用“待检索”占位", str(doc_path))
    if (
        len(competitor_body) < 3
        or not competitor_body[0].startswith("检索范围：")
        or not competitor_body[1].startswith("检索日期：")
        or not competitor_body[2].startswith("检索结论：")
    ):
        ctx.error("CMP-004", "竞品章节必须呈现已完成的检索范围、日期和结论", str(doc_path))
    for heading in ("## 基本信息", "## 提案内容"):
        if heading not in lines:
            ctx.error("PKG-904", f"缺少章节标题：{heading}", str(doc_path))
    headings = {line[4:].strip() for line in lines if line.startswith("### ")}
    missing_headings = [heading for heading in REQUIRED_DISCLOSURE_H3 if heading not in headings]
    if missing_headings:
        ctx.error("PKG-904", f"缺少固定三级章节：{', '.join(missing_headings)}", str(doc_path))
    embedded, block_count = _extract_embedded_diagrams(text)
    if block_count:
        marker_count = len(re.findall(r"<!--\s*diagram-id:\s*D[1-9]\d*\s*-->", text, flags=re.IGNORECASE))
        if marker_count != block_count or len(embedded) != block_count:
            ctx.error("FIG-001", "每个 PlantUML 代码块前必须有唯一 diagram-id", str(doc_path))
    if re.search(r"\b[MR][1-9]\d*(?:\.\d+)?\b", text):
        ctx.error("FLOW-004", "专利草稿不得出现 M/R 编号", str(doc_path))
    flow_diagrams = [puml for puml in embedded.values() if _tokens(puml, "S")]
    if not flow_diagrams:
        ctx.error("FLOW-001", "草稿必须包含使用 S 编号的主流程图", str(doc_path))
    for puml in flow_diagrams:
        _validate_flow_numbers(ctx, puml, str(doc_path))
    ctx.warning("PKG-900", "当前仅完成草稿格式检查；缺少交付包、同源哈希及语义/视觉复核验证", str(doc_path))
    return ctx, ctx.result("draft")


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _print_summary(result: dict[str, Any]) -> None:
    for item in result["diagnostics"]:
        label = {"error": "ERROR", "warning": "WARN", "review": "REVIEW"}[item["severity"]]
        location = f" ({item['location']})" if item.get("location") else ""
        stream = sys.stderr if item["severity"] == "error" else sys.stdout
        print(f"[{label}] {item['rule_id']} {item['message']}{location}", file=stream)
    print(f"final_status={result['final_status']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="校验专利创新交底书草稿或完整交付包")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--package", type=Path, help="交底书目录；外发稿位于根部，内部工件位于 disclosure-workspace/")
    mode.add_argument("--draft", type=Path, help="仅做草稿格式兼容检查")
    parser.add_argument("--output", type=Path, help="自定义验证报告路径；默认写入 disclosure-workspace/")
    args = parser.parse_args()

    if args.package is not None:
        disclosure_dir = args.package.resolve()
        try:
            ctx, result = validate_package(disclosure_dir)
        except Exception as exc:  # 保证畸形输入仍产出结构化三态报告
            ctx = ValidationContext()
            ctx.error("PKG-999", f"校验器无法处理输入：{type(exc).__name__}: {exc}", str(disclosure_dir))
            result = ctx.result("package")
        output = args.output or ((ctx.package_dir / "disclosure-validation.json") if ctx.package_dir else None)
        if output is not None and disclosure_dir.is_dir():
            _write_result(output, result)
    else:
        ctx, result = validate_draft(args.draft.resolve())
        if args.output:
            _write_result(args.output, result)
    _ = ctx
    _print_summary(result)
    return EXIT_BY_STATUS[result["final_status"]]


if __name__ == "__main__":
    raise SystemExit(main())
