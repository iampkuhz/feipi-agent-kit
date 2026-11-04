#!/usr/bin/env python3
"""期望配置的 plan/apply/verify 与只读 doctor；不维护第二个任务调度器。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

from adaptation import (ROOT, MACHINE, STATE, ACTIVE, AdaptError, agent_runs, cli, digest, expand,
                        file_inventory, lock, machine, private_write, read_json,
                        render, resolve_runtime, task_context)


def catalog():
    return read_json(ROOT / 'config/agents.json')


def skill_body(m, c):
    path = Path(expand(m['agent_kit'])) / c['skill']['path'] / 'SKILL.md'
    return path.read_text()


def evidence_fingerprint(m, c):
    kit = Path(expand(m['agent_kit']))
    evidence = {'machine': m, 'catalog': c, 'capabilities': read_json(ROOT / 'config/capabilities.json'),
                'skills': {p: file_inventory(kit / p) for p in c['skill_checks']},
                'implementation': {p: file_inventory(ROOT / p) for p in ['bin', 'scripts']}}
    if any(a['runtime'] == 'openclaw-isolated' for a in c['agents']):
        evidence['openclaw'] = read_json(Path(expand(m['openclaw_state'])) / 'openclaw.json')
    return digest(evidence)


def desired_agent(item, m):
    text = (ROOT / item['instructions']).read_text().rstrip()
    text += '\n' + (ROOT / 'config/instructions/collaboration.md').read_text()
    desired = {k: item[k] for k in ['name', 'model', 'thinking_level', 'max_concurrent_tasks']}
    desired['instructions'] = render(text, m).rstrip()
    desired['runtime_id'] = m['runtimes'][item['runtime']]['id']
    if 'runtime_config' in item:
        desired['runtime_config'] = item['runtime_config']
    return desired


def normalize(value, field):
    if field == 'instructions':
        return (value or '').rstrip()
    if field in {'thinking_level', 'model'}:
        return value or ''
    return value


def build_plan():
    m, c = machine(), catalog()
    if m.get('role') != 'primary':
        raise AdaptError('临时客户端不应用主力执行配置。')
    ws = cli('workspace', 'get')
    if ws['id'] != m['workspace_id']:
        raise AdaptError('当前 CLI 工作区与机器绑定不一致。')
    runtimes = cli('runtime', 'list')
    for binding in m['runtimes'].values():
        resolve_runtime(binding, m['daemon_id'], runtimes)
    agents = cli('agent', 'list')
    by_id = {a['id']: a for a in agents}
    actions, basis = [], {}
    for item in c['agents']:
        key = item['key']
        aid = m['agents'].get(key)
        desired = desired_agent(item, m)
        if not aid:
            if not item.get('create'):
                raise AdaptError('未显式绑定已有 Agent：' + key)
            if any(a['name'] == item['name'] for a in agents):
                raise AdaptError('发现同名未管理 Agent；先明确绑定，拒绝自动接管：' + key)
            basis[key] = None
            actions.append({'kind': 'agent-create', 'key': key, 'desired': desired})
            continue
        if aid not in by_id:
            raise AdaptError('已绑定 Agent 不存在：' + key)
        current = cli('agent', 'get', aid)
        selected = {k: normalize(current.get(k), k) for k in desired}
        basis[key] = selected
        changed = {k: v for k, v in desired.items() if normalize(v, k) != selected[k]}
        if changed:
            actions.append({'kind': 'agent-update', 'key': key, 'id': aid, 'desired': changed})
    skills = cli('skill', 'list')
    skill_id = m.get('skill_id')
    body = skill_body(m, c)
    if skill_id:
        actual = cli('skill', 'get', skill_id, '--with-content')
        current_body = actual.get('content', '')
        basis['skill'] = {'id': skill_id, 'content_hash': digest(current_body)}
        if current_body.rstrip() != body.rstrip():
            actions.append({'kind': 'skill-update', 'id': skill_id, 'content': body})
    else:
        if any(s['name'] == c['skill']['name'] for s in skills):
            raise AdaptError('同名工作区技能尚未建立管理归属；请绑定 skill_id。')
        basis['skill'] = None
        actions.append({'kind': 'skill-create', 'name': c['skill']['name'], 'content': body})
    for item in c['agents']:
        aid = m['agents'].get(item['key'])
        attached = cli('agent', 'skills', 'list', aid) if aid else []
        enabled = any(s.get('id') == skill_id and s.get('enabled', True) for s in attached) if skill_id else False
        basis['skill:' + item['key']] = enabled
        if not enabled:
            actions.append({'kind': 'skill-attach', 'key': item['key']})
    for key in c['projects']:
        p = m['projects'][key]
        resources = cli('project', 'resource', 'list', p['id'])
        found = [r for r in resources if r['id'] == p['resource_id']]
        if len(found) != 1 or found[0]['resource_type'] != 'local_directory':
            raise AdaptError('项目本地资源绑定不成立：' + key)
        ref = found[0]['resource_ref']
        desired = {'daemon_id': m['daemon_id'], 'local_path': expand(p['root']), 'execution_mode': p['execution_mode']}
        basis['project:' + key] = {k: ref.get(k) for k in desired}
        if basis['project:' + key] != desired:
            if not Path(desired['local_path']).is_dir():
                raise AdaptError('新项目目录不存在：' + key)
            actions.append({'kind': 'project-update', 'key': key, 'desired': desired})
    # 摘要绑定实际输入和读回状态，不把指令正文或私有路径复制进普通输出。
    return {'plan_id': digest({'catalog': c, 'machine': m, 'basis': basis, 'actions': actions}),
            'actions': actions, 'basis': basis}


def public_plan(plan):
    def brief(values):
        return {k: {'sha256': digest(v), 'lines': len((v or '').splitlines())} if k == 'instructions' else v for k, v in (values or {}).items()}
    changes = []
    for a in plan['actions']:
        key = a.get('key', a.get('name', 'collaboration-skill'))
        before = plan['basis'].get(('project:' if a['kind']=='project-update' else '') + key)
        changes.append({'operation': a['kind'], 'target': key, 'fields': sorted(a.get('desired', {})),
                        'before': brief({k: before.get(k) for k in a.get('desired', {})}) if isinstance(before, dict) else before,
                        'after': brief(a.get('desired', {})),
                        **({'content_sha256': digest(a['content'])} if 'content' in a else {})})
    return {'plan_id': plan['plan_id'], 'changes': changes}


def assert_idle(m):
    for aid in m['agents'].values():
        if any(r.get('status') in ACTIVE for r in agent_runs(aid)):
            raise AdaptError('仍有活动任务；排空后再更新配置。')


def apply(expected):
    with lock('configuration'):
        plan = build_plan()
        if expected != plan['plan_id']:
            raise AdaptError('计划已变化；重新 plan 并检查差异。')
        m = machine()
        assert_idle(m)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        private_write(STATE / 'rollback' / (stamp + '.json'), {'machine': m, 'plan': plan})
        for action in plan['actions']:
            kind = action['kind']
            if kind.startswith('agent-'):
                command = ['agent', 'create'] if kind == 'agent-create' else ['agent', 'update', action['id']]
                for key, value in action['desired'].items():
                    command += ['--' + key.replace('_', '-'), json.dumps(value) if isinstance(value, dict) else str(value)]
                if kind == 'agent-create':
                    command += ['--permission-mode', 'private']
                result = cli(*command)
                if kind == 'agent-create':
                    m['agents'][action['key']] = result['id']
                    private_write(MACHINE, m)
            elif kind in {'skill-create', 'skill-update'}:
                command = ['skill', 'create', '--name', action['name']] if kind == 'skill-create' else ['skill', 'update', action['id']]
                result = cli(*command, '--content-stdin', stdin=action['content'])
                if kind == 'skill-create':
                    m['skill_id'] = result['id']
                    private_write(MACHINE, m)
            elif kind == 'skill-attach':
                cli('agent', 'skills', 'add', m['agents'][action['key']], '--skill-ids', m['skill_id'])
            elif kind == 'project-update':
                p = m['projects'][action['key']]
                d = action['desired']
                cli('project', 'resource', 'update', p['id'], p['resource_id'], '--daemon-id', d['daemon_id'], '--local-path', d['local_path'], '--execution-mode', d['execution_mode'])
        after = build_plan()
        if after['actions']:
            raise AdaptError('应用后仍存在差异；保留回退快照，请运行 plan。')
        return {'status': 'verified', 'changes_applied': len(plan['actions']), 'rollback': stamp}


def doctor():
    m, c = machine(), catalog()
    runtimes = {a['runtime'] for a in c['agents']}
    checks = []
    def check(name, ok, detail):
        checks.append({'check': name, 'status': 'pass' if ok else 'blocked', 'detail': detail})
    urls = [('multica-ready', m['server_url'].rstrip('/') + '/readyz')]
    if any(a['key'] == 'litellm-coder' for a in c['agents']):
        urls.append(('litellm-ready', m.get('litellm_readiness_url')))
    for label, url in urls:
        if not url:
            check(label, False, '已启用的执行器缺少服务地址')
            continue
        try:
            with urllib.request.urlopen(url, timeout=4) as response:
                check(label, response.status == 200, '仅验证服务就绪，不代表模型请求通过')
        except Exception as exc:
            check(label, False, type(exc).__name__)
    for key, version in c['compatibility'].items():
        try:
            command = {'qoder': 'qodercli', 'openclaw-isolated': 'multica-openclaw'}.get(key, key)
            command = expand(m.get('commands', {}).get(key, command))
            p = subprocess.run([command, '--version'], text=True, capture_output=True, timeout=15)
            check('version:' + key, p.returncode == 0 and version in p.stdout, '期望 ' + version)
        except (OSError, subprocess.TimeoutExpired):
            check('version:' + key, False, '命令不可用或超时')
    directories = list(dict.fromkeys(str(Path(expand(p)).parent) for p in m.get('commands', {}).values()))
    daemon_path = os.pathsep.join(directories + [str(Path.home()/'.local/bin'), '/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin'])
    for key, name in [('codex','codex'),('qoder','qodercli'),('openclaw','openclaw')]:
        if ('openclaw-isolated' if key == 'openclaw' else key) not in runtimes:
            continue
        declared = m.get('commands', {}).get(key)
        found = shutil.which(name, path=daemon_path)
        check('command-binding:' + key, bool(declared and found) and Path(expand(declared)).resolve() == Path(found).resolve(),
              '机器声明应与 daemon 搜索到的可执行文件一致；同版本也不能代替路径核对')
    native = read_json(Path.home() / '.multica/profiles' / m['profile'] / 'config.json', {})
    check('profile', native.get('server_url') == m['server_url'] and native.get('workspace_id') == m['workspace_id'], '只比较服务与工作区，不输出凭据')
    check('daemon-concurrency', native.get('max_concurrent_tasks') == 1, '试点并发为 1')
    capabilities = read_json(ROOT / 'config/capabilities.json', {'runtimes': {}})
    for key, entry in capabilities['runtimes'].items():
        missing = [name for name in entry['required_commands'] if not shutil.which(name)]
        check('commands:' + key, not missing, {'missing': missing, 'model_selection': entry['model_selection']})
    for relative in c['skill_checks']:
        source = Path(expand(m['agent_kit'])) / relative
        expected = file_inventory(source)
        clients = {'.codex'}
        clients.update(client for runtime, client in [('qoder', '.qoder'), ('openclaw-isolated', '.openclaw')] if runtime in runtimes)
        for client in sorted(clients):
            actual = file_inventory(Path.home() / client / 'skills' / source.name)
            changed = sorted(k for k in set(expected or {}) | set(actual or {}) if (expected or {}).get(k) != (actual or {}).get(k))
            check('skill:' + client + ':' + source.name, bool(expected) and not changed, {'different_files': changed[:12], 'count': len(changed)})
    kit = Path(expand(m['agent_kit']))
    head = subprocess.run(['git', '-C', str(kit), 'rev-parse', 'HEAD'], text=True, capture_output=True)
    checks.append({'check': 'skill-source', 'status': 'recorded', 'detail': {'repository': str(kit), 'head': head.stdout.strip(),
                   'content_sha256': {Path(p).name: digest(file_inventory(kit / p)) for p in c['skill_checks']},
                   'note': '内容摘要包含未提交更改；HEAD 不能单独代表安装内容'}})
    if 'openclaw-isolated' in runtimes:
        isolated = read_json(Path(expand(m.get('openclaw_state', ''))) / 'openclaw.json', {})
        check('openclaw-isolated', bool(m.get('openclaw_state')) and not isolated.get('channels') and isolated.get('plugins', {}).get('slots', {}).get('memory') == 'none', '隔离配置无渠道且关闭 memory 插件；实际 MCP 另由运行验收核对')
    for key, p in m['projects'].items():
        check('project:' + key, Path(expand(p['root'])).is_dir(), '目录存在；项目工程规则由项目维护')
    try:
        plan = build_plan()
        check('desired-state', not plan['actions'], public_plan(plan))
    except AdaptError as exc:
        check('desired-state', False, str(exc))
    receipts = read_json(STATE / 'acceptance.json', {})
    fingerprint = evidence_fingerprint(m, c)
    current = receipts.get('environment_fingerprint') == fingerprint
    checks.append({'check': 'runtime-capabilities', 'status': 'recorded' if current else 'evidence-required',
                   'detail': {'current': current, 'results': receipts.get('summary'), 'scope': '真实模型/任务认证/回写/附件；MCP 实际调用单独标记'} if receipts else '需实际任务验证模型、技能和 MCP；在线及静态配置不替代验收'})
    return {'checks': checks, 'static_ok': all(x['status'] != 'blocked' for x in checks)}


def rebind(daemon_id):
    """新机显式选 daemon；共享 Agent 身份来自恢复的数据，设备身份重新注册。"""
    m, c = machine(), catalog()
    runtimes = cli('runtime', 'list')
    result = {}
    for key, old in m['runtimes'].items():
        matches = [r for r in runtimes if r['daemon_id'] == daemon_id and r['provider'] == old['provider'] and r.get('profile_id') == old.get('profile_id') and r['status'] == 'online']
        if len(matches) != 1:
            raise AdaptError('新机 runtime 不唯一或未上线：' + key)
        result[key] = {**old, 'id': matches[0]['id']}
    m['daemon_id'], m['runtimes'] = daemon_id, result
    private_write(MACHINE, m)
    return {'status': 'bound', 'next': 'plan；尚未更改服务端 Agent 或项目绑定'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'apply', 'verify', 'doctor', 'rebind'], nargs='?', default='plan')
    parser.add_argument('--plan-id')
    parser.add_argument('--daemon-id')
    args = parser.parse_args()
    if task_context():
        raise AdaptError('配置管理仅供本机用户；后台任务使用 multica-work。')
    if args.action == 'apply':
        if not args.plan_id:
            raise AdaptError('apply 需要已审阅 plan 的 --plan-id。')
        result = apply(args.plan_id)
    elif args.action == 'doctor':
        result = doctor()
    elif args.action == 'rebind':
        if not args.daemon_id:
            raise AdaptError('rebind 需要明确 --daemon-id。')
        result = rebind(args.daemon_id)
    else:
        result = public_plan(build_plan())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if (args.action == 'verify' and result['changes']) or (args.action == 'doctor' and not result['static_ok']):
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (AdaptError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('适配检查失败：' + str(exc), file=sys.stderr)
        sys.exit(1)
