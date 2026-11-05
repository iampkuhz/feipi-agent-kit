#!/usr/bin/env python3
"""按锁文件准备本机共享依赖；不向技能源码或安装目录写入 node_modules。"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def command(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-1500:])
    return result.stdout


def identity(root):
    node = json.loads(command(['node', '-p', 'JSON.stringify({version:process.versions.node,abi:process.versions.modules,platform:process.platform,arch:process.arch})']))
    version = tuple(map(int, node.pop('version').split('.')))
    if version < (22, 13, 0):
        raise RuntimeError('需要系统 Node.js 22.13+；不会自动安装或更换 Node。')
    node['major'] = version[0]
    content = {name: (root/name).read_bytes() for name in ('package.json', 'package-lock.json')}
    key = hashlib.sha256(json.dumps(node, sort_keys=True).encode() + b''.join(content.values())).hexdigest()
    return key, content


def cache_root():
    default = Path.home()/('Library/Caches' if sys.platform == 'darwin' else '.cache')
    return Path(os.environ.get('XDG_CACHE_HOME', default)).expanduser()/'feipi-agent-kit/mermaid'


def ready(target, key, content):
    try:
        if target.is_symlink() or (target/'.ready').read_text() != key:
            return False
        if any((target/name).read_bytes() != data for name, data in content.items()):
            return False
        locked = json.loads(content['package-lock.json'])['packages']
        for name in ('puppeteer', '@mermaid-js/mermaid-cli', 'mermaid'):
            installed = json.loads((target/'node_modules'/name/'package.json').read_text())
            if installed['version'] != locked['node_modules/'+name]['version']:
                return False
        return True
    except (OSError, ValueError, KeyError):
        return False


def ensure_runtime(root=ROOT, check=False):
    root = Path(root)
    key, content = identity(root)
    base = cache_root()
    target = base/key
    if ready(target, key, content):
        return {'path': str(target), 'reused': True, 'key': key}
    if check:
        raise RuntimeError('固定依赖尚未准备；运行 python3 scripts/prepare_runtime.py，或使用 scripts/run.py 首次按需准备。')
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (base/(key+'.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if ready(target, key, content):
            return {'path': str(target), 'reused': True, 'key': key}
        if target.is_symlink():
            raise RuntimeError('依赖缓存目录不能是符号链接。')
        print('准备 Mermaid 固定依赖（npm ci，仅首次或锁文件变化时执行）…', file=sys.stderr, flush=True)
        with tempfile.TemporaryDirectory(prefix=key+'.tmp-', dir=base) as directory:
            staging = Path(directory)/'runtime'
            staging.mkdir(mode=0o700)
            for name, data in content.items():
                (staging/name).write_bytes(data)
            command(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund', '--prefer-offline'],
                    cwd=staging, env=dict(os.environ, PUPPETEER_SKIP_DOWNLOAD='true'))
            # 安装成功且版本一致后才发布；失败不污染正在使用的依赖。
            (staging/'.ready').write_text(key)
            if not ready(staging, key, content):
                raise RuntimeError('npm ci 未准备出与锁文件匹配的依赖。')
            if target.exists():
                shutil.rmtree(target)
            staging.replace(target)
        return {'path': str(target), 'reused': False, 'key': key}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只读检查；不安装、不联网')
    args = parser.parse_args()
    try:
        print(json.dumps(ensure_runtime(check=args.check), ensure_ascii=False))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, '依赖准备失败：'+str(exc)+'\n')
