"""图包合同与独立文件复核；不调用浏览器。"""
import json
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from model import ROOT, TYPES, Invalid, check_source, check_visible_text, fingerprint, load, require, safe_relative, sha, validate

CONTRACT = 1
ARTIFACTS = ('brief.json', 'diagram.mmd', 'diagram.svg', 'diagram.png', 'render-evidence.json', 'explanation.md')


def contract_hash():
    paths = sorted((ROOT / 'scripts').glob('*.py')) + sorted((ROOT / 'scripts').glob('*.mjs'))
    paths += [ROOT / 'package-lock.json', ROOT / 'assets/brief.schema.json']
    return sha(b''.join(p.name.encode() + p.read_bytes() for p in paths))


def artifact_hashes(folder):
    paths = list(ARTIFACTS)
    parent = folder / 'evidence/overview.json'
    if parent.is_file():
        paths.append('evidence/overview.json')
    return {p: sha(safe_relative(folder, p).read_bytes()) for p in paths}


def layout_issues(evidence):
    """复算浏览器提供的几何证据；遮挡标签有背景时不判本边穿字。"""
    issues = []
    box = evidence['view_box']
    texts = evidence['texts']
    require(texts and all(math.isfinite(v) for v in box), 'SVG 缺少有效文字几何')
    for t in texts:
        r = t['rect']
        require(len(r) == 4 and all(math.isfinite(v) for v in r), '文字坐标无效')
        if r[0] < box[0]-2 or r[1] < box[1]-2 or r[0]+r[2] > box[0]+box[2]+2 or r[1]+r[3] > box[1]+box[3]+2:
            issues.append({'kind': 'clipped_text', 'text': t['text'], 'rect': r})
    for i, a in enumerate(texts):
        for b in texts[i+1:]:
            x,y,w,h = a['rect']; u,v,s,t = b['rect']
            if min(x+w,u+s)-max(x,u) > 2 and min(y+h,v+t)-max(y,v) > 2:
                issues.append({'kind': 'overlapping_text', 'text': [a['text'],b['text']]})
    for edge in evidence['edges']:
        require(edge['points'] and all(len(p)==2 and all(math.isfinite(v) for v in p) for p in edge['points']), '关系线坐标无效')
        for node in evidence.get('nodes',[]):
            if node['id'] in edge.get('masked_endpoints',[]):
                continue
            x,y,w,h=node['rect']
            if any(x+2 < p[0] < x+w-2 and y+2 < p[1] < y+h-2 for p in edge['points']):
                issues.append({'kind':'edge_crosses_node','edge':edge['id'],'node':node['id']})
        for text in texts:
            if text.get('masked_node') in edge.get('masked_endpoints',[]):
                continue
            if text.get('masked_edge') and edge['id'].endswith(text['masked_edge']):
                continue
            x,y,w,h = text['rect']
            if any(x+2 < p[0] < x+w-2 and y+2 < p[1] < y+h-2 for p in edge['points']):
                issues.append({'kind': 'edge_crosses_text', 'edge': edge['id'], 'text': text['text']})
    return issues[:100]


def verify(folder, allow_pending=False):
    folder = Path(folder).resolve()
    r = json.loads((folder/'validation.json').read_text())
    allowed = ('success', 'review_required') if allow_pending else ('success',)
    require(r['final_status'] in allowed, '图包尚未验收通过')
    require(r['contract_version'] == CONTRACT and r['contract_hash'] == contract_hash(), '合同版本或实现已变化')
    require(r['artifacts'] == artifact_hashes(folder), '图包文件 hash 不匹配')
    b = validate(load(folder/'brief.json'), folder)
    source = (folder/'diagram.mmd').read_text()
    require(check_source(b, source) == r['metrics'], '源码 metrics 不匹配')
    require(r['diagram_type'] == b['diagram_type'] and r['diagram_id'] == b['diagram_id'], '图包身份不匹配')
    require(r['failure_class'] is None and not r['repairable'] and not r['issues'], '成功包仍有失败字段')
    require(r['input_fingerprint'] == fingerprint(b,source,r['contract_hash']) == r['last_render_fingerprint'] and r['last_render_status']=='passed', '输入身份或最近一次渲染记录不一致')
    require(r['checks'] == {'brief':'passed','coverage':'passed','render':'passed','layout':'passed'}, '质量门禁没有全部通过')
    svg = ET.fromstring((folder/'diagram.svg').read_bytes())
    require(svg.tag == '{http://www.w3.org/2000/svg}svg' and len(svg) > 0, '不是实际 SVG')
    require(not any(e.tag.split('}')[-1] in ('script','iframe','image') for e in svg.iter()), 'SVG 含不允许的活动资源')
    png = (folder/'diagram.png').read_bytes()
    require(png[:8] == b'\x89PNG\r\n\x1a\n' and len(png) > 100, 'PNG 无效')
    w,h = struct.unpack('>II',png[16:24])
    require(w > 0 and h > 0, 'PNG 尺寸无效')
    ev = json.loads((folder/'render-evidence.json').read_text())
    require(ev['svg_sha256'] == sha((folder/'diagram.svg').read_bytes()), '几何证据未绑定当前 SVG')
    require(ev['source_sha256'] == sha(source.encode()) and ev['renderer'] == r['renderer'], '渲染证据身份不同')
    require(ev['renderer']['cli'] == '12.0.0' and ev['renderer']['browser'], 'renderer 身份缺失')
    check_visible_text(b,ev)
    if b['diagram_type'] in TYPES:
        require(len(ev['edges']) == r['metrics']['edges'], '关系线几何数量与源码不一致，不能跳过布局检查')
    require(not layout_issues(ev), '重新计算的布局检查失败')
    require(r['attempt_index'] in (1,2) and r['max_render_attempts'] == 2 and r['attempts_remaining'] == 2-r['attempt_index'], '渲染次数无效')
    for key in ('timings','last_run_timings'):
        ts = r[key]
        require(all(isinstance(x,(int,float)) and math.isfinite(x) and x >= 0 for x in ts.values()), '计时无效')
        require(abs(ts['total_ms']-ts['render_ms']-ts['static_ms']) < .01, '计时无法闭合')
    require(r['counters']['render_calls'] == 1 and r['counters']['verifier_calls'] == 1, '生成计数无效')
    require(r['last_run_counters'] in ({'render_calls':1,'verifier_calls':1,'cache_hits':0},{'render_calls':0,'verifier_calls':2,'cache_hits':1}), '调用计数无效')
    review = r['visual_review']
    if r['final_status'] == 'success':
        require(review['status'] == 'passed' and review['notes'].strip() and review['svg_sha256'] == r['artifacts']['diagram.svg'], '视觉复核未绑定当前 SVG')
        if b['diagram_type'] not in TYPES:
            require(review.get('semantic_review') == 'passed', '通用图型缺少语义人工复核')
    else:
        require(review['status'] == 'pending', '等待复核状态不一致')
    return r
