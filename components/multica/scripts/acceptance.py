#!/usr/bin/env python3
"""独立项目的可重复实机验收；prepare 不派发，start 一次只接受一个角色。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from adaptation import STATE, AdaptError, cli, digest, machine, private_write, read_json
import work

INDEX = STATE / 'acceptance-fixture.json'
PROBE_AGENTS = ('codex-builder', 'litellm-coder', 'qoder-worker')


def active_agents():
    """按当前声明选择代表性验收角色；已声明但未绑定不能伪装成跳过。"""
    import adapt
    m = machine()
    declared = {item['key']: item for item in adapt.catalog()['agents']}
    active = []
    for key in PROBE_AGENTS:
        if key not in declared:
            continue
        runtime = declared[key]['runtime']
        if not m.get('agents', {}).get(key) or runtime not in m.get('runtimes', {}):
            raise AdaptError('已声明的验收角色缺少机器绑定：' + key)
        active.append(key)
    if not active:
        raise AdaptError('当前声明没有可验收的代表角色。')
    return active

PROBE = '''import hashlib,json,os,pathlib,sys
key=sys.argv[1]
assert key in ['codex-builder','litellm-coder','qoder-worker']
keys=['MULTICA_TOKEN','MULTICA_TASK_ID','MULTICA_AGENT_ID','MULTICA_WORKSPACE_ID','MULTICA_SERVER_URL']
report={'agent_key':key,'cwd':str(pathlib.Path.cwd().resolve()),'task_contract':{k:bool(os.getenv(k)) for k in keys},'task_id':os.getenv('MULTICA_TASK_ID'),'agent_id':os.getenv('MULTICA_AGENT_ID'),'workspace_id':os.getenv('MULTICA_WORKSPACE_ID'),'probe_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'token_kind':'task' if os.getenv('MULTICA_TOKEN','').startswith('mat_') else 'invalid','mcp_actual_call':'not-tested','calculation':sum([2,3])}
assert all(report['task_contract'].values()) and report['token_kind']=='task'
assert report['calculation']==5
if key=='litellm-coder':
 p=pathlib.Path(os.environ['OPENCLAW_CONFIG_PATH']); c=json.loads(p.read_text()); report['openclaw']={'channels':sorted(c.get('channels',{})),'mcp_names':sorted(c.get('mcp',{}).get('servers',{})),'selector':c.get('agents',{}).get('entries',{}).get('litellm-coder',{}).get('model'), 'state_dir':os.getenv('OPENCLAW_STATE_DIR')}
pathlib.Path(key+'.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\\n')
print('probe passed: '+key)
'''


def prepare_files(root, keys):
    """仅在验收任务排空后刷新受管探针，已有 fixture 不沿用旧版本脚本。"""
    root.mkdir(parents=True, exist_ok=True)
    (root / 'probe.py').write_text(PROBE)
    (root / 'AGENTS.md').write_text('独立适配验收目录。仅操作本目录和当前 Issue，不操作其他项目。禁止委派、外部通知及读取凭据。验收要求执行 probe.py 并上传报告；不得修改探针或验收标准，工具缺失应真实报告。\n')
    for key in keys:
        body = ('仅执行本目录的适配验收。先读取共享 feipi-multica-manage-tasks 技能及 AGENTS.md，阅读所用原生命令帮助。\n'
                '1. 实际运行 `python3 probe.py '+key+'`；不得修改探针或伪造报告。\n'
                '2. 使用 multica-work note 回写进度，request-id 固定为当前 MULTICA_TASK_ID 加 -note；完全相同的命令重复一次，核对 replayed_receipt=true。\n'
                '3. 将实际执行命令、重试回执与结果写入 '+key+'-result.md。\n'
                '4. 使用 multica-work deliver 上传 '+key+'.json 和结果说明，request-id 固定为当前 MULTICA_TASK_ID 加 -deliver；进入 in_review，不设 Done。\n'
                '评论触发时从本 Issue runs 找到本 MULTICA_TASK_ID 的 trigger_comment_id，note 和 deliver 都传真实 --parent。\n'
                '这次不要求 MCP 调用，报告中保留 not-tested；不推测桌面工具后台可用。禁止委派、外部消息和访问任何凭据。\n')
        (root / (key+'-task.md')).write_text(body)
        handoff = {'objective':body,'scope':'仅当前验收目录与此 Issue；按 AGENTS.md；不委派，不发送外部消息',
                   'directory':str(root),'acceptance':'probe 真实执行；任务身份与评论线程正确；重复 note 仅一次副作用；本次 JSON 可重新下载；in_review',
                   'artifacts':[], 'remaining':['执行本角色验收'], 'required_commands':['python3','multica-work','multica-task'],'required_mcp':[]}
        private_write(root / (key+'-packet.json'), handoff)


def prepare():
    keys = active_agents()
    old = read_json(INDEX)
    if old:
        if not set(keys).issubset(old.get('issues', {})):
            raise AdaptError('当前验收角色未全部准备；核对既有 fixture 和项目绑定后补齐，不重复创建项目。')
        for key in keys:
            if cli('issue', 'runs', old['issues'][key], '--active'):
                raise AdaptError('验收任务仍有活动 run；不能覆盖正在使用的探针。')
        prepare_files(Path(old['root']), keys)
        return old
    m = machine()
    root = Path.home() / '.local/share/multica/acceptance-workspace'
    prepare_files(root, keys)
    projects = cli('project', 'list')
    name = 'Multica 适配验收'
    matches = [p for p in projects if p.get('name', p.get('title')) == name]
    if matches:
        raise AdaptError('存在同名试验项目但本机无回执；请核对后恢复 fixture 绑定，禁止重复创建。')
    project = cli('project', 'create', '--title', name, '--description', '独立环境适配验收；不承载正式业务。')
    fixture = {'project_id':project['id'], 'root':str(root), 'issues':{}}
    private_write(INDEX, fixture)
    resource = cli('project', 'resource', 'add', project['id'], '--type', 'local_directory', '--daemon-id', m['daemon_id'], '--local-path', root, '--execution-mode', 'in_place')
    fixture['resource_id'] = resource['id']
    for key in keys:
        body = root / (key + '-task.md')
        args = type('Args', (), {})()
        args.action='record'; args.project=project['id']; args.title='适配验收：'+key
        args.body_file=str(body);args.request_id='adaptation-v1-record-'+key;args.parent=None
        result = work.run(args)
        fixture['issues'][key] = result['issue_id']
        private_write(INDEX, fixture)
    return fixture


def check():
    import adapt
    keys = active_agents()
    m = machine()
    declared = {item['key']: item for item in adapt.catalog()['agents']}
    fixture = read_json(INDEX)
    if not fixture or not set(keys).issubset(fixture.get('issues', {})):
        raise AdaptError('验收准备未完成；检查 fixture 和已创建的远端对象，不能盲目重跑。')
    results = {}
    for key in keys:
        issue = fixture['issues'][key]
        runs = cli('issue','runs',issue)
        issue_data = cli('issue','get',issue)
        comments = cli('issue','comment','list',issue,'--full')
        report = read_json(Path(fixture['root'])/(key+'.json'),{})
        latest = (runs or [{}])[0]
        expected = {'agent_key': key, 'agent_id': m['agents'][key], 'workspace_id': m['workspace_id'],
                    'runtime_id': m['runtimes'][declared[key]['runtime']]['id'],
                    'cwd': str(Path(fixture['root']).resolve()), 'probe_sha256': hashlib.sha256(PROBE.encode()).hexdigest()}
        current = [c for c in comments if c.get('source_task_id') == latest.get('id')
                   and c.get('author_type') == 'agent' and c.get('author_id') == expected['agent_id']
                   and c.get('parent_id') == latest.get('trigger_comment_id')]
        progress = [c for c in current if ('request-id: '+str(latest.get('id'))+'-note') in c.get('content', '').splitlines()
                    and c.get('content', '').startswith('/note\n')
                    and not c.get('attachments')]
        deliveries = [c for c in current if ('request-id: '+str(latest.get('id'))+'-deliver') in c.get('content', '').splitlines()
                      and c.get('content', '').startswith('/note\n')]
        verified = False
        for comment in deliveries:
            for attachment in comment.get('attachments') or []:
                name = attachment.get('filename', '')
                if name not in [key+'.json', 'workbench-'+str(report.get('task_id'))+'.json']:
                    continue
                destination = STATE/'acceptance-downloads'/attachment['id']
                destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                cli('attachment', 'download', attachment['id'], '--output-dir', destination)
                downloaded = read_json(destination/name, {})
                verified |= bool(report) and downloaded == report
        results[key] = {'issue_id':issue,'runs':[{k:r.get(k) for k in ['id','status','agent_id','runtime_id','workspace_id','work_dir','trigger_comment_id']} for r in runs],
                        'issue_status':issue_data.get('status'),'probe':report,'attachment_verified':verified,
                        'expected': expected, 'progress_verified': len(progress) == 1,
                        'delivery_verified': len(deliveries) == 1,
                        'comment_ids': [c['id'] for c in progress + deliveries],
                        'attachment_count':sum(len(c.get('attachments') or []) for c in comments)}
    return results


def passed(value):
    report = value['probe']
    required = ['MULTICA_TOKEN', 'MULTICA_TASK_ID', 'MULTICA_AGENT_ID', 'MULTICA_WORKSPACE_ID', 'MULTICA_SERVER_URL']
    latest = (value['runs'] or [{}])[0]
    expected = value.get('expected', {})
    return (all(report.get('task_contract', {}).get(k) for k in required)
            and report.get('token_kind') == 'task' and report.get('calculation') == 5
            and value['issue_status'] == 'in_review' and value.get('attachment_verified', False)
            and latest.get('id') == report.get('task_id') and latest.get('status') == 'completed'
            and bool(expected) and value.get('progress_verified', False) and value.get('delivery_verified', False)
            and all(report.get(k) == expected.get(k) for k in ['agent_key','agent_id','workspace_id','cwd','probe_sha256'])
            and all(latest.get(k) == expected.get(k) for k in ['agent_id','runtime_id','workspace_id'])
            and latest.get('work_dir') == expected.get('cwd'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','start','check'])
    p.add_argument('--agent',choices=['codex-builder','litellm-coder','qoder-worker'])
    p.add_argument('--request-id',help='start 必填，同一次派发重试保持不变')
    p.add_argument('--save',action='store_true',help='check 时保存本次环境与逐项结果，不把部分通过写成全通过')
    a=p.parse_args()
    if a.action=='prepare': result=prepare()
    elif a.action=='check':
        result=check()
        if a.save:
            import datetime
            import adapt
            m,c=machine(),adapt.catalog()
            summary={k:{'passed': passed(v), 'issue_id':v['issue_id'],'mcp_actual_call':v['probe'].get('mcp_actual_call','not-tested')} for k,v in result.items()}
            private_write(STATE/'acceptance.json',{'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'environment_fingerprint':adapt.evidence_fingerprint(m,c),'summary':summary,'evidence':result})
    else:
        if not a.agent or not a.request_id: raise AdaptError('start 需要 --agent 和 --request-id')
        if a.agent not in active_agents():
            raise AdaptError('当前声明未启用该验收角色：' + a.agent)
        fixture=read_json(INDEX)
        if not fixture: raise AdaptError('先 prepare')
        args=type('Args',(),{})()
        args.action='dispatch'; args.issue=fixture['issues'][a.agent];args.agent=a.agent
        args.packet=str(Path(fixture['root'])/(a.agent+'-packet.json'));args.request_id=a.request_id;args.parent=None
        result=work.run(args)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if a.action == 'check' and not all(passed(value) for value in result.values()):
        sys.exit(1)

if __name__=='__main__':
    try: main()
    except AdaptError as exc: sys.exit(str(exc))
