"""draw.io 图包的纯数据校验、生成与几何检查。仅使用 Python 标准库。"""
import base64
import hashlib
import json
import math
import re
import struct
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

CONTRACT = 1
MAX_BYTES = 2 * 1024 * 1024
SHAPES = {'rectangle': '', 'rounded': 'rounded=1;', 'ellipse': 'ellipse;',
          'diamond': 'rhombus;', 'cylinder': 'shape=cylinder3;',
          'group': 'swimlane;startSize=36;horizontal=1;'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    require(Path(path).stat().st_size <= MAX_BYTES, '输入超过 2 MiB')
    return json.loads(Path(path).read_text(encoding='utf-8'))


def text(value, field, empty=False):
    require(isinstance(value, str) and (empty or value.strip()) and len(value) <= 200,
            f'{field} 必须为最多 200 字符的文本')
    require(not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value), f'{field} 含控制字符')


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_brief(brief):
    require(isinstance(brief, dict), 'brief 必须为 JSON 对象')
    require(set(brief) == {'title', 'diagram_type', 'nodes', 'edges'}, 'brief 字段须为 title/diagram_type/nodes/edges')
    text(brief['title'], 'title')
    text(brief['diagram_type'], 'diagram_type')
    nodes, edges = brief['nodes'], brief['edges']
    require(isinstance(nodes, list) and 1 <= len(nodes) <= 60, '节点预算为 1–60')
    require(isinstance(edges, list) and len(edges) <= 100, '连线预算为 0–100')
    ids = {'0', '1'}
    for kind, items in [('node', nodes), ('edge', edges)]:
        for item in items:
            require(isinstance(item, dict), f'{kind} 必须为对象')
            ident = item.get('id')
            require(isinstance(ident, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', ident), 'id 格式无效')
            require(ident not in ids, f'id 重复：{ident}')
            ids.add(ident)
            text(item.get('label', ''), f'{ident}.label', empty=kind == 'edge')
    node_map = {n['id']: n for n in nodes}
    for node in nodes:
        require(set(node) <= {'id', 'label', 'x', 'y', 'width', 'height', 'shape', 'parent'}, f"{node['id']} 含未知字段")
        require(node.get('shape', 'rounded') in SHAPES, '不支持的 shape')
        for key in ('x', 'y', 'width', 'height'):
            require(number(node.get(key)), f"{node['id']}.{key} 必须为有限数字")
        require(0 <= node['x'] <= 5000 and 0 <= node['y'] <= 5000 and
                40 <= node['width'] <= 5000 and 36 <= node['height'] <= 5000, '节点坐标/尺寸超出预算')
        seen = {node['id']}
        parent = node.get('parent')
        while parent:
            require(parent in node_map and parent not in seen, 'parent 缺失或形成环')
            require(node_map[parent].get('shape') == 'group', 'parent 必须为 group')
            seen.add(parent)
            parent = node_map[parent].get('parent')
        require(len(seen) <= 4, '分组深度最多 4 层')
    for edge in edges:
        require(set(edge) <= {'id', 'label', 'source', 'target', 'points'}, f"{edge['id']} 含未知字段")
        require(edge.get('source') in node_map and edge.get('target') in node_map, '连线端点缺失')
        require(edge['source'] != edge['target'], '自环需手工拆为显式中间节点')
        points = edge.get('points', [])
        require(isinstance(points, list) and len(points) <= 12, '每线最多 12 个路由点')
        require(all(isinstance(p, list) and len(p) == 2 and all(number(x) and 0 <= x <= 6000 for x in p)
                    for p in points), '路由点须为 [x,y]')
    return brief


def generate(brief):
    model = ET.Element('mxGraphModel', grid='1', page='0', background='#ffffff')
    root = ET.SubElement(model, 'root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    for node in brief['nodes']:
        shape = node.get('shape', 'rounded')
        style = (SHAPES[shape] + 'whiteSpace=wrap;html=0;fontFamily=Noto Sans CJK SC;'
                 'fontSize=16;fontColor=#172B4D;strokeColor=#64748B;fillColor=#E8F1FC;'
                 'spacing=8;')
        cell = ET.SubElement(root, 'mxCell', id=node['id'], value=node['label'],
                             style=style, vertex='1', parent=node.get('parent', '1'))
        ET.SubElement(cell, 'mxGeometry', **{k: str(node[k]) for k in ('x', 'y', 'width', 'height')}, **{'as': 'geometry'})
    for edge in brief['edges']:
        cell = ET.SubElement(root, 'mxCell', id=edge['id'], value=edge.get('label', ''), edge='1',
                             parent='1', source=edge['source'], target=edge['target'],
                             style='edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;'
                                   'fontFamily=Noto Sans CJK SC;fontSize=14;labelBackgroundColor=#FFFFFF;')
        geo = ET.SubElement(cell, 'mxGeometry', relative='1', y='-16', **{'as': 'geometry'})
        if edge.get('points'):
            array = ET.SubElement(geo, 'Array', **{'as': 'points'})
            for x, y in edge['points']:
                ET.SubElement(array, 'mxPoint', x=str(x), y=str(y))
    mxfile = ET.Element('mxfile', host='localhost', compressed='false')
    diagram = ET.SubElement(mxfile, 'diagram', id='page1', name=brief['title'])
    diagram.append(model)
    return ET.tostring(mxfile, encoding='unicode')


def parse_xml(raw):
    require(len(raw.encode()) <= MAX_BYTES and not re.search(r'<!DOCTYPE|<!ENTITY', raw, re.I), 'XML 超限或包含 DTD/实体')
    doc = ET.fromstring(raw)
    if doc.tag == 'mxfile':
        pages = doc.findall('diagram')
        require(len(pages) == 1, '一次图包仅接受一页；多页请分别导出并保留页名')
        model = pages[0].find('mxGraphModel')
        if model is None:
            compressed = base64.b64decode(pages[0].text or '', validate=True)
            inflater = zlib.decompressobj(-15)
            expanded = inflater.decompress(compressed, MAX_BYTES + 1)
            require(len(expanded) <= MAX_BYTES and inflater.eof, '压缩图无效或超过 2 MiB')
            return parse_xml(urllib.parse.unquote(expanded.decode()))
    elif doc.tag == 'mxGraphModel':
        model = doc
    else:
        raise ValueError('需要 mxfile 或 mxGraphModel')
    require(model is not None and model.find('root') is not None, '缺少 mxGraphModel/root')
    require(not model.get('backgroundImage'), '不支持外部背景图')
    # 安装包允许确定性的本地矢量元素；HTML、图片、链接和动态资源须先转成普通文本/图形。
    for element in model.iter():
        require(element.tag in {'mxGraphModel', 'root', 'mxCell', 'mxGeometry', 'mxPoint', 'Array', 'mxRectangle'},
                f'不支持的元素：{element.tag}')
        require(not any(k.lower() in {'link', 'href', 'src'} or k.lower().startswith('on') for k in element.attrib), '不支持链接或脚本属性')
        style = element.get('style', '')
        require(not re.search(r'html=1|image=|image;|https?:|file:|javascript:|data:|fontSource=|shape=stencil', style, re.I), '样式包含 HTML 或外部/动态资源')
        require(not re.search(r'(?:^|;)(?:opacity|textOpacity|fillOpacity|strokeOpacity)=0(?:;|$)', style), '不接受透明隐藏内容')
        require(element.get('visible', '1') != '0' and element.get('collapsed', '0') != '1', '不接受隐藏或折叠内容')
    return model


def inspect_source(brief, raw):
    model = parse_xml(raw)
    cells = model.findall('./root/mxCell')
    ids = [c.get('id') for c in cells]
    require(None not in ids and len(ids) == len(set(ids)), 'cell id 缺失或重复')
    mapping = {c.get('id'): c for c in cells}
    require('0' in mapping and '1' in mapping and mapping['1'].get('parent') == '0', '缺少根层 0/1')
    nodes = {c.get('id'): c for c in cells if c.get('vertex') == '1'}
    edges = {c.get('id'): c for c in cells if c.get('edge') == '1'}
    require(set(nodes) == {n['id'] for n in brief['nodes']}, '节点覆盖不一致')
    require(set(edges) == {e['id'] for e in brief['edges']}, '连线覆盖不一致')
    require(set(ids) == {'0', '1'} | set(nodes) | set(edges), '存在未声明 cell')
    for node in brief['nodes']:
        cell = nodes[node['id']]
        style = cell.get('style', '').split(';')
        shape = node.get('shape', 'rounded')
        markers = {'rectangle': None, 'rounded': 'rounded=1', 'ellipse': 'ellipse',
                   'diamond': 'rhombus', 'cylinder': 'shape=cylinder3', 'group': 'swimlane'}
        marker = markers[shape]
        require(marker is None or marker in style or ('shape=' + marker) in style, f"节点形状不一致：{node['id']}")
        require(cell.get('value', '') == node['label'], f"节点标签不一致：{node['id']}")
        require(cell.get('parent') == node.get('parent', '1'), '节点分组不一致')
        geo = cell.find('mxGeometry')
        require(geo is not None and geo.get('relative', '0') != '1', '节点需要绝对几何坐标')
        for key in ('x', 'y', 'width', 'height'):
            value = float(geo.get(key, '0'))
            require(math.isfinite(value) and abs(value - node[key]) < 0.01, f"{node['id']}.{key} 与 brief 不一致")
    for edge in brief['edges']:
        cell = edges[edge['id']]
        require(cell.get('source') == edge['source'] and cell.get('target') == edge['target'], '连线方向/端点不一致')
        require(cell.get('value', '') == edge.get('label', ''), '连线标签不一致')
        require(cell.get('parent') == '1', '连线须位于根层')
    return ET.tostring(model, encoding='unicode')


def overlap(a, b, margin=1):
    return (min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0]) > margin and
            min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]) > margin)


