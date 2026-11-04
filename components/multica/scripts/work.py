#!/usr/bin/env python3
"""任务与结果同步：record、bind、note、dispatch、deliver、handoff、recover。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from adaptation import (ROOT, STATE, AdaptError, cli, digest, expand, lock, machine,
                        private_write, read_json, resolve_runtime, task_context)


def once(request_id, payload, action, before_request=None):
    """先写意图再请求。网络结果不明时保留 pending，绝不自动重放。"""
    if not request_id.strip():
        raise AdaptError('request-id 不能为空。')
    m = machine()
    key = digest([m['server_url'], m['workspace_id'], request_id])
    path = STATE / 'requests' / (key + '.json')
    with lock('request-' + key):
        old = read_json(path)
        if old:
            if old['fingerprint'] != digest(payload):
                raise AdaptError('request-id 已用于不同输入；请核对原请求。')
            if old['state'] == 'done':
                return {'replayed_receipt': True, **old['result']}
            raise AdaptError('请求结果未确认。先 recover 核对服务端；禁止用新 request-id 盲目重试。回执：' + str(path))
        # 只读预检失败没有发送请求，不应留下含义为“远端结果未知”的 pending。
        # 放在同一把锁内，并且在旧回执检查之后，成功的重试仍直接返回原回执。
        if before_request:
            before_request()
        record = {'request_id': request_id, 'fingerprint': digest(payload), 'operation': payload,
                  'state': 'pending', 'time': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        private_write(path, record)
        result = action()
        record.update(state='done', result=result)
        private_write(path, record)
        return result


def comment(issue, body, parent=None, attachments=()):
    command = ['issue', 'comment', 'add', issue, '--content-stdin']
    if parent:
        command += ['--parent', parent]
    for path in attachments:
        command += ['--attachment', path, '--allow-external-file']
    return cli(*command, stdin=body)


def inspect(issue):
    details = cli('issue', 'get', issue)
    refs = {issue, details.get('id')}
    receipts = []
    for path in (STATE / 'requests').glob('*.json'):
        value = read_json(path, {})
        if value.get('operation', {}).get('issue') in refs or value.get('result', {}).get('issue_id') in refs:
            receipts.append({'request_id': value.get('request_id'), 'state': value.get('state'),
                             'operation': value.get('operation', {}).get('action'), 'path': str(path)})
    comments = cli('issue', 'comment', 'list', issue, '--full')
    evidence = [{'id': c['id'], 'parent_id': c.get('parent_id'),
                 'source_task_id': c.get('source_task_id'), 'author_type': c.get('author_type'),
                 'request_ids': re.findall(r'^request-id: (.+)$', c.get('content', ''), re.MULTILINE),
                 'attachments': [{k: a.get(k) for k in ['id', 'filename']} for a in c.get('attachments') or []]}
                for c in comments]
    return {'issue': details, 'runs': cli('issue', 'runs', issue),
            'comments': evidence, 'receipts': receipts}


def packet(path):
    value = read_json(path)
    required = ['objective', 'scope', 'directory', 'acceptance', 'artifacts', 'remaining', 'required_commands', 'required_mcp']
    if not isinstance(value, dict) or any(k not in value for k in required):
        raise AdaptError('交接包缺字段：' + ', '.join(required))
    if not all(isinstance(value[k], str) and value[k].strip()
               for k in ['objective', 'scope', 'directory', 'acceptance']):
        raise AdaptError('目标、范围、目录和验收要求必须为非空字符串。')
    for key in ['artifacts', 'remaining', 'required_commands', 'required_mcp']:
        if not isinstance(value[key], list):
            raise AdaptError('交接包字段必须为数组：' + key)
        if any(not isinstance(item, str) or not item.strip() for item in value[key]):
            raise AdaptError('交接包数组只能包含非空字符串：' + key)
    if not Path(expand(value['directory'])).is_dir():
        raise AdaptError('交接执行目录不存在。')
    return value


def preflight(issue, key, handoff, allow_current=False):
    import shutil
    m = machine()
    if key not in m['agents']:
        raise AdaptError('仅接受机器绑定中的准确 Agent 逻辑键。')
    agent = cli('agent', 'get', m['agents'][key])
    declared = next((item for item in read_json(ROOT / 'config/agents.json')['agents'] if item['key'] == key), None)
    if declared is None:
        raise AdaptError('Agent 不在当前声明管理范围。')
    binding_key = declared['runtime']
    runtime = m['runtimes'].get(binding_key)
    if runtime is None or runtime['id'] != agent['runtime_id']:
        raise AdaptError('Agent runtime 已偏离声明；先检查 multica-ops plan，禁止临时选择其他实例。')
    for field in ['model', 'thinking_level', 'max_concurrent_tasks', 'runtime_config']:
        if field in declared and (agent.get(field) or '') != (declared[field] or ''):
            raise AdaptError('Agent 执行配置已偏离声明：' + field + '；先检查 multica-ops plan。')
    resolve_runtime(runtime, m['daemon_id'], cli('runtime', 'list'))
    active = cli('issue', 'runs', issue, '--active')
    if allow_current and task_context():
        active = [r for r in active if r.get('id') != os.environ.get('MULTICA_TASK_ID') and r.get('task_id') != os.environ.get('MULTICA_TASK_ID')]
    if active:
        raise AdaptError('Issue 存在活动 run；先恢复或等待完成，不能重复派发。')
    issue_data = cli('issue', 'get', issue)
    project_id = issue_data.get('project_id')
    resources = cli('project', 'resource', 'list', project_id) if project_id else []
    target = Path(expand(handoff['directory'])).resolve()
    paths = [r['resource_ref'] for r in resources if r.get('resource_type') == 'local_directory']
    if not any(p.get('daemon_id') == m['daemon_id'] and
               Path(expand(p.get('local_path', ''))).resolve() == target and
               p.get('execution_mode') == 'in_place' for p in paths):
        raise AdaptError('交接目录必须与 Issue 项目在当前 daemon 上的 in_place 资源一致；worktree 使用原生流程并记录真实目录。')
    capabilities = read_json(ROOT / 'config/capabilities.json', {'runtimes': {}})['runtimes'].get(binding_key, {})
    missing = [name for name in set(handoff['required_commands'] + capabilities.get('required_commands', [])) if not shutil.which(name)]
    if missing:
        raise AdaptError('缺少必需命令：' + ', '.join(missing))
    # 声明或宿主机配置不构成任务内 MCP 可用性的证明。
    if handoff['required_mcp'] or capabilities.get('required_mcp'):
        raise AdaptError('此通用入口尚无任务内 MCP 验证器；请先运行专门能力探针，不能凭配置自动派发依赖 MCP 的任务。')
    skills = cli('agent', 'skills', 'list', agent['id'])
    if not any(s.get('id') == m.get('skill_id') for s in skills):
        raise AdaptError('Agent 未绑定共享协作技能；先 multica-ops verify。')
    return agent


def run(args):
    if args.action in {'status', 'recover'}:
        result = inspect(args.issue)
        result['recovery'] = '先检查 run 状态、Issue 评论、附件和已有提交。工具不同则用交接包；同一工具由原生 runtime 处理续接。pending 回执人工核对后保留审计，不自动重放。'
        return result
    body = Path(args.body_file).read_text() if getattr(args, 'body_file', None) else None
    if body is not None and not body.strip():
        raise AdaptError('正文不能为空。')
    data = vars(args).copy()
    data['body'] = body
    if getattr(args, 'packet', None):
        data['handoff'] = packet(args.packet)
    if args.action == 'deliver':
        if not args.artifact:
            raise AdaptError('提交验收必须有可持久保存的附件；测试结果写入正文。')
        data['artifact_hashes'] = {}
        for name in args.artifact:
            p = Path(name).resolve()
            if not p.is_file():
                raise AdaptError('附件不存在：' + str(p))
            import hashlib
            data['artifact_hashes'][str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    prepared = {}
    def before_request():
        if args.action == 'bind':
            if cli('issue', 'runs', args.issue, '--active'):
                raise AdaptError('已有后台任务；先交接或排空后绑定当前聊天。')
            directory = Path(args.directory).expanduser().resolve(strict=True)
            if not directory.is_dir() or not args.owner.strip():
                raise AdaptError('绑定需要实际目录和非空的交互归属。')
            prepared['directory'] = str(directory)
        if args.action in {'dispatch', 'handoff'}:
            if args.action == 'dispatch' and task_context():
                raise AdaptError('后台任务交接请使用 handoff 回复触发评论；dispatch 由本机用户使用。')
            prepared['agent'] = preflight(args.issue, args.agent, data['handoff'], args.action == 'handoff')
    def action():
        marker = '\n\nrequest-id: ' + args.request_id
        if args.action == 'record':
            issue = cli('issue', 'create', '--project', args.project, '--title', args.title,
                        '--status', 'backlog', '--description-stdin', stdin=body + marker)
            return {'issue_id': issue['id'], 'status': 'recorded-without-dispatch'}
        if args.action == 'bind':
            result = comment(args.issue, '/note\n当前交互处理：' + args.owner + '\n目录：' + prepared['directory'] + marker, args.parent)
            return {'comment_id': result['id'], 'status': 'bound-without-dispatch'}
        if args.action == 'note':
            result = comment(args.issue, '/note\n' + body + marker, args.parent)
            return {'comment_id': result['id'], 'status': 'noted-without-dispatch'}
        if args.action in {'dispatch', 'handoff'}:
            handoff = data['handoff']
            agent = prepared['agent']
            context = '交接包（事实和范围；不包含其他工具私有会话）：\n```json\n' + json.dumps(handoff, ensure_ascii=False, indent=2) + '\n```' + marker
            if args.action == 'dispatch':
                if task_context():
                    raise AdaptError('后台任务交接请使用 handoff 回复触发评论；dispatch 由本机用户使用。')
                # Backlog 的 assign 不触发执行；归属静默写入，再用唯一显式 @评论派发。
                # 不使用 rerun：它可能取消已有运行。跨客户端并发仍以服务端合并为准。
                cli('issue', 'assign', args.issue, '--to-id', agent['id'], '--no-start')
                result = comment(args.issue, '[@' + agent['name'] + '](mention://agent/' + agent['id'] + ')\n' + context, args.parent)
                return {'issue_id': args.issue, 'agent_id': agent['id'], 'runtime_id': agent.get('runtime_id'),
                        'model_field': agent.get('model'), 'comment_id': result['id'],
                        'trigger_outcomes': result.get('trigger_outcomes'), 'status': 'dispatch-requested'}
            result = comment(args.issue, '[@' + agent['name'] + '](mention://agent/' + agent['id'] + ')\n' + context, args.parent)
            return {'comment_id': result['id'], 'status': 'handoff-posted', 'trigger_outcomes': result.get('trigger_outcomes')}
        if args.action == 'deliver':
            result = comment(args.issue, '/note\n待验收交付：\n' + body + marker, args.parent,
                             [str(Path(p).resolve()) for p in args.artifact])
            cli('issue', 'update', args.issue, '--status', 'in_review', '--no-start')
            return {'comment_id': result['id'], 'status': 'awaiting-review', 'accepted': False}
        raise AdaptError('未知操作。')
    return once(args.request_id, data, action, before_request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ['record', 'bind', 'note', 'dispatch', 'deliver', 'handoff', 'status', 'recover']:
        p = sub.add_parser(action)
        if action != 'record':
            p.add_argument('issue')
        else:
            p.add_argument('--project', required=True)
            p.add_argument('--title', required=True)
        if action in {'status', 'recover'}:
            continue
        p.add_argument('--request-id', required=True, help='同一次意图固定不变；重试复用，不要每次重新生成')
        p.add_argument('--parent', help='评论触发的任务必须填写原触发评论 ID')
        if action in {'record', 'note', 'deliver'}:
            p.add_argument('--body-file', required=True)
        if action in {'dispatch', 'handoff'}:
            p.add_argument('--agent', required=True)
            p.add_argument('--packet', required=True)
        if action == 'bind':
            p.add_argument('--directory', required=True)
            p.add_argument('--owner', required=True, help='例如 Codex 当前聊天及其可用链接')
        if action == 'deliver':
            p.add_argument('--artifact', action='append', required=True)
    print(json.dumps(run(parser.parse_args()), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (AdaptError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('任务同步失败：' + str(exc), file=sys.stderr)
        sys.exit(1)
