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


def parse_activities(raw_text: str) -> list[ActivityDeclaration]:
    result: list[ActivityDeclaration] = []
    for line_no, line in _active_lines(raw_text):
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


def parse_activity_relations(raw_text: str) -> list[Relation]:
    activities = parse_activities(raw_text)
    explicit = parse_relations(raw_text)
    colon = [item for item in activities if item.syntax == "colon"]
    implicit = [
        Relation(left.alias, right.alias, "", right.line_no)
        for left, right in zip(colon, colon[1:])
    ]
    return explicit + implicit


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
            item for item in parse_activity_relations(raw_text)
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
