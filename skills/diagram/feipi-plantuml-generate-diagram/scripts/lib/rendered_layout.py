"""检查 PlantUML SVG 中可见连线是否穿入文字区域；不依赖额外图形库。"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"
IDENTITY = (1., 0., 0., 1., 0., 0.)
TOLERANCE = 0.25


def numbers(value):
    return [float(v) for v in re.findall(NUMBER, value)]


def number(value):
    # 坐标列表、百分比和相对字体单位必须交复核，不能只取第一项。
    if not re.fullmatch(NUMBER + r"(?:px)?", str(value)):
        raise ValueError("不支持的 SVG 数值：" + str(value))
    result = float(str(value).removesuffix("px"))
    if not math.isfinite(result):
        raise ValueError("SVG 数值必须有限")
    return result


def multiply(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def point(p, matrix):
    x, y = p
    a, b, c, d, e, f = matrix
    return (a*x+c*y+e, b*x+d*y+f)


def transform(value):
    matrix = IDENTITY
    matches = list(re.finditer(r"([A-Za-z]+)\s*\(([^)]*)\)", value))
    if re.sub(r"([A-Za-z]+)\s*\(([^)]*)\)", "", value).strip(" ,\t\n"):
        raise ValueError("无法解析 SVG transform")
    for match in matches:
        name, values = match[1], numbers(match[2])
        if name == "matrix" and len(values) == 6:
            current = tuple(values)
        elif name == "translate" and len(values) in (1, 2):
            current = (1, 0, 0, 1, values[0], values[1] if len(values) == 2 else 0)
        elif name == "scale" and len(values) in (1, 2):
            current = (values[0], 0, 0, values[-1], 0, 0)
        elif name == "rotate" and len(values) in (1, 3):
            angle = math.radians(values[0])
            current = (math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle), 0, 0)
            if len(values) == 3:
                x, y = values[1:]
                current = multiply(multiply((1, 0, 0, 1, x, y), current), (1, 0, 0, 1, -x, -y))
        else:
            raise ValueError("不支持的 SVG transform：" + name)
        matrix = multiply(matrix, current)
    return matrix


def mix(a, b, t=0.5):
    return (a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t)


def cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def subtract(a, b):
    return (a[0]-b[0], a[1]-b[1])


def bezier(points, depth=0):
    # 控制多边形平坦度约束避免固定采样跳过窄标签。
    start, end = points[0], points[-1]
    chord = subtract(end, start)
    length = math.hypot(*chord)
    error = max((abs(cross(subtract(p, start), chord))/length if length
                 else math.dist(p, start)) for p in points[1:-1])
    excess = sum(math.dist(a, b) for a, b in zip(points, points[1:])) - length
    if error <= TOLERANCE and excess <= TOLERANCE:
        return [start, end]
    if depth >= 18:
        raise ValueError("SVG 曲线超出细分预算")
    levels = [points]
    while len(levels[-1]) > 1:
        levels.append([mix(a, b) for a, b in zip(levels[-1], levels[-1][1:])])
    left = [row[0] for row in levels]
    right = [row[-1] for row in reversed(levels)]
    return bezier(left, depth+1)[:-1] + bezier(right, depth+1)


def arc(start, values):
    rx, ry, angle, large, sweep, x, y = values
    end = (x, y)
    rx, ry = abs(rx), abs(ry)
    if start == end:
        return [start]
    if not rx or not ry:
        return [start, end]
    phi = math.radians(angle)
    c, s = math.cos(phi), math.sin(phi)
    dx, dy = ((start[0]-x)/2, (start[1]-y)/2)
    xp, yp = c*dx+s*dy, -s*dx+c*dy
    ratio = (xp/rx)**2+(yp/ry)**2
    if ratio > 1:
        rx, ry = rx*math.sqrt(ratio), ry*math.sqrt(ratio)
    factor = math.sqrt(max(0, (rx*ry)**2-(rx*yp)**2-(ry*xp)**2) /
                       max(1e-30, (rx*yp)**2+(ry*xp)**2))
    if bool(large) == bool(sweep):
        factor = -factor
    cxp, cyp = factor*rx*yp/ry, -factor*ry*xp/rx
    cx, cy = c*cxp-s*cyp+(start[0]+x)/2, s*cxp+c*cyp+(start[1]+y)/2
    theta = math.atan2((yp-cyp)/ry, (xp-cxp)/rx)
    delta = math.atan2((-yp-cyp)/ry, (-xp-cxp)/rx)-theta
    if sweep and delta < 0:
        delta += 2*math.pi
    if not sweep and delta > 0:
        delta -= 2*math.pi
    step = 2*math.acos(max(-1, 1-TOLERANCE/max(rx, ry)))
    count = max(1, math.ceil(abs(delta)/max(step, 1e-6)))
    if count > 10000:
        raise ValueError("SVG 弧线超出检查预算")
    return [start] + [(cx+c*rx*math.cos(theta+delta*i/count)-s*ry*math.sin(theta+delta*i/count),
                      cy+s*rx*math.cos(theta+delta*i/count)+c*ry*math.sin(theta+delta*i/count))
                     for i in range(1, count)] + [end]


def paths(value):
    tokens = re.findall(r"[A-Za-z]|" + NUMBER, value)
    if re.sub(r"[A-Za-z]|" + NUMBER, "", value).strip(" ,\t\r\n"):
        raise ValueError("无法解析 SVG path")
    result, current, start = [], (0., 0.), (0., 0.)
    subpath, command, previous, control = [], "", "", None
    i = 0
    sizes = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7)
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        op = command.upper()
        if op == "Z":
            subpath.append(start)
            current, previous, command = start, op, ""
            continue
        if op not in sizes or i+sizes[op] > len(tokens):
            raise ValueError("不支持或不完整的 SVG path 命令：" + command)
        values = [float(v) for v in tokens[i:i+sizes[op]]]
        i += sizes[op]
        relative = command.islower()
        def coord(x, y):
            return (x+current[0], y+current[1]) if relative else (x, y)
        end = coord(*values[-2:]) if op not in ("H", "V") else (
            ((current[0]+values[0] if relative else values[0]), current[1]) if op == "H" else
            (current[0], (current[1]+values[0] if relative else values[0])))
        if op == "M":
            if subpath:
                result.append(subpath)
            subpath, start = [end], end
            command = "l" if relative else "L"
        elif op in ("C", "S", "Q", "T"):
            reflected = (2*current[0]-control[0], 2*current[1]-control[1]) if control and (
                previous in ("C", "S") if op == "S" else previous in ("Q", "T")) else current
            if op == "C":
                controls = [coord(*values[:2]), coord(*values[2:4])]
            elif op == "S":
                controls = [reflected, coord(*values[:2])]
            elif op == "Q":
                controls = [coord(*values[:2])]
            else:
                controls = [reflected]
            subpath.extend(bezier([current, *controls, end])[1:])
            control = controls[-1]
        elif op == "A":
            subpath.extend(arc(current, [*values[:5], *end])[1:])
        else:
            subpath.append(end)
        current, previous = end, op
    if subpath:
        result.append(subpath)
    return result


def inside(p, polygon):
    x, y = p
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            result = not result
    return result


def intervals(a, b, polygon):
    ts, direction = [0., 1.], subtract(b, a)
    for c, d in zip(polygon, polygon[1:] + polygon[:1]):
        edge = subtract(d, c)
        denominator = cross(direction, edge)
        if abs(denominator) < 1e-10:
            continue
        t, u = cross(subtract(c, a), edge)/denominator, cross(subtract(c, a), direction)/denominator
        if 0 < t < 1 and 0 <= u <= 1:
            ts.append(t)
    ts = sorted(set(ts))
    return [(lo, hi) for lo, hi in zip(ts, ts[1:])
            if hi-lo > 1e-9 and inside(mix(a, b, (lo+hi)/2), polygon)]


def visible_contact(a, b, text_polygon, masks):
    for lo, hi in intervals(a, b, text_polygon):
        remaining = [(lo, hi)]
        for polygon in masks:
            for left, right in intervals(a, b, polygon):
                remaining = [(x, y) for start, end in remaining
                             for x, y in ((start, min(end, left)), (max(start, right), end)) if y-x > 1e-7]
        if remaining:
            return mix(a, b, sum(remaining[0])/2)
    return None


def dashed(polylines, pattern, offset):
    """沿每个子路径的弧长切分实际绘制的虚线段，不把空隙当作实体线。"""
    if not pattern or pattern == "none":
        return polylines
    lengths = numbers(pattern)
    if not lengths or any(v < 0 for v in lengths) or sum(lengths) == 0:
        raise ValueError("无效 stroke-dasharray")
    if len(lengths) % 2:
        lengths *= 2
    output = []
    for polyline in polylines:
        phase = offset % sum(lengths)
        slot = 0
        while phase >= lengths[slot]:
            phase -= lengths[slot]
            slot = (slot+1) % len(lengths)
        remaining = lengths[slot]-phase
        for a, b in zip(polyline, polyline[1:]):
            distance = math.dist(a, b)
            at = 0.
            while at < distance:
                if remaining <= 1e-9:
                    slot = (slot+1) % len(lengths)
                    remaining = lengths[slot]
                    continue
                advance = min(distance-at, remaining)
                if slot % 2 == 0:
                    output.append([mix(a,b,at/distance), mix(a,b,(at+advance)/distance)])
                at += advance
                remaining -= advance
    return output


def inspect_rendered_layout(path: str | Path) -> dict:
    """返回可重算的证据；无法检查的可见特性不会被当作通过。"""
    texts, strokes, masks, unsupported = [], [], [], []
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return dict(status="review_required", text_count=0, connector_count=0, issues=[str(exc)])
    order = 0
    def walk(element, matrix=IDENTITY, inherited=None, context="", role=""):
        nonlocal order
        order += 1
        index = order
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in ("defs", "metadata", "desc", "title"):
            return
        own_style = dict(element.attrib)
        own_style.update(dict(tuple(v.strip() for v in part.split(":", 1))
                              for part in element.get("style", "").split(";") if ":" in part))
        style = {**(inherited or {}), **own_style}
        if style.get("display") == "none" or style.get("visibility") == "hidden":
            return
        context = element.get("id", "") or element.get("class", "") or context
        for name in element.get("class", "").split():
            if name in ("entity", "cluster", "title", "legend", "message", "link"):
                role = name
        try:
            matrix = multiply(matrix, transform(element.get("transform", "")))
            opacity = number(own_style.get("opacity", "1")) * number((inherited or {}).get("opacity", "1"))
            style["opacity"] = str(opacity)
            if opacity == 0:
                return
            if any(style.get(k, "none") != "none" for k in ("clip-path", "mask", "filter", "marker-start", "marker-mid", "marker-end")):
                raise ValueError("裁剪、mask、filter 或 marker 需要视觉复核")
            if tag in ("style", "use", "image", "foreignObject", "textPath"):
                raise ValueError("不支持的可见 SVG 元素：" + tag)
            polygons = []
            if tag == "text":
                content = "".join(element.itertext())
                if content.strip() and style.get("fill", "black").lower() not in ("none", "transparent"):
                    texts.append((index, content, dict(style), matrix, context, len(element)))
            elif tag == "path":
                polygons = paths(element.get("d", ""))
            elif tag in ("polygon", "polyline"):
                values = numbers(element.get("points", ""))
                if len(values) % 2:
                    raise ValueError("SVG points 必须成对")
                polygons = [list(zip(values[::2], values[1::2]))]
                if tag == "polygon" and polygons[0]:
                    polygons[0].append(polygons[0][0])
            elif tag == "line":
                polygons = [[(number(style.get("x1", "0")), number(style.get("y1", "0"))),
                             (number(style.get("x2", "0")), number(style.get("y2", "0")))]]
            elif tag == "rect":
                x, y = number(style.get("x", "0")), number(style.get("y", "0"))
                w, h = number(style.get("width", "0")), number(style.get("height", "0"))
                # 圆角背景保守缩小，不能用外接矩形掩盖圆角内的可见线。
                rx = min(w/2, number(style.get("rx", style.get("ry", "0"))))
                ry = min(h/2, number(style.get("ry", style.get("rx", "0"))))
                polygons = [[(x+rx,y), (x+w-rx,y), (x+w,y+ry), (x+w,y+h-ry),
                             (x+w-rx,y+h), (x+rx,y+h), (x,y+h-ry), (x,y+ry), (x+rx,y)]]
            elif tag in ("circle", "ellipse"):
                x, y = number(style.get("cx", "0")), number(style.get("cy", "0"))
                rx = number(style.get("r", style.get("rx", "0")))
                ry = number(style.get("r", style.get("ry", "0")))
                polygons = [[(x+rx*math.cos(i*math.pi/64), y+ry*math.sin(i*math.pi/64)) for i in range(129)]]
            elif tag not in ("svg", "g", "text", "tspan"):
                raise ValueError("不支持的 SVG 元素：" + tag)
            connector_polylines = []
            for local in polygons:
                polygon = [point(p, matrix) for p in local]
                fill = style.get("fill", "black").lower()
                if tag != "line" and fill not in ("none", "transparent"):
                    if fill.startswith(("url(", "rgba(", "hsla(")) or (fill.startswith("#") and len(fill) in (5, 9)):
                        raise ValueError("渐变、图案或带颜色透明度的背景需要复核")
                    if tag == "path" and len(polygons) > 1:
                        raise ValueError("多子路径填充背景需要复核")
                    if opacity * number(style.get("fill-opacity", "1")) == 1:
                        masks.append((index, polygon))
                # 连线：开放路径/line/polyline，以及 link 组内的箭头。
                decoration = role in ("entity", "cluster", "title", "legend") or context.startswith(("entity_", "cluster_"))
                connector = (tag in ("line", "polyline") or (tag == "path" and fill == "none")
                             or (tag == "polygon" and (role == "link" or context.startswith("link_")))) and not decoration
                if root.get("data-diagram-type", "").upper() == "SEQUENCE":
                    # 生命线属于结构标记；只检查 message 组中的真实消息箭头。
                    connector = connector and role == "message"
                if connector and style.get("stroke", "none").lower() not in ("none", "transparent"):
                    width = number(style.get("stroke-width", "1"))
                    if width > 0 and number(style.get("stroke-opacity", "1")) > 0:
                        connector_polylines.append(local)
            if connector_polylines:
                # 虚线长度在元素的局部坐标中定义，切分后再转换到画布坐标。
                local_lines = dashed(connector_polylines, style.get("stroke-dasharray", "none"),
                                     number(style.get("stroke-dashoffset", "0")))
                for local in local_lines:
                    scale = max(math.hypot(matrix[0],matrix[1]), math.hypot(matrix[2],matrix[3]))
                    strokes.append((index, [point(p,matrix) for p in local], width*scale, context or f"{tag}#{index}"))
        except (ValueError, OverflowError) as exc:
            unsupported.append(f"{context or tag}：{exc}")
        for child in element:
            walk(child, matrix, style, context, role)
    walk(root)
    issues = []
    # 无连线的空 SVG 不在此推断渲染真实性；由独立 SVG/artifact 门禁负责。
    if strokes:
        for text_index, content, style, matrix, context, child_count in texts:
            try:
                if child_count:
                    raise ValueError("tspan/textPath 文字布局需要复核")
                width = number(style.get("textLength", ""))
                size = number(style.get("font-size", ""))
                x = number(style.get("x", "0")) + number(style.get("dx", "0"))
                y = number(style.get("y", "0")) + number(style.get("dy", "0"))
                anchor = style.get("text-anchor", "start")
                if anchor not in ("start", "middle", "end"):
                    raise ValueError("不支持 text-anchor")
                x -= width * {"start": 0, "middle": .5, "end": 1}[anchor]
                baseline = style.get("dominant-baseline", "auto")
                if baseline not in ("auto", "alphabetic", "middle", "central", "hanging", "text-before-edge"):
                    raise ValueError("不支持 dominant-baseline")
                top = y - .85*size
                if baseline in ("middle", "central"):
                    top = y - .5*size
                elif baseline in ("hanging", "text-before-edge"):
                    top = y
                scale = max(1e-9, min(math.hypot(matrix[0],matrix[1]), math.hypot(matrix[2],matrix[3])))
                seen = set()
                for line_index, polyline, stroke_width, line_id in strokes:
                    if line_index in seen:
                        continue
                    # 文字内部区域加半线宽；边缘留一像素避免字形边缘贴边误报。
                    pad = (stroke_width/2 + TOLERANCE)/scale - 1.
                    polygon = [point(p, matrix) for p in ((x-pad,top-pad), (x+width+pad,top-pad),
                               (x+width+pad,top+size+pad), (x-pad,top+size+pad))]
                    blockers = [p for index, p in masks if line_index < index < text_index]
                    contact = next((p for a,b in zip(polyline, polyline[1:])
                                    if (p := visible_contact(a,b,polygon,blockers)) is not None), None)
                    if contact:
                        seen.add(line_index)
                        issues.append(f"连线 {line_id} 穿过文字 {content!r}（{context or 'text'}），"
                                      f"位置 ({contact[0]:.2f}, {contact[1]:.2f})")
            except (ValueError, OverflowError) as exc:
                unsupported.append(f"文字 {content!r}：{exc}")
    return dict(status="failed" if issues else "review_required" if unsupported else "ok",
                text_count=len(texts), connector_count=len({row[0] for row in strokes}), issues=(issues + unsupported)[:50])
