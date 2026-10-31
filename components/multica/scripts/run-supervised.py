#!/usr/bin/env python3
"""按机器绑定启动本栈，检查模型依赖后运行唯一的后台 daemon。"""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from adaptation import expand, machine

m = machine()
if m.get('role') != 'primary':
    sys.exit('This machine is a temporary client; disable its managed LaunchAgent.')
root = Path(__file__).resolve().parent.parent
directories = list(dict.fromkeys(str(Path(expand(p)).parent) for p in m.get('commands', {}).values()))
os.environ['PATH'] = os.pathsep.join(directories + [os.environ.get('PATH', '')])
service = str(root / 'bin/multica-service')
podman_name = m.get('startup', {}).get('podman_machine')
if podman_name:
    import json
    entries = json.loads(subprocess.check_output(['podman', 'machine', 'list', '--format', 'json'], text=True))
    selected = [entry for entry in entries if entry['Name'] == podman_name]
    if len(selected) != 1:
        sys.exit('Configured Podman machine missing; create it explicitly before startup.')
    if not selected[0]['Running']:
        subprocess.run(['podman', 'machine', 'start', podman_name], check=True, timeout=120)
for attempt in range(45):
    try:
        subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=True)
        break
    except (subprocess.SubprocessError, OSError):
        if attempt == 0:
            print('Waiting for configured container engine.', flush=True)
        time.sleep(2)
else:
    sys.exit('Container engine unavailable; launchd will retry.')
subprocess.run([service, 'up', '-d', '--pull', 'never'], check=True, timeout=90)
# 只启动绑定中明确列出的既有依赖，不创建、升级或重配它们。
for name in m.get('startup', {}).get('podman_containers', []):
    import json
    entries = json.loads(subprocess.check_output(['podman', 'ps', '-a', '--format', 'json'], text=True))
    selected = [entry for entry in entries if name in entry.get('Names', [])]
    if len(selected) != 1:
        sys.exit('Configured dependency container missing: ' + name)
    if selected[0].get('State') != 'running':
        subprocess.run(['podman', 'start', name], check=True, timeout=60)
# LiteLLM 由它自己的服务管理器维护；这里只验证依赖，不重启个人 Gateway。
for label, url in [('Multica', m['server_url'].rstrip('/') + '/readyz'), ('LiteLLM', m['litellm_readiness_url'])]:
    for attempt in range(30):
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    break
        except OSError:
            pass
        time.sleep(2)
    else:
        sys.exit(label + ' readiness unavailable; daemon deferred, launchd will retry.')
# 发现能力与启动包装命令必须使用同一来源。此环境仅作用于本 daemon 及子进程。
state = expand(m['openclaw_state'])
os.environ['OPENCLAW_STATE_DIR'] = state
os.environ['OPENCLAW_CONFIG_PATH'] = str(Path(state) / 'openclaw.json')
os.environ['CLAWDBOT_CONFIG_PATH'] = str(Path(state) / 'openclaw.json')
binary = expand(m['commands']['multica'])
os.execv(binary, [binary, '--profile', m['profile'], 'daemon', 'start', '--foreground'])
