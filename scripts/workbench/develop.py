#!/usr/bin/env python3
"""组件源码入口；运行测试与源码命令不会自动发布到日常环境。"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PATHS = {'mac': ROOT/'components/mac', 'multica': ROOT/'components/multica',
         'openclaw': ROOT/'components/openclaw', 'openclash': ROOT/'components/openclash',
         'skills': ROOT, 'services': ROOT, 'workbench': ROOT}


def main():
    p = argparse.ArgumentParser(description='研发：定位源码、回归、显式调试；日常应用用 ./workbench apply <组件>。')
    p.add_argument('component', choices=PATHS)
    p.add_argument('action', choices=['path', 'test', 'run', 'link'])
    p.add_argument('args', nargs=argparse.REMAINDER)
    a = p.parse_args()
    root = PATHS[a.component]
    if a.action == 'path':
        print(root)
        return 0
    if a.action == 'run':
        args = a.args[1:] if a.args[:1] == ['--'] else a.args
        if not args:
            p.error('run 后需要源码命令，例如 ./develop mac run -- bash bootstrap/brew.sh check')
        print('显式运行源码：'+str(root), flush=True)
        return subprocess.run(args, cwd=root).returncode
    if a.action == 'link':
        if a.component == 'skills':
            print('显式启用源码链接：编辑会影响已链接的 Skills；退出调试用 workbench apply skills。', flush=True)
            return subprocess.run(['bash', str(ROOT/'scripts/install_skills.sh'), *a.args]).returncode
        p.error('只提供 Skills 的链接调试；其他组件用 run 或隔离目录。')
    commands = {
        'mac': [['bash', 'bootstrap/test.sh']],
        'multica': [['/usr/bin/python3', '-m', 'unittest', 'discover', '-s', 'tests', '-v']],
        'openclaw': [['make', 'test'], ['bash', 'scripts/validate-config.sh']],
        'openclash': [['python3', 'router.py', 'test']],
        'skills': [['bash', 'scripts/harness/doctor.sh']],
        'services': [['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_service*.py']],
        'workbench': [['python3', '-m', 'unittest', 'discover', '-s', 'tests/workbench', '-v']],
    }
    for command in commands[a.component]:
        result = subprocess.run(command, cwd=root)
        if result.returncode:
            return result.returncode
    print('研发检查已结束；真实功能验收另做。')
    if a.component != 'workbench':
        print('进入日常环境：./workbench diff '+a.component+'；./workbench apply '+a.component)
    return 0


if __name__ == '__main__':
    sys.exit(main())