def contains(outer, inner, tolerance=3):
    return (inner[0] >= outer[0]-tolerance and inner[1] >= outer[1]-tolerance and
            inner[0]+inner[2] <= outer[0]+outer[2]+tolerance and
            inner[1]+inner[3] <= outer[1]+outer[3]+tolerance)


def segment_hits(a, b, rect):
    # Liang–Barsky：仅检查内部，擦过边界不算穿过。
    x, y, width, height = rect
    bounds = (x+2, y+2, x+width-2, y+height-2)
    lo, hi = 0.0, 1.0
    for start, delta, low, high in ((a[0], b[0]-a[0], bounds[0], bounds[2]),
                                   (a[1], b[1]-a[1], bounds[1], bounds[3])):
        if abs(delta) < 1e-9:
            if not low < start < high:
                return False
        else:
            t1, t2 = sorted(((low-start)/delta, (high-start)/delta))
            lo, hi = max(lo, t1), min(hi, t2)
            if lo >= hi:
                return False
    return True


def layout_issues(brief, geometry):
    require(isinstance(geometry, list), '缺少渲染几何数据')
    by_id = {g['id']: g for g in geometry}
    expected = {x['id'] for x in brief['nodes'] + brief['edges']}
    require(set(by_id) == expected and len(by_id) == len(geometry), '渲染后的 cell 覆盖不一致')
    for g in geometry:
        for field in ('rect', 'text'):
            box = g.get(field)
            require((box is None and field == 'text') or (isinstance(box, list) and len(box) == 4 and
                    all(number(v) for v in box) and box[2] >= 0 and box[3] >= 0), '渲染包围盒无效')
        require(all(isinstance(p, list) and len(p) == 2 and all(number(v) for v in p) for p in g.get('points', [])), '渲染路由无效')
    nodes = {n['id']: n for n in brief['nodes']}

    def ancestors(ident):
        result = set()
        while nodes[ident].get('parent'):
            ident = nodes[ident]['parent']
            result.add(ident)
        return result

    issues = []
    for ident, node in nodes.items():
        g = by_id[ident]
        if g.get('edge') or not g['text']:
            issues.append(f'节点不可见或缺少标签：{ident}')
        elif not contains(g['rect'], g['text']):
            issues.append(f'文字超出节点：{ident}')
        if node.get('parent'):
            parent_rect = list(by_id[node['parent']]['rect'])
            parent_rect[1] += 36
            parent_rect[3] -= 36
            if not contains(parent_rect, g['rect'], 0):
                issues.append(f'节点超出分组正文区域：{ident}')
        for other in nodes:
            if ident < other and other not in ancestors(ident) and ident not in ancestors(other):
                if overlap(g['rect'], by_id[other]['rect']):
                    issues.append(f'节点重叠：{ident}/{other}')
    for edge in brief['edges']:
        g = by_id[edge['id']]
        require(g.get('edge') and len(g.get('points', [])) >= 2, '连线缺少实际路径')
        if edge.get('label') and not g['text']:
            issues.append(f"连线标签不可见：{edge['id']}")
        excluded = {edge['source'], edge['target']} | ancestors(edge['source']) | ancestors(edge['target'])
        for ident in nodes:
            if ident not in excluded and any(segment_hits(a, b, by_id[ident]['rect']) for a, b in zip(g['points'], g['points'][1:])):
                issues.append(f"连线穿过节点：{edge['id']}/{ident}")
            if g['text'] and ident not in ancestors(edge['source']) | ancestors(edge['target']) and overlap(g['text'], by_id[ident]['rect']):
                issues.append(f"连线标签覆盖节点：{edge['id']}/{ident}")
        for other in geometry:
            if other['id'] != edge['id'] and other['text']:
                if any(segment_hits(a, b, other['text']) for a, b in zip(g['points'], g['points'][1:])):
                    issues.append(f"连线穿过文字：{edge['id']}/{other['id']}")
    labels = [g for g in geometry if g['text']]
    for i, a in enumerate(labels):
        for b in labels[i+1:]:
            if overlap(a['text'], b['text']):
                issues.append(f"文字重叠：{a['id']}/{b['id']}")
    return sorted(set(issues))


