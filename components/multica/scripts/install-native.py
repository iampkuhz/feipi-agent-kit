#!/usr/bin/env python3
"""从固定官方来源准备 Multica CLI 和单个 Compose；不登录、不启动、不覆盖。"""
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

ROOT = Path(__file__).resolve().parents[1]


def lock():
    data = json.loads((ROOT/'versions.json').read_text())
    expected = json.loads((ROOT/'config/agents.json').read_text())['compatibility']['multica']
    if (data['release'] != 'v'+expected
            or not re.fullmatch(r'[0-9a-f]{40}', data['upstream_commit'])
            or any(not re.fullmatch(r'[0-9a-f]{64}', data[key])
                   for key in ('cli_archive_sha256', 'compose_sha256'))):
        raise ValueError('Multica 版本、摘要与兼容清单不一致，未安装。')
    return data


def version(binary, expected):
    output = subprocess.check_output([str(binary), '--version'], text=True,
                                     stderr=subprocess.PIPE, timeout=30)
    found = re.search(r'^multica\s+(\d+\.\d+\.\d+)\b', output)
    if not found or found[1] != expected:
        raise ValueError('已有 Multica CLI 与锁定版本不同，未覆盖或降级；先审查迁移基线。')


def download(url, target, expected):
    subprocess.run(['curl', '-fLSs', '--retry', '2', '--connect-timeout', '15',
                    '--max-time', '300', url, '-o', str(target)], check=True, timeout=330)
    if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        raise ValueError('Multica 官方文件摘要不匹配，未发布。')


def safe_parent(target, home):
    for parent in target.parents:
        if parent == home:
            return
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError('安装父路径冲突，未写入：'+str(parent))
    raise ValueError('安装目标不在当前 HOME 内。')


def prepare(action):
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('该固定发布包仅用于 Apple Silicon macOS；未下载其他架构。')
    home = Path.home().resolve()
    if home == Path('/'):
        raise ValueError('请用普通用户的非根 HOME 安装。')
    data = lock()
    expected = data['release'][1:]
    cli = home/'.local/bin/multica'
    compose = home/'.local/share/multica/server/docker-compose.selfhost.yml'
    has_cli = cli.exists() or cli.is_symlink()
    if has_cli:
        if not cli.is_file() or not os.access(cli, os.X_OK):
            raise ValueError('Multica 命令路径已被占用，未覆盖。')
        version(cli, expected)
    else:
        executable = shutil.which('multica')
        if executable:
            version(executable, expected)
        # 包装入口固定调用 ~/.local/bin/multica；其他 PATH 位置不能代替它。
    if compose.exists() or compose.is_symlink():
        if (compose.is_symlink() or not compose.is_file()
                or hashlib.sha256(compose.read_bytes()).hexdigest() != data['compose_sha256']):
            raise ValueError('已有 Multica 服务定义与锁定内容不同，未覆盖。')
        has_compose = True
    else:
        has_compose = False
    if action == 'check':
        if not has_cli or not has_compose:
            raise ValueError('缺少固定程序或服务定义；执行 workbench install multica，或 install-native.py install。')
    elif not has_cli or not has_compose:
        # 在 HOME 内暂存；所有下载、摘要和程序版本通过后才发布，拒绝覆盖并发新建的文件。
        for target in (cli, compose):
            safe_parent(target, home)
        storage = home/'.local/share/multica'
        storage.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix='.native-', dir=storage) as directory:
            temporary = Path(directory)
            pending = []
            if not has_cli:
                archive = temporary/'cli.tar.gz'
                url = ('https://github.com/multica-ai/multica/releases/download/'+data['release']+
                       '/multica-cli-'+expected+'-darwin-arm64.tar.gz')
                download(url, archive, data['cli_archive_sha256'])
                with tarfile.open(archive) as packed:
                    matches = [member for member in packed.getmembers() if Path(member.name).name == 'multica']
                    if len(matches) != 1 or not matches[0].isfile():
                        raise ValueError('Multica 包中的程序缺失、重复或不是普通文件。')
                    binary = temporary/'multica'
                    # 只读取已校验包内的一个普通文件，不解压目录或链接。
                    binary.write_bytes(packed.extractfile(matches[0]).read())
                binary.chmod(0o755)
                version(binary, expected)
                pending.append((binary, cli, 0o755))
            if not has_compose:
                source = temporary/'docker-compose.selfhost.yml'
                url = ('https://raw.githubusercontent.com/multica-ai/multica/'+data['upstream_commit']+
                       '/docker-compose.selfhost.yml')
                download(url, source, data['compose_sha256'])
                pending.append((source, compose, 0o600))
            for source, target, mode in pending:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                source.chmod(mode)
                # 同文件系统的原生原子创建；目标出现即失败，不替换用户文件。
                os.link(source, target)
    print('Multica 固定程序与服务定义检查通过；登录、数据恢复和本机绑定另行执行。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'check'), nargs='?', default='check')
    args = parser.parse_args()
    os.umask(0o077)
    prepare(args.action)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
