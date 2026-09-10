#!/usr/bin/env python3
"""批量估算时序图消息 note 的方向、折行与跨全宽兜底；不调用 renderer。"""

from __future__ import annotations

import math
import re
import unicodedata


# 均为显示列：中文通常占 2 列，ASCII 占 1 列。不是 SVG 像素。
PARTICIPANT_GAP = 24
EDGE_MARGIN = 12
NOTE_PADDING = 4
MIN_SIDE_LINES = 4
MIN_LINES_SAVED = 3


def display_width(text: str) -> int:
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def wrap_text(text: str, width: int) -> list[str]:
    """保留显式段落，优先保留英文单词，超长词按字符拆分。"""
    if width < 2:
        raise ValueError("可用宽度至少需要 2 个显示列")
    lines = []
    for paragraph in text.replace("\\n", "\n").split("\n"):
        line = ""
        # 合并组合附加符，避免把 e + 重音符拆到两行。
        units = []
        for token in re.findall(r"[A-Za-z0-9_]+|[^\S\n]+|.", paragraph):
            if unicodedata.combining(token[0]) and units:
                units[-1] += token
            else:
                units.append(token)
        for token in units:
            if display_width(token) <= width:
                chunks = [token]
            else:
                chunks = []
                for char in token:
                    if unicodedata.combining(char) and chunks:
                        chunks[-1] += char
                    else:
                        chunks.append(char)
            for chunk in chunks:
                if display_width(line + chunk) > width:
                    if line.strip():
                        lines.append(line.rstrip())
                    line = ""
                if line or not chunk.isspace():
                    line += chunk
        lines.append(line.rstrip())
    return lines


def require_keys(value, required: set[str], optional: set[str] = frozenset()):
    if not isinstance(value, dict):
        raise ValueError("必须是 JSON 对象")
    if missing := required - value.keys():
        raise ValueError(f"缺少字段：{', '.join(sorted(missing))}")
    if unknown := value.keys() - required - optional:
        raise ValueError(f"未知字段：{', '.join(sorted(unknown))}")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", value):
        raise ValueError("id 必须以字母或下划线开头，仅含字母、数字、下划线、点、连字符")
    return value


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("坐标必须是有限数字")
    return value


def geometry_for(diagram):
    participants = diagram["participants"]
    if not isinstance(participants, list) or not 2 <= len(participants) <= 8:
        raise ValueError("participants 必须是从左到右排列的 2–8 个参与者 id")
    for participant in participants:
        identifier(participant)
    if len(set(participants)) != len(participants):
        raise ValueError("参与者 id 重复")
    if "geometry" not in diagram:
        x = {p: EDGE_MARGIN + i * PARTICIPANT_GAP for i, p in enumerate(participants)}
        return 0, x[participants[-1]] + EDGE_MARGIN, x, "estimated"
    geometry = diagram["geometry"]
    require_keys(geometry, {"left", "right", "x"})
    left, right = number(geometry["left"]), number(geometry["right"])
    x = geometry["x"]
    require_keys(x, set(participants))
    coordinates = [left, *(number(x[p]) for p in participants), right]
    if any(a >= b for a, b in zip(coordinates, coordinates[1:])):
        raise ValueError("geometry 必须满足 left < 各参与者 x（声明顺序）< right")
    return left, right, x, "provided"


def plan_diagram(diagram):
    require_keys(diagram, {"id", "participants", "notes"}, {"geometry"})
    diagram_id = identifier(diagram["id"])
    left, right, x, source = geometry_for(diagram)
    if not isinstance(diagram["notes"], list):
        raise ValueError("notes 必须是数组")
    results, seen = [], set()
    participants = diagram["participants"]
    for index, note in enumerate(diagram["notes"]):
        try:
            require_keys(note, {"id", "from", "to", "text"})
            note_id = identifier(note["id"])
            if note_id in seen:
                raise ValueError("note id 重复；同一消息的说明请合并成一个 note")
            seen.add(note_id)
            if note["from"] not in x or note["to"] not in x:
                raise ValueError("from/to 必须引用当前图的参与者")
            text = note["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("text 必须是非空纯文本")
            text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")
            # 不自动改写富文本、预处理或块终止符，避免生成破损源码。
            if re.search(r"(?im)^\s*(?:end\s*note\b|[@!])", text):
                raise ValueError("text 不能包含 note 终止符、预处理或图定界符")
            if re.search(r"<[^>]+>|\[\[|\*\*|//|__|~~|\"\"", text):
                raise ValueError("text 仅支持纯文本；富文本请保留人工排版")
            if any(unicodedata.category(c).startswith("C") for c in text if c != "\n"):
                raise ValueError("text 不支持控制字符或隐藏格式字符")
            low, high = sorted((x[note["from"]], x[note["to"]]))
            widths = {
                "left": max(0, math.floor(low - left - NOTE_PADDING)),
                "right": max(0, math.floor(right - high - NOTE_PADDING)),
                # across 跨参与者区，不借用两端外侧留白。
                "across": max(0, math.floor(x[participants[-1]] - x[participants[0]] - NOTE_PADDING)),
            }
            side = "right" if widths["right"] >= widths["left"] else "left"
            side_lines = wrap_text(text, widths[side]) if widths[side] >= 2 else None
            across_lines = wrap_text(text, widths["across"]) if widths["across"] >= 2 else None
            if side_lines is None:
                if across_lines is None:
                    raise ValueError("侧边和全宽均无足够空间；需调整参与者间距")
                placement, reason = "across", "no_side_space"
            elif (across_lines is not None and len(side_lines) >= MIN_SIDE_LINES
                  and len(side_lines) - len(across_lines) >= MIN_LINES_SAVED):
                placement, reason = "across", "save_at_least_3_lines"
            else:
                placement, reason = side, "more_side_space"
            lines = across_lines if placement == "across" else side_lines
            # 自动折行也不能意外形成块终止符或预处理行。
            if any(re.match(r"(?i)^\s*(?:end\s*note\b|[@!])", line) for line in lines):
                raise ValueError("折行产生 PlantUML 控制行；请调整原文")
            results.append({
                "id": note_id, "from": note["from"], "to": note["to"],
                "placement": placement, "reason": reason,
                "widths": widths, "side": side,
                "side_line_count": len(side_lines) if side_lines is not None else None,
                "across_line_count": len(across_lines) if across_lines is not None else None,
                "line_count": len(lines), "lines": lines,
                "puml": f"note {placement}\n" + "\n".join(lines) + "\nend note",
            })
        except (ValueError, TypeError) as exc:
            raise ValueError(f"notes[{index}]: {exc}") from exc
    return {"id": diagram_id, "geometry_source": source,
            "geometry": {"left": left, "right": right, "x": x}, "notes": results}



def plan_brief(brief):
    """从已通过 schema 的原始 sequence brief 派生排版输入。"""
    diagram = {
        "id": brief["diagram_id"],
        "participants": [p["id"] for p in brief["participants"]],
        "notes": [{"id": m["id"], "from": m["from"], "to": m["to"], "text": m["note"]}
                  for m in brief["messages"] if "note" in m],
    }
    if "note_geometry" in brief.get("layout", {}):
        diagram["geometry"] = brief["layout"]["note_geometry"]
    return plan_diagram(diagram)
