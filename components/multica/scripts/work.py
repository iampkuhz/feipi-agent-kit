#!/usr/bin/env python3
"""可选的本机操作回执：使用官方 CLI；不读取运维 Agent 声明或机器映射。"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

from adaptation import STATE, AdaptError, digest, lock, private_write, read_json


TASK_FIELDS = ('MULTICA_TOKEN', 'MULTICA_TASK_ID', 'MULTICA_AGENT_ID',
               'MULTICA_WORKSPACE_ID', 'MULTICA_SERVER_URL')
SCOPE = {}


def task_context():
    return any(os.environ.get(k) for k in TASK_FIELDS[:-1] + ('MULTICA_TASK_CONFIG_ROOT', 'MULTICA_DAEMON_PORT'))


def identity_guard(profile=None, workspace_id=None, server_url=None):
    if not task_context():
        return
    missing = [k for k in TASK_FIELDS if not os.environ.get(k)]
    if missing:
        raise AdaptError('任务身份不完整：' + ', '.join(missing) + '；不回退个人身份。')
    if not os.environ['MULTICA_TOKEN'].startswith('mat_'):
        raise AdaptError('后台必须使用任务凭据。')
    if (profile or (workspace_id and workspace_id != os.environ['MULTICA_WORKSPACE_ID'])
            or (server_url and server_url.rstrip('/') != os.environ['MULTICA_SERVER_URL'].rstrip('/'))):
        raise AdaptError('后台不能切换个人 profile、服务或工作区。')


def cli(*args, with_cursor=False):
    identity_guard()
    binary = os.environ.get('MULTICA_CLI_BIN') or shutil.which('multica')
    if not binary:
        raise AdaptError('找不到官方 multica CLI；加入 PATH 或设置 MULTICA_CLI_BIN。')
    command = [binary]
    for field in ('profile', 'server_url', 'workspace_id'):
        if SCOPE.get(field):
            command += ['--' + field.replace('_', '-'), SCOPE[field]]
    raw = args[:2] == ('config', 'show')
    result = subprocess.run([*command, *map(str, args), *([] if raw else ['--output', 'json'])],
                            capture_output=True, text=True, timeout=90)
    if result.returncode:
        # 不抄未知服务正文；保留可操作的错误类别与步骤。
        error = result.stderr.lower()
        kind, next_step = 'cli', '核对原生命令帮助及服务状态'
        for needle, category, advice in (
                ('unauthorized', 'authentication', '核对所选身份'),
                ('forbidden', 'permission', '核对目标权限'),
                ('unknown flag', 'unsupported', '核对 CLI 版本和子命令帮助'),
                ('unknown command', 'unsupported', '核对 CLI 版本和子命令帮助'),
                ('connection refused', 'connection', '核对服务地址和连通性'),
                ('not found', 'not-found', '核对 UUID 和工作区')):
            if needle in error:
                kind, next_step = category, advice
                break
        raise AdaptError('Multica ' + ' '.join(args[:2]) + ' 失败 [' + kind + ']；' + next_step + '。')
    if raw:
        return result.stdout
    try:
        value = json.loads(result.stdout)
    except ValueError as exc:
        raise AdaptError('CLI 返回非 JSON；请求结果未确认，先查回执。') from exc
    if with_cursor:
        before = re.search(r'--before ("(?:[^"\\]|\\.)*")', result.stderr)
        before_id = re.search(r'--before-id ("(?:[^"\\]|\\.)*")', result.stderr)
        return value, (json.loads(before.group(1)), json.loads(before_id.group(1))) if before and before_id else None
    return value


def scope(args):
    identity_guard(args.profile, args.workspace_id, args.server_url)
    SCOPE.clear()
    SCOPE.update({k: getattr(args, k) for k in ('profile', 'workspace_id', 'server_url') if getattr(args, k)})
    if task_context():
        SCOPE.update(workspace_id=os.environ['MULTICA_WORKSPACE_ID'], server_url=os.environ['MULTICA_SERVER_URL'])
    workspace = cli('workspace', 'get')
    if not workspace.get('id') or (args.workspace_id and workspace['id'] != args.workspace_id):
        raise AdaptError('CLI 工作区与指定工作区不一致。')
    SCOPE['workspace_id'] = workspace['id']
    project = cli('project', 'get', args.project)
    if project.get('id') != args.project or project.get('workspace_id') != workspace['id']:
        raise AdaptError('项目不属于所选工作区。')
    if not SCOPE.get('server_url'):
        text = cli('config', 'show')  # 官方输出不含 token；只保留服务地址。
        match = re.search(r'^server_url:\s+(https?://\S+)\s*$', text, re.MULTILINE)
        if not match:
            raise AdaptError('无法确认服务地址；请显式指定 --server-url。')
        SCOPE['server_url'] = os.environ.get('MULTICA_SERVER_URL') or match.group(1)
    actor = ('agent:' + os.environ['MULTICA_AGENT_ID']) if task_context() else ('user:' + cli('user', 'profile', 'get')['id'])
    return {**SCOPE, 'actor': actor, 'run_id': os.environ.get('MULTICA_TASK_ID') if task_context() else None}


def checked_issue(issue, project):
    value = cli('issue', 'get', issue)
    if value.get('project_id') != project or value.get('workspace_id') != SCOPE['workspace_id']:
        raise AdaptError('Issue 不属于所选项目或工作区；未发送写入。')
    return value


def packet(path):
    value = read_json(path)
    if not isinstance(value, dict):
        raise AdaptError('交接包必须是 JSON 对象。')
    for key in ('objective', 'scope', 'directory', 'acceptance'):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise AdaptError('交接包缺少非空字段：' + key)
    # 旧字段只作为兼容输入；不再用 which() 检查整条验收命令。
    if 'required_commands' in value:
        if 'required_executables' in value:
            raise AdaptError('请只使用 required_executables；不要同时提供旧 required_commands。')
        value['required_executables'] = value.pop('required_commands')
    for key in ('artifacts', 'remaining', 'required_executables', 'validation_commands', 'required_mcp'):
        value.setdefault(key, [])
        if not isinstance(value[key], list) or any(not isinstance(x, str) or not x.strip() for x in value[key]):
            raise AdaptError('交接包字段须为非空字符串数组：' + key)
    if any(re.search(r'\s', x) for x in value['required_executables']):
        raise AdaptError('required_executables 只写可执行文件名；完整命令放 validation_commands。')
    return value


def preflight(issue, target, handoff, allow_current=False):
    agents = cli('agent', 'list')
    matches = [a for a in agents if a.get('id') == target or a.get('name') == target]
    if len(matches) != 1:
        raise AdaptError('目标 Agent 不存在或不唯一；从平台清单选择准确 UUID。')
    agent = cli('agent', 'get', matches[0]['id'])
    if agent.get('workspace_id') != SCOPE['workspace_id'] or agent.get('archived_at'):
        raise AdaptError('Agent 不属于所选工作区或已归档。')
    active = cli('issue', 'runs', issue, '--active')
    if allow_current and task_context():
        active = [r for r in active if r.get('id') != os.environ['MULTICA_TASK_ID'] and r.get('task_id') != os.environ['MULTICA_TASK_ID']]
    if active:
        raise AdaptError('Issue 存在活动 run；先核对接手方式，不能重复派发。')
    resources = cli('project', 'resource', 'list', SCOPE['project_id'])
    local = [r['resource_ref'] for r in resources if r.get('resource_type') == 'local_directory']
    if local:
        runtimes = cli('runtime', 'list')
        runtime = next((r for r in runtimes if r.get('id') == agent.get('runtime_id')), {})
        daemon = runtime.get('daemon_id')
        # 只比较平台已知的执行端路径；不在派发端检查目录、PATH 或 MCP。
        candidates = [r for r in local if r.get('daemon_id') == daemon] if daemon else []
        if candidates and not any(str(PurePosixPath(r.get('local_path', ''))) == str(PurePosixPath(handoff['directory'])) for r in candidates):
            raise AdaptError('交接目录与目标 runtime 的项目目录不一致。')
    return agent


def content_file(text):
    fd, name = tempfile.mkstemp(prefix='.multica-reply-', suffix='.md', dir=Path.cwd())
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(text)
    return Path(name)


def comment(issue, body, parent=None, attachments=()):
    path = content_file(body)
    args = ['issue', 'comment', 'add', issue, '--content-file', str(path)]
    if parent:
        args += ['--parent', parent]
    for attachment in attachments:
        args += ['--attachment', attachment]
    if attachments:
        args += ['--allow-external-file']
    result = cli(*args)
    path.unlink()  # 未知/失败时保留文件，不用清理的成功掩盖写入失败。
    return result


def thread_comments(issue, thread):
    cursor, seen = None, set()
    while True:
        args = ['issue', 'comment', 'list', issue, '--thread', thread, '--tail', '20']
        if cursor:
            args += ['--before', cursor[0], '--before-id', cursor[1]]
        rows, following = cli(*args, with_cursor=True)
        yield from rows
        if not following:
            return
        if following in seen:
            raise AdaptError('评论游标重复，不能确认请求结果。')
        seen.add(following)
        cursor = following


def find_post(issue, parent, marker, comment_id=None):
    roots = [{'id': parent or comment_id}] if parent or comment_id else cli('issue', 'comment', 'list', issue, '--roots-only', '--summary')
    for root in roots:
        if parent or comment_id or marker in root.get('content', ''):
            for row in thread_comments(issue, root['id']):
                if marker in row.get('content', '') and (not comment_id or row['id'] == comment_id):
                    if task_context() and row.get('source_task_id') != os.environ['MULTICA_TASK_ID']:
                        raise AdaptError('发现标记但执行身份不匹配；不能作为当前回执。')
                    return row
    return None


def run(args):
    if args.action not in ('status', 'recover') and not (args.request_id or '').strip():
        raise AdaptError('request-id 不能为空。')
    principal = scope(args)
    SCOPE['project_id'] = args.project
    item = None if args.action == 'record' else checked_issue(args.issue, args.project)
    if item:
        args.issue = item['id']
    rid = getattr(args, 'request_id', None)
    key = digest([principal, rid]) if rid else None
    path = STATE / 'requests' / ('v2-' + key + '.json') if key else None
    marker = 'receipt-key: ' + str(key)
    legacy = STATE / 'requests' / (digest([principal['server_url'], principal['workspace_id'], rid]) + '.json') if rid else None
    if args.action in ('status', 'recover'):
        receipt = (read_json(path) or read_json(legacy)) if path else None
        return {'issue': item, 'runs': cli('issue', 'runs', args.issue, '--active'),
                'threads': cli('issue', 'comment', 'list', args.issue, '--roots-only', '--summary'),
                'receipt': receipt, 'notice': '只读；续接原操作时使用相同内容、身份和 request-id。'}
    body = Path(args.body_file).read_text(encoding='utf-8') if getattr(args, 'body_file', None) else None
    if body is not None and not body.strip():
        raise AdaptError('正文不能为空。')
    handoff = packet(args.packet) if getattr(args, 'packet', None) else None
    artifacts, fingerprints = [], []
    for name in getattr(args, 'artifact', []) or []:
        file = Path(name).expanduser().resolve(strict=True)
        if not file.is_file():
            raise AdaptError('附件不是普通文件。')
        artifacts.append(str(file))
        fingerprints.append([file.name, hashlib.sha256(file.read_bytes()).hexdigest()])
    operation = {k: getattr(args, k, None) for k in ('action', 'project', 'issue', 'parent', 'title', 'owner', 'agent', 'status')}
    operation.update(body=body, handoff=handoff, artifacts=fingerprints)
    if args.action == 'bind':
        directory = Path(args.directory).expanduser().resolve(strict=True)
        if not directory.is_dir() or not args.owner.strip() or not (Path.cwd() == directory or directory in Path.cwd().parents):
            raise AdaptError('bind 仅备注当前实际目录的归属；不注册会话或取得锁。')
        operation['directory'] = str(directory)
    with lock('request-v2-' + key):
        if legacy and legacy.exists():
            raise AdaptError('存在旧版回执；先用 recover 和平台核对，不能自动重发或迁移为成功。')
        old = read_json(path)
        if old and old['fingerprint'] != digest(operation):
            raise AdaptError('request-id 已用于不同输入；请核对原请求。')
        if task_context():
            runs = cli('issue', 'runs', args.issue, '--active')
            current = next((r for r in runs if r.get('id') == os.environ['MULTICA_TASK_ID'] or r.get('task_id') == os.environ['MULTICA_TASK_ID']), None)
            if not current:
                raise AdaptError('找不到当前 Run；不猜线程或回退个人身份。')
            if current.get('trigger_comment_id') and args.parent != current['trigger_comment_id']:
                raise AdaptError('必须回复当前 Run 的 trigger_comment_id。合并多线程请用平台给定的原生回复路径。')
            if args.action in ('record', 'dispatch', 'bind'):
                raise AdaptError('后台只发布当前任务结果或明确 handoff；不建立新的本机执行归属。')
            if not old:
                prior = (thread_comments(args.issue, args.parent) if args.parent else
                         cli('issue', 'comment', 'list', args.issue, '--roots-only', '--summary'))
                if any(c.get('source_task_id') == os.environ['MULTICA_TASK_ID'] for c in prior):
                    raise AdaptError('本 Run 已发布最终评论；先核对原结果，不再另发过程或重复交付评论。')
        agent = None
        if args.action in ('dispatch', 'handoff') and not old:
            agent = preflight(args.issue, args.agent, handoff, args.action == 'handoff')
        if args.action == 'bind' and not old and cli('issue', 'runs', args.issue, '--active'):
            raise AdaptError('已有后台任务，不能备注为当前聊天处理。')
        record = old or {'schema': 2, 'request_id': rid, 'principal': principal, 'operation': operation,
                         'fingerprint': digest(operation), 'state': 'pending', 'steps': {},
                         'initial_status': item.get('status') if item else None,
                         'initial_assignee': item.get('assignee_id') if item else None,
                         'agent': agent, 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        private_write(path, record)

        def step(name, send, reconcile):
            saved = record['steps'].get(name)
            if saved:
                confirmed = reconcile(saved.get('result'))
                if confirmed is not None:
                    saved.update(state='done', result=confirmed)
                    private_write(path, record)
                    return confirmed
                if saved['state'] == 'done' or name in ('comment', 'create'):
                    raise AdaptError(name + ' 远端结果无法确认；保留 pending，不自动重发。')
            record['steps'][name] = {'state': 'pending'}
            private_write(path, record)
            result = send()
            record['steps'][name] = {'state': 'done', 'result': result}
            private_write(path, record)
            return result

        if args.action == 'record':
            def create():
                file = content_file(body + '\n\n' + marker)
                status = ['--status', args.status] if getattr(args, 'status', None) else []
                result = cli('issue', 'create', '--project', args.project, '--title', args.title,
                             *status, '--description-file', str(file))
                file.unlink()
                return result
            result = step('create', create, lambda saved: checked_issue(saved['id'], args.project) if saved else None)
        else:
            agent = record.get('agent')
            if args.action == 'dispatch':
                if item.get('assignee_id') not in (record['initial_assignee'], agent['id']):
                    raise AdaptError('Issue 归属已改变；不覆盖新的分派。')
                step('assign', lambda: cli('issue', 'assign', args.issue, '--to-id', agent['id'], '--no-start'),
                     lambda saved: item if item.get('assignee_id') == agent['id'] else None)
            text = body
            if handoff:
                text = '[@' + agent['name'] + '](mention://agent/' + agent['id'] + ')\n' + marker + '\n' + json.dumps(handoff, ensure_ascii=False, indent=2)
            else:
                if args.action == 'bind':
                    text = '当前交互处理：' + args.owner + '\n目录：' + operation['directory']
                text = '/note\n' + marker + '\nrequest-id: ' + rid + '\n' + (text or '')
            result = step('comment', lambda: comment(args.issue, text, args.parent, artifacts),
                          lambda saved: find_post(args.issue, args.parent, marker, saved.get('id') if saved else None))
            if getattr(args, 'status', None):
                if item.get('status') not in (record['initial_status'], args.status):
                    raise AdaptError('Issue 状态已被其他操作改变；材料已发布，不覆盖新状态。')
                step('status', lambda: cli('issue', 'update', args.issue, '--status', args.status, '--no-start'),
                     lambda saved: item if item.get('status') == args.status else None)
        record.update(state='done', result=result)
        private_write(path, record)
        return {'replayed_receipt': bool(old), 'result': result, 'steps': record['steps'],
                'accepted': False,
                'execution_checks': {'state': 'verify-in-runtime', 'required_executables': handoff['required_executables'],
                                     'required_mcp': handoff['required_mcp']} if handoff else None,
                'notice': '本机操作回执，不证明测试通过、全局只执行一次或任务验收。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('record', 'bind', 'note', 'dispatch', 'deliver', 'handoff', 'status', 'recover'):
        p = sub.add_parser(action)
        p.add_argument('--project', required=True, help='明确的项目 UUID；不需要本机映射')
        p.add_argument('--workspace-id')
        p.add_argument('--profile')
        p.add_argument('--server-url')
        p.add_argument('--request-id', required=action not in ('status', 'recover'))
        p.add_argument('--parent')
        if action == 'record':
            p.add_argument('--title', required=True)
            p.add_argument('--status', help='项目实际的初始状态键；默认沿用原生未分派状态')
        else:
            p.add_argument('issue')
        if action in ('record', 'note', 'deliver'):
            p.add_argument('--body-file', required=True)
        if action in ('dispatch', 'handoff'):
            p.add_argument('--agent', required=True, help='平台 Agent UUID 或唯一精确名称')
            p.add_argument('--packet', required=True)
        if action == 'bind':
            p.add_argument('--directory', required=True)
            p.add_argument('--owner', required=True)
        if action == 'deliver':
            p.add_argument('--artifact', action='append', default=[])
            p.add_argument('--status', help='明确要求改变整单状态时才传；默认只发布材料')
    args = parser.parse_args()
    if args.request_id is not None and not args.request_id.strip():
        parser.error('request-id 不能为空')
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (AdaptError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('任务操作失败：' + str(exc), file=sys.stderr)
        sys.exit(1)
