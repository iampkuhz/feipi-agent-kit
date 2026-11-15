#!/usr/bin/env python3
"""派生本机 Docker API 套接字与独立 Compose 插件路径，不创建或切换容器引擎。"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import urllib.parse


def environment():
    home = Path.home()
    result = {name: os.environ[name] for name in ('PATH', 'HOME', 'TMPDIR') if name in os.environ}
    uri = os.environ.get('DOCKER_HOST')
    if not uri:
        binding = home/'.config/multica-selfhost/machine.json'
        machine = json.loads(binding.read_text()).get('startup', {}).get('podman_machine') if binding.is_file() else None
        if machine:
            # machine inspect 查询本机元数据；不继承远端连接或其他业务环境变量。
            output = subprocess.check_output(['podman', 'machine', 'inspect', machine], env=result,
                                             text=True, timeout=15)
            rows = json.loads(output)
            if len(rows) != 1 or rows[0].get('Name') != machine or rows[0].get('State') != 'running':
                raise ValueError('绑定的本机 Podman machine 未运行；先执行 workbench service podman ensure。')
            path = rows[0].get('ConnectionInfo', {}).get('PodmanSocket', {}).get('Path')
            if not path:
                raise ValueError('Podman 未提供本机 Docker API socket。')
            uri = 'unix://'+path
        else:
            uri = 'unix:///var/run/docker.sock'
    parsed = urllib.parse.urlsplit(uri)
    if parsed.scheme != 'unix' or parsed.netloc or parsed.query or parsed.fragment or not parsed.path.startswith('/'):
        raise ValueError('Multica 仅使用本机 unix Docker API socket；拒绝远端 DOCKER_HOST。')
    path = Path(urllib.parse.unquote(parsed.path))
    if not path.exists() or not stat.S_ISSOCK(path.stat().st_mode):
        raise ValueError('本机 Docker API socket 不可用；先启动绑定的 Podman machine。')
    result['DOCKER_HOST'] = 'unix://'+str(path)
    return result


def public_config():
    source = Path.home()/'.docker/config.json'
    directories = json.loads(source.read_text()).get('cliPluginsExtraDirs', []) if source.is_file() else []
    if not isinstance(directories, list) or not all(isinstance(item, str) for item in directories):
        raise ValueError('Docker cliPluginsExtraDirs 必须是路径列表。')
    docker = shutil.which('docker')
    if docker:
        # Homebrew 的 docker-compose 采用独立插件目录；全新 HOME 没有旧机 ~/.docker 配置。
        candidate = Path(docker).absolute().parent.parent/'lib/docker/cli-plugins'
        if (candidate/'docker-compose').is_file():
            directories = [*directories, str(candidate)]
    return {'auths': {}, 'cliPluginsExtraDirs': list(dict.fromkeys(directories))}


if __name__ == '__main__':
    try:
        print(environment()['DOCKER_HOST'])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
