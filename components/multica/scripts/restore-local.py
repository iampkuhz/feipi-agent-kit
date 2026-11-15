#!/usr/bin/env python3
"""从同批小配置重建新机路径，保留业务 UUID，清除旧设备绑定；不启动或登录。"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.parse

from configure import SECRET_MAP, read_values
from container_engine import public_config

ROOT = Path(__file__).resolve().parents[1]
CONTROL_FILES = ('source-home.json', 'machine.reference.json', 'server.env',
                 'versions.json', 'compose.pinned.yml')


def verify_controls(batch):
    manifest = json.loads((batch/'SHA256SUMS.json').read_text())
    if not isinstance(manifest, dict):
        raise ValueError('Multica 备份清单格式无效。')
    for name in CONTROL_FILES:
        path = batch/name
        expected = manifest.get(name)
        if (not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected)
                or path.is_symlink() or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ValueError('Multica 控制配置缺少或校验失败：'+name+'；用当前入口重新备份。')
    saved = json.loads((batch/'versions.json').read_text())
    current = json.loads((ROOT/'versions.json').read_text())
    if not isinstance(saved, dict) or any(saved.get(key) != current[key] for key in ('release', 'upstream_commit')):
        raise ValueError('备份服务版本与当前迁移基线不同，未恢复。')
    if (batch/'compose.pinned.yml').read_bytes() != (ROOT/'config/compose.pinned.yml').read_bytes():
        raise ValueError('备份镜像锁定与当前迁移基线不同，未恢复。')
    metadata = json.loads((batch/'source-home.json').read_text())
    value = metadata.get('source_home') if isinstance(metadata, dict) else None
    if (not isinstance(metadata, dict) or metadata.get('schema') != 1
            or not isinstance(value, str) or not Path(value).is_absolute()
            or value == '/' or '..' in Path(value).parts):
        raise ValueError('备份原 HOME 记录无效，未恢复。')
    return Path(value)


def relocate_path(value, source_home, home):
    if not isinstance(value, str) or not value:
        raise ValueError('机器绑定中的路径无效。')
    path = home/value[2:] if value.startswith('~/') else Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('机器绑定中的路径必须是绝对路径或 ~/ 路径。')
    if path.is_relative_to(source_home):
        path = home/path.relative_to(source_home)
    return str(path)


def local_podman_name():
    rows = json.loads(subprocess.check_output(
        ['podman', 'machine', 'list', '--format', 'json'], text=True,
        stderr=subprocess.PIPE, timeout=15))
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError('本机 Podman machine 列表无效，未恢复。')
    if not rows:
        return 'podman-machine-default'  # 与原生 machine init 的默认名称一致。
    defaults = [row for row in rows if row.get('Default')]
    if len(defaults) != 1 or not isinstance(defaults[0].get('Name'), str) or not defaults[0]['Name']:
        raise ValueError('本机 Podman 默认 machine 不明确，未恢复。')
    return defaults[0]['Name']


def restore(batch, kit):
    home = Path.home().resolve()
    target = home/'.config/multica-selfhost'
    if home == Path('/') or os.path.lexists(target):
        raise ValueError('HOME 无效或 Multica 本机配置已存在，未覆盖。')
    for parent in target.parents:
        if parent == home:
            break
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError('Multica 本机配置父路径冲突，未写入。')
    kit = kit.expanduser().resolve()
    if not (kit/'workbench').is_file() or not (kit/'components/multica/versions.json').is_file():
        raise ValueError('Agent Kit 来源不是已克隆的统一仓库。')
    source_home = verify_controls(batch)
    if not (home/'.env').is_file():
        raise ValueError('先 restore-mac 恢复本机 env，再恢复 Multica 控制配置。')
    saved_keys = read_values(batch/'server.env', set(SECRET_MAP))
    vault_keys = read_values(home/'.env', set(SECRET_MAP.values()))
    if any(not saved_keys.get(key) or saved_keys[key] != vault_keys.get(source)
           for key, source in SECRET_MAP.items()):
        raise ValueError('同批服务密钥与本机 env 不一致，未生成替代值或恢复配置。')
    value = json.loads((batch/'machine.reference.json').read_text())
    if (not isinstance(value, dict) or value.get('schema') != 1
            or any(not isinstance(value.get(key), dict) for key in ('runtimes', 'commands', 'projects', 'agents'))
            or any(not isinstance(value.get(key), str) or not value[key]
                   for key in ('profile', 'workspace_id', 'server_url', 'app_url'))
            or not isinstance(value.get('startup', {}), dict)):
        raise ValueError('备份机器参考结构无效，未恢复。')
    value = copy.deepcopy(value)
    for key in ('server_url', 'app_url'):
        url = urllib.parse.urlsplit(value[key])
        if url.scheme not in ('http', 'https') or url.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('备份服务地址不是本机回环地址；先明确新机服务地址。')
    for key in ('workspaces_root', 'openclaw_source', 'openclaw_state'):
        if key in value:
            value[key] = relocate_path(value[key], source_home, home)
    for project in value['projects'].values():
        if not isinstance(project, dict) or 'root' not in project:
            raise ValueError('备份项目绑定无效，未恢复。')
        project['root'] = relocate_path(project['root'], source_home, home)
    # 路径按新机实际入口重建，避免把旧 Homebrew 路径写给 nvm 安装的 Codex。
    for key in sorted(set(value['commands']) | {'multica', 'codex'}):
        name = {'qoder': 'qodercli', 'openclaw-isolated': 'multica-openclaw'}.get(key, key)
        binary = str(home/'.local/bin/multica') if key == 'multica' else shutil.which(name)
        if not binary or not Path(binary).is_file() or not os.access(binary, os.X_OK):
            raise ValueError('缺少新机程序入口：'+name+'；先完成锁定程序安装和环境激活。')
        value['commands'][key] = str(Path(binary).absolute())
    value.update(role='primary', device_name=platform.node(), daemon_id=None, agent_kit=str(kit))
    if 'openclaw_source' in value:
        value['openclaw_source'] = str(kit/'components/openclaw/openclaw.json')
    for runtime in value['runtimes'].values():
        if not isinstance(runtime, dict) or not isinstance(runtime.get('provider'), str) or not runtime['provider']:
            raise ValueError('备份 runtime 提供方无效，未恢复。')
        runtime['id'] = None  # 只保留逻辑 profile/provider；新设备须原生注册后 rebind。
    value.setdefault('startup', {})['podman_machine'] = local_podman_name()
    docker = public_config()
    with tempfile.TemporaryDirectory(prefix='.multica-local-', dir=home) as temporary:
        stage = Path(temporary)/'multica-selfhost'; stage.mkdir(mode=0o700)
        (stage/'machine.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
        (stage/'server.env').write_bytes((batch/'server.env').read_bytes())
        (stage/'docker-public').mkdir(mode=0o700)
        (stage/'docker-public/config.json').write_text(json.dumps(docker)+'\n')
        for name in ('machine.json', 'server.env', 'docker-public/config.json'):
            (stage/name).chmod(0o600)
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(target):
            raise ValueError('恢复期间目标已出现，未覆盖。')
        stage.rename(target)
    print('Multica 控制配置已恢复；旧 daemon/runtime 绑定已清空。')
    print('未读取数据库或附件，未复制登录身份、启动服务或创建项目目录；继续同批数据恢复、原生登录和 rebind。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch', type=Path)
    parser.add_argument('--agent-kit', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    restore(args.batch.expanduser().resolve(), args.agent_kit)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
