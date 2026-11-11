#!/usr/bin/env python3
"""显式运行的真实平台集成：唯一容器/身份/数据，不调用模型或现有业务服务。

需要官方 multica、Podman 及已缓存的组件锁定镜像；不拉取镜像、不读取个人 token。
成功证明原生队列、任务身份、评论、附件和恢复契约，不证明模型遵循指令。
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid


SKILL = Path(__file__).resolve().parents[1]
REPO = SKILL.parents[2]
WORK = REPO / 'components/multica/scripts/work.py'


def checked(command, env=None, cwd=None):
    result = subprocess.run(list(map(str, command)), env=env, cwd=cwd, capture_output=True, text=True, timeout=90)
    if result.returncode:
        # 原始输出可能带临时认证材料，不输出到报告。
        raise RuntimeError('命令失败：' + Path(str(command[0])).name + '（退出码 ' + str(result.returncode) + '）')
    return result.stdout


def request(server, path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(server + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError('平台 HTTP ' + str(exc.code) + '：' + path) from None


def eventually(check, label, seconds=40):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError, RuntimeError):
            pass
        time.sleep(0.4)
    raise RuntimeError('等待超时：' + label)


def smoke(root, server, token, cli, profiles, compat_cli=None, attachment_count=None):
    # 只创建本次 profile；不改 HOME、默认 profile、机器映射或受管声明。
    with tempfile.TemporaryDirectory(prefix='skill-smoke-', dir=profiles) as profile_dir:
        profile = Path(profile_dir).name
        config = Path(profile_dir) / 'config.json'
        config.write_text(json.dumps({'server_url': server, 'token': token}))
        config.chmod(0o600)
        bin_dir = root / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'multica').symlink_to(cli)
        env = {k:v for k,v in os.environ.items() if not k.startswith('MULTICA_')}
        env.update(PATH=str(bin_dir) + os.pathsep + os.defpath,
                   MULTICA_MACHINE_CONFIG=str(root / 'absent-machine.json'),
                   MULTICA_OPS_STATE=str(root / 'receipts'))
        assert not shutil.which('multica-work', path=env['PATH'])
        assert not shutil.which('multica-task', path=env['PATH'])

        def native(*args, workspace=None, raw=False):
            command = [cli, '--profile', profile, '--server-url', server]
            if workspace:
                command += ['--workspace-id', workspace]
            output = checked([*command, *args, *([] if raw else ['--output', 'json'])], env, root)
            return output if raw else json.loads(output)

        ws = native('workspace', 'create', '--name', 'Skill fixture', '--slug', 'skill-' + secrets.token_hex(4))['id']
        config.write_text(json.dumps({'server_url':server, 'token':token, 'workspace_id':ws}))
        other_ws = native('workspace', 'create', '--name', 'Other fixture', '--slug', 'other-' + secrets.token_hex(4))['id']
        project = native('project', 'create', '--title', 'Primary fixture')['id']
        other = native('project', 'create', '--title', 'Other project')['id']
        native('project', 'create', '--title', 'Other workspace project', workspace=other_ws)
        issue = native('issue', 'create', '--project', project, '--title', 'Materials fixture', '--status', 'in_progress')['id']
        body = root / 'body.md'
        body.write_text('本次局部结果；整单仍在进行。\n', encoding='utf-8')
        renamed = root / 'renamed.md'
        renamed.write_bytes(body.read_bytes())

        def helper(action, target=issue, request_id='materials', body_file=body, extra=(), selected=project, identity=None, fail=False):
            command = [sys.executable, WORK, action, target, '--project', selected, '--request-id', request_id]
            if identity is None:
                command += ['--profile', profile, '--workspace-id', ws, '--server-url', server]
            if action in ('deliver', 'note'):
                command += ['--body-file', body_file]
            command += list(extra)
            result = subprocess.run(list(map(str, command)), cwd=root, env=identity or env,
                                    capture_output=True, text=True, timeout=90)
            diagnostic = root/'cli-error.txt'
            detail = diagnostic.read_text().replace(token, '[fixture-user-token]') if diagnostic.exists() else ''
            if identity and identity.get('MULTICA_TOKEN'):
                detail = detail.replace(identity['MULTICA_TOKEN'], '[fixture-task-token]')
            if fail:
                assert result.returncode != 0, '应拒绝的请求被接受'
                return result.stderr + '；' + detail
            if result.returncode:
                raise RuntimeError('回执操作失败：' + action + '；' + result.stderr.strip() + '；' + detail)
            return json.loads(result.stdout)

        # 只有官方 CLI 的明确项目入口；不需要本机部署文件或包装命令。
        print('验证：原生身份、项目、全部线程摘要', flush=True)
        for index in range(12):
            body.write_text('线程 ' + str(index) + '\n' + '独立要求。' * 180)
            native('issue', 'comment', 'add', issue, '--content-file', body)
        read = json.loads(checked([sys.executable, SKILL/'scripts/project.py', 'read', issue,
                                 '--project-id', project, '--profile', profile, '--workspace-id', ws], env, root))
        assert len(read['comments']) == 12 and read['comments_mode'] == 'all-root-previews'
        assert all(c['content_truncated'] for c in read['comments'])
        thread = read['comments'][-1]['id']
        expanded = json.loads(checked([sys.executable, SKILL/'scripts/project.py', 'read', issue,
                                     '--project-id', project, '--profile', profile, '--thread', thread], env, root))
        assert expanded['comments'][0]['id'] == thread and len(expanded['comments'][0]['content']) > 360
        body.write_text(renamed.read_text())
        helper('deliver', selected=other, fail=True)
        wrong_workspace = subprocess.run([sys.executable, str(WORK), 'deliver', issue, '--project',project,
                                         '--profile',profile,'--workspace-id',other_ws,'--server-url',server,
                                         '--body-file',str(body),'--request-id','foreign-workspace'],
                                        env=env,cwd=root,capture_output=True,text=True,timeout=90)
        assert wrong_workspace.returncode != 0
        assert len(native('issue', 'comment', 'list', issue, '--roots-only', '--summary')) == 12
        first = helper('deliver')
        replay = helper('deliver', body_file=renamed)
        assert replay['replayed_receipt'] and first['result']['id'] == replay['result']['id']
        assert native('issue', 'get', issue)['status'] == 'in_progress'
        assert not first['result'].get('attachments')

        # 故障只注入 CLI 传输边界，远端仍是真实 API 和数据库。
        print('验证：评论、附件与分步恢复', flush=True)
        proxy = root / 'cli-proxy'
        proxy.write_text('#!' + sys.executable + '\n' + '''import os, pathlib, subprocess, sys
args = sys.argv[1:]
mode = os.environ.get('FIXTURE_FAIL_STEP', '')
flag = pathlib.Path(os.environ['FIXTURE_FAIL_FLAG'])
selected = ('issue', 'update') if mode == 'status-before' else ('issue', 'comment', 'add')
hit = any(tuple(args[i:i+len(selected)]) == selected for i in range(len(args))) and not flag.exists()
if hit and mode in ('status-before', 'comment-before'):
    flag.touch(); sys.stderr.write('connection refused (fixture)'); sys.exit(1)
result = subprocess.run([os.environ['FIXTURE_REAL_CLI'], *args], capture_output=True)
if result.returncode:
    pathlib.Path(os.environ['FIXTURE_ERROR_FILE']).write_bytes(result.stderr)
if hit and mode == 'comment-after' and result.returncode == 0:
    flag.touch(); sys.stderr.write('connection refused (fixture lost response)'); sys.exit(1)
sys.stdout.buffer.write(result.stdout); sys.stderr.buffer.write(result.stderr); sys.exit(result.returncode)
''')
        proxy.chmod(0o700)
        env.update(MULTICA_CLI_BIN=str(proxy), FIXTURE_REAL_CLI=str(cli), FIXTURE_FAIL_STEP='status-before',
                   FIXTURE_FAIL_FLAG=str(root/'status-failed'), FIXTURE_ERROR_FILE=str(root/'cli-error.txt'))
        artifact = root / 'artifact.json'
        artifact.write_text(json.dumps({'calculation':2+3, 'fixture':True}))
        options = ['--artifact', artifact, '--status', 'in_review']
        failure = helper('deliver', request_id='partial', extra=options, fail=True)
        assert 'issue update' in failure, failure
        comments = native('issue', 'comment', 'list', issue, '--roots-only', '--summary')
        partial = next(c for c in comments if 'request-id: partial' in c['content'])
        assert len(partial['attachments']) == 1 and native('issue', 'get', issue)['status'] == 'in_progress'
        resumed = helper('deliver', request_id='partial', body_file=renamed, extra=options)
        assert resumed['result']['id'] == partial['id'] and native('issue', 'get', issue)['status'] == 'in_review'
        assert len(native('issue', 'comment', 'list', issue, '--roots-only', '--summary')) == 14
        env.update(FIXTURE_FAIL_STEP='comment-after', FIXTURE_FAIL_FLAG=str(root/'comment-lost'))
        helper('deliver', request_id='lost-response', fail=True)
        recovered = helper('deliver', request_id='lost-response', body_file=renamed)
        assert recovered['replayed_receipt']
        env.update(FIXTURE_FAIL_STEP='comment-before', FIXTURE_FAIL_FLAG=str(root/'comment-unknown'))
        helper('deliver', request_id='unknown', fail=True)
        helper('deliver', request_id='unknown', fail=True)
        assert len(native('issue', 'comment', 'list', issue, '--roots-only', '--summary')) == 15
        env.pop('MULTICA_CLI_BIN')

        # 平台真实注册、派发及 claim；不加入本机运维声明，不运行模型。
        print('验证：名单外 Agent 的真实派发与任务身份', flush=True)
        registered = request(server, '/api/daemon/register', {'workspace_id':ws, 'daemon_id':str(uuid.uuid4()),
                             'device_name':'Isolated skill fixture', 'cli_version':'0.6.3',
                             'runtimes':[{'name':'Fixture runtime','type':'codex','version':'fixture','status':'online'}]}, token)
        runtime = registered['runtimes'][0]['id']
        agent = native('agent', 'create', '--name', 'Unmanaged Fixture Worker', '--runtime-id', runtime)['id']
        managed = json.loads((REPO/'components/multica/config/agents.json').read_text())
        assert 'Unmanaged Fixture Worker' not in json.dumps(managed)
        dispatched_issue = native('issue', 'create', '--project', project, '--title', 'Dispatch fixture')['id']
        packet = root / 'handoff.json'
        packet.write_text(json.dumps({'objective':'执行实际计算并发布最终结果', 'scope':'仅当前隔离测试目录和 Issue',
                          'directory':str(root), 'acceptance':'计算为 5，任务身份、parent 和附件正确',
                          'required_executables':['python3','multica'], 'validation_commands':['python3 probe.py'],
                          'required_mcp':['fixture-unverified']}))
        dispatch = helper('dispatch', target=dispatched_issue, request_id='dispatch',
                          extra=['--agent',agent,'--packet',packet])
        assert any(t.get('status') == 'queued' for t in dispatch['result'].get('trigger_outcomes', []))
        again = helper('dispatch', target=dispatched_issue, request_id='dispatch', extra=['--agent',agent,'--packet',packet])
        assert again['replayed_receipt'] and again['result']['id'] == dispatch['result']['id']
        runs = native('issue', 'runs', dispatched_issue, '--active')
        assert len(runs) == 1 and runs[0]['agent_id'] == agent
        claim = request(server, '/api/daemon/runtimes/' + runtime + '/tasks/claim', {}, token)['task']
        assert claim['id'] == runs[0]['id'] and claim['auth_token'].startswith('mat_')
        request(server, '/api/daemon/tasks/' + claim['id'] + '/start', {}, token)
        task_root = root/'task-config'
        task_root.mkdir()
        task_env = dict(env, MULTICA_CLI_BIN=str(proxy), FIXTURE_FAIL_STEP='',
                        MULTICA_TOKEN=claim['auth_token'], MULTICA_TASK_ID=claim['id'], MULTICA_AGENT_ID=agent,
                        MULTICA_WORKSPACE_ID=ws, MULTICA_SERVER_URL=server, MULTICA_TASK_CONFIG_ROOT=str(task_root))
        parent = runs[0]['trigger_comment_id']
        assert parent == dispatch['result']['id']
        for missing in ('MULTICA_TOKEN','MULTICA_TASK_ID','MULTICA_AGENT_ID','MULTICA_WORKSPACE_ID','MULTICA_SERVER_URL'):
            incomplete = dict(task_env)
            incomplete.pop(missing)
            error = helper('deliver', target=dispatched_issue, identity=incomplete, request_id='final',
                           extra=['--parent',parent], fail=True)
            assert '身份不完整' in error
        helper('deliver', target=dispatched_issue, identity=task_env, request_id='final', fail=True)
        checked([sys.executable, '-c', 'import json,os,pathlib; pathlib.Path("probe.json").write_text(json.dumps({"calculation":2+3,"task_id":os.environ["MULTICA_TASK_ID"],"cwd":str(pathlib.Path.cwd())}))'], task_env, root)
        final_options = ['--parent',parent,'--artifact',root/'probe.json','--status','in_review']
        final = helper('deliver', target=dispatched_issue, identity=task_env, request_id='final', extra=final_options)
        repeat = helper('deliver', target=dispatched_issue, identity=task_env, request_id='final', body_file=renamed, extra=final_options)
        assert repeat['result']['id'] == final['result']['id']
        helper('deliver', target=dispatched_issue, identity=task_env, request_id='another-final', extra=final_options, fail=True)
        thread = native('issue', 'comment', 'list', dispatched_issue, '--thread', parent, '--tail', '20')
        finals = [c for c in thread if c.get('source_task_id') == claim['id']]
        assert len(finals) == 1 and finals[0]['parent_id'] == parent and finals[0]['author_id'] == agent
        download = root/'download'
        download.mkdir()
        native('attachment','download',finals[0]['attachments'][0]['id'],'--output-dir',download,raw=True)
        assert (download/'probe.json').read_bytes() == (root/'probe.json').read_bytes()
        request(server, '/api/daemon/tasks/' + claim['id'] + '/complete', {'output':'fixture completed'}, token)
        assert native('issue','runs',dispatched_issue)[0]['status'] == 'completed'
        compatibility = None
        if compat_cli:
            print('验证：当前 CLI 与锁定 API 的兼容性及失败后防重发', flush=True)
            compat_issue = native('issue','create','--project',project,'--title','CLI compatibility','--status','in_progress')['id']
            env.update(MULTICA_CLI_BIN=str(proxy), FIXTURE_REAL_CLI=str(compat_cli), FIXTURE_FAIL_STEP='')
            helper('deliver',target=compat_issue,request_id='compat-materials')
            before = attachment_count()
            error = helper('deliver',target=compat_issue,request_id='compat-attachment',extra=['--artifact',artifact],fail=True)
            assert '[conflict]' in error, error
            uploaded = attachment_count()
            assert uploaded == before + 1
            helper('deliver',target=compat_issue,request_id='compat-attachment',extra=['--artifact',artifact],fail=True)
            assert attachment_count() == uploaded
            assert len(native('issue','comment','list',compat_issue,'--roots-only','--summary')) == 1
            receipt = helper('recover',target=compat_issue,request_id='compat-attachment')['receipt']
            assert receipt['steps']['comment']['state'] == 'pending'
            compatibility = {'cli':checked([compat_cli,'version']).splitlines()[0],
                             'plain_materials':'passed', 'attachment':'conflict-unbound-upload',
                             'receipt':'pending', 'retry_created_another_upload':False}
        return {'official_cli_only':True, 'all_root_previews':12, 'foreign_scope_refused':True,
                'materials_without_state_or_attachment':True, 'body_path_replay':True,
                'partial_resume_without_duplicate_upload':True, 'lost_response_reconciled':True,
                'unknown_result_not_resent':True, 'unmanaged_agent_dispatched_and_claimed':True,
                'missing_task_identity_refused':5, 'one_task_final_correct_parent':True,
                'download_matches_current_probe':True, 'model_execution':'not-tested',
                'mcp_execution':'not-tested', 'mixed_version_probe':compatibility}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--cli', type=Path, help='本次隔离测试使用的官方 CLI；不替换全局命令')
    parser.add_argument('--compat-cli', type=Path, help='额外复现新版 CLI 对旧 API 的附件冲突与安全恢复')
    args = parser.parse_args()
    cli = str(args.cli) if args.cli else shutil.which('multica')
    if not cli or not shutil.which('podman'):
        parser.error('需要官方 multica 与已启动的 Podman；本脚本不安装依赖或改服务')
    cli = str(Path(cli).expanduser().resolve())
    compat_cli = args.compat_cli.expanduser().resolve() if args.compat_cli else None
    version = checked([cli,'version']).splitlines()[0]
    pinned = (REPO/'components/multica/config/compose.pinned.yml').read_text()
    images = re.findall(r'^    image: (\S+)', pinned, re.MULTILINE)
    for image in images[:2]:
        checked(['podman','image','exists',image])
    namespace = 'multica-skill-' + secrets.token_hex(5)
    db, api = namespace+'-db', namespace+'-api'
    profiles = Path.home()/'.multica/profiles'
    profiles.mkdir(parents=True, exist_ok=True)
    network_created, containers = False, []
    try:
        checked(['podman','network','create',namespace])
        network_created = True
        env = dict(os.environ, POSTGRES_USER='fixture', POSTGRES_DB='fixture', POSTGRES_PASSWORD=secrets.token_hex(24))
        checked(['podman','run','--pull=never','-d','--name',db,'--network',namespace,
                 '-e','POSTGRES_USER','-e','POSTGRES_DB','-e','POSTGRES_PASSWORD',images[0]],env)
        containers.append(db)
        eventually(lambda: subprocess.run(['podman','exec',db,'pg_isready','-U','fixture'],capture_output=True).returncode == 0, '隔离数据库')
        code = str(secrets.randbelow(900000)+100000)
        env.update(DATABASE_URL='postgres://fixture:'+env['POSTGRES_PASSWORD']+'@'+db+':5432/fixture?sslmode=disable',
                   JWT_SECRET=secrets.token_hex(32), MULTICA_VCS_SECRET_KEY=secrets.token_hex(32),
                   APP_ENV='development', ALLOW_SIGNUP='true', DO_NOT_TRACK='1', MULTICA_DEV_VERIFICATION_CODE=code)
        keys = ('DATABASE_URL','JWT_SECRET','MULTICA_VCS_SECRET_KEY','APP_ENV','ALLOW_SIGNUP','DO_NOT_TRACK','MULTICA_DEV_VERIFICATION_CODE')
        checked(['podman','run','--pull=never','-d','--name',api,'--network',namespace,'-p','127.0.0.1::8080',
                 *[item for key in keys for item in ('-e',key)],images[1]],env)
        containers.append(api)
        port = checked(['podman','port',api,'8080/tcp']).strip().rsplit(':',1)[-1]
        server = 'http://127.0.0.1:'+port
        eventually(lambda: request(server,'/health'), '隔离 API')
        email = namespace+'@example.invalid'
        request(server,'/auth/send-code',{'email':email})
        auth = request(server,'/auth/verify-code',{'email':email,'code':code})
        token = auth.get('token') or auth['access_token']
        with tempfile.TemporaryDirectory(prefix=namespace+'-') as temp:
            def attachment_count():
                return int(checked(['podman','exec',db,'psql','-U','fixture','-d','fixture','-At','-c','SELECT count(*) FROM attachment;']).strip())
            report = smoke(Path(temp).resolve(),server,token,cli,profiles,compat_cli,attachment_count)
        report.update(platform='isolated pinned Multica 0.6.3', cli=version, cleaned=True)
    except Exception:
        if api in containers:
            log = subprocess.run(['podman','logs',api],capture_output=True,text=True,timeout=15)
            for line in (log.stdout + log.stderr).splitlines():
                if 'failed to create attachment record' in line:
                    # 仅输出本次附件数据库错误；排除验证码等无关服务日志。
                    for key in ('POSTGRES_PASSWORD','JWT_SECRET','MULTICA_VCS_SECRET_KEY','MULTICA_DEV_VERIFICATION_CODE'):
                        line = line.replace(env.get(key, '[absent]'), '[redacted]')
                    print('隔离 API 附件错误：' + line, file=sys.stderr)
            rows = checked(['podman','exec',db,'psql','-U','fixture','-d','fixture','-At','-c',
                            "SELECT json_build_object('id',id,'workspace_id',workspace_id,'issue_id',issue_id,'comment_id',comment_id,'source_context_id',source_context_id) FROM attachment;"])
            print('隔离附件关联记录：' + rows.strip(), file=sys.stderr)
        raise
    finally:
        for container in reversed(containers):
            checked(['podman','rm','-f','-v',container])
        if network_created:
            checked(['podman','network','rm',namespace])
    output = json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
