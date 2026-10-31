#!/usr/bin/env python3
"""选择性收回 UI 中的 Agent 字段；不回收账号身份、项目路径或私有任务。"""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys

from adaptation import ROOT, STATE, AdaptError, cli, machine, render, private_write, task_context
from adapt import catalog, desired_agent

FIELDS = ('name', 'model', 'thinking_level', 'max_concurrent_tasks', 'instructions')


def unrender_instructions(text, item, m):
    shared = render((ROOT/'config/instructions/collaboration.md').read_text(), m).rstrip()
    if not text.rstrip().endswith(shared):
        raise AdaptError('共享协作约束已改变；先查看私有差异，不自动把共享规则混入单个 Agent。')
    body = text.rstrip()[:-len(shared)].rstrip()
    # 仅恢复原模板中实际使用的占位，不把全量机器信息变成通用替换规则。
    import re
    original = (ROOT/item['instructions']).read_text()
    for key in set(re.findall(r'\$\{([^}]+)\}', original)):
        rendered = render('${'+key+'}', m)
        if rendered != '${'+key+'}' and rendered:
            body = body.replace(rendered, '${'+key+'}')
    return body+'\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--agent', required=True, help='机器已绑定的逻辑键，如 codex-builder')
    p.add_argument('--field', choices=FIELDS, action='append', default=[])
    p.add_argument('--write', action='store_true', help='不加时仅生成私有 diff；确认所选字段后写回源码')
    a = p.parse_args()
    if task_context():
        raise AdaptError('后台任务不能回收个人配置。')
    m, c = machine(), catalog()
    matches = [x for x in c['agents'] if x['key'] == a.agent]
    if len(matches) != 1 or not m['agents'].get(a.agent):
        raise AdaptError('Agent 未明确绑定。')
    item = matches[0]
    actual = cli('agent', 'get', m['agents'][a.agent])
    expected = desired_agent(item, m)
    fields = a.field or [k for k in FIELDS if actual.get(k) != expected.get(k)]
    changes = {k:{'repository':expected.get(k),'live':actual.get(k)} for k in fields if actual.get(k) != expected.get(k)}
    path = STATE/'capture'/('agent-'+a.agent+'.json')
    private_write(path, changes)
    print('差异字段：'+', '.join(changes)+'；私有原文：'+str(path))
    if not a.write:
        print('写回：重复命令并添加 --field 要保留的字段 --write；不修改服务端。')
        return
    if not a.field:
        raise AdaptError('写回必须逐项选择 --field。')
    if not changes:
        print('所选字段已一致。'); return
    body = None
    for field in changes:
        value = actual.get(field)
        if field == 'max_concurrent_tasks' and (not isinstance(value, int) or value < 1):
            raise AdaptError('无效并发配置。')
        if field == 'instructions':
            body = unrender_instructions(value or '', item, m)
        else:
            item[field] = value if value is not None else ''
    # 复用主入口的公开配置检查，防止在 UI 中添加的 token 流回 Git。
    sys.path.insert(0, str(ROOT.parents[1]/'scripts/workbench'))
    from main import check_public
    check_public(ROOT/'config/agents.json', json.dumps(c).encode())
    if body is not None:
        check_public(ROOT/item['instructions'], body.encode())
    batch = STATE/'capture'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    batch.mkdir(parents=True, mode=0o700)
    shutil.copy2(ROOT/'config/agents.json', batch/'agents.json')
    if body is not None:
        shutil.copy2(ROOT/item['instructions'], batch/'instructions.md')
        (ROOT/item['instructions']).write_text(body)
    (ROOT/'config/agents.json').write_text(json.dumps(c, ensure_ascii=False, indent=2)+'\n')
    print('所选字段已回收源码；旧声明：'+str(batch)+'。尚未提交或发布。')


if __name__ == '__main__':
    try:
        main()
    except (AdaptError, OSError, ValueError) as exc:
        print('未完成：'+str(exc), file=sys.stderr)
        sys.exit(1)
