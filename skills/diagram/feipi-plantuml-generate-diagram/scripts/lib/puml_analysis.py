#!/usr/bin/env python3
"""PlantUML typed profile 的保守语法提取与实际图面指标。

这里刻意采用“识别到合法对象声明就计入”的策略。typed profile 不能因为
对象使用了另一种 PlantUML 关键字而把它从覆盖校验和密度指标中漏掉。
"""

from __future__ import annotations

import collections
import re
from dataclasses import dataclass


OBJECT_KINDS = (
    "actor", "agent", "artifact", "boundary", "card", "cloud",
    "collections", "component", "control", "database", "device",
    "entity", "file", "folder", "frame", "hexagon", "interface",
    "node", "package", "person", "queue", "rectangle", "stack",
    "storage", "usecase",
)

OBJECT_RE = re.compile(
    rf'^\s*({"|".join(OBJECT_KINDS)})\s+"([^"]+)"\s+as\s+'
    r'([A-Za-z_][A-Za-z0-9_]*)\b(.*)$',
    re.IGNORECASE,
)
OBJECT_UNALIASED_RE = re.compile(
    rf'^\s*({"|".join(OBJECT_KINDS)})\s+"([^"]+)"(?!\s+as\b)(.*)$',
    re.IGNORECASE,
)
ACTIVITY_ANY_RE = re.compile(
    r'^\s*activity\s+"([^"]+)"\s+as\s+([A-Za-z_][A-Za-z0-9_.]*)\b',
    re.IGNORECASE,
)
ACTIVITY_UNALIASED_RE = re.compile(
    r'^\s*activity\s+"([^"]+)"(?!\s+as\b)',
    re.IGNORECASE,
)
ACTIVITY_COLON_RE = re.compile(r'^\s*:\s*(.*?)\s*;\s*$')
ACTIVITY_IF_RE = re.compile(r'^if\s*\(.+\)\s+then(?:\s*\((.*)\))?\s*$', re.IGNORECASE)
ACTIVITY_ELSE_RE = re.compile(r'^else(?:\s*\((.*)\))?\s*$', re.IGNORECASE)
SEQUENCE_PARTICIPANT_RE = re.compile(
    r'^\s*(participant|actor|database|boundary|control|entity|collections|queue)'
    r'\s+"([^"]+)"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b',
    re.IGNORECASE,
)
RELATION_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s+"
    r"([<.ox*#\[\]/\\=-]*[-.][>.ox*#\[\]/\\=-]*)\s+"
    r"([A-Za-z_][A-Za-z0-9_.]*)(?:\s*:\s*(.*?))?\s*$"
)


@dataclass(frozen=True)
class ObjectDeclaration:
    kind: str
    name: str
    alias: str
    is_container: bool
    line_no: int


@dataclass(frozen=True)
class ActivityDeclaration:
    label: str
    alias: str
    line_no: int
    syntax: str


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    label: str
    line_no: int


@dataclass(frozen=True)
class ActivityFlowAnalysis:
    relations: list[Relation]
    errors: list[str]


@dataclass
class _ActivityBranch:
    entry: list[tuple[str | None, str]]
    line_no: int
    then_exits: list[tuple[str | None, str]] | None = None


def _active_lines(raw_text: str):
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("'") or stripped.startswith("//"):
            continue
        yield line_no, line


def parse_objects(raw_text: str) -> list[ObjectDeclaration]:
    declarations: list[ObjectDeclaration] = []
    for line_no, line in _active_lines(raw_text):
        match = OBJECT_RE.match(line)
        if match:
            kind, name, alias, suffix = match.groups()
        elif unaliased := OBJECT_UNALIASED_RE.match(line):
            kind, name, suffix = unaliased.groups()
            alias = f"__unbound_object_{line_no}"
        else:
            continue
        declarations.append(ObjectDeclaration(
            kind=kind.lower(),
            name=name,
            alias=alias,
            is_container="{" in suffix,
            line_no=line_no,
        ))
    return declarations


