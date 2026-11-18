#!/usr/bin/env python3
"""期望配置的 plan/apply/verify 与只读 doctor；不维护第二个任务调度器。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

from configure import require_personal_ready

from adaptation import (ROOT, MACHINE, STATE, ACTIVE, AdaptError, agent_runs, cli, digest, expand,
                        file_inventory, lock, machine, private_write, read_json,
                        render, resolve_runtime, task_context)


def catalog():
    return read_json(ROOT / 'config/agents.json')


def skill_body(m, c):
    source = Path(expand(m['agent_kit'])) / c['skill']['path']
    # 当前受管执行链为 Codex。同名 workspace Skill 会遮蔽用户完整包，
    # 生成的单文件入口明确指向已发布资源，不能让后台读研发源码或空相对路径。
    installed = Path.home() / '.codex/skills' / c['skill']['name']
    if installed.is_symlink() or file_inventory(source) != file_inventory(installed):
        raise AdaptError('共享 Skill 尚未完整发布或内容漂移；先 workbench install skills，再 plan。')
    body = (installed / 'SKILL.md').read_text()
    body = re.sub(r'\]\(((?:references|templates)/[^)]+)\)',
                  lambda match: '](<' + str(installed / match.group(1)) + '>)', body)
    header, content = body.split('\n---\n', 1)
    return (header + '\n---\n\n完整资源目录（SKILL_DIR）：`' + str(installed) + '`。'
            '这是本机已发布完整 Skill；本文为工作区单文件入口，脚本、模板与参考以该目录为根，'
            '不要以当前仅有 SKILL.md 的任务目录解析资源。\n' + content)


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


LOCAL_REBIND_SECONDS = 120


def runtime_bindings(m, daemon_id, runtimes):
    if not isinstance(m.get('runtimes'), dict):
        raise AdaptError('机器 runtime 声明无效，未修改绑定。')
    if not isinstance(runtimes, list) or not all(isinstance(row, dict) for row in runtimes):
        raise AdaptError('runtime 列表格式无效，未修改机器绑定。')
    result, pending = {}, []
    for key, old in m['runtimes'].items():
        if not isinstance(old, dict) or not isinstance(old.get('provider'), str) or not old['provider']:
            raise AdaptError('机器 runtime 声明无效，未修改绑定。')
        matches = [r for r in runtimes if r.get('daemon_id') == daemon_id and r.get('provider') == old['provider']
                   and r.get('profile_id') == old.get('profile_id') and r.get('status') == 'online']
        if len(matches) > 1:
            raise AdaptError('新机 runtime 不唯一：'+key+'；未修改机器绑定。')
        if not matches:
            pending.append(key)
        elif not isinstance(matches[0].get('id'), str) or not matches[0]['id']:
            raise AdaptError('线上 runtime 缺少有效 ID，未修改机器绑定。')
        else:
            result[key] = {**old, 'id': matches[0]['id']}
    return result, pending


def save_rebind(m, daemon_id, bindings):
    changed = m.get('daemon_id') != daemon_id or m['runtimes'] != bindings
    if changed:
        m['daemon_id'], m['runtimes'] = daemon_id, bindings
        private_write(MACHINE, m)
    return {'status': 'bound', 'changed': changed, 'next': 'plan；尚未更改服务端 Agent 或项目绑定'}


def rebind(daemon_id):
    """显式选 daemon；不按设备名猜测或复用其他 runtime。"""
    with lock('configuration'):
        m = machine()
        bindings, pending = runtime_bindings(m, daemon_id, cli('runtime', 'list'))
        if pending:
            raise AdaptError('新机 runtime 未上线：'+', '.join(pending))
        return save_rebind(m, daemon_id, bindings)


def local_identity(m, health):
    """只确认本机原生 UUID 与本次固定构建；不创建或复制设备身份。"""
    pinned = read_json(ROOT/'versions.json')
    commit = health.get('cli_commit')
    if (health.get('profile') != m['profile'] or health.get('device_name') != m['device_name']
            or not isinstance(health.get('server_url'), str)
            or health['server_url'].rstrip('/') != m['server_url'].rstrip('/')
            or health.get('os') != sys.platform or health.get('cli_version') != pinned['release'].lstrip('v')
            or not isinstance(commit, str) or len(commit) < 7 or not pinned['upstream_commit'].startswith(commit)):
        raise AdaptError('本机 daemon 的 profile、设备、服务或程序构建不匹配，未修改绑定。')
    record = Path.home()/'.multica/daemon.id'
    if record.is_symlink() or not record.is_file():
        raise AdaptError('缺少本机原生 daemon.id；先由固定 CLI 注册，不复制旧设备身份。')
    identity = record.read_text().strip()
    try:
        uuid.UUID(identity)
    except ValueError as error:
        raise AdaptError('本机原生 daemon.id 格式无效，未修改绑定。') from error
    if health.get('daemon_id') != identity:
        raise AdaptError('运行中的 daemon 与本机原生 UUID 不一致，未修改绑定。')
    return identity


def rebind_local():
    with lock('configuration'):
        require_personal_ready(Path.home())
        m = machine()
        if not isinstance(m.get('runtimes'), dict) or not m['runtimes']:
            raise AdaptError('缺少待重绑 runtime 声明，未修改机器绑定。')
        workspace = cli('workspace', 'get', timeout=15)
        if not isinstance(workspace, dict) or workspace.get('id') != m['workspace_id']:
            raise AdaptError('本机 CLI 工作区与机器绑定不一致，未修改绑定。')
        deadline = time.monotonic()+LOCAL_REBIND_SECONDS
        reason = 'daemon 尚未启动'
        while time.monotonic() < deadline:
            health = cli('daemon', 'status', timeout=min(5, max(0.1, deadline-time.monotonic())))
            if not isinstance(health, dict) or health.get('status') not in ('stopped', 'starting', 'running'):
                raise AdaptError('本机 daemon 状态无效，未修改绑定。')
            if health.get('port_conflict'):
                raise AdaptError('本机 daemon 健康端口存在身份冲突，未修改绑定。')
            reason = 'daemon 尚未就绪'
            if health['status'] == 'running':
                identity = local_identity(m, health)
                if type(health.get('active_task_count')) is not int or health['active_task_count'] < 0:
                    raise AdaptError('本机 daemon 活动任务计数无效，未修改绑定。')
                rows = cli('runtime', 'list', timeout=min(15, max(0.1, deadline-time.monotonic())))
                bindings, pending = runtime_bindings(m, identity, rows)
                workspaces = health.get('workspaces')
                if workspaces is None:
                    workspaces = []
                if not isinstance(workspaces, list) or not all(isinstance(row, dict) for row in workspaces):
                    raise AdaptError('本机 daemon 的工作区注册记录无效，未修改绑定。')
                current = [row for row in workspaces if row.get('id') == m['workspace_id']]
                if len(current) > 1:
                    raise AdaptError('本机 daemon 的工作区注册不唯一，未修改绑定。')
                registered = current[0].get('runtimes', []) if current else []
                if registered is None:
                    registered = []
                if not isinstance(registered, list) or not all(isinstance(item, str) for item in registered):
                    raise AdaptError('本机 daemon 的 runtime 注册记录无效，未修改绑定。')
                complete = not pending and {row['id'] for row in bindings.values()}.issubset(registered)
                if complete and health.get('active_task_count') == 0:
                    return save_rebind(m, identity, bindings)
                reason = 'runtime 注册未齐全或仍有活动任务'
            delay = min(2, max(0, deadline-time.monotonic()))
            if delay:
                time.sleep(delay)
        raise AdaptError('本机 daemon/runtime 在 '+str(LOCAL_REBIND_SECONDS)+' 秒内未就绪（'+reason+'）；未修改绑定。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'apply', 'verify', 'doctor', 'rebind'], nargs='?', default='plan')
    parser.add_argument('--plan-id')
    identity = parser.add_mutually_exclusive_group()
    identity.add_argument('--daemon-id')
    identity.add_argument('--local', action='store_true', help='从本机原生状态核对身份，最多等待 120 秒后重绑')
    args = parser.parse_args()
    if (args.local or args.daemon_id) and args.action != 'rebind':
        parser.error('--local/--daemon-id 只适用于 rebind')
    if task_context():
        raise AdaptError('配置管理仅供本机用户；后台任务使用 multica-work。')
    if args.action == 'apply':
        if not args.plan_id:
            raise AdaptError('apply 需要已审阅 plan 的 --plan-id。')
        result = apply(args.plan_id)
    elif args.action == 'doctor':
        result = doctor()
    elif args.action == 'rebind':
        if not args.daemon_id and not args.local:
            raise AdaptError('rebind 需要 --local 或明确 --daemon-id。')
        result = rebind_local() if args.local else rebind(args.daemon_id)
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
