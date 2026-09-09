"""思维导图的受控树模型、源码解析与布局检查。"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
import unicodedata


def label_key(text: str) -> str:
    return " ".join(text.replace(r"\n", " ").split())


def label_errors(text: str) -> list[str]:
    # 只接受纯文本和换行，避免内容成为 Creole、预处理器或节点语法。
    if not text.strip() or any(c in text for c in "<>[]{}\\|~") or re.search(
        r"[\x00-\x09\x0b-\x1f]|\*\*|//|__|~~|--|==|\^\^|,,|\"\"|^[\s]*[:;=@!]", text
    ):
        return ["标签须为非空纯文本；不支持标记、反斜杠或控制指令"]
    if len(text.splitlines()) > 3 or sum(
        2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text
    ) > 96:
        return ["标签超出预算：最多 3 行、96 显示列，请精简或拆分节点"]
    return []


def validate_mindmap(data: dict) -> list[str]:
    errors = []
    layout = data.get("layout", {})
    if not isinstance(layout, dict) or layout.get("direction") not in ("balanced", "right", "left"):
        errors.append("layout.direction 必须是 balanced、right 或 left")
    nodes = data.get("nodes", [])
    if not isinstance(nodes, list) or not all(isinstance(n, dict) for n in nodes):
        return ["nodes 必须是节点对象列表"]
    if not 2 <= len(nodes) <= 32:
        errors.append("mindmap 节点预算为 2–32 个")
    ids = [n.get("id") for n in nodes]
    if not all(isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        return errors + ["nodes.id 必须为唯一字符串"]
    by_id = {n["id"]: n for n in nodes}
    roots = [n for n in nodes if n.get("parent") == ""]
    if len(roots) != 1:
        errors.append("mindmap 必须恰有一个 parent 为空字符串的根节点")
    siblings = set()
    children = Counter()
    for node in nodes:
        node_id, parent, label = node["id"], node.get("parent"), node.get("label")
        if not isinstance(parent, str) or (parent and parent not in by_id):
            errors.append(f"{node_id}: parent 必须引用已定义节点")
            continue
        if not isinstance(label, str):
            errors.append(f"{node_id}: label 必须是字符串")
            continue
        errors.extend(f"{node_id}: {e}" for e in label_errors(label))
        signature = (parent, label_key(label))
        if signature in siblings:
            errors.append(f"{node_id}: 同一父节点下的标签不能重复")
        siblings.add(signature)
        children[parent] += 1
        visited, current = set(), node_id
        while current in by_id:
            if current in visited:
                errors.append(f"{node_id}: parent 存在循环")
                break
            visited.add(current)
            current = by_id[current].get("parent")
            if not isinstance(current, str):
                break
        if len(visited) > 4:
            errors.append(f"{node_id}: 层级预算最多 4 层（含根），请拆图")
    if any(count > 6 for count in children.values()):
        errors.append("mindmap 每个节点最多 6 个直接子节点，请分组或拆图")
    errors.extend(f"title: {e}" for e in label_errors(data.get("title", "")))
    if "\n" in data.get("title", ""):
        errors.append("title 必须为单行")
    return errors


def ordered_tree(data: dict) -> list[tuple[dict, int, str]]:
    """固定 brief 顺序；balanced 按子树叶节点文本行数贪心分配左右。"""
    children = defaultdict(list)
    for node in data["nodes"]:
        children[node["parent"]].append(node)
    root = children[""][0]

    def weight(node):
        return max(1, (len(node["label"]) + 11) // 12, sum(weight(n) for n in children[node["id"]]))

    result = [(root, 1, "right")]
    loads = {"right": 0, "left": 0}
    direction = data["layout"]["direction"]

    def visit(node, depth, side):
        result.append((node, depth, side))
        for child in children[node["id"]]:
            visit(child, depth + 1, side)

    for branch in children[root["id"]]:
        side = min(loads, key=loads.get) if direction == "balanced" else direction
        loads[side] += weight(branch)
        visit(branch, 2, side)
    return result


@dataclass
class MindmapNode:
    label: str
    depth: int
    side: str
    parent: int | None


def parse_mindmap(raw: str) -> tuple[list[MindmapNode], list[str]]:
    """仅解析单根 arithmetic 或 OrgMode；未知语法显式失败，不猜父子关系。"""
    nodes, errors = [], []
    stacks = {"left": {}, "right": {}}
    started = ended = in_style = in_comment = False
    mode, side = "", "right"
    root = None
    for line_no, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if in_comment:
            if "'/" in s:
                in_comment = False
            continue
        if s.startswith("/'"):
            in_comment = "'/" not in s[2:]
            continue
        if not s or s.startswith(("'", "//")):
            continue
        if s == "@startmindmap" and not started:
            started = True
            continue
        if s == "@endmindmap" and started and not ended and not in_style:
            ended = True
            continue
        if not started or ended:
            errors.append(f"line {line_no}: 只允许一个 @startmindmap / @endmindmap 包围图内容")
            continue
        if s == "<style>" and not in_style:
            in_style = True
            continue
        if in_style:
            if s == "</style>":
                in_style = False
            elif s.startswith(("@", "!", "<")):
                errors.append(f"line {line_no}: style 中不允许控制指令")
            continue
        if s.startswith("title ") or re.fullmatch(r"skinparam (?:backgroundColor|shadowing|defaultFontName) .+", s, re.I):
            continue
        if s in ("left side", "right side"):
            if mode != "org" or root is None:
                errors.append(f"line {line_no}: side 指令仅用于 OrgMode 根节点之后")
            side = s.split()[0]
            stacks[side] = {1: root}
            continue
        match = re.fullmatch(r"(\++|-{2,}|\*+)(?:\[#[A-Za-z0-9]+\])?(_)?\s+(.+)", s)
        if not match:
            errors.append(f"line {line_no}: 超出 mindmap profile 语法；使用 +/− 层级或 OrgMode 星号")
            continue
        marks, _, label = match.groups()
        syntax = "org" if marks[0] == "*" else "arithmetic"
        if mode and mode != syntax:
            errors.append(f"line {line_no}: 不混用 arithmetic 与 OrgMode")
        mode = syntax
        depth = len(marks)
        node_side = side if syntax == "org" else ("left" if marks[0] == "-" else "right")
        label = re.sub(r"\s+<<[A-Za-z][A-Za-z0-9_]*>>$", "", label)
        errors.extend(f"line {line_no}: {e}" for e in label_errors(label.replace(r"\n", "\n")))
        parent = None
        if depth == 1:
            if root is not None:
                errors.append(f"line {line_no}: profile 只允许一个根节点")
            root = len(nodes)
            stacks = {"left": {1: root}, "right": {1: root}}
        else:
            parent = stacks[node_side].get(depth - 1)
            if parent is None:
                errors.append(f"line {line_no}: 层级跳跃或缺少同侧父节点")
            stacks[node_side] = {d: i for d, i in stacks[node_side].items() if d < depth}
            stacks[node_side][depth] = len(nodes)
        nodes.append(MindmapNode(label, depth, node_side, parent))
    if not started or not ended or in_style or in_comment:
        errors.append("mindmap 图、style 或块注释未闭合")
    if root is None:
        errors.append("mindmap 缺少根节点")
    return nodes, errors


def coverage_errors(data: dict, raw: str) -> list[str]:
    errors = validate_mindmap(data)
    if errors:
        return errors
    nodes, errors = parse_mindmap(raw)
    expected_paths = {}
    expected = Counter()
    for node, depth, side in ordered_tree(data):
        path = expected_paths.get(node["parent"], ()) + (label_key(node["label"]),)
        expected_paths[node["id"]] = path
        expected[(path, side if depth > 1 else "root")] += 1
    actual_paths, actual = {}, Counter()
    for index, node in enumerate(nodes):
        path = actual_paths.get(node.parent, ()) + (label_key(node.label),)
        actual_paths[index] = path
        actual[(path, node.side if node.depth > 1 else "root")] += 1
    if expected != actual:
        errors.append(f"节点标签、父子层级或左右归属与 brief 不一致：缺少 {sum((expected - actual).values())}，额外 {sum((actual - expected).values())}")
    return errors


def mindmap_metrics(raw: str) -> dict[str, int]:
    nodes, _ = parse_mindmap(raw)
    degree = Counter()
    edge_count = 0
    for index, node in enumerate(nodes):
        if node.parent is not None:
            edge_count += 1
            degree[index] += 1
            degree[node.parent] += 1
    return {"node_count": len(nodes), "edge_count": edge_count, "max_degree": max(degree.values(), default=0)}


def layout_errors(raw: str) -> list[str]:
    nodes, errors = parse_mindmap(raw)
    children = Counter(n.parent for n in nodes if n.parent is not None)
    if not 2 <= len(nodes) <= 32 or any(n.depth > 4 for n in nodes) or max(children.values(), default=0) > 6:
        errors.append("mindmap 布局预算：2–32 节点、最多 4 层、每节点最多 6 个子节点")
    # 检查真正的 style 内容，注释不能充当布局声明。
    cleaned = re.sub(r"/'[\s\S]*?'/", "", raw)
    cleaned = "\n".join(l for l in cleaned.splitlines() if not l.strip().startswith(("'", "//")))
    styles = "\n".join(re.findall(r"<style>([\s\S]*?)</style>", cleaned))
    node_styles = "\n".join(re.findall(r"\bnode\s*\{([^{}]*)\}", styles, re.I))
    for prop, low, high in (("MaximumWidth", 120, 240), ("FontSize", 13, 20), ("Padding", 8, 20), ("Margin", 4, 20)):
        values = re.findall(rf"\b{prop}\s+(\d+(?:\.\d+)?)\b", node_styles, re.I)
        if not values or any(not low <= float(v) <= high for v in values):
            errors.append(f"mindmap node style 必须设置 {prop}，范围 {low}–{high}")
    return errors
