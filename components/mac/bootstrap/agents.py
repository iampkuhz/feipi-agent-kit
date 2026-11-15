#!/usr/bin/env python3
"""从原生发布包和 npm 补装四个锁定版 Agent CLI；不复制登录/设备身份。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
HOME = Path.home()


def command(args, capture=False, timeout=1200):
    return subprocess.run(list(map(str, args)), check=True, capture_output=capture,
                          text=True, timeout=timeout,
                          env=dict(os.environ, DISABLE_AUTOUPDATER='1')).stdout


def version(name):
    path = shutil.which(name)
    if not path:
        return None
    output = command([path, '--version'], capture=True, timeout=30)
    found = re.search(r'\b\d+\.\d+\.\d+\b', output)
    if not found:
        raise ValueError(name+' 版本输出无法识别；未替换现有程序。')
    return found[0]


def specs():
    data = json.loads((BASE/'config/cli-versions.json').read_text())
    codex = json.loads((ROOT/'components/multica/config/agents.json').read_text())['compatibility']['codex']
    return [dict(name='codex', version=codex, package='@openai/codex', integrity=data['codex_integrity']),
            dict(name='qwen', package='@qwen-code/qwen-code', **data['qwen']),
            dict(name='claude', **data['claude']), dict(name='qodercli', **data['qodercli'])]


def native_install(spec):
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('锁定原生 Agent 包目前仅支持 Apple Silicon macOS；未下载其他架构。')
    storage = HOME/'.local/share/feipi-workbench/cli'/spec['name']/spec['version']
    destination = HOME/'.local/bin'/spec['name']
    if destination.exists() or destination.is_symlink():
        raise ValueError('命令路径已占用，未覆盖：'+str(destination))
    storage.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='feipi-agent-', dir=storage.parent) as scratch:
        scratch = Path(scratch)
        archive = scratch/'download'
        command(['curl', '-fL', '--retry', '2', '--connect-timeout', '15', '--max-time', '600',
                 spec['url'], '-o', archive], timeout=650)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != spec['sha256']:
            raise ValueError(spec['name']+' 发布包摘要不匹配；未安装。')
        binary = scratch/spec['name']
        if spec['name'] == 'qodercli':
            # 只读取已校验归档内的一个普通文件，不解压目录/链接，避免归档越界。
            with tarfile.open(archive) as packed:
                member = packed.getmember('./qodercli')
                if not member.isfile():
                    raise ValueError('Qoder 包内程序不是普通文件。')
                binary.write_bytes(packed.extractfile(member).read())
            if hashlib.sha256(binary.read_bytes()).hexdigest() != spec['binary_sha256']:
                raise ValueError('Qoder 程序摘要不匹配。')
        else:
            archive.rename(binary)
        binary.chmod(0o755)
        if not re.search(r'\b'+re.escape(spec['version'])+r'\b',
                         command([binary, '--version'], capture=True, timeout=30)):
            raise ValueError(spec['name']+' 下载后的版本不匹配。')
        storage.mkdir(mode=0o700, exist_ok=True)
        target = storage/spec['name']
        if target.exists() and target.read_bytes() != binary.read_bytes():
            raise ValueError('安装缓存存在不同文件，未替换：'+str(target))
        os.replace(binary, target)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.symlink_to(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'install', 'check'], default='check', nargs='?')
    args = parser.parse_args()
    missing = []
    selected = specs()
    # 先核对整个集合，已安装其他版本时不先安装一半再报冲突。
    for spec in selected:
        actual = version(spec['name'])
        print(f"{spec['name']}: 需要 {spec['version']}；当前 {actual or '缺失'}", flush=True)
        if actual and actual != spec['version']:
            raise ValueError(spec['name']+' 版本与迁移基线不同；未升级、降级或覆盖现有安装。')
        if not actual:
            missing.append(spec)
    if args.action == 'plan':
        return
    if args.action == 'check' and missing:
        raise ValueError('缺少 Agent CLI：'+', '.join(s['name'] for s in missing))
    for spec in missing:
        if 'package' in spec:
            package = spec['package']+'@'+spec['version']
            integrity = json.loads(command(['npm', 'view', package, 'dist.integrity', '--json'], capture=True))
            if integrity != spec['integrity']:
                raise ValueError(package+' registry 摘要与锁定值不同；未安装。')
            command(['npm', 'install', '-g', '--no-audit', '--no-fund', package])
        else:
            native_install(spec)
        if version(spec['name']) != spec['version']:
            raise ValueError(spec['name']+' 安装后当前 PATH 的版本不符。')
    print('四个 Agent CLI 版本检查通过；账号认证和真实任务另行验收。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