def _activity_content_lines(raw_text: str, errors: list[str]):
    """仅跳过明确的展示块，未知语句留给控制流校验拒绝。"""
    block_end: str | None = None
    block_line = 0
    skin_depth = 0
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        stripped = line.strip()
        if block_end:
            if re.fullmatch(block_end, stripped, re.IGNORECASE):
                block_end = None
            continue
        if skin_depth:
            skin_depth += stripped.count("{") - stripped.count("}")
            continue
        if stripped.startswith("/'"):
            if "'/" not in stripped[2:]:
                block_end, block_line = r".*'/", line_no
            continue
        if not stripped or stripped.startswith("'") or stripped.startswith("//"):
            continue
        if re.match(r"^skinparam\s+", stripped, re.IGNORECASE):
            skin_depth = stripped.count("{") - stripped.count("}")
            block_line = line_no
            continue
        if re.fullmatch(r"legend(?:\s+(?:left|right|top|bottom|center))*", stripped, re.IGNORECASE):
            block_end, block_line = r"end\s*legend", line_no
            continue
        if re.match(r"^note\s+(?:left|right|top|bottom)\b", stripped, re.IGNORECASE):
            if ":" not in stripped:
                block_end, block_line = r"end\s*note", line_no
            continue
        if re.fullmatch(r"title|caption|header|footer", stripped, re.IGNORECASE):
            block_end, block_line = rf"end\s*{stripped}", line_no
            continue
        if re.match(r"^(?:title|caption|header|footer)\s+", stripped, re.IGNORECASE):
            continue
        if re.fullmatch(r"\|[^|]+\|", stripped):
            continue
        yield line_no, line
    if block_end or skin_depth:
        errors.append(f"line {block_line} activity 展示块未闭合")


def parse_activities(raw_text: str) -> list[ActivityDeclaration]:
    result: list[ActivityDeclaration] = []
    for line_no, line in _activity_content_lines(raw_text, []):
        if match := ACTIVITY_ANY_RE.match(line):
            result.append(ActivityDeclaration(match.group(1), match.group(2), line_no, "declared"))
        elif match := ACTIVITY_UNALIASED_RE.match(line):
            result.append(ActivityDeclaration(
                match.group(1), f"__unbound_activity_{line_no}", line_no, "declared",
            ))
        elif match := ACTIVITY_COLON_RE.match(line):
            label = match.group(1).strip()
            id_match = re.match(r"^(S[1-9][0-9]*(?:\.[1-9][0-9]*)?)\b", label)
            alias = id_match.group(1) if id_match else f"__unbound_activity_{line_no}"
            result.append(ActivityDeclaration(label, alias, line_no, "colon"))
    return result


