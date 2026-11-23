#!/usr/bin/env python3
"""检查 Agent CLI 并通过包管理器补装缺项。"""
import argparse
import os
import shutil
import subprocess

INSTALL_COMMANDS = {
    'codex': ('brew', 'install', '--cask', 'codex'),
    'qwen': ('npm', 'install', '-g', '--no-audit', '--no-fund', '@qwen-code/qwen-code@latest'),
    'claude': ('brew', 'install', '--cask', 'claude-code'),
    'qodercli': ('brew', 'install', '--cask', 'qoderai/qoder/qodercli'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'install', 'check'], default='check', nargs='?')
    args = parser.parse_args()
    missing = []
    # 先检查命令路径，已有安装沿用原渠道。
    for name in INSTALL_COMMANDS:
        path = shutil.which(name)
        if path:
            print(f'{name}：{path}', flush=True)
        else:
            print(f'{name}：缺失，可运行 {" ".join(INSTALL_COMMANDS[name])}', flush=True)
            missing.append(name)
    if args.action == 'plan':
        return
    if args.action == 'check' and missing:
        raise ValueError('缺少 Agent CLI：'+', '.join(missing))
    for name in missing:
        # 初始化只补装清单缺项，沿用 Homebrew 的非自动升级策略。
        subprocess.run(INSTALL_COMMANDS[name], check=True, timeout=1200,
                       env=dict(os.environ, HOMEBREW_NO_AUTO_UPDATE='1', HOMEBREW_NO_INSTALL_UPGRADE='1'))
        if not shutil.which(name):
            raise ValueError(name+' 安装后未出现在 PATH 中。')
    print('四个 Agent CLI 均已找到；账号认证和真实任务另行验收。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