def validate_images(svg, png):
    require(len(svg.encode()) <= 16*MAX_BYTES, 'SVG 超出预算')
    require(not re.search(r'<!ENTITY|<!DOCTYPE', svg, re.I), 'SVG 含实体声明')
    root = ET.fromstring(svg)
    require(root.tag == '{http://www.w3.org/2000/svg}svg', '产物不是 SVG')
    require(any(e.tag.rsplit('}', 1)[-1] in {'path', 'rect', 'ellipse', 'polygon'} for e in root.iter()), 'SVG 缺少图形')
    for e in root.iter():
        tag = e.tag.rsplit('}', 1)[-1]
        require(tag in {'svg', 'g', 'defs', 'path', 'rect', 'ellipse', 'circle', 'polygon', 'polyline',
                        'line', 'text', 'tspan', 'switch', 'foreignObject', 'div', 'br', 'clipPath'},
                f'SVG 含不支持的元素：{tag}')
        # draw.io 将纯文字换行导出为 foreignObject/div/br；保留排版，拒绝任意 HTML 和 CSS 外链。
        require(not re.search(r'url\s*\(|@import|expression\s*\(', e.get('style', ''), re.I), 'SVG 样式含外部/动态资源')
        require(not any(k.rsplit('}', 1)[-1].lower().startswith('on') or
                        (k.rsplit('}', 1)[-1] in {'href', 'src'} and not v.startswith('#'))
                        for k, v in e.attrib.items()), 'SVG 含外部引用')
    require(png[:8] == b'\x89PNG\r\n\x1a\n' and len(png) > 100, 'PNG 无效')
    width, height = struct.unpack('>II', png[16:24])
    require(1 <= width <= 6000 and 1 <= height <= 6000, 'PNG 尺寸无效')
    offset, chunks, image_data = 8, [], bytearray()
    while offset + 12 <= len(png):
        size = struct.unpack('>I', png[offset:offset+4])[0]
        kind = png[offset+4:offset+8]
        require(offset + size + 12 <= len(png), 'PNG 数据截断')
        content = png[offset+8:offset+8+size]
        crc = struct.unpack('>I', png[offset+8+size:offset+12+size])[0]
        require(zlib.crc32(kind + content) & 0xffffffff == crc, 'PNG CRC 不匹配')
        chunks.append(kind)
        if kind == b'IDAT':
            image_data.extend(content)
        offset += size + 12
    require(offset == len(png) and chunks[0] == b'IHDR' and chunks[-1] == b'IEND' and image_data, 'PNG 结构不完整')
    inflater = zlib.decompressobj()
    pixels = inflater.decompress(image_data, (width * 4 + 1) * height + 1)
    require(inflater.eof and len(pixels) in {(width*3+1)*height, (width*4+1)*height}, 'PNG 像素数据无效')
    return {'width': width, 'height': height}