def analyze_activity_flow(raw_text: str) -> ActivityFlowAnalysis:
    """解析现代活动图的保守子集；终点不计作步骤，未知控制流明确报错。"""
    errors: list[str] = []
    relations: list[Relation] = []
    activities = {item.line_no: item for item in parse_activities(raw_text)}
    frontier: list[tuple[str | None, str]] = []
    branches: list[_ActivityBranch] = []
    started = False
    opened = False
    closed = False

    def labeled(entry: list[tuple[str | None, str]], label: str | None):
        return [(source, " && ".join(part for part in (prior, (label or "").strip()) if part))
                for source, prior in entry]

    for line_no, line in _activity_content_lines(raw_text, errors):
        statement = line.strip()
        keyword = statement.lower()
        if re.fullmatch(r"@startuml(?:\s+\S+)?", statement, re.IGNORECASE):
            if opened or closed:
                errors.append(f"line {line_no} activity 只允许一个 @startuml 图")
            opened = True
            continue
        if keyword == "@enduml":
            if not opened or closed:
                errors.append(f"line {line_no} @enduml 没有匹配的 @startuml")
            closed = True
            continue
        if not opened or closed:
            errors.append(f"line {line_no} activity 语句必须位于 @startuml / @enduml 内")
        if keyword == "start":
            if started or branches:
                errors.append(f"line {line_no} activity 仅支持单一入口 start")
            started = True
            frontier = [(None, "")]
        elif declaration := activities.get(line_no):
            if declaration.syntax != "colon":
                errors.append(f"line {line_no} 不支持 activity 声明语法，请使用 `:Sx 动作;`")
                continue
            if not frontier:
                errors.append(f"line {line_no} activity 步骤不可达：{declaration.alias}")
            relations.extend(Relation(source, declaration.alias, label, line_no)
                             for source, label in frontier if source is not None)
            frontier = [(declaration.alias, "")] if frontier else []
        elif match := ACTIVITY_IF_RE.fullmatch(statement):
            branches.append(_ActivityBranch(frontier.copy(), line_no))
            frontier = labeled(frontier, match.group(1))
        elif match := ACTIVITY_ELSE_RE.fullmatch(statement):
            if not branches or branches[-1].then_exits is not None:
                errors.append(f"line {line_no} else 缺少匹配 if 或重复 else")
                continue
            branch = branches[-1]
            branch.then_exits = frontier
            frontier = labeled(branch.entry, match.group(1))
        elif keyword == "endif":
            if not branches:
                errors.append(f"line {line_no} endif 缺少匹配 if")
                continue
            branch = branches.pop()
            other = branch.entry if branch.then_exits is None else branch.then_exits
            frontier = list(dict.fromkeys(other + frontier))
        elif keyword in {"stop", "end"}:
            frontier = []
        else:
            errors.append(f"line {line_no} 不支持或无法解析 activity 控制流语句：{statement}")
    if not opened or not closed:
        errors.append("activity 必须包含 @startuml 与 @enduml")
    if not started:
        errors.append("activity 必须包含入口 start")
    errors.extend(f"line {branch.line_no} if 缺少 endif" for branch in branches)
    return ActivityFlowAnalysis(relations, errors)


def parse_activity_relations(raw_text: str) -> list[Relation]:
    analysis = analyze_activity_flow(raw_text)
    if analysis.errors:
        raise ValueError("; ".join(analysis.errors))
    return analysis.relations


def parse_relations(raw_text: str) -> list[Relation]:
    relations: list[Relation] = []
    for line_no, line in _active_lines(raw_text):
        if match := RELATION_RE.match(line):
            source, arrow, target, label = match.groups()
            # 左向箭头按视觉方向归一；度数不受方向影响，覆盖签名会受影响。
            if arrow.lstrip().startswith("<") and not arrow.rstrip().endswith(">"):
                source, target = target, source
            relations.append(Relation(source, target, (label or "").strip(), line_no))
    return relations


def _degree_metrics(node_count: int, relations: list[Relation]) -> dict[str, int]:
    degree: collections.Counter[str] = collections.Counter()
    for relation in relations:
        degree[relation.source] += 1
        degree[relation.target] += 1
    return {
        "node_count": node_count,
        "edge_count": len(relations),
        "max_degree": max(degree.values(), default=0),
    }


def compute_puml_metrics(diagram_type: str, raw_text: str) -> dict[str, int]:
    """从实际 PUML 计算指标，不能从 brief 反推。"""
    if diagram_type == "activity":
        activities = parse_activities(raw_text)
        aliases = {item.alias for item in activities}
        edges = [
            # 失败图仍需产出 metrics；语法错误由 coverage 显式报告。
            item for item in analyze_activity_flow(raw_text).relations
            if item.source in aliases or item.target in aliases
        ]
        return _degree_metrics(len(activities), edges)

    if diagram_type == "sequence":
        participants: set[str] = set()
        for _, line in _active_lines(raw_text):
            if match := SEQUENCE_PARTICIPANT_RE.match(line):
                participants.add(match.group(3))
        message_relations = [
            item for item in parse_relations(raw_text)
            if item.source in participants and item.target in participants
        ]
        return _degree_metrics(len(participants), message_relations)

    objects = parse_objects(raw_text)
    node_aliases = {item.alias for item in objects if not item.is_container}
    edges = [
        item for item in parse_relations(raw_text)
        if item.source in node_aliases or item.target in node_aliases
    ]
    return _degree_metrics(len(node_aliases), edges)
