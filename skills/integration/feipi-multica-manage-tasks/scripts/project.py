#!/usr/bin/env python3
"""查询 Multica 项目与任务，定位并显式启用仓库协作。"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import quote, urlsplit
import uuid


class ContextError(ValueError):
    pass


TASK_FIELDS = ('MULTICA_TOKEN', 'MULTICA_TASK_ID', 'MULTICA_AGENT_ID',
               'MULTICA_WORKSPACE_ID', 'MULTICA_SERVER_URL')
BEGIN, END = '<!-- multica:begin -->', '<!-- multica:end -->'
KEY_LINE = re.compile(r'^Multica 项目键：`([a-z0-9_-]+)`\s*$', re.MULTILINE)


def in_task():
    return any(os.environ.get(k) for k in TASK_FIELDS[:-1] + ('MULTICA_TASK_CONFIG_ROOT', 'MULTICA_DAEMON_PORT'))


def task_identity(profile=None, workspace_id=None, server_url=None):
    if not in_task():
        return
    missing = [k for k in TASK_FIELDS if not os.environ.get(k)]
    if missing:
        raise ContextError('任务身份不完整：' + ', '.join(missing) + '；不回退个人身份。')
    if not os.environ['MULTICA_TOKEN'].startswith('mat_'):
        raise ContextError('任务上下文必须使用任务凭据；不回退个人身份。')
    if (profile or (workspace_id and workspace_id != os.environ['MULTICA_WORKSPACE_ID'])
            or (server_url and server_url.rstrip('/') != os.environ['MULTICA_SERVER_URL'].rstrip('/'))):
        raise ContextError('任务上下文不能切换个人 profile、服务或工作区。')


def machine():
    path = Path(os.environ.get('MULTICA_MACHINE_CONFIG',
                              str(Path.home() / '.config/multica-selfhost/machine.json')))
    value = json.loads(path.read_text())
    if value.get('schema') != 1 or not isinstance(value.get('projects'), dict):
        raise ContextError('机器绑定缺少 schema=1 或 projects；请使用 Multica 运维入口配置。')
    if in_task():
        missing = [k for k in TASK_FIELDS if not os.environ.get(k)]
        if missing:
            raise ContextError('任务身份不完整：' + ', '.join(missing) + '；不回退个人身份。')
        if (os.environ['MULTICA_WORKSPACE_ID'] != value.get('workspace_id') or
                os.environ['MULTICA_SERVER_URL'].rstrip('/') != value.get('server_url', '').rstrip('/')):
            raise ContextError('任务的服务或工作区与本机项目绑定冲突；先修正绑定。')
    for key in ('server_url', 'app_url'):
        url = urlsplit(value.get(key, ''))
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ContextError(key + ' 必须是无凭据、无查询参数的 HTTP(S) 地址。')
    if not value.get('workspace_id') or not value.get('profile'):
        raise ContextError('机器绑定缺少 workspace_id 或 profile。')
    return value


def cli(config, *args):
    task_identity(workspace_id=config.get('workspace_id'), server_url=config.get('server_url'))
    binary = os.environ.get('MULTICA_CLI_BIN') or shutil.which('multica')
    if not binary:
        raise ContextError('找不到官方 multica CLI；请安装并加入 PATH，或设置 MULTICA_CLI_BIN。')
    command = [binary]
    if not in_task() and config.get('profile'):
        command += ['--profile', config['profile']]
    if config.get('server_url'):
        command += ['--server-url', config['server_url']]
    if config.get('_explicit'):
        command += ['--workspace-id', config['workspace_id']]
    return run_json(command, args)


def run_json(command, args, env=None):
    task_identity()
    result = subprocess.run([*command, *map(str, args), '--output', 'json'],
                            capture_output=True, text=True, env=env, timeout=30)
    if result.returncode:
        error = result.stderr.lower()
        kind, advice = 'cli', '核对该子命令帮助和服务状态'
        for patterns, category, next_step in (
                (('unauthorized', 'not signed in', 'not authenticated', 'task token was rejected', '尚未登录', 'task token 已被拒绝'), 'authentication', '核对当前身份；后台不回退个人凭据'),
                (('forbidden', 'not have permission', '无权访问'), 'permission', '核对当前身份对目标项目的权限'),
                (('unknown flag', 'unknown command'), 'unsupported', '核对已安装 CLI 版本和子命令帮助'),
                (('connection refused', 'could not reach', '无法访问 multica'), 'connection', '检查所选服务地址和连通性'),
                (('request conflict', '请求冲突'), 'conflict', '读回目标并核对并发变更'),
                (('no server configured',), 'configuration', '选择已配置的 CLI profile'),
                (('not found', '未找到请求的资源'), 'not-found', '核对目标 UUID 和所属工作区')):
            if any(pattern in error for pattern in patterns):
                kind, advice = category, next_step
                break
        raise ContextError('Multica ' + ' '.join(args[:2]) + ' 失败 [' + kind + ']（退出码 '
                           + str(result.returncode) + '）；' + advice + '。')
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise ContextError('原生 CLI 没有返回有效 JSON。') from exc


def within(path, root):
    return path == root or root in path.parents


def git_paths(directory):
    result = subprocess.run(['git', '-C', str(directory), 'rev-parse', '--show-toplevel', '--git-common-dir'],
                            capture_output=True, text=True, timeout=5)
    if result.returncode:
        return None, None
    top, common = result.stdout.strip().splitlines()
    common = (directory / common).resolve()
    # 仅识别原生 worktree；不能按同名目录或相同 origin 猜测绑定。
    main = common.parent if common.name == '.git' else None
    return Path(top).resolve(), main


def locate(config, directory, key=None):
    current = Path(directory).expanduser().resolve(strict=True)
    if not current.is_dir():
        raise ContextError('当前路径不是目录。')
    top, main = git_paths(current)
    matches = []
    for name, binding in config['projects'].items():
        if key and name != key:
            continue
        for role in ('root', 'release'):
            if not binding.get(role):
                continue
            root = Path(binding[role]).expanduser().resolve()
            if within(current, root):
                if top and within(top, root) and top != root:
                    continue  # 嵌套 Git 仓库须独立绑定，不能借用外层项目。
                matches.append((name, binding, role, root, root))
            elif top and main == root:
                matches.append((name, binding, role + '-worktree', root, top))
    if len(matches) != 1:
        raise ContextError('当前目录没有唯一项目绑定；核对 machine.json 的 projects，歧义时指定 --project 项目键。')
    name, binding, role, root, entry_root = matches[0]
    if not re.fullmatch('[a-z0-9_-]+', name) or not binding.get('id'):
        raise ContextError('项目键或项目 ID 无效。')
    entry = entry_root / 'AGENTS.md'
    content = entry.read_text() if entry.exists() else ''
    keys = KEY_LINE.findall(content)
    if keys and keys != [name]:
        raise ContextError('仓库 AGENTS.md 的项目键与目录绑定不一致或重复。')
    return {'directory': str(current), 'directory_role': role, 'bound_root': str(root),
            'entry_file': str(entry), 'project_key': name, 'project_id': binding['id'],
            'enabled': keys == [name]}


def bound_project(config, directory, key=None):
    value = locate(config, directory, key)
    # 检查当前 CLI 工作区，而非仅证明能够读取另一个指定工作区。
    workspace = cli(config, 'workspace', 'get')
    if workspace.get('id') != config['workspace_id'] or not workspace.get('slug'):
        raise ContextError('CLI 当前工作区与机器绑定不一致；未切换工作区、未发送写入。')
    project = cli(config, 'project', 'get', value['project_id'])
    if project.get('id') != value['project_id'] or project.get('workspace_id') != workspace['id']:
        raise ContextError('服务端项目身份与本机绑定不一致。')
    value.update(workspace_id=workspace['id'], project_title=project.get('title'),
                 workspace_url=config['app_url'].rstrip('/') + '/' + quote(workspace['slug'], safe=''))
    value['project_url'] = value['workspace_url'] + '/projects/' + quote(value['project_id'], safe='')
    if not in_task():
        value['profile'] = config['profile']
    value['notice'] = '项目身份已核实；复用以上 ID/URL，不为定位项目扫描客户端、会话、记忆或凭据目录。主动协作仍须遵守仓库限定的客户端和工作范围。'
    return value, project


def context(config, directory, key=None):
    return bound_project(config, directory, key)[0]


def native_workspace(profile, workspace_id):
    task_identity(profile, workspace_id)
    if in_task():
        workspace_id = os.environ['MULTICA_WORKSPACE_ID']
    binary = os.environ.get('MULTICA_CLI_BIN') or shutil.which('multica')
    if not binary:
        raise ContextError('找不到 multica；安装 CLI 并加入 PATH，或设置现有 MULTICA_CLI_BIN。')
    command = [binary] + (['--profile', profile] if profile else [])
    if workspace_id:
        command += ['--workspace-id', workspace_id]
    workspace = run_json(command, ('workspace', 'get'))
    if not isinstance(workspace, dict) or not workspace.get('id') or (workspace_id and workspace['id'] != workspace_id):
        raise ContextError('无法核实所选工作区的身份。')
    workspace = {k: workspace.get(k) for k in ('id', 'name', 'slug')}
    pinned = [binary] + (['--profile', profile] if profile else []) + ['--workspace-id', workspace['id']]
    return workspace, lambda *args: run_json(pinned, args)


PROJECT_FIELDS = ('id', 'title', 'status', 'lead_id', 'lead_type', 'start_date',
                  'due_date', 'issue_count', 'done_count', 'resource_count', 'updated_at')


def project_summary(item, workspace_id, project_id=None):
    if (not isinstance(item, dict) or not item.get('id') or item.get('workspace_id') != workspace_id
            or (project_id is not None and item['id'] != project_id)):
        raise ContextError('服务端返回的项目身份与请求范围不一致。')
    return {k: item.get(k) for k in PROJECT_FIELDS}


def catalog(workspace, query, status=None):
    args = ('--status', status) if status else ()
    rows = query('project', 'list', *args)
    if not isinstance(rows, list):
        raise ContextError('原生 CLI 没有返回预期的项目清单。')
    return {'workspace': workspace, 'projects': [project_summary(p, workspace['id']) for p in rows]}


def overview(ctx, item, query, limit, offset, status, resources, full_description):
    summary = project_summary(item, ctx['workspace_id'], ctx['project_id'])
    summary['description'], summary['description_truncated'] = clip(
        item.get('description'), sys.maxsize if full_description else 1600)
    if ctx.get('project_url'):
        summary['url'] = ctx['project_url']
    page = issue_page(query, ctx, limit, offset, status)
    result = {'workspace_id': ctx['workspace_id'], 'project': summary,
              'issue_page': {'issues': [issue_summary(ctx, row) for row in page['issues']],
                             'total': page.get('total'), 'offset': offset, 'status_filter': status,
                             'has_more': page['has_more'], 'next_offset': page['next_offset']}}
    if resources:
        rows = query('project', 'resource', 'list', ctx['project_id'])
        if not isinstance(rows, list):
            raise ContextError('原生 CLI 没有返回预期的项目资源清单。')
        result['resources'] = []
        for row in rows:
            if (not isinstance(row, dict) or not row.get('id') or row.get('project_id') != ctx['project_id']
                    or row.get('workspace_id') != ctx['workspace_id']):
                raise ContextError('服务端返回的资源不属于当前项目或工作区。')
            result['resources'].append({k: row.get(k) for k in ('id', 'resource_type', 'label', 'resource_ref')})
    return result


def issue_summary(ctx, issue):
    if (not isinstance(issue, dict) or not issue.get('id') or issue.get('project_id') != ctx['project_id']
            or issue.get('workspace_id') != ctx['workspace_id']):
        raise ContextError('Issue 不属于当前项目或工作区；拒绝关联。')
    result = {k: issue.get(k) for k in ('id', 'identifier', 'title', 'status', 'assignee_id', 'parent_issue_id', 'updated_at')}
    if ctx.get('workspace_url'):
        result['url'] = ctx['workspace_url'] + '/issues/' + quote(issue['id'], safe='')
    return result


def issue_page(query, ctx, limit, offset, status=None):
    fields = 'id,identifier,title,status,assignee_id,parent_issue_id,updated_at,project_id,workspace_id'
    args = ('--status', status) if status else ()
    page = query('issue', 'list', '--project', ctx['project_id'], '--fields', fields,
                 '--limit', limit, '--offset', offset, *args)
    if not isinstance(page, dict) or not isinstance(page.get('issues'), list) or not isinstance(page.get('has_more'), bool):
        raise ContextError('原生 CLI 没有返回完整的 Issue 分页信息。')
    if page['has_more'] and not page['issues']:
        raise ContextError('分页返回空页但仍声明更多数据，不能确认查询完整。')
    return {**page, 'next_offset': offset + len(page['issues']) if page['has_more'] else None}


def find(config, ctx, query, limit, offset):
    page = issue_page(lambda *args: cli(config, *args), ctx, limit, offset)
    rows = page['issues']
    # 不把模糊匹配或一页无结果视为确定不存在；不自动创建或合并 Issue。
    matches = [issue_summary(ctx, item) for item in rows
               if not query or query.casefold() in ((item.get('title') or '') + ' ' + (item.get('identifier') or '')).casefold()]
    return {'project_url': ctx.get('project_url'), 'issues': matches, 'match_scope': 'title-and-identifier',
            'scanned': len(rows), 'offset': offset, 'has_more': page['has_more'],
            'next_offset': page['next_offset'],
            'notice': '标题匹配只用于找候选；分页未读完不能认定不存在，候选需 read 核对范围。'}


def clip(value, limit):
    text = value or ''
    return text[:limit], len(text) > limit


def read(config, ctx, issue, thread=None, limit=5, full_description=False, with_runs=False):
    item = cli(config, 'issue', 'get', issue)
    value = issue_summary(ctx, item)
    value['description'], value['description_truncated'] = clip(item.get('description'),
                                                               sys.maxsize if full_description else 1600)
    if with_runs:
        runs = cli(config, 'issue', 'runs', item['id'], '--active')
        value['active_runs'] = [{k: run.get(k) for k in ('id', 'agent_id', 'status', 'trigger_comment_id', 'started_at')} for run in runs]
    args = ('--thread', thread, '--tail', str(limit)) if thread else ('--roots-only', '--summary')
    comments = cli(config, 'issue', 'comment', 'list', item['id'], *args)
    comments.sort(key=lambda c: (c.get('last_activity_at') or c.get('created_at') or '', c['id']), reverse=True)
    selected = comments  # 根索引保留所有轻量摘要；limit 仅限制展开线程的回复。
    value['comments'] = []
    for c in selected:
        text, truncated = clip(c.get('content'), 1600 if thread else 360)
        value['comments'].append({**{k: c.get(k) for k in ('id', 'parent_id', 'author_type', 'source_task_id',
                                                          'created_at', 'last_activity_at', 'reply_count')},
                                  'content': text, 'content_truncated': truncated or bool(c.get('content_truncated')),
                                  'attachments': [{k: a.get(k) for k in ('id', 'filename')} for a in c.get('attachments') or []]})
    value['comments_mode'] = 'thread-tail' if thread else 'all-root-previews'
    value['comments_may_be_incomplete'] = bool(thread) or any(
        c.get('content_truncated') or c.get('reply_count') for c in value['comments'])
    value['read_more'] = '按评论 ID 使用 read ISSUE --thread ID；完整需求用 --full-description；完整线程/更早评论用原生 CLI 游标。'
    return value


def enable(ctx, apply=False):
    if in_task():
        raise ContextError('后台任务不能修改仓库协作入口。')
    path = Path(ctx['entry_file'])
    if path.is_symlink():
        raise ContextError('AGENTS.md 是符号链接，需在真实规则维护源手工接入。')
    old = path.read_bytes() if path.exists() else b''
    content = old.decode('utf-8')
    if BEGIN in content or END in content:
        if content.count(BEGIN) != 1 or content.count(END) != 1 or content.index(BEGIN) > content.index(END):
            raise ContextError('现有 Multica 入口块不完整，请先核对，未覆盖原文件。')
        if not ctx['enabled']:
            raise ContextError('现有 Multica 入口块缺少有效项目键，请在规则维护源核对。')
        return {'entry_file': str(path), 'changed': False, 'enabled': ctx['enabled']}
    if ctx['enabled']:
        return {'entry_file': str(path), 'changed': False, 'enabled': True}
    block = (BEGIN + '\n## Multica 任务协作\n\nMultica 项目键：`' + ctx['project_key'] + '`\n\n'
             '本项目的实质执行工作使用 feipi-multica-manage-tasks Skill，先解析当前目录与项目，'
             '查询并关联已有 Issue，再在开始、范围或阻塞变化、交付时回写。普通咨询和仅讨论方案不建任务。'
             '当前聊天执行不另派后台；派发须有明确授权。项目自身的验收与 Git 规则继续有效。\n' + END + '\n')
    result = {'entry_file': str(path), 'project_url': ctx['project_url'], 'changed': True,
              'applied': apply, 'append': block}
    if apply:
        backup_root = Path(os.environ.get('MULTICA_ENTRY_BACKUPS',
                                         str(Path.home() / '.local/state/multica/entry-backups')))
        backup_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        backup = backup_root / (str(uuid.uuid4()) + '.md')
        with backup.open('xb') as stream:
            os.chmod(backup, 0o600)
            stream.write(old)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.multica-entry-')
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(old + (b'\n\n' if old else b'') + block.encode('utf-8'))
            os.chmod(tmp, stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644)
            if (path.read_bytes() if path.exists() else b'') != old:
                raise ContextError('AGENTS.md 已被其他操作修改，未覆盖。')
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        result['backup'] = str(backup)
    return result


def full_uuid(value):
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError('需要完整 UUID；先查清单核对目标。') from exc


def project_query(args):
    if args.action == 'overview' and not args.project_id:
        if args.profile or args.workspace_id:
            raise ContextError('按目录查询使用机器绑定；指定 profile 或工作区时须提供项目 UUID。')
        config = machine()
        ctx, item = bound_project(config, args.directory or '.', args.project)
        query = lambda *params: cli(config, *params)
    else:
        if args.action == 'overview' and (args.directory or args.project):
            raise ContextError('项目 UUID 与目录绑定二选一。')
        workspace, query = native_workspace(args.profile, args.workspace_id)
        if args.action == 'projects':
            return catalog(workspace, query, args.status)
        ctx = {'workspace_id': workspace['id'], 'project_id': args.project_id}
        item = query('project', 'get', args.project_id)
    return overview(ctx, item, query, args.limit, args.offset, args.issue_status,
                    args.resources, args.full_description)


def explicit_project(profile, workspace_id, project_id):
    workspace, query = native_workspace(profile, workspace_id)
    item = query('project', 'get', project_id)
    project_summary(item, workspace['id'], project_id)
    config = {'profile': profile, 'workspace_id': workspace['id'], '_explicit': True}
    if in_task():
        config['server_url'] = os.environ['MULTICA_SERVER_URL']
    return config, {'workspace_id': workspace['id'], 'project_id': project_id,
                    'enabled': False, 'source': 'explicit-platform-project'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('context', 'find', 'read', 'enable'):
        p = sub.add_parser(action)
        p.add_argument('--directory', default='.', help='实际工作目录，默认当前目录')
        p.add_argument('--project', help='机器 projects 中的逻辑键；仍核对目录归属')
        if action != 'enable':
            p.add_argument('--project-id', type=full_uuid, help='明确的平台项目 UUID；无需目录映射')
            p.add_argument('--profile', help='已配置的 CLI profile；后台不允许切换')
            p.add_argument('--workspace-id', type=full_uuid, help='明确的工作区 UUID')
        if action == 'find':
            p.add_argument('--query', default='', help='当前页的标题/编号包含匹配，不是语义去重')
            p.add_argument('--limit', type=int, default=50, choices=range(1, 101), metavar='1..100')
            p.add_argument('--offset', type=int, default=0)
        if action == 'read':
            p.add_argument('issue')
            p.add_argument('--thread', help='需要展开的评论线程 ID')
            p.add_argument('--limit', type=int, default=5, choices=range(1, 21), metavar='1..20')
            p.add_argument('--full-description', action='store_true')
            p.add_argument('--runs', action='store_true', help='按需读取活动运行')
        if action == 'enable':
            p.add_argument('--apply', action='store_true', help='默认只预览；显式追加仓库入口，不创建项目或派发任务')
    projects = sub.add_parser('projects', help='查询本机 CLI 工作区的项目清单')
    projects.add_argument('--status', help='项目状态键')
    summary = sub.add_parser('overview', help='按项目 UUID 或当前目录查看项目与一页任务')
    summary.add_argument('project_id', nargs='?', type=full_uuid, metavar='PROJECT_UUID')
    summary.add_argument('--directory', help='目录绑定模式的实际工作目录，默认当前目录')
    summary.add_argument('--project', help='目录绑定模式的机器项目键')
    summary.add_argument('--limit', type=int, default=10, choices=range(1, 51), metavar='1..50')
    summary.add_argument('--offset', type=int, default=0)
    summary.add_argument('--issue-status', help='只过滤当前页的 Issue 查询，不改变项目总计')
    summary.add_argument('--resources', action='store_true', help='按需查看附加资源')
    summary.add_argument('--full-description', action='store_true')
    for p in (projects, summary):
        p.add_argument('--profile', help='本机 CLI profile，省略时沿用原生默认')
        p.add_argument('--workspace-id', type=full_uuid, help='工作区 UUID，省略时核对当前工作区')
    a = parser.parse_args()
    if getattr(a, 'offset', 0) < 0:
        raise ContextError('offset 不能为负。')
    if a.action in ('projects', 'overview'):
        result = project_query(a)
    else:
        if getattr(a, 'project_id', None):
            if a.project:
                raise ContextError('平台项目 UUID 与本机项目键二选一。')
            config, ctx = explicit_project(a.profile, a.workspace_id, a.project_id)
        else:
            if getattr(a, 'profile', None) or getattr(a, 'workspace_id', None):
                raise ContextError('显式 profile/工作区需配合 --project-id，或使用已有目录绑定。')
            config = machine()
            ctx = context(config, a.directory, a.project)
        if a.action == 'context':
            result = ctx
        elif a.action == 'find':
            result = find(config, ctx, a.query, a.limit, a.offset)
        elif a.action == 'read':
            result = read(config, ctx, a.issue, a.thread, a.limit, a.full_description, a.runs)
        else:
            result = enable(ctx, a.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('项目协作失败：' + str(exc), file=sys.stderr)
        sys.exit(1)
