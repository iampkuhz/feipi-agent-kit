#!/usr/bin/env python3
"""个人工作台：固定组件、明确方向、复用组件原有能力。"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
# 工作台与脱离源码运行的自启脚本共用同一就绪合同。
sys.path.insert(0, str(ROOT/'tools/runtime'))
sys.path.insert(0, str(ROOT/'scripts/harness'))
from validate_registry import parse_registry
from service_health import wait_service
from rollback import rollback_on_failure
from agent_config import (MODES, current_project, initialize_project, installation_lock,
                          profile_mappings, profile_receipt, profile_updates, session_brief, write_atomic)

HOME = Path.home()
STATE = HOME / '.local/state/feipi-workbench'
RUNTIME = HOME / '.local/share/feipi-workbench'
ENV_HISTORY_LABEL = 'com.feipi.env-history'
COMPONENTS = ('mac', 'skills', 'services', 'openclaw', 'openclash', 'codex')
SERVICE_SCRIPTS = {'litellm': 'gateway/litellm/scripts/litellm.sh',
                   'searxng': 'search/searxng/scripts/searxng.sh',
                   'crawl4ai': 'crawl/crawl4ai/scripts/crawl4ai.sh',
                   'diagrams': 'diagram/diagrams.sh',
                   'fastmcp': 'gateway/fastmcp/scripts/fastmcp.sh',
                   'otel': 'gateway/otel/scripts/otel.sh'}
SERVICE_ACTIONS = {name: ('up', 'down', 'restart', 'status', 'logs') for name in SERVICE_SCRIPTS}
SERVICE_ACTIONS['omlx'] = ('up', 'down', 'restart', 'status', 'logs')
SERVICE_ACTIONS['openclaw'] = ('up', 'down', 'restart', 'status', 'logs')
SERVICE_ACTIONS['podman'] = ('check', 'ensure')
SERVICE_ACTIONS['startup'] = ('install', 'start', 'check')


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def private_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + '.new')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.chmod(0o600)
    os.replace(temp, path)


def source_files(directory):
    """沿用 Git 忽略规则，包括用户尚未提交的源码，排除缓存与私有目录。"""
    data = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--cached',
                                    '--others', '--exclude-standard', '-z', '--', str(directory.relative_to(ROOT))])
    return sorted({ROOT / name for name in data.decode().split('\0') if name and (ROOT/name).is_file()})


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def mappings(component):
    """列出用于配置发布或状态比较的仓库文件与运行目标。"""
    result = {}
    base = ROOT / 'components' / component
    if component == 'codex':
        return profile_mappings(ROOT, codex_home())
    if component == 'mac':
        result['zsh/.zshrc'] = (base/'zsh/.zshrc', HOME/'.zshrc')
        for package, directory in [('zsh', '.zsh_config'), ('neovim', '.config'), ('qwen', '.qwen')]:
            for src in source_files(base/package/directory):
                relative = src.relative_to(base/package)
                if any(part == '.env' or part.startswith('.env.') for part in relative.parts):
                    continue
                if not src.resolve().is_relative_to((base/package).resolve()):
                    raise ValueError('dotfile 来源越过包目录：' + str(src))
                result[str(src.relative_to(base))] = (src, HOME/relative)
        for relative, target in [
            ('desktop/karabiner/karabiner.json', '.config/karabiner/karabiner.json'),
            ('desktop/iterm2/profile.json', 'Library/Application Support/iTerm2/DynamicProfiles/dotfiles.json')]:
            result[relative] = (base/relative, HOME/target)
    elif component == 'openclaw':
        for rel in ['openclaw.json', 'scripts/transcribe-audio-omlx.sh']:
            result[rel] = (base/rel, HOME/'.openclaw'/rel)
        manifest = json.loads((base/'templates/workspace/manifest.json').read_text())
        for rel in manifest['files']:
            if Path(rel).is_absolute() or '..' in Path(rel).parts:
                raise ValueError('workspace manifest 路径越界')
            result['templates/workspace/'+rel] = (base/'templates/workspace'/rel, HOME/'.openclaw/workspace'/rel)
    elif component == 'services':
        for src in source_files(ROOT/'tools'):
            if any(x in src.parts for x in ['config', 'settings', 'compose']):
                rel = str(src.relative_to(ROOT))
                result[rel] = (src, RUNTIME/'services'/rel)
        for src in source_files(ROOT/'runtimes/fastmcp'):
            if src.suffix == '.py' or src.name in ('Containerfile', 'pyproject.toml'):
                rel = str(src.relative_to(ROOT))
                result[rel] = (src, RUNTIME/'services'/rel)
    elif component == 'skills':
        skill_names = {ROOT / entry['path']: entry['name'] for entry in parse_registry(ROOT)}
        clients = {client: HOME/('.'+client)/'skills'
                   for client in ('codex', 'cursor', 'claude', 'qwen', 'qoder', 'openclaw')
                   if (HOME/('.'+client)).is_dir()}
        for src in source_files(ROOT/'skills'):
            directory = next((parent for parent in src.parents if parent in skill_names), None)
            if directory is None:
                continue
            relative = src.relative_to(directory)
            if any(part in ('maintenance', 'tests', 'evals', 'node_modules', '__pycache__')
                   for part in relative.parts) or relative.suffix == '.pyc':
                continue
            name = skill_names[directory]
            for client, destination in clients.items():
                result[f'{client}/{name}/{relative}'] = (src, destination/name/relative)
    return result


def differences(component):
    changed = []
    for name, (src, live) in mappings(component).items():
        linked = component != 'mac' or (
            live.is_symlink() and live.resolve() == (RUNTIME/'mac/dotfiles'/live.relative_to(HOME)).resolve()
        )
        if not linked or digest(src) != digest(live):
            changed.append(name)
            print(('缺少运行文件' if not live.exists() else '存在差异') + ': ' + name)
    if not changed:
        print(component + ': 受管配置内容一致。')
    return changed


def snapshot(source, target, files=None):
    stage = target.with_name(target.name+'.new')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, mode=0o700)
    if files is None:
        files = {src: src.relative_to(source) for src in source_files(source)}
    for src, relative in files.items():
        dst = stage/relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    if target.exists():
        shutil.rmtree(target)
    os.replace(stage, target)


def receipt(component, pairs, **metadata):
    private_json(STATE/(component+'.json'), {
        'source': str(ROOT), 'component': component, **metadata,
        'head': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'applied_at': datetime.datetime.now().astimezone().isoformat(),
        'files': {name: digest(src) for name, (src, _) in pairs.items()},
        'note': '包含未提交工作，以文件摘要为准；不代表真实功能验收通过。'})


def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(HOME/'.codex'))).expanduser().resolve()


def install_codex():
    target = codex_home()
    pairs = profile_mappings(ROOT, target)
    record = STATE/'codex.json'
    with installation_lock(STATE):
        previous = profile_receipt(record)
        updates = profile_updates(pairs, previous, target)
        wanted = {name: digest(source) for name, (source, _) in pairs.items()}
        if updates or previous.get('codex_home') != str(target) or previous.get('files') != wanted:
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            with rollback_on_failure([*updates, record]):
                for path, content in updates.items():
                    write_atomic(path, content)
                receipt('codex', pairs, codex_home=str(target))
    print('Codex 命名档位已就绪：feipi-develop、feipi-review。')


def install(component, agent=None, skill=None):
    if (agent or skill) and component != 'skills':
        raise ValueError('--agent/--skill 只适用于 install skills')
    skill_args = []
    if agent:
        skill_args += ['--agent', agent]
    if skill:
        if not skill.startswith('feipi-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in skill):
            raise ValueError('无效 skill 名称')
        skill_args += ['--skill', skill]
    if component == 'codex':
        install_codex()
        return
    if component == 'openclash':
        run([sys.executable, ROOT/'components/openclash/router.py', 'apply'])
        return
    base = ROOT/'components'/component
    pairs = {} if component == 'skills' else mappings(component)
    if component == 'mac':
        runtime = RUNTIME/'mac'
        mac_link_conflicts(pairs)
        run(['bash', base/'bootstrap/run.sh'])
        # 依赖安装或用户并发编辑后再次检查，避免覆盖刚出现的文件。
        replace = mac_link_conflicts(pairs)
        runtime_files = {src: Path('dotfiles')/target.relative_to(HOME) for src, target in pairs.values()}
        env_history = Path('bootstrap/env-history.py')
        runtime_files[base/env_history] = env_history
        history_plist = HOME/'Library/LaunchAgents'/(ENV_HISTORY_LABEL+'.plist')
        # 父目录是旧目录链接时，只备份该链接，避免通过它写入子文件。
        paths = [runtime, history_plist, *replace, *(
            target for _, target in pairs.values() if not any(parent in replace for parent in target.parents)
        )]
    elif component == 'skills':
        clients = {'codex': '.codex', 'cursor': '.cursor', 'claudecode': '.claude', 'qwen': '.qwen',
                   'qoder': '.qoder', 'openclaw': '.openclaw', '': '.agents'}
        selected = [agent] if agent else list(clients)
        roots = []
        for name in selected:
            if name == 'codex':
                base = Path(os.environ.get('CODEX_HOME', str(HOME/'.codex')))
            elif name == 'openclaw':
                base = Path(os.environ.get('OPENCLAW_HOME', str(HOME/'.openclaw')))
            else:
                base = HOME/clients[name]
            if agent or base.is_dir():
                roots.append(base/'skills')
        if not roots:
            roots = [HOME/'.agents/skills']
        paths = roots
        if skill:
            source = next((ROOT/entry['path'] for entry in parse_registry(ROOT) if entry['name'] == skill), None)
            if source is None:
                raise ValueError('未找到唯一 skill：'+skill)
            # 与安装器一致，只扫描被选 skill 的运行脚本中的直接共享依赖。
            shared = set()
            for script in source.rglob('*.sh'):
                if any(x in ('maintenance', 'tests', 'evals', 'node_modules') for x in script.relative_to(source).parts):
                    continue
                for name in re.findall(r'\$REPO_ROOT/([A-Za-z0-9._-]+)', script.read_text()):
                    if name != 'skills' and not name.startswith('.') and (ROOT/name).exists():
                        shared.add(name)
            paths = [p/skill for p in roots] + [p.parent/name for p in roots for name in sorted(shared)]
    elif component == 'services':
        run(['bash', ROOT/'scripts/bootstrap/setup.sh'])
        paths = [RUNTIME/'services']
    else:
        paths = [t for _, t in pairs.values()] + [HOME/'.openclaw/.env']
    with rollback_on_failure(paths):
        if component == 'mac':
            snapshot(base, runtime, runtime_files)
            for path in replace:
                path.unlink()
            stow = ['stow', '--dir', runtime.resolve(), '--target', HOME.resolve(), '--no-folding']
            # 独立 HOME 屏蔽用户 .stowrc，同时避免 Stow 展开路径时读取空 HOME。
            environment = dict(os.environ, HOME=str(runtime.resolve()))
            environment.pop('STOW_DIR', None)
            run([*stow, '--simulate', 'dotfiles'], cwd=runtime, env=environment)
            run([*stow, 'dotfiles'], cwd=runtime, env=environment)
            run([sys.executable, runtime/env_history, 'install'])
        elif component == 'skills':
            run(['bash', ROOT/'scripts/install_skills.sh', '--copy', *skill_args])
            receipt_client = 'claude' if agent == 'claudecode' else agent
            pairs = {name: pair for name, pair in mappings(component).items()
                     if (not agent or name.split('/')[0] == receipt_client)
                     and (not skill or name.split('/')[1] == skill)}
        elif component == 'services':
            snapshot(ROOT/'tools', RUNTIME/'services/tools')
            snapshot(ROOT/'runtimes/fastmcp', RUNTIME/'services/runtimes/fastmcp')
            print('运行定义已安装。对需要更新的服务执行 ./workbench service <名称> restart。')
        else:
            run(['bash', base/'scripts/deploy.sh', '--yes'])
        receipt(component, pairs)


def doctor(component):
    failed = False
    chosen = ([name for name in COMPONENTS if name != 'codex' or (STATE/'codex.json').exists()]
              if component is None else [component])
    for name in chosen:
        print('\n['+name+']', flush=True)
        if name in ('mac', 'openclaw', 'services'):
            failed |= bool(differences(name))
        if name == 'codex':
            target = codex_home()
            record = STATE/'codex.json'
            installed = profile_receipt(record)
            pairs = profile_mappings(ROOT, target)
            wanted = {name: digest(source) for name, (source, _) in pairs.items()}
            failed |= bool(differences(name))
            if (any(live.is_symlink() for _, live in pairs.values())
                    or installed.get('codex_home') != str(target)
                    or installed.get('files') != wanted):
                print('Codex 档位的来源或安装位置无法确认。')
                failed = True
        elif name == 'mac':
            for command in ['brew', 'git', 'stow', 'zsh', 'nvim', 'node', 'python3', 'podman']:
                found = shutil.which(command)
                if not found:
                    # SSH/launchd 不读取交互 PATH；只读探测 Homebrew 原生位置，避免误报需重装。
                    found = shutil.which(command, path='/opt/homebrew/bin:/usr/local/bin')
                if command == 'node' and not found and (Path(os.environ.get('NVM_DIR', str(HOME/'.nvm')))/'nvm.sh').is_file():
                    checked = subprocess.run(['bash', str(ROOT/'components/mac/bootstrap/environment.sh'), 'check'],
                                             capture_output=True, text=True, timeout=30)
                    if checked.returncode == 0:
                        found = checked.stdout.splitlines()[0]
                print(('发现' if found else '缺少')+': '+command+((' → '+found) if found else '；先 workbench install mac'))
                failed |= not bool(found)
        elif name == 'skills':
            print('更新技能：./workbench install skills')
            failed |= bool(differences(name))
            linked = {str(live.parent) for _, live in mappings(name).values()
                      if live.is_symlink() or any(p.is_symlink() for p in live.parents if p != HOME)}
            if linked:
                print('发现源码链接模式；执行 workbench install skills 恢复实拷。'); failed = True
        elif name == 'services':
            failed |= not services_ready()
        elif name == 'openclaw':
            try:
                status = openclaw_status()
                ok = status['service']['runtime']['status'] == 'running' and status['rpc']['ok']
                print('Gateway: '+('运行且 RPC 可连接；真实交互需另验' if ok else '未就绪'))
                failed |= not ok
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
                print('Gateway 状态未能核实'); failed = True
        elif name == 'openclash':
            proc = subprocess.run(['python3', str(ROOT/'components/openclash/router.py'), 'doctor'])
            failed |= proc.returncode != 0
        if not (STATE/(name+'.json')).exists():
            print('无工作台安装回执；不能认定已接管。'); failed = True
    print('\n这是配置/服务层检查；真实使用证据见 docs/workbench-validation.md。')
    return int(failed)


def services_ready():
    """当前工作流必需 LiteLLM；其他服务按需启用，不以未启动判错。"""
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://localhost:4000/health/readiness', timeout=5) as response:
            ready = response.status == 200
        data = json.loads(subprocess.check_output(['podman', 'inspect', 'litellm-proxy-podman'], text=True, stderr=subprocess.DEVNULL))
        owned = any(m.get('Source') == str(RUNTIME/'services/tools/gateway/litellm/config/config.yaml')
                    and m.get('Destination') == '/app/config.yaml' for m in data[0].get('Mounts', []))
        print('LiteLLM：就绪='+str(ready)+'；配置挂载来自运行副本='+str(owned))
        print('SearXNG / Crawl4AI / OTel 按需启用；未启动不视为当前工作流缺项。')
        return ready and owned
    except (OSError, ValueError, subprocess.CalledProcessError):
        print('LiteLLM 未就绪或来源未接管：先 workbench install services，再 service litellm restart；检查私有 env 和 Podman。')
        return False


def openclaw_gateway(*args):
    environment = ROOT/'components/mac/bootstrap/environment.sh'
    return ['bash', '-c', 'set -e; source "$1"; shift; exec openclaw gateway "$@"', '--', environment, *args]


def openclaw_status(*args):
    result = run(openclaw_gateway('status', '--json', *args), capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def openclaw_service(action):
    if action == 'logs':
        run(['tail', '-n', '50', HOME/'Library/Logs/openclaw/gateway.log'])
    elif action == 'status':
        run(openclaw_gateway('status', '--require-rpc'), timeout=30)
    elif action == 'down':
        run(openclaw_gateway('stop', '--force'), timeout=60)
    else:
        status = openclaw_status('--no-probe')
        gateway = status.get('gateway', {})
        port = gateway.get('port')
        if gateway.get('bindMode') != 'loopback' or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError('仅支持有效本机回环地址上的 OpenClaw Gateway。')
        installed = status.get('service', {})
        if not installed.get('command'):
            run(openclaw_gateway('install'), timeout=60)
        elif installed.get('runtime', {}).get('status') != 'running':
            run(openclaw_gateway('start'), timeout=60)
        elif action == 'restart':
            run(openclaw_gateway('restart'), timeout=60)
        wait_service('openclaw', f'http://127.0.0.1:{port}/readyz', seconds=45)


def service(component, args):
    allowed = SERVICE_ACTIONS.get(component, ())
    if not args or args[0] not in allowed:
        raise ValueError(component + ' 支持的操作为 ' + ' / '.join(allowed))
    action, *extra = args
    if extra and not (component == 'litellm' and action == 'logs' and extra in (['postgres'], ['all'])):
        raise ValueError('额外参数仅用于 service litellm logs postgres 或 logs all。')
    if component == 'podman':
        run([sys.executable, ROOT/'tools/runtime/podman.py', *args])
    elif component == 'omlx':
        run([sys.executable, ROOT/'scripts/workbench/omlx_service.py', *args])
    elif component == 'openclaw':
        openclaw_service(action)
    elif component == 'startup':
        script = RUNTIME/'services/tools/runtime/startup.py'
        if not script.is_file():
            raise ValueError('先 workbench install services，发布独立自启运行副本。')
        if args == ['install']:
            plist = HOME/'Library/LaunchAgents/com.feipi.podman-services.plist'
            with rollback_on_failure([plist]):
                run([sys.executable, script, *args])
        else:
            run([sys.executable, script, *args])
    elif component in SERVICE_SCRIPTS:
        script = RUNTIME/'services/tools'/SERVICE_SCRIPTS[component]
        if not script.exists():
            raise ValueError('尚未安装运行定义：先 ./workbench install services')
        run(['bash', script, *args])
        endpoints = {'litellm': 'http://localhost:4000/health/readiness',
                     'searxng': 'http://127.0.0.1:8873/healthz',
                     'fastmcp': 'http://127.0.0.1:18080/healthz',
                     'crawl4ai': 'http://127.0.0.1:11235/health'}
        if component in endpoints and action in ('up', 'restart'):
            wait_service(component, endpoints[component])


def mac_link_conflicts(pairs):
    """接受已知旧发布与同内容副本，拒绝覆盖其他用户文件。"""
    runtime = RUNTIME/'mac'
    package = runtime/'dotfiles'
    legacy = {HOME/target for target, source in [
        ('.zsh_config', 'zsh/.zsh_config'), ('bin', 'zsh/bin'), ('.config/nvim', 'neovim/.config/nvim'),
    ] if (HOME/target).is_symlink() and (HOME/target).resolve() == (runtime/source).resolve()}
    replace = sorted(legacy)
    manifest = STATE/'mac.json'
    known = json.loads(manifest.read_text()).get('files', {}) if manifest.is_file() else {}
    for path in (runtime, runtime.parent, runtime.parent.parent, HOME/'Library/LaunchAgents'):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError('发布目录存在冲突：' + str(path))
    for name, (source, target) in pairs.items():
        relative = target.relative_to(HOME)
        parents = [HOME/parent for parent in relative.parents if parent != Path('.')]
        for parent in parents:
            if parent not in legacy and (parent.is_symlink() or (parent.exists() and not parent.is_dir())):
                raise ValueError('配置父路径存在冲突：' + str(parent))
        if any(parent in legacy for parent in parents):
            continue
        expected = (package/relative).resolve()
        if target.is_symlink():
            resolved = target.resolve()
            if resolved == expected and not target.readlink().is_absolute():
                continue
            if resolved not in (expected, source.resolve(), (runtime/name).resolve()):
                raise ValueError('配置链接存在冲突：' + str(target))
            replace.append(target)
        elif target.exists():
            current = digest(target)
            if current is None or current not in (digest(source), digest(runtime/name), known.get(name)):
                raise ValueError('配置文件已存在且内容不同，请先检查：' + str(target))
            replace.append(target)
    targets = {target for _, target in pairs.values()}
    for old in package.rglob('*'):
        target = HOME/old.relative_to(package)
        parents = (parent for parent in target.parents if parent != HOME and HOME in parent.parents)
        if (old.is_file() and target not in targets and target.is_symlink()
                and not any(parent.is_symlink() for parent in parents) and target.resolve() == old.resolve()):
            replace.append(target)
    return replace


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(prog='./workbench', description='个人工作台')
    sub = p.add_subparsers(dest='action')
    doctor_parser = sub.add_parser('doctor', help='检查配置与运行状态')
    doctor_parser.add_argument('component', choices=COMPONENTS, nargs='?')
    install_parser = sub.add_parser('install', help='准备依赖并发布组件配置')
    install_components = install_parser.add_subparsers(dest='component', required=True)
    for component in COMPONENTS:
        parser = install_components.add_parser(component, allow_abbrev=False)
        if component == 'skills':
            parser.add_argument('--agent', choices=('codex', 'cursor', 'claudecode', 'qwen', 'qoder', 'openclaw'),
                                help='限定目标客户端')
            parser.add_argument('--skill', help='限定已注册的技能')
    project_parser = sub.add_parser('project', help='初始化或检查本机项目绑定')
    project_actions = project_parser.add_subparsers(dest='operation', required=True)
    for operation in ('init', 'doctor'):
        project_actions.add_parser(operation).add_argument('path', nargs='?', type=Path, default=Path.cwd())
    session_parser = sub.add_parser('session', help='为指定项目生成一次性会话简报')
    session_parser.add_argument('mode', choices=MODES)
    session_parser.add_argument('path', nargs='?', type=Path, default=Path.cwd())
    service_parser = sub.add_parser('service', help='管理工作台托管的本地服务')
    services = service_parser.add_subparsers(dest='component', required=True)
    for component, actions in SERVICE_ACTIONS.items():
        parser = services.add_parser(component, help=' / '.join(actions))
        if component == 'litellm':
            operations = parser.add_subparsers(dest='operation', required=True)
            for operation in actions:
                operation_parser = operations.add_parser(operation)
                if operation == 'logs':
                    operation_parser.add_argument('log_scope', choices=('postgres', 'all'), nargs='?',
                                                  help='省略时查看网关日志')
        else:
            parser.add_argument('operation', choices=actions)
    a = p.parse_args()
    if a.action is None:
        p.print_help()
    elif a.action == 'doctor':
        return doctor(a.component)
    elif a.action == 'install':
        install(a.component, getattr(a, 'agent', None), getattr(a, 'skill', None))
    elif a.action == 'project':
        if a.operation == 'init':
            initialize_project(ROOT, a.path)
        else:
            project, _ = current_project(ROOT, a.path)
            print(f'项目绑定一致，入口可定位：{project}')
    elif a.action == 'session':
        session_brief(ROOT, a.path, a.mode)
    elif a.action == 'service':
        arguments = [a.operation]
        if getattr(a, 'log_scope', None):
            arguments.append(a.log_scope)
        service(a.component, arguments)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('未完成：'+str(exc)+'\n已完成阶段可保留；修复后重试同一组件。', file=sys.stderr)
        sys.exit(1)