def verify_package(directory):
    directory = Path(directory)
    report = read_json(directory / 'validation.json')
    require(report.get('contract') == CONTRACT and report.get('status') == 'passed', '图包未通过自动校验')
    require(report.get('stage') == 'complete' and report.get('render_attempts') in (1, 2) and
            report.get('issues') == [] and report.get('visual_review') == 'pending', '验证报告合同不符')
    names = {'brief.json', 'diagram.drawio', 'diagram.svg', 'diagram.png', 'render.json'}
    require(set(report.get('sha256', {})) == names, '产物哈希清单不完整')
    for name in names:
        require((directory / name).is_file() and not (directory / name).is_symlink(), f'缺少普通文件：{name}')
        require(digest(directory / name) == report['sha256'][name], f'产物哈希不匹配：{name}')
    brief = validate_brief(read_json(directory / 'brief.json'))
    inspect_source(brief, (directory / 'diagram.drawio').read_text())
    render = read_json(directory / 'render.json')
    require(render.get('source_sha256') == digest(directory / 'diagram.drawio'), '渲染与源文件不一致')
    require(render.get('renderer', {}).get('network') == 'local-only' and
            render['renderer'].get('service') == 'feipi-drawio' and render['renderer'].get('contract') == CONTRACT,
            'renderer 合同不符')
    require(not layout_issues(brief, render['geometry']), '图包仍存在渲染布局问题')
    dimensions = validate_images((directory / 'diagram.svg').read_text(), (directory / 'diagram.png').read_bytes())
    require(dimensions == report.get('dimensions'), '报告尺寸与实际图像不一致')
    return report
