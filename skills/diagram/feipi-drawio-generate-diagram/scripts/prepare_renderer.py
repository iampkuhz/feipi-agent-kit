#!/usr/bin/env python3
"""显式准备专用 renderer，完成后重新执行只读预检。"""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import threading

from renderer import RendererError, failure, preflight

TOOL_FILES = ('drawio.sh', 'runtime.py', 'network.py', 'Containerfile', 'server.py', 'render.js')


def find_tool_dir(explicit=None):
    if explicit is not None:
        candidates = [Path(explicit).expanduser().resolve()]
    else:
        script = Path(__file__).absolute()
        roots = list(script.resolve().parents)
        marker = script.parent.parent / '.feipi-agent-kit-source'
        if marker.is_file():
            roots.extend(Path(marker.read_text(encoding='utf-8').strip()).parents)
        candidates = [root / 'tools/diagram/drawio' for root in roots]
    for candidate in candidates:
        if all((candidate / name).is_file() for name in TOOL_FILES):
            return candidate
    checkout = Path.home() / '.local/share/feipi-agent-kit'
    raise RendererError('preparation_tool_missing', '未找到完整的 draw.io 准备工具；安装后的 skill 首次准备需要 Agent Kit 源码',
                        next_steps=[shlex.join(['git', 'clone', '--depth', '1',
                                              'https://github.com/iampkuhz/feipi-agent-kit.git', str(checkout)]),
                                    shlex.join(['python3', str(Path(__file__).absolute()), '--tool-dir',
                                                str(checkout / 'tools/diagram/drawio')])])


def prepare(tool_dir=None):
    tool = find_tool_dir(tool_dir)
    command = ['bash', str(tool / 'drawio.sh'), 'ensure']
    try:
        # 构建日志直接保留，不把下载或构建错误折叠成一个退出码。
        process = subprocess.Popen(command, start_new_session=True, stderr=subprocess.PIPE,
                                   text=True, errors='replace')
    except OSError as exc:
        raise RendererError('preparation_failed', f'准备工具未完成: {exc}', command=command) from exc
    diagnostics = []
    def relay_stderr():
        try:
            for line in process.stderr:
                sys.stderr.write(line)
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and data.get('status') == 'blocked':
                    diagnostics.append(data)
                    del diagnostics[:-8]
        finally:
            process.stderr.close()
    reader = threading.Thread(target=relay_stderr, daemon=True)
    reader.start()
    try:
        timeout = 3600 if os.environ.get('AGENT_DRAWIO_ALLOW_SLOW_DOWNLOAD') == '1' else 1800
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # 清理整个独立客户端进程组，避免只杀父进程后留下下载/构建客户端。
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue
        reader.join(timeout=5)
        raise RendererError('preparation_timeout', f'环境准备超过 {timeout} 秒，已终止本轮客户端；请检查构建日志',
                            command=command) from exc
    reader.join(timeout=5)
    if code:
        # 内层代理诊断比外层泛化失败更具体；实时日志和最终 JSON 都保留它。
        detail = next((d for d in reversed(diagnostics) if d.get('proxy_probe') is not None), None)
        detail = detail or next((d for d in reversed(diagnostics) if d.get('code')), None)
        if detail:
            error = RendererError(detail.get('code', 'preparation_failed'), detail['reason'])
            error.details.update({key: value for key, value in detail.items() if key not in ('status', 'reason')})
            error.details.setdefault('exit_code', code)
            raise error
        if code == 75:
            error = RendererError('download_confirmation_required', '下载或初始化耗时过长，需要用户确认；上方保留代理探测和阶段诊断',
                                  command=command, exit_code=code)
            error.details['confirmation_required'] = True
            raise error
        raise RendererError('preparation_failed', '准备工具失败；上方保留原始诊断',
                            command=command, exit_code=code)
    return preflight(existing_only=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool-dir', type=Path, help='仅独立拷贝且无法定位源码时指定 tools/diagram/drawio 路径')
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.tool_dir), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps(failure(exc), ensure_ascii=False))
        sys.exit(2)
