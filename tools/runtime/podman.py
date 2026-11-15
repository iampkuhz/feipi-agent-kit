#!/usr/bin/env python3
"""仅准备默认本机 Podman；不切换连接、不重建或停止已有 machine。"""
import argparse
import json
import os
import platform
import subprocess
import time
import urllib.parse


def command(*args, timeout=15, capture=True):
    result = subprocess.run(['podman', *args], check=True, timeout=timeout,
                            capture_output=capture, text=True)
    return result.stdout if capture else ''


def local_connection():
    if os.environ.get('CONTAINER_HOST') or os.environ.get('CONTAINER_CONNECTION'):
        raise ValueError('请清除 CONTAINER_HOST/CONTAINER_CONNECTION；未修改 Podman。')
    connections = json.loads(command('system', 'connection', 'list', '--format', 'json')) or []
    defaults = [item for item in connections if item.get('Default')]
    if len(defaults) > 1 or (connections and not defaults):
        raise ValueError('Podman 默认连接不明确；未选择或切换连接。')
    if defaults:
        uri = urllib.parse.urlsplit(defaults[0].get('URI', ''))
        if not (uri.scheme == 'unix' or (uri.scheme == 'ssh' and
                uri.hostname in {'localhost', '127.0.0.1', '::1'})):
            raise ValueError('默认 Podman 连接不是本机；未修改任何 machine。')
    return defaults[0] if defaults else None


def ensure():
    connection = local_connection()
    if platform.system() == 'Darwin':
        support = subprocess.run(['/usr/sbin/sysctl', '-n', 'kern.hv_support'],
                                 capture_output=True, text=True, timeout=10)
        if support.returncode or support.stdout.strip() != '1':
            raise ValueError('当前 macOS 不提供本地虚拟化能力（kern.hv_support != 1）；未下载或创建 Podman machine。请在支持虚拟化的物理 Mac 上验收容器服务。')
        machines = json.loads(command('machine', 'list', '--format', 'json')) or []
        if not machines:
            if connection:
                raise ValueError('有连接但没有本机 machine，拒绝自动接管；请检查已有连接。')
            print('首次创建默认本机 Podman machine。', flush=True)
            command('machine', 'init', timeout=900, capture=False)
            connection = local_connection()
            machines = json.loads(command('machine', 'list', '--format', 'json')) or []
        candidates = [item for item in machines if item.get('Default')]
        if len(candidates) != 1:
            raise ValueError('未找到唯一默认 machine，拒绝选择其他虚拟机。')
        machine = candidates[0]
        name = machine['Name']
        if not connection or connection.get('Name') not in {name, name+'-root'}:
            raise ValueError('默认连接与默认 machine 不一致，未切换连接或启动虚拟机。')
        if not machine.get('Running') and not machine.get('Starting'):
            print('启动已有默认 machine：'+name, flush=True)
            command('machine', 'start', name, timeout=300, capture=False)
    # machine start 返回后 socket 可能尚未就绪；只等待，不重复 start/init。
    deadline = time.monotonic()+90
    while True:
        try:
            command('info', timeout=10)
            break
        except (subprocess.SubprocessError, OSError):
            if time.monotonic() >= deadline:
                raise RuntimeError('Podman 未在期限内就绪；保留 machine 状态，请检查 podman machine inspect。')
            time.sleep(2)
    print('默认本机 Podman 已就绪。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'ensure'])
    args = parser.parse_args()
    if args.action == 'ensure':
        ensure()
    else:
        local_connection()
        command('info')
        print('默认本机 Podman 检查通过；未创建或启动 machine。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
