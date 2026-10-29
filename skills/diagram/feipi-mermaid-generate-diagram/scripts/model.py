"""有界 brief、语义约束与确定性 Mermaid 源码；不执行渲染。"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
TYPES = ('architecture', 'sequence', 'component', 'activity', 'deployment', 'mindmap')


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    raw = Path(path).read_text(encoding='utf-8')
    require(len(raw) <= 100_000, 'brief 超过 100 KB')
    # 不允许重复键覆盖需求，也不允许 YAML alias 创建递归结构。
    class Loader(yaml.SafeLoader):
        def compose_node(self, parent, index):
            require(not self.check_event(yaml.AliasEvent), 'brief 禁止 YAML alias')
            return super().compose_node(parent, index)

        def construct_mapping(self, node, deep=False):
            keys = [self.construct_object(k, deep=deep) for k, _ in node.value]
            require(all(isinstance(k, str) for k in keys), 'brief 键必须是字符串')
            require(len(set(keys)) == len(keys), 'brief 存在重复键')
            return super().construct_mapping(node, deep)
    return yaml.load(raw, Loader=Loader)


def safe_relative(base, value):
    p = Path(value)
    require(not p.is_absolute() and '..' not in p.parts and p.parts, '必须使用包内安全相对路径')
    result = (Path(base) / p).resolve()
    require(result.is_relative_to(Path(base).resolve()), '路径越界')
    return result


def unique(items, name='id'):
    values = [n[name] for n in items]
    require(len(values) == len(set(values)), f'{name} 重复')
    return set(values)


def validate(b, base):
    schema = json.loads((ROOT / 'assets/brief.schema.json').read_text())
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(b), key=lambda e: str(e.path))
    require(not errors, 'brief schema: ' + '; '.join(f'{list(e.path)} {e.message}' for e in errors[:4]))
    def text_check(value):
        if isinstance(value, str):
            require(not any(ord(c) < 32 and c != '\n' for c in value), '显示文本含控制字符')
        elif isinstance(value, list):
            for item in value:
                text_check(item)
        elif isinstance(value, dict):
            for item in value.values():
                text_check(item)
    text_check(b)
    t = b['diagram_type']
    if t not in TYPES:
        return b
    nodes = b.get('nodes', b.get('participants', []))
    ids = unique(nodes)
    require(not ids.intersection({'end', 'graph', 'flowchart', 'subgraph'}), '节点 ID 使用了保留字')
    if t == 'mindmap':
        by_id = {n['id']: n for n in nodes}
        roots = [n for n in nodes if not n['parent']]
        require(len(roots) == 1, '思维导图必须唯一根')
        for n in nodes:
            require(not n['parent'] or n['parent'] in ids, '父节点不存在')
            seen, cur = set(), n
            while cur['parent']:
                require(cur['id'] not in seen, '思维导图存在循环')
                seen.add(cur['id'])
                cur = by_id[cur['parent']]
            require(len(seen) < 4, '思维导图最多 4 层')
            children = [v['label'] for v in nodes if v['parent'] == n['id']]
            require(len(children) <= 6 and len(set(children)) == len(children), '每节点最多 6 个子节点且同级标签唯一')
        return b
    if t == 'sequence':
        messages = b['messages']
        unique(messages)
        groups = b.get('groups', [])
        gids = unique(groups)
        for n in nodes:
            require(n.get('group', '') in gids | {''}, '参与者分组不存在')
        require(all(any(n.get('group') == g for n in nodes) for g in gids), '分组为空')
        for g in gids:
            positions = [i for i,n in enumerate(nodes) if n.get('group') == g]
            require(positions == list(range(min(positions),max(positions)+1)), '时序分组参与者必须连续，不可重排用户顺序')
        for i, m in enumerate(messages):
            require(m['from'] in ids and m['to'] in ids, '消息引用未知参与者')
            pattern = r'S[1-9]\d*(?:\.[1-9]\d*)?' if b.get('numbering', 'interaction_mr') == 'process_s' else r'[MR][1-9]\d*'
            require(re.fullmatch(pattern, m['id']), '消息编号不符合 numbering，禁止混用')
        blocks = b.get('blocks', [])
        for x in blocks:
            require(1 <= x['start'] <= x['end'] <= len(messages), '时序块范围无效')
            if x['kind'] == 'alt':
                require(x['start'] < x.get('else_at', 0) <= x['end'] and x.get('else_label'), 'alt 必须含第二分支')
            else:
                require('else_at' not in x and 'else_label' not in x, '只有 alt 可以含 else')
        for i, x in enumerate(blocks):
            for y in blocks[i+1:]:
                disjoint = x['end'] < y['start'] or y['end'] < x['start']
                nested = x['start'] <= y['start'] and y['end'] <= x['end'] or y['start'] <= x['start'] and x['end'] <= y['end']
                require(disjoint or nested, '时序块交叉')
                require((x['start'], x['end']) != (y['start'], y['end']), '时序块范围重复')
                for outer, inner in ((x, y), (y, x)):
                    if outer['start'] <= inner['start'] and inner['end'] <= outer['end'] and outer.get('else_at'):
                        require(not inner['start'] < outer['else_at'] <= inner['end'], '内层时序块跨越 else')
        return b
    groups = b.get('groups', [])
    gids = unique(groups)
    require(not ids.intersection(gids), '分组与节点 ID 冲突')
    for n in nodes:
        require(n.get('group', '') in gids | {''}, '节点分组不存在')
        if groups:
            require(n.get('group') in gids, '节点必须属于分组')
    require(all(any(n.get('group') == g for n in nodes) for g in gids), '分组为空')
    edges = b['edges']
    unique(edges)
    signatures = [(e['from'], e['to'], e.get('label', '')) for e in edges]
    require(len(set(signatures)) == len(signatures), '关系重复')
    degree = {i: 0 for i in ids}
    adjacency = {i: set() for i in ids}
    reverse = {i: set() for i in ids}
    for e in edges:
        require(e['from'] in ids and e['to'] in ids, '关系引用未知节点')
        degree[e['from']] += 1
        degree[e['to']] += 1
        adjacency[e['from']].add(e['to'])
        reverse[e['to']].add(e['from'])
    require(all(degree.values()), '存在孤立节点')
    if t == 'architecture':
        require(all(sum(n['group'] == g for n in nodes) <= 5 for g in gids), '每层最多 5 个组件')
    if t == 'component':
        require(max(degree.values()) <= 4, '组件连接度最多 4')
        if b['view'] == 'overview':
            require('parent_ref' not in b, 'overview 不能有 parent_ref')
            require(all(n['kind'] in ('system', 'domain', 'endpoint') for n in nodes), 'overview 不含内部模块')
        else:
            require(len(groups) == 1 and b.get('parent_ref'), 'module_detail 必须绑定唯一父组件')
            ref = b['parent_ref']
            path = safe_relative(base, ref['path'])
            require(path.is_file() and sha(path.read_bytes()) == ref['sha256'], '父 brief hash 不匹配')
            parent = load(path)
            require(parent.get('diagram_type') == 'component' and parent.get('view') == 'overview', '父 brief 必须是 component overview')
            validate(parent, path.parent)
            require(parent['diagram_id'] == ref['diagram_id'] and ref['node_id'] in {n['id'] for n in parent['nodes']}, '父组件身份不匹配')
    if t == 'activity':
        require(set(b['narrative_step_ids']) == ids and len(b['narrative_step_ids']) == len(ids), '叙述步骤与节点集合不同')
        numbered = sorted(int(i[1:]) for i in ids if re.fullmatch(r'S\d+', i))
        require(5 <= len(numbered) <= 10 and numbered == list(range(1, len(numbered)+1)), '活动顶层编号应为连续 S1...Sn，5–10 步')
        require(all('.' not in i or i.split('.')[0] in ids for i in ids), '活动子步骤缺少父步骤')
        starts = [n['id'] for n in nodes if n['kind'] == 'start']
        ends = [n['id'] for n in nodes if n['kind'] == 'stop']
        require(len(starts) == 1 and ends, '活动图必须唯一起点和至少一个终点')
        require(not reverse[starts[0]] and all(not adjacency[e] for e in ends), '起点不能有入边，终点不能有出边')
        for n in nodes:
            out = [e for e in edges if e['from'] == n['id']]
            if n['kind'] == 'decision':
                labels = [e.get('label', '') for e in out]
                require(len(labels) >= 2 and all(labels) and len(set(labels)) == len(labels), '判断节点至少两个不同且非空条件分支')
            elif n['kind'] != 'stop':
                require(len(out) == 1, '非判断活动必须唯一后继')
        def reachable(seeds, graph):
            found, todo = set(), list(seeds)
            while todo:
                cur = todo.pop()
                if cur not in found:
                    found.add(cur)
                    todo.extend(graph[cur])
            return found
        require(reachable(starts, adjacency) == ids and reachable(ends, reverse) == ids, '活动有不可达步骤或无法到终点的分支')
    if t == 'deployment':
        by_id = {n['id']: n for n in nodes}
        pairs = [(by_id[e['from']], by_id[e['to']]) for e in edges]
        require(any(n['kind'] == 'endpoint' for n in nodes), '部署图缺少物理端点')
        require(any(a['group'] != z['group'] for a, z in pairs), '部署图缺少跨区关系')
        triggers = {
            'cross_network': any(a['network_id'] != z['network_id'] for a, z in pairs),
            'cross_chain': any(a['chain_id'] != z['chain_id'] for a, z in pairs),
            'online_offline': any({a['mode'], z['mode']} == {'online', 'offline'} for a, z in pairs),
            'hsm': any(n['kind'] == 'hsm' for n in nodes),
            'manual_transfer': any(n['kind'] == 'human_transfer' for n in nodes),
            'manual_handoff': any(n['kind'] == 'human_handoff' for n in nodes),
        }
        require(b['boundary_triggers'] == triggers, '部署 boundary_triggers 与节点/关系不一致')
    return b


def encode(value, width=24):
    """仅转义语法敏感字符，避免 renderer 按实体长度放大布局。"""
    lines, line, used = [], '', 0
    for c in value:
        size = 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
        if c == '\n' or used + size > width:
            lines.append(line)
            line, used = '', 0
        if c != '\n':
            line += f'#{ord(c)};' if c in '&<>"#;`%\\' else c
            used += size
    lines.append(line)
    return '<br/>'.join(lines)


def generate(b):
    t = b['diagram_type']
    require(t in TYPES, '通用图型需提供 --diagram 源码')
    direction = b.get('layout', {}).get('direction', 'TB')
    if t == 'sequence':
        lines = ['sequenceDiagram']
        groups = b.get('groups', [])
        labels = {g['id']:g['label'] for g in groups}
        active = ''
        for n in b['participants']:
            group = n.get('group','')
            if group != active:
                if active:
                    lines.append('end')
                if group:
                    lines.append('box ' + encode(labels[group],40))
                active = group
            lines.append(f"participant {n['id']} as {encode(n['label'])}")
        if active:
            lines.append('end')
        blocks = b.get('blocks', [])
        for i, m in enumerate(b['messages'], 1):
            # 先切换外层 else，再打开从第二分支首条消息开始的内层块。
            for x in blocks:
                if x.get('else_at') == i:
                    lines.append('else ' + encode(x['else_label'], 50))
            for x in sorted([x for x in blocks if x['start'] == i], key=lambda x: -x['end']):
                lines.append(f"{x['kind']} {encode(x['label'], 50)}")
            lines.append(f"{m['from']}{m.get('arrow', '->>')}{m['to']}: {encode(m['id'] + ' ' + m['label'], 50)}")
            if m.get('note'):
                position = f"over {m['from']},{m['to']}" if m['from'] != m['to'] and len(m['note']) > 24 else f"right of {m['to']}"
                lines.append(f"Note {position}: {encode(m['note'], 44)}")
            lines.extend('end' for x in sorted([x for x in blocks if x['end'] == i], key=lambda x: -x['start']))
    elif t == 'mindmap' and direction == 'balanced':
        lines = ['mindmap']
        def add(parent, depth):
            for n in b['nodes']:
                if n['parent'] == parent:
                    lines.append('  ' * depth + f"{n['id']}[\"{encode(n['label'])}\"]")
                    add(n['id'], depth+1)
        add('', 1)
    else:
        if t == 'mindmap':
            direction = {'right': 'LR', 'left': 'RL'}[direction]
        lines = ['flowchart ' + direction]
        groups = b.get('groups', [])
        for group in groups + [{'id': '', 'label': ''}]:
            items = [n for n in b['nodes'] if n.get('group', '') == group['id']]
            if not items:
                continue
            if group['id']:
                lines.append(f"subgraph {group['id']}[\"{encode(group['label'], 40)}\"]")
            for n in items:
                label = n['label']
                if t == 'activity':
                    label = n['id'] + ' ' + label
                if t == 'deployment':
                    label += '\n' + n['mode'] + ' / ' + n['network_id'] + ' / ' + n['chain_id']
                opening, closing = {'decision': ('{', '}'), 'start': ('([', '])'), 'stop': ('([', '])'), 'database': ('[(', ')]')}.get(n.get('kind'), ('[', ']'))
                lines.append(f"{n['id']}{opening}\"{encode(label)}\"{closing}")
            if group['id']:
                lines.append('end')
        edges = b.get('edges', [{'from': n['parent'], 'to': n['id'], 'label': ''} for n in b['nodes'] if n.get('parent')])
        for e in edges:
            label = e.get('label', '')
            if t in ('architecture', 'component', 'deployment'):
                label = e['id']
            suffix = f'|"{encode(label, 36)}"|' if label else ''
            lines.append(f"{e['from']} -->{suffix} {e['to']}")
    return '\n'.join(lines) + '\n'


def normalize(source):
    return '\n'.join(line.strip() for line in source.splitlines() if line.strip() and not line.lstrip().startswith('%%')) + '\n'


def check_source(b, source):
    require(0 < len(source.encode()) <= 100_000, '源码为空或超过 100 KB')
    require(not re.search(r'%%\{|^---|\bclick\s|<\s*(?:script|iframe|img)\b|javascript:', source, re.I | re.M), '源码不允许配置注入、交互或外部资源')
    if b['diagram_type'] in TYPES:
        require(normalize(source) == normalize(generate(b)), '源码与 brief 的节点、关系、顺序、分组或显示文本不一致；通过 brief 调整 typed 图')
    else:
        require(source.lstrip().startswith(b['syntax'] + '\n') or source.lstrip().startswith(b['syntax'] + ' '), '通用图源码头与 syntax 不同')
        require(all(v in source for v in b['expected_text']), '通用图缺少 expected_text；仅文字覆盖，语义需复核')
    metrics = {'lines': len(normalize(source).splitlines()), 'characters': len(source),
               'statements': len([x for x in normalize(source).splitlines()[1:] if x != 'end']),
               'source_sha256': sha(source.encode())}
    if b['diagram_type'] in TYPES:
        if source.lstrip().startswith('sequenceDiagram'):
            metrics['nodes'] = len(re.findall(r'^\s*participant ',source,re.M))
            metrics['edges'] = len(re.findall(r'^\s*\w+(?:--?>>?|--?x)\w+:',source,re.M))
        else:
            metrics['nodes'] = len(re.findall(r'^\s*[A-Za-z][\w.]*[\[{(]',source,re.M))
            metrics['edges'] = metrics['nodes']-1 if source.lstrip().startswith('mindmap') else len(re.findall(r'^\s*[A-Za-z][\w.]* -->',source,re.M))
    return metrics


def fingerprint(b, source, contract):
    normalized = json.loads(json.dumps(b))
    if normalized.get('parent_ref'):
        normalized['parent_ref']['path'] = 'evidence/overview.json'
    return sha(json.dumps(normalized,ensure_ascii=False,sort_keys=True).encode()+source.encode()+contract.encode())


def check_visible_text(b, evidence):
    """检查真实浏览器可见文字，避免转义编码被直接画到图上。"""
    compact = lambda s: re.sub(r'\s+', '', s)
    visible = ''.join(compact(x['text']) for x in evidence['texts'])
    expected = [n['label'] for n in b.get('nodes',b.get('participants',[]))]
    expected += [g['label'] for g in b.get('groups',[])]
    for m in b.get('messages',[]):
        expected += [m['id'] + ' ' + m['label']]
        if m.get('note'):
            expected.append(m['note'])
    for block in b.get('blocks',[]):
        expected += [block['label']]
        if block.get('else_label'):
            expected.append(block['else_label'])
    if b['diagram_type'] in ('architecture','component','deployment'):
        expected += [e['id'] for e in b['edges']]
    if b['diagram_type'] == 'activity':
        expected += [e['label'] for e in b['edges'] if e.get('label')]
    if b['diagram_type'] not in TYPES:
        expected += b['expected_text']
    missing = [s for s in expected if compact(s) not in visible]
    require(not missing, '渲染显示文本失真或缺失: ' + repr(missing))
