#!/usr/bin/env python3
"""个人工作台：固定组件、明确方向、复用组件原有能力。"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
STATE = HOME / '.local/state/feipi-workbench'
RUNTIME = HOME / '.local/share/feipi-workbench'
PRIVATE = HOME / '.config/feipi-workbench/private'
COMPONENTS = ('mac', 'skills', 'services', 'multica', 'openclaw', 'openclash')
SERVICE_SCRIPTS = {'litellm': 'gateway/litellm/scripts/litellm.sh',
                   'searxng': 'search/searxng/scripts/searxng.sh',
                   'crawl4ai': 'crawl/crawl4ai/scripts/crawl4ai.sh',
                   'otel': 'gateway/otel/scripts/otel.sh'}


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
    """只允许明确列出的配置回收；记忆、会话、账号、订阅不能落入此集合。"""
    result = {}
    base = ROOT / 'components' / component
    if component == 'mac':
        for package in ('zsh', 'neovim'):
            for src in source_files(base/package):
                result[str(src.relative_to(base))] = (src, HOME/src.relative_to(base/package))
        for relative, target in [
            ('desktop/karabiner/karabiner.json', '.config/karabiner/karabiner.json'),
            ('desktop/iterm2/profile.json', 'Library/Application Support/iTerm2/DynamicProfiles/dotfiles.json'),
            ('qwen/.qwen/output-language.md', '.qwen/output-language.md')]:
            result[relative] = (base/relative, HOME/target)
    elif component == 'openclaw':
        for rel in ['openclaw.json', 'scripts/transcribe-audio-whispercpp-openclaw.sh']:
            result[rel] = (base/rel, HOME/'.openclaw'/rel)
        manifest = json.loads((base/'templates/workspace/manifest.json').read_text())
        for rel in manifest['files']:
            if Path(rel).is_absolute() or '..' in Path(rel).parts:
                raise ValueError('workspace manifest 路径越界')
            result['templates/workspace/'+rel] = (base/'templates/workspace'/rel, HOME/'.openclaw/workspace'/rel)
    elif component == 'multica':
        for src in source_files(base/'config'):
            rel = str(src.relative_to(base))
            result[rel] = (src, HOME/'.local/share/multica/ops'/rel)
    elif component == 'services':
        for src in source_files(ROOT/'tools'):
            if any(x in src.parts for x in ['config', 'settings', 'compose']):
                rel = str(src.relative_to(ROOT))
                result[rel] = (src, RUNTIME/'services'/rel)
    elif component == 'skills':
        for src in source_files(ROOT/'skills'):
            parts = src.relative_to(ROOT/'skills').parts
            if len(parts) < 3 or any(p in ('maintenance', 'tests', 'evals', 'node_modules', '__pycache__') for p in parts[2:]):
                continue
            for client in ['codex', 'claude', 'qwen', 'qoder', 'openclaw']:
                if (HOME/('.'+client)).is_dir():
                    relative = Path(*parts[2:])
                    result[client+'/'+parts[1]+'/'+str(relative)] = (src, HOME/('.'+client)/'skills'/parts[1]/relative)
    elif component == 'openclash':
        rel = 'OIX-Region-Priority.conf'
        result[rel] = (base/rel, PRIVATE/'openclash'/rel)
    return result


def differences(component, show=True):
    pairs = mappings(component)
    if component == 'multica':
        # 运行代码也可能比仓库新；只读比对，回收白名单仍仅限配置。
        base = ROOT/'components/multica'
        for src in source_files(base/'scripts') + source_files(base/'bin') + [base/'versions.json']:
            if src.is_file():
                rel = str(src.relative_to(base))
                pairs[rel] = (src, HOME/'.local/share/multica/ops'/rel)
    changed = []
    for name, (src, live) in pairs.items():
        if digest(src) == digest(live):
            continue
        changed.append(name)
        print(('缺少运行文件' if not live.exists() else '存在差异') + ': ' + name)
        if show and live.is_file():
            # 原文 diff 只写私有文件，避免应用写入的凭据意外进入聊天或终端日志。
            try:
                delta = ''.join(difflib.unified_diff(src.read_text().splitlines(True), live.read_text().splitlines(True),
                                                   fromfile='仓库/'+name, tofile='本机/'+name))
            except UnicodeError:
                delta = '二进制文件不同；请在应用中比较。\n'
            out = STATE/'diff'/component/(name+'.diff')
            out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            out.write_text(delta)
            out.chmod(0o600)
            print('  私有差异文件：' + str(out))
    if not changed:
        print(component + ': 受管配置内容一致。')
    if component == 'multica':
        print('运行代码差异需审阅后合并；capture --select 仅允许受管配置。')
        print('服务端 UI 字段的差异：./workbench multica plan；选择回收：./workbench multica capture --help')
    return changed


def check_public(path, data):
    """回收时拒绝常见明文凭据；SecretRef 和环境引用保持原样。"""
    text = data.decode('utf-8', errors='strict')
    if re.search(r'(?:sk-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY-----)', text):
        raise ValueError('发现疑似秘密，未回收：' + str(path))
    if path.suffix == '.json':
        value = json.loads(text)
        def visit(v):
            if isinstance(v, dict):
                for k, child in v.items():
                    if re.search(r'^(apiKey|password|token|secret|botToken|accessToken|refreshToken)$', k, re.I):
                        if isinstance(child, str) and child and not child.startswith(('${', '<')):
                            raise ValueError('JSON 包含明文秘密字段 ' + k + '；先改用私有 env/SecretRef。')
                    visit(child)
            elif isinstance(v, list):
                for child in v:
                    visit(child)
        visit(value)
    if path.suffix == '.conf' and re.search(r'(?im)^\s*(?:url|secret|password|token):\s*["\']?https?://.*[?&](?:token|key|auth)=', text):
        raise ValueError('模块包含订阅凭据；未回收。')
    if path.suffix in ('.conf', '.yaml', '.yml', '.zsh', '.sh'):
        for value in re.findall(r'(?im)^\s*(?:export\s+)?[\w-]*(?:secret|password|api_key|token)[\w-]*\s*[:=]\s*([^\n#]+)', text):
            value = value.strip().strip('"\'')
            if value and not value.startswith(('$', '<', 'os.environ')) and value not in ('null', 'false', 'true'):
                raise ValueError('发现可能含明文凭据的字段；请先改成私有环境引用再回收。')


def capture(component, selected):
    if not selected:
        differences(component)
        print('选择后执行：./workbench capture ' + component + ' --select 上述文件名（可重复）')
        return
    pairs = mappings(component)
    # 整体校验后再写；调用者只能选择显示过的受管相对路径。
    pending = []
    for name in selected:
        if name not in pairs:
            raise ValueError('不在允许回收范围：' + name)
        src, live = pairs[name]
        data = live.read_bytes()
        check_public(src, data)
        pending.append((src, data))
    batch = backup('capture-'+component, [p for p, _ in pending])
    for path, data in pending:
        path.write_bytes(data)
    print('已回收到源码，尚未提交 Git；旧源码备份：' + str(batch))


def backup(name, paths):
    """只备份将修改的文件/目录。数据库另走组件的一致性备份。"""
    batch = STATE/'changes'/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'-'+name)
    batch.mkdir(parents=True, mode=0o700)
    records = []
    for index, path in enumerate(dict.fromkeys(paths)):
        entry = {'path': str(path), 'kind': 'absent'}
        dest = batch/str(index)
        if path.is_symlink():
            entry.update(kind='link', target=os.readlink(path))
        elif path.is_dir():
            entry.update(kind='directory', saved=str(index))
            shutil.copytree(path, dest, symlinks=True)
        elif path.exists():
            entry.update(kind='file', saved=str(index))
            shutil.copy2(path, dest)
        records.append(entry)
    private_json(batch/'restore.json', records)
    return batch


def restore(batch):
    batch = Path(batch).expanduser().resolve()
    if STATE.resolve() not in batch.parents:
        raise ValueError('只接受本机工作台生成的私有回退批次。')
    records = json.loads((batch/'restore.json').read_text())
    for entry in reversed(records):
        path = Path(entry['path'])
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if entry['kind'] == 'link':
            path.symlink_to(entry['target'])
        elif entry['kind'] == 'file':
            shutil.copy2(batch/entry['saved'], path)
        elif entry['kind'] == 'directory':
            shutil.copytree(batch/entry['saved'], path, symlinks=True)
    print('已恢复受管文件。服务组件仍须执行对应 restart/verify：' + str(batch))


def snapshot(source, target):
    stage = target.with_name(target.name+'.new')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, mode=0o700)
    for src in source_files(source):
        dst = stage/src.relative_to(source)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    if target.exists():
        shutil.rmtree(target)
    os.replace(stage, target)


def receipt(component, pairs=None):
    private_json(STATE/(component+'.json'), {
        'source': str(ROOT), 'component': component,
        'head': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'applied_at': datetime.datetime.now().astimezone().isoformat(),
        'files': {name: digest(src) for name, (src, _) in (pairs or mappings(component)).items()},
        'note': '包含未提交工作，以文件摘要为准；不代表真实功能验收通过。'})


def apply(component, agent=None, skill=None):
    if (agent or skill) and component != 'skills':
        raise ValueError('--agent/--skill 只适用于 apply skills')
    skill_args = []
    if agent:
        skill_args += ['--agent', agent]
    if skill:
        if not skill.startswith('feipi-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in skill):
            raise ValueError('无效 skill 名称')
        skill_args += ['--skill', skill]
    if component == 'openclash':
        run(['python3', ROOT/'components/openclash/router.py', 'apply'])
        return
    base = ROOT/'components'/component
    pairs = mappings(component)
    if component == 'mac':
        links = {HOME/'.zshrc': RUNTIME/'mac/zsh/.zshrc', HOME/'.zsh_config': RUNTIME/'mac/zsh/.zsh_config',
                 HOME/'bin': RUNTIME/'mac/zsh/bin', HOME/'.config/nvim': RUNTIME/'mac/neovim/.config/nvim'}
        desktop = [(s, t) for n, (s, t) in pairs.items() if n.startswith(('desktop/', 'qwen/'))]
        # 目录中可能含用户文件，正常实目录需先人工合并，不自动删掉。
        for path in links:
            if path.is_dir() and not path.is_symlink():
                raise ValueError('先合并现有目录再切换，未覆盖：' + str(path))
        paths = [RUNTIME/'mac', *links, *[t for _, t in desktop]]
    elif component == 'skills':
        clients = {'codex': '.codex', 'claudecode': '.claude', 'qwen': '.qwen', 'qoder': '.qoder', 'openclaw': '.openclaw', '': '.agents'}
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
            sources = list((ROOT/'skills').glob('*/'+skill))
            if len(sources) != 1 or not (sources[0]/'SKILL.md').is_file():
                raise ValueError('未找到唯一 skill：'+skill)
            # 与安装器一致，只扫描被选 skill 的运行脚本中的直接共享依赖。
            shared = set()
            for script in sources[0].rglob('*.sh'):
                if any(x in ('maintenance', 'tests', 'evals', 'node_modules') for x in script.relative_to(sources[0]).parts):
                    continue
                for name in re.findall(r'\$REPO_ROOT/([A-Za-z0-9._-]+)', script.read_text()):
                    if name != 'skills' and not name.startswith('.') and (ROOT/name).exists():
                        shared.add(name)
            paths = [p/skill for p in roots] + [p.parent/name for p in roots for name in sorted(shared)]
        if agent or skill:
            receipt_client = 'claude' if agent == 'claudecode' else agent
            pairs = {name: pair for name, pair in pairs.items()
                     if (not agent or name.split('/')[0] == receipt_client)
                     and (not skill or name.split('/')[1] == skill)}
    elif component == 'services':
        paths = [RUNTIME/'services', PRIVATE/'services/crawl4ai.env']
    elif component == 'multica':
        paths = [HOME/'.local/share/multica/ops', HOME/'.config/multica-selfhost/machine.json']
        # 不改变任务身份、数据库或调度；已有排空检查来自组件自身。
        sys.path.insert(0, str(base/'scripts'))
        from adaptation import cli, agent_runs, ACTIVE
        for agent in cli('agent', 'list'):
            if any(r.get('status') in ACTIVE for r in agent_runs(agent['id'])):
                raise ValueError('Multica 仍有活动任务；完成后重试。')
    else:
        run(['bash', base/'scripts/validate-config.sh'])
        paths = [t for _, t in pairs.values()] + [HOME/'.openclaw/.env']
    batch = backup(component, paths)
    print('回退：./workbench restore ' + str(batch), flush=True)
    try:
        if component == 'mac':
            snapshot(base, RUNTIME/'mac')
            for path, dest in links.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.is_symlink() or path.exists():
                    path.unlink()
                path.symlink_to(dest)
            for src, target in desktop:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink():
                    target.unlink()
                shutil.copy2(src, target)
        elif component == 'skills':
            run(['bash', ROOT/'scripts/install_skills.sh', '--copy', *skill_args])
        elif component == 'services':
            # 一次性收纳旧的忽略文件；后续以 HOME 私有副本为准，发布源码不会删除它。
            old_env = ROOT/'tools/crawl/crawl4ai/env/.env.local'
            private_env = PRIVATE/'services/crawl4ai.env'
            if old_env.is_file() and not private_env.exists():
                private_env.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copy2(old_env, private_env)
                private_env.chmod(0o600)
            snapshot(ROOT/'tools', RUNTIME/'services/tools')
            print('运行定义已安装；对需要更新的服务执行 ./workbench service <名称> recreate/restart。')
        elif component == 'multica':
            run(['python3', base/'scripts/install-runtime.py'])
            machine = HOME/'.config/multica-selfhost/machine.json'
            data = json.loads(machine.read_text())
            data['agent_kit'] = str(ROOT)
            data['openclaw_source'] = str(ROOT/'components/openclaw/openclaw.json')
            private_json(machine, data)
            print('运行副本与机器来源已接管。配置生成、plan/apply 与 daemon 重启通过 service multica 显式执行。')
        else:
            run(['bash', base/'scripts/install-runtime.sh', '--write', '--yes'])
            print('配置已应用；./workbench service openclaw restart --force 后验证实际交互。')
        receipt(component, pairs)
    except Exception:
        print('应用失败，正在恢复本批受管文件。', file=sys.stderr)
        restore(batch)
        raise


def doctor(component):
    failed = False
    chosen = COMPONENTS if component == 'all' else [component]
    for name in chosen:
        print('\n['+name+']', flush=True)
        if name in ['mac', 'openclaw', 'multica', 'services']:
            failed |= bool(differences(name, show=False))
        if name == 'mac':
            for command in ['brew', 'git', 'zsh', 'nvim', 'node', 'python3', 'podman']:
                found = shutil.which(command)
                print(('发现' if found else '缺少')+': '+command+((' → '+found) if found else '；先 workbench install mac'))
                failed |= not bool(found)
            live = HOME/'.zshrc'
            if RUNTIME not in live.resolve().parents:
                print('日常 Zsh 仍未使用运行副本；先 diff/capture，再 apply mac。')
                failed = True
        elif name == 'skills':
            print('日常使用实拷；安装命令：./workbench apply skills。源码调试：./develop skills link。')
            failed |= bool(differences(name, show=False))
            linked = {str(live.parent) for _, live in mappings(name).values()
                      if live.is_symlink() or any(p.is_symlink() for p in live.parents if p != HOME)}
            if linked:
                print('发现源码链接模式；执行 apply skills 恢复实拷。'); failed = True
        elif name == 'services':
            failed |= not services_ready()
        elif name == 'openclaw':
            proc = subprocess.run(['openclaw', 'gateway', 'status', '--json'], capture_output=True, text=True, timeout=30)
            try:
                status = json.loads(proc.stdout)
                ok = status['service']['runtime']['status'] == 'running' and status['rpc']['ok']
                print('Gateway: '+('运行且 RPC 可连接；真实交互需另验' if ok else '未就绪'))
                failed |= not ok
            except (ValueError, KeyError):
                print('Gateway 状态未能核实'); failed = True
        elif name == 'multica':
            proc = subprocess.run([str(HOME/'.local/bin/multica-ops'), 'doctor'])
            failed |= proc.returncode != 0
        elif name == 'openclash':
            proc = subprocess.run(['python3', str(ROOT/'components/openclash/router.py'), 'doctor'])
            failed |= proc.returncode != 0
        if not (STATE/(name+'.json')).exists():
            print('无工作台应用回执；不能认定已接管。'); failed = True
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
        print('LiteLLM 未就绪或来源未接管：先 apply services，再 service litellm restart；检查私有 env 和 Podman。')
        return False


def service(component, args):
    if component in SERVICE_SCRIPTS:
        script = RUNTIME/'services/tools'/SERVICE_SCRIPTS[component]
        if not script.exists():
            raise ValueError('尚未安装运行定义：先 ./workbench apply services')
        environment = dict(os.environ)
        if component == 'crawl4ai' and (PRIVATE/'services/crawl4ai.env').is_file():
            environment.setdefault('CRAWL4AI_ENV_FILE', str(PRIVATE/'services/crawl4ai.env'))
        run(['bash', script, *args], env=environment)
        if component == 'litellm' and (args[:1] or ['up'])[0] in ('up', 'start', 'restart', 'recreate'):
            for attempt in range(60):
                try:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://localhost:4000/health/readiness', timeout=3) as response:
                        if response.status == 200:
                            print('LiteLLM readiness 已通过；模型能力需真实请求验证。')
                            break
                except OSError:
                    pass
                if attempt % 10 == 0:
                    print('等待 LiteLLM 数据库迁移及服务就绪…', flush=True)
                time.sleep(2)
            else:
                raise ValueError('LiteLLM 未在期限内就绪；保留运行状态供 service litellm logs 检查，不重复重建数据库。')
    elif component == 'openclaw':
        run(['openclaw', 'gateway', *args])
    elif component == 'multica':
        run(['python3', HOME/'.local/share/multica/ops/scripts/manage-runtime.py', *args])
    elif component == 'openclash':
        run(['python3', ROOT/'components/openclash/router.py', *args])
    else:
        raise ValueError('支持 litellm/searxng/crawl4ai/otel/openclaw/multica/openclash')


def install(component):
    if component == 'mac':
        # 复用安装器的依赖阶段；配置由工作台应用，避免重新链接研发目录。
        base = ROOT/'components/mac/bootstrap'
        for stage in ['brew', 'node', 'rust', 'ohmyzsh']:
            print('安装阶段：'+stage, flush=True)
            run(['bash', base/(stage+'.sh'), 'install'])
        print('依赖已准备；下一步 diff/capture/apply mac。')
    elif component == 'openclaw':
        run(['bash', ROOT/'components/openclaw/scripts/deploy.sh', '--yes'])
    elif component == 'skills':
        apply(component)
    elif component == 'services':
        run(['bash', ROOT/'scripts/bootstrap/setup.sh'])
        apply(component)
    elif component == 'multica':
        if not (HOME/'.config/multica-selfhost/machine.json').exists() or not shutil.which('multica'):
            raise ValueError('先按 components/multica/docs/mac-mini-migration.md 安装锁定版本并登录/绑定本机；不复制另一台机器的 runtime 身份。随后重跑 install multica。')
        apply(component)
    else:
        raise ValueError('OpenClash 在路由器 LuCI 安装锁定版本；本机先配置私有 router.json。见 components/openclash/README.md，随后 apply openclash。')


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description='日常工作台：检查 → 查看差异 → 选择回收或应用 → 真实验证。')
    sub = p.add_subparsers(dest='action')
    for action in ['doctor', 'plan', 'diff', 'capture', 'apply', 'install']:
        parser = sub.add_parser(action)
        parser.add_argument('component', choices=(*COMPONENTS, 'all') if action == 'doctor' else COMPONENTS,
                            nargs='?' if action == 'doctor' else None, default='all')
        if action == 'capture':
            parser.add_argument('--select', action='append', default=[])
        if action == 'apply':
            parser.add_argument('--agent', choices=('codex', 'claudecode', 'qwen', 'qoder', 'openclaw'))
            parser.add_argument('--skill')
    parser = sub.add_parser('restore'); parser.add_argument('batch')
    parser = sub.add_parser('service'); parser.add_argument('component'); parser.add_argument('args', nargs=argparse.REMAINDER)
    parser = sub.add_parser('private'); parser.add_argument('args', nargs=argparse.REMAINDER)
    parser = sub.add_parser('multica'); parser.add_argument('args', nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.action is None:
        print('个人工作台（打开入口不会安装或启动服务）\n\n'
              '  ./workbench doctor                 检查缺项、配置漂移和接管状态\n'
              '  ./workbench plan mac               查看组件范围与操作顺序\n'
              '  ./workbench install mac            补装依赖，不主动升级\n'
              '  ./workbench diff mac               仓库 ↔ 本机差异（原文仅存私有文件）\n'
              '  ./workbench capture mac --select zsh/.zshrc\n'
              '                                     将所选本机改动收回源码，尚不提交\n'
              '  ./workbench apply mac              备份后应用到日常运行副本\n'
              '  ./workbench service openclaw restart --force\n'
              '  ./workbench private check          必需/可选资料与恢复提示\n'
              '  ./workbench restore <私有批次>      回退本次文件变更\n\n'
              '组件：'+', '.join(COMPONENTS)+'\n研发、回归和显式源码调试：./develop --help')
    elif a.action == 'doctor':
        return doctor(a.component)
    elif a.action == 'plan':
        print('组件：'+a.component+'\n来源：'+str(ROOT)+'\n以下为实际受管目标；私有资料原位保留；应用前逐项备份。')
        for name, (_, target) in mappings(a.component).items():
            print(name+' → '+str(target))
        print('先 diff；保留本机改动用 capture --select；恢复声明用 apply。源码修改不自动进入运行环境。')
    elif a.action == 'diff':
        if a.component == 'openclash':
            run(['python3', ROOT/'components/openclash/router.py', 'fetch'])
        differences(a.component)
    elif a.action == 'capture':
        capture(a.component, a.select)
    elif a.action == 'apply':
        apply(a.component, a.agent, a.skill)
    elif a.action == 'install':
        install(a.component)
    elif a.action == 'restore':
        restore(a.batch)
    elif a.action == 'service':
        service(a.component, a.args)
    elif a.action == 'multica':
        if a.args[:1] == ['capture']:
            run(['python3', ROOT/'components/multica/scripts/capture.py', *a.args[1:]])
        else:
            run([HOME/'.local/bin/multica-ops', *a.args])
    else:
        run(['python3', ROOT/'scripts/workbench/private.py', *a.args])
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('未完成：'+str(exc)+'\n已完成阶段可保留；修复后重试同一组件。', file=sys.stderr)
        sys.exit(1)
