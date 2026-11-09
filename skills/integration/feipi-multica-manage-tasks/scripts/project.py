#!/usr/bin/env python3
"""从当前目录定位 Multica 项目，按需读取任务，显式启用仓库协作。"""
import argparse
import json
import os
from pathlib import Path
import re
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
    return any(os.environ.get(k) for k in TASK_FIELDS[:-1] + ('MULTICA_TASK_CONFIG_ROOT',))


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
    env = dict(os.environ)
    if not in_task():
        env['MULTICA_PERSONAL_PROFILE'] = config['profile']
    command = os.environ.get('MULTICA_TASK_CLI', str(Path.home() / '.local/bin/multica-task'))
    result = subprocess.run([command, *map(str, args), '--output', 'json'],
                            capture_output=True, text=True, env=env, timeout=30)
    if result.returncode:
        # 原始错误可能含服务端正文，不转抄凭据或未知输出。
        raise ContextError('Multica ' + ' '.join(args[:2]) + ' 查询失败（退出码 ' + str(result.returncode) + '）。')
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


def context(config, directory, key=None):
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
    value['notice'] = '项目身份已核实；复用以上 ID/URL，不为定位项目扫描客户端、会话、记忆或凭据目录。主动协作仍须遵守仓库限定的客户端和工作范围。'
    return value


def issue_summary(ctx, issue):
    if issue.get('project_id') != ctx['project_id'] or issue.get('workspace_id') != ctx['workspace_id']:
        raise ContextError('Issue 不属于当前项目或工作区；拒绝关联。')
    result = {k: issue.get(k) for k in ('id', 'identifier', 'title', 'status', 'assignee_id', 'parent_issue_id', 'updated_at')}
    result['url'] = ctx['workspace_url'] + '/issues/' + quote(issue['id'], safe='')
    return result


def find(config, ctx, query, limit, offset):
    fields = 'id,identifier,title,status,assignee_id,parent_issue_id,updated_at,project_id,workspace_id'
    page = cli(config, 'issue', 'list', '--project', ctx['project_id'], '--fields', fields,
               '--limit', limit, '--offset', offset)
    rows = page['issues']
    # 不把模糊匹配或一页无结果视为确定不存在；不自动创建或合并 Issue。
    matches = [issue_summary(ctx, item) for item in rows
               if not query or query.casefold() in ((item.get('title') or '') + ' ' + (item.get('identifier') or '')).casefold()]
    more = bool(page.get('has_more'))
    if more and not rows:
        raise ContextError('分页返回空页但仍声明更多数据，不能确认查询完整。')
    return {'project_url': ctx['project_url'], 'issues': matches, 'match_scope': 'title-and-identifier',
            'scanned': len(rows), 'offset': offset, 'has_more': more,
            'next_offset': offset + len(rows) if more else None,
            'notice': '标题匹配只用于找候选；分页未读完不能认定不存在，候选需 read 核对范围。'}


def clip(value, limit):
    text = value or ''
    return text[:limit], len(text) > limit


def read(config, ctx, issue, thread=None, limit=5, full_description=False):
    item = cli(config, 'issue', 'get', issue)
    value = issue_summary(ctx, item)
    value['description'], value['description_truncated'] = clip(item.get('description'),
                                                               sys.maxsize if full_description else 1600)
    runs = cli(config, 'issue', 'runs', item['id'], '--active')
    value['active_runs'] = [{k: run.get(k) for k in ('id', 'agent_id', 'status', 'trigger_comment_id', 'started_at')} for run in runs]
    args = ('--thread', thread, '--tail', str(limit)) if thread else ('--roots-only', '--summary')
    comments = cli(config, 'issue', 'comment', 'list', item['id'], *args)
    comments.sort(key=lambda c: (c.get('last_activity_at') or c.get('created_at') or '', c['id']), reverse=True)
    selected = comments if thread else comments[:limit]
    value['comments'] = []
    for c in selected:
        text, truncated = clip(c.get('content'), 1600 if thread else 360)
        value['comments'].append({**{k: c.get(k) for k in ('id', 'parent_id', 'author_type', 'source_task_id',
                                                          'created_at', 'last_activity_at', 'reply_count')},
                                  'content': text, 'content_truncated': truncated or bool(c.get('content_truncated')),
                                  'attachments': [{k: a.get(k) for k in ('id', 'filename')} for a in c.get('attachments') or []]})
    value['comments_mode'] = 'thread-tail' if thread else 'root-previews'
    value['comments_may_be_incomplete'] = bool(thread) or len(comments) > limit or any(
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('context', 'find', 'read', 'enable'):
        p = sub.add_parser(action)
        p.add_argument('--directory', default='.', help='实际工作目录，默认当前目录')
        p.add_argument('--project', help='机器 projects 中的逻辑键；仍核对目录归属')
        if action == 'find':
            p.add_argument('--query', default='', help='当前页的标题/编号包含匹配，不是语义去重')
            p.add_argument('--limit', type=int, default=50, choices=range(1, 101), metavar='1..100')
            p.add_argument('--offset', type=int, default=0)
        if action == 'read':
            p.add_argument('issue')
            p.add_argument('--thread', help='需要展开的评论线程 ID')
            p.add_argument('--limit', type=int, default=5, choices=range(1, 21), metavar='1..20')
            p.add_argument('--full-description', action='store_true')
        if action == 'enable':
            p.add_argument('--apply', action='store_true', help='默认只预览；显式追加仓库入口，不创建项目或派发任务')
    a = parser.parse_args()
    if getattr(a, 'offset', 0) < 0:
        raise ContextError('offset 不能为负。')
    config = machine()
    ctx = context(config, a.directory, a.project)
    if a.action == 'context':
        result = ctx
    elif a.action == 'find':
        result = find(config, ctx, a.query, a.limit, a.offset)
    elif a.action == 'read':
        result = read(config, ctx, a.issue, a.thread, a.limit, a.full_description)
    else:
        result = enable(ctx, a.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('项目协作失败：' + str(exc), file=sys.stderr)
        sys.exit(1)
