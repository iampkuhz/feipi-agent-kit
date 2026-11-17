#!/usr/bin/env python3
"""将已有组件命令组成显式阶段；只执行用户指定阶段，不替代人工验收。"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
STATE = HOME/'.local/state/feipi-workbench'
BUNDLE = HOME/'feipi-mac-private'
RESTORE = HOME/'feipi-restore'
RECEIPT = STATE/'new-mac-backups.json'
DATA = (
    '.local/env-vault',
    'Documents/life/child-growth-diary', 'Documents/life/家庭健康',
    'Documents/life/2028.装修/home-renovation-playbook-2028',
    'Documents/life/2030.房地产', 'Documents/tools/llm/lexiflow',
    'Documents/tools/llm/feipi-session-browser-java', '.omlx/models',
    'Documents/service-data/litellm/chatgpt-tokens',
)


def run(args, *, capture=False, vault=False, **kwargs):
    # 子进程新安装的 nvm/CLI 不能修改父进程 PATH；每次重新激活，不读启动文件。
    shell = 'set -euo pipefail; source "$1/components/mac/bootstrap/environment.sh"; shift; '
    if vault:
        shell += 'set -a; source "$HOME/.env"; set +a; '
    shell += 'exec "$@"'
    if capture:
        kwargs.update(text=True, stdout=subprocess.PIPE)
    proc = subprocess.run(['/bin/bash', '-c', shell, '--', str(ROOT), *map(str, args)],
                          check=True, **kwargs)
    return proc.stdout.strip() if capture else None


def wb(*args, **kwargs):
    return run([ROOT/'workbench', *args], **kwargs)


def need_file(path):
    if not path.is_file():
        raise ValueError('缺少所需文件：'+str(path))


def vacant(path):
    if path.exists() or path.is_symlink():
        raise ValueError('目标已存在，未合并或覆盖：'+str(path))


def done(check, next_step):
    print('\n本阶段命令完成。人工检查：'+check)
    print('检查符合预期后，下一步：'+next_step)


def software():
    wb('install', 'mac', '--apps', '--agents')
    wb('apply', 'mac')
    run(['/bin/bash', ROOT/'components/mac/bootstrap/neovim.sh'])
    done('新终端能使用 Node/Codex，Neovim 可打开，常用应用可启动。',
         '旧机 export；新机 receive 账号@IP，然后 config。')


def export():
    vacant(BUNDLE)
    wb('private', 'export-mac', BUNDLE)
    wb('private', 'verify-mac', BUNDLE)
    done('小配置包已校验；在 FlClash 界面导出 ~/FlClash-backup.zip。',
         '在新机执行 ./workbench new-mac receive 旧机账号@IP')


def remote(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('连接使用 账号@IPv4 或 账号@主机名；雷雳网桥/Wi-Fi 均可。')
    return value


def remote_exists(host, relative, kind):
    command = 'test -'+kind+' "$HOME"/'+shlex.quote(relative)
    proc = subprocess.run(['ssh', '-n', host, command])
    if proc.returncode not in (0, 1):
        raise subprocess.CalledProcessError(proc.returncode, proc.args)
    return proc.returncode == 0


def receive(host):
    vacant(BUNDLE)
    proxy_backup = remote_exists(host, 'FlClash-backup.zip', 'f')
    if proxy_backup and ((HOME/'FlClash-backup.zip').exists() or (HOME/'FlClash-backup.zip').is_symlink()):
        print('保留本机已存在的 FlClash 备份，本阶段只接收小配置包。')
        proxy_backup = False
    run(['ssh', '-n', host, 'id -un'])
    # 校验完成才发布固定目标；断网留下的本次半包不会挡住下次接收。
    with tempfile.TemporaryDirectory(prefix='.feipi-config-', dir=HOME) as temporary:
        incoming = Path(temporary)
        run(['scp', '-pr', host+':feipi-mac-private', incoming])
        wb('private', 'verify-mac', incoming/'feipi-mac-private')
        if proxy_backup:
            run(['scp', '-p', host+':FlClash-backup.zip', incoming])
        os.rename(incoming/'feipi-mac-private', BUNDLE)
        if proxy_backup:
            os.rename(incoming/'FlClash-backup.zip', HOME/'FlClash-backup.zip')
    done('配置包校验通过；需要时在 FlClash 中导入备份、登录并同步。',
         './workbench new-mac config')


def config():
    wb('private', 'verify-mac', BUNDLE)
    wb('private', 'restore-mac', BUNDLE)
    wb('apply', 'mac')
    wb('apply', 'skills')
    done('新终端正常，代理与原生应用设置正确；账号按原生界面重新登录。',
         './workbench new-mac services')


def services():
    need_file(HOME/'.env')
    wb('service', 'podman', 'ensure')
    wb('install', 'services')
    for component in ('searxng', 'crawl4ai', 'otel'):
        wb('service', component, 'up')
    done('Podman 与搜索/抓取服务可用。LiteLLM 数据库尚未恢复，本阶段不启动它。',
         'copy-data 账号@IP；旧机排空后 backup；新机 receive-backup 账号@IP。')


def copy_data(host):
    run(['ssh', '-n', host, 'id -un'])
    for relative in DATA:
        if not remote_exists(host, relative, 'd'):
            print('旧机没有该可选目录，跳过：'+relative)
            continue
        target = HOME/relative
        target.mkdir(parents=True, exist_ok=True)
        run(['rsync', '-a', '-e', 'ssh', host+':'+shlex.quote(relative+'/'), str(target)+'/'])
    done('所需项目、资料和模型可打开；只直传固定目录，不打包或盘点容量。',
         '安排旧机停写窗口后，在旧机执行 ./workbench new-mac backup')


def new_batch(parent, action):
    before = set(parent.iterdir()) if parent.exists() else set()
    action()
    batches = set(parent.iterdir())-before
    if len(batches) != 1:
        raise ValueError('未唯一识别本次备份批次；保留原始输出，不猜测最新目录。')
    return batches.pop()


def backup():
    # 用户显式执行本阶段后才停 daemon；原生备份继续检查活动任务和一致性。
    wb('service', 'multica', 'stop')
    multica = new_batch(HOME/'.local/state/multica/backups',
                        lambda: wb('private', 'backup', 'multica'))
    openclaw = new_batch(STATE/'openclaw-backups',
                         lambda: wb('private', 'backup', 'openclaw'))
    wb('service', 'podman', 'check')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    litellm = Path(tempfile.mkdtemp(prefix='litellm-backup-', dir=STATE))
    partial = litellm/'database.dump.partial'
    with partial.open('xb') as stream:
        run(['podman', 'exec', 'litellm-db-podman', 'pg_dump', '-Fc', '-U', 'litellm', 'litellm'],
            stdout=stream)
    with partial.open('rb') as stream:
        run(['podman', 'exec', '-i', 'litellm-db-podman', 'pg_restore', '--list'], stdin=stream,
            stdout=subprocess.DEVNULL)
    partial.rename(litellm/'database.dump')
    receipt = {'multica': str(multica), 'openclaw': str(openclaw), 'litellm': str(litellm)}
    fd, temporary = tempfile.mkstemp(prefix='new-mac-backups-', dir=STATE)
    with os.fdopen(fd, 'w') as stream:
        json.dump(receipt, stream)
    os.replace(temporary, RECEIPT)
    done('三项原生备份成功；保持暂停派发，旧机 Multica daemon 已停止。回执仅保存批次路径。',
         '在新机执行 ./workbench new-mac receive-backup 旧机账号@IP')


def receive_backup(host):
    for component in ('multica', 'openclaw', 'litellm'):
        vacant(RESTORE/component)
    with tempfile.TemporaryDirectory(prefix='feipi backup paths ') as temporary:
        receipt = Path(temporary)/'paths.json'
        run(['scp', host+':.local/state/feipi-workbench/new-mac-backups.json', receipt])
        paths = json.loads(receipt.read_text())
    if not isinstance(paths, dict) or set(paths) != {'multica', 'openclaw', 'litellm'}:
        raise ValueError('备份回执必须包含准确的三个组件。')
    for value in paths.values():
        if (not isinstance(value, str) or not PurePosixPath(value).is_absolute()
                or value == '/' or '..' in PurePosixPath(value).parts):
            raise ValueError('备份回执含无效批次路径。')
    RESTORE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='.incoming-', dir=RESTORE) as temporary:
        incoming = Path(temporary)
        for component, source in paths.items():
            destination = incoming/component
            destination.mkdir(mode=0o700)
            run(['rsync', '-a', '-e', 'ssh', host+':'+shlex.quote(source+'/'), str(destination)+'/'])
        for component in paths:
            os.rename(incoming/component, RESTORE/component)
    done('三项备份已直传至 ~/feipi-restore；后续各组件仍执行原生完整性检查。',
         '分别执行 restore litellm、restore openclaw、restore multica；每项完成后人工检查。')


LITELLM_RESTORE = r'''
set -euo pipefail
# shellcheck source=tools/lib/podman.sh
source "$1/tools/lib/podman.sh"
podman_require_runtime
set -a
source "$HOME/.env"
set +a
agent_service_data_root
runtime_tools="$HOME/.local/share/feipi-workbench/services/tools"
dump="$HOME/feipi-restore/litellm/database.dump"
[[ -f "$dump" ]]
if [[ "$(podman inspect litellm-proxy-podman --format '{{.State.Running}}' 2>/dev/null || true)" == true ]]; then
  echo 'LiteLLM 已运行，未恢复数据库。' >&2; exit 1
fi
mkdir -p "$AGENT_SERVICE_DATA_DIR/postgres" "$AGENT_SERVICE_DATA_DIR/litellm/chatgpt-tokens"
podman_compose --env-file /dev/null -f "$runtime_tools/gateway/litellm/compose/docker-compose.yml" up -d postgres
for ((attempt=0; attempt<60; attempt++)); do
  if podman exec litellm-db-podman pg_isready -U litellm -d litellm >/dev/null 2>&1; then break; fi
  sleep 2
done
podman exec litellm-db-podman pg_isready -U litellm -d litellm >/dev/null
tables="$(podman exec litellm-db-podman psql -U litellm -d litellm -Atc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")"
[[ "$tables" == 0 ]] || { echo '目标库已有业务表，未覆盖；不要盲目重跑数据库恢复。' >&2; exit 1; }
podman exec -i litellm-db-podman pg_restore -U litellm -d litellm --exit-on-error < "$dump"
'''


def restore_litellm():
    need_file(RESTORE/'litellm/database.dump')
    need_file(HOME/'.env')
    wb('service', 'podman', 'ensure')
    wb('apply', 'services')
    run(['/bin/bash', '-c', LITELLM_RESTORE, '--', ROOT])
    wb('service', 'litellm', 'up')
    done('LiteLLM readiness 通过后，用原客户端发起一次真实请求并核对原有访问密钥。',
         '其他组件 restore；完成后 startup。')


def restore_openclaw():
    wb('private', 'restore-state', 'openclaw', RESTORE/'openclaw')
    version = json.loads((ROOT/'components/openclaw/versions.json').read_text())['openclaw']
    run(['npm', 'install', '--global', 'openclaw@'+version])
    run(['/bin/bash', ROOT/'components/openclaw/scripts/deploy.sh', '--dependencies-only', '--yes'])
    run(['/bin/bash', ROOT/'components/mac/bootstrap/ohmyzsh.sh', 'install'])
    wb('apply', 'openclaw')
    wb('apply', 'skills')
    done('原有会话/记忆可读取，渠道凭据按需重新授权；Gateway 尚未启动。',
         '完成其他组件恢复，再 startup 和 verify。渠道切换由 Codex 单独引导。')


def restore_multica():
    base = ROOT/'components/multica'
    batch = RESTORE/'multica'
    need_file(batch/'database.dump')
    receipts = batch/'adaptation'
    destination = HOME/'.local/state/multica/adaptation'
    if receipts.is_dir():
        vacant(destination)
    run(['python3', base/'scripts/backup.py', '--verify', batch])
    wb('service', 'podman', 'ensure')
    run(['python3', base/'scripts/install-native.py', 'install'])
    run(['python3', base/'scripts/install-runtime.py'])
    wb('private', 'restore-state', 'multica', batch)
    run(['python3', base/'scripts/configure.py', '--personal-profile'])
    service = HOME/'.local/bin/multica-service'
    if run([service, 'ps', '--status', 'running', '--services', 'backend', 'frontend'], capture=True):
        raise ValueError('Web/API 正在运行；未恢复数据库。')
    run([service, 'pull'])
    run([service, 'up', '-d', '--pull', 'never', 'postgres'])
    ready = [service, 'exec', '-T', 'postgres', 'pg_isready', '-U', 'multica', '-d', 'multica']
    for _ in range(60):
        try:
            run(ready, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            break
        except subprocess.CalledProcessError:
            time.sleep(2)
    run(ready, stdout=subprocess.DEVNULL)
    query = ("SELECT count(*) FROM information_schema.tables "
             "WHERE table_schema='public' AND table_type='BASE TABLE'")
    tables = run([service, 'exec', '-T', 'postgres', 'psql', '-U', 'multica', '-d', 'multica',
                  '-Atc', query], capture=True)
    if tables != '0':
        raise ValueError('目标库已有业务表，未覆盖；不要盲目重跑数据库恢复。')
    with (batch/'database.dump').open('rb') as stream:
        run([service, 'exec', '-T', 'postgres', 'pg_restore', '-U', 'multica', '-d', 'multica',
             '--exit-on-error'], stdin=stream)
    run([service, 'create', '--pull', 'never', 'backend'])
    run([service, 'cp', str(batch/'uploads')+'/.', 'backend:/app/data/uploads/'])
    if receipts.is_dir():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(receipts, destination)
    run([service, 'up', '-d', '--pull', 'never'])
    done('Web 中原有项目/Issue 可见，下载一个历史附件核对；daemon 尚未启动。',
         './workbench new-mac login-multica')


def login_multica():
    binding = HOME/'.config/multica-selfhost/machine.json'
    need_file(binding)
    workspace = json.loads(binding.read_text())['workspace_id']
    run([HOME/'.local/bin/multica-task', 'login'])
    run([HOME/'.local/bin/multica-task', 'workspace', 'switch', workspace])
    done('原生 CLI 已访问准确工作区；daemon 未启动。',
         '确认旧机不再派发，执行 ./workbench new-mac bind-multica。')


def bind_multica():
    run(['python3', ROOT/'components/multica/scripts/install-runtime.py'])
    run(['python3', ROOT/'components/multica/scripts/manage-runtime.py', 'install'])
    run([HOME/'.local/bin/multica-ops', 'rebind', '--local'])
    run([HOME/'.local/bin/multica-ops', 'plan'])
    done('审阅 plan 中受管对象与路径的变化，保留该次 plan_id；此阶段未 apply。',
         './workbench new-mac apply-multica 已审阅的plan_id')


def apply_multica(plan_id):
    if not re.fullmatch(r'[a-f0-9]{64}', plan_id):
        raise ValueError('必须传入已审阅 plan 的完整 SHA-256 摘要。')
    for args in (('apply', '--plan-id', plan_id), ('verify',), ('doctor',)):
        run([HOME/'.local/bin/multica-ops', *args])
    done('本机绑定和声明校验通过；再派发一个真实小任务并下载产物。',
         'startup；完整关机开机后复验同一业务路径。')


def startup():
    need_file(RESTORE/'litellm/database.dump')
    # status/容器存在不足以证明数据库已恢复；不就绪时禁止安装自启以免先建空库。
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            'http://127.0.0.1:4000/health/readiness', timeout=5) as response:
        if response.status != 200:
            raise ValueError('LiteLLM 尚未就绪，请先完成 restore litellm。')
    wb('service', 'startup', 'install')
    wb('service', 'startup', 'check')
    wb('service', 'startup', 'start')
    done('Session Browser 可打开；在 oMLX 原生界面设置登录启动及服务自动启动。',
         '本人完成 CLI 登录/权限后 verify；随后完整关机开机并再次 verify。')


def verify_openclaw():
    validation = STATE/'validation'
    validation.mkdir(parents=True, exist_ok=True, mode=0o700)
    probe = Path(tempfile.mkdtemp(prefix='openclaw-agent-', dir=validation))
    work = probe/'workspace'; work.mkdir()
    state = probe/'state'; state.mkdir()
    marker = 'OPENCLAW_NEW_MAC_NATIVE_OK_7b0d4f92'
    prompt = ('这是一项本地初始化验收。请使用文件写入工具，在当前目录创建 proof.txt，'
              '内容精确为 '+marker+' 并在末尾添加一个换行。不要读取其他文件，'
              '不要发送消息，不要委派任务。完成后只回复 '+marker+'，不附加其他文字。')
    print('OpenClaw 私有验收日志：'+str(probe), flush=True)
    with (probe/'result.json').open('wb') as output, (probe/'request.log').open('wb') as error:
        run(['openclaw', 'agent', 'exec', '--config', HOME/'.openclaw/openclaw.json',
             '--cwd', work, '--state-dir', state, '--timeout', '90', '--json', prompt],
            vault=True, stdout=output, stderr=error, timeout=120)
    result = json.loads((probe/'result.json').read_text())
    proof = work/'proof.txt'
    if (result.get('ok') is not True or result.get('status') != 'ok'
            or result.get('final') != marker or not proof.is_file() or proof.is_symlink()
            or proof.read_bytes() != (marker+'\n').encode()):
        raise ValueError('OpenClaw 原生结果或文件产物不符；保留私有验收日志。')


def verify():
    need_file(HOME/'.env')
    wb('doctor', 'mac')
    run(['/bin/bash', ROOT/'components/mac/bootstrap/check.sh'])
    run(['python3', ROOT/'components/mac/bootstrap/verify-apps.py'])
    run(['python3', ROOT/'components/mac/bootstrap/verify-extras.py'])
    run(['/bin/bash', ROOT/'components/mac/bootstrap/verify-agents.sh'], vault=True)
    verify_openclaw()
    done('本机基础配置、应用和四个 CLI/OpenClaw 的隔离文件任务通过。此结果不代替 Multica 业务切换或渠道验收。',
         '完整关机开机并登录，再执行 verify；Codex 继续核对业务、自启和实际产物。')


def main():
    os.umask(0o077)
    if sys.platform != 'darwin' or os.getuid() == 0 or not HOME.is_absolute() or not HOME.is_dir():
        raise ValueError('请通过 workbench 在 macOS 普通用户账号下执行。')
    if sys.version_info < (3, 10):
        raise ValueError('需要 Python 3.10+；先运行 bash workbench new-mac prepare。')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='stage', required=True)
    simple = {'software': software, 'config': config, 'services': services, 'export': export,
              'backup': backup, 'login-multica': login_multica, 'bind-multica': bind_multica,
              'startup': startup, 'verify': verify}
    for name in simple:
        sub.add_parser(name)
    for name in ('receive', 'copy-data', 'receive-backup'):
        description = '只直传下列固定目录：\n'+'\n'.join(DATA) if name == 'copy-data' else None
        sub.add_parser(name, description=description,
                       formatter_class=argparse.RawDescriptionHelpFormatter).add_argument('remote', type=remote)
    sub.add_parser('restore').add_argument('component', choices=('litellm', 'openclaw', 'multica'))
    sub.add_parser('apply-multica').add_argument('plan_id')
    args = parser.parse_args()
    if args.stage in simple:
        simple[args.stage]()
    elif args.stage == 'apply-multica':
        apply_multica(args.plan_id)
    elif args.stage == 'restore':
        {'litellm': restore_litellm, 'openclaw': restore_openclaw, 'multica': restore_multica}[args.component]()
    else:
        {'receive': receive, 'copy-data': copy_data, 'receive-backup': receive_backup}[args.stage](args.remote)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('本阶段未完成：'+str(error)+'\n已完成内容保留；处理原因后重跑该阶段。数据库部分恢复失败须先核查，不能盲目重复导入。', file=sys.stderr)
        sys.exit(1)
