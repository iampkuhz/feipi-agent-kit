#!/usr/bin/env python3
"""用迁入的用户设置执行真实 CLI 文件任务；退出码和精确产物必须同时通过。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

from agents import ROOT, specs, version

PROOF = b'FEIPI_NEW_MAC_OK\n'
PROMPT = ('Create a file named proof.txt in the current directory containing exactly '
          'FEIPI_NEW_MAC_OK followed by one newline. Use the file writing tool, then finish. '
          'Do not read other files, use external tools, or delegate the task.')


def arguments(name):
    if name == 'codex':
        return ['exec', '--sandbox', 'workspace-write', '-c', 'approval_policy="never"',
                '--skip-git-repo-check', '--ephemeral', '--json', PROMPT]
    if name == 'qwen':
        return ['--prompt', PROMPT, '--approval-mode', 'auto-edit', '--output-format', 'json',
                '--max-session-turns', '3']
    if name == 'claude':
        return ['--tools', 'Write', '--allowedTools', 'Write', '--permission-mode', 'acceptEdits',
                '--no-session-persistence', '--output-format', 'json', '--max-budget-usd', '0.20',
                '--print', PROMPT]
    return ['--tools', 'Write', '--allowed-tools', 'Write', '--permission-mode', 'accept_edits',
            '--no-session-persistence', '--output-format', 'json', '--max-output-tokens', '512',
            '--print', PROMPT]


def check(spec, base):
    name = spec['name']
    folder = base/name
    work = folder/'workspace'
    work.mkdir(parents=True)
    result = {'passed': False, 'expected_version': spec['version'], 'workspace': str(work)}
    actual = version(name)
    result['version'] = actual
    if actual != spec['version']:
        result['failure'] = 'missing_cli' if actual is None else 'version_mismatch'
        return result
    environment = dict(os.environ, DISABLE_AUTOUPDATER='1')
    with (folder/'stdout.log').open('w') as output, (folder/'stderr.log').open('w') as error:
        process = subprocess.Popen([shutil.which(name), *arguments(name)], cwd=work,
                                   env=environment, stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=error, start_new_session=True)
        try:
            code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            code = 124
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
    proof = work/'proof.txt'
    exact = (proof.is_file() and not proof.is_symlink() and
             proof.stat().st_size == len(PROOF) and proof.read_bytes() == PROOF)
    result.update(exit_code=code, proof_matches=exact, passed=code == 0 and exact)
    if not result['passed']:
        result['failure'] = 'timeout' if code == 124 else 'native_task_failed'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', choices=('codex', 'qwen', 'claude', 'qodercli'), action='append',
                        help='只验收所选 CLI；默认逐项验收全部四个，单项失败不跳过其余项')
    args = parser.parse_args()
    os.umask(0o077)
    state = Path.home()/'.local/state/feipi-workbench/validation'
    state.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix='agent-tasks-', dir=state))
    report = {
        'source': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'source_dirty': bool(subprocess.check_output(
            ['git', '-C', str(ROOT), 'status', '--porcelain'], text=True)),
        'settings': 'native user configuration and inherited environment; no model override',
        'node': subprocess.check_output(['node', '--version'], text=True).strip(),
        'checks': {},
    }
    path = base/'report.json'
    print('私有日志及验收报告：'+str(path), flush=True)
    for spec in specs():
        name = spec['name']
        if args.cli and name not in args.cli:
            continue
        try:
            result = check(spec, base)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result = {'passed': False, 'failure': type(error).__name__}
        report['checks'][name] = result
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(name+('：真实文件任务通过' if result['passed'] else '：失败，请检查对应私有日志'), flush=True)
    return 0 if all(item['passed'] for item in report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
