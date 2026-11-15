#!/usr/bin/env python3
"""在隔离数据目录实际启动 Session Browser/oMLX；不使用现有服务端口和登录资料。"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import uuid


def port():
    with socket.socket() as stream:
        stream.bind(('127.0.0.1', 0))
        return stream.getsockname()[1]


@contextmanager
def server(command, log, environment):
    with log.open('w') as output:
        process = subprocess.Popen(command, env=environment, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            yield process
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)


def request(url, data=None, headers=None, timeout=15):
    # 本机验证不经过用户 HTTP_PROXY；只请求自己刚启动的随机 loopback 端口。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(url, data=data, headers=headers or {}), timeout=timeout) as response:
        return response.read()


def ready(process, url, headers=None):
    deadline = time.monotonic()+120
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('验证服务提前退出：'+str(process.returncode))
        try:
            return request(url, headers=headers, timeout=2)
        except OSError:
            time.sleep(0.5)
    raise TimeoutError('验证服务 120 秒内未就绪。')


def session_browser(base, environment):
    home = base/'session-home'
    sessions = home/'.codex/sessions/2026/11/15'
    sessions.mkdir(parents=True)
    session_id = str(uuid.uuid4())
    text = 'Feipi new Mac synthetic session'
    rows = [
        {'type': 'session_meta', 'payload': {'id': session_id, 'cwd': '/synthetic/new-mac', 'source': 'cli'}},
        {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
         'content': [{'type': 'input_text', 'text': text}]}},
        {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant',
         'content': [{'type': 'output_text', 'text': 'Verified local runtime.'}]}},
    ]
    for row in rows:
        row['timestamp'] = '2026-11-15T00:00:00Z'
    (sessions/('rollout-'+session_id+'.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in rows))
    (home/'.codex/session_index.jsonl').write_text(json.dumps({
        'id': session_id, 'thread_name': text, 'updated_at': '2026-11-15T00:00:00Z'})+'\n')
    endpoint = 'http://127.0.0.1:'+str(port())
    # HOME 与 JVM user.home 同时隔离，避免扫描操作者真实会话。
    env = dict(environment, HOME=str(home), JAVA_TOOL_OPTIONS='-Duser.home="'+str(home)+'"')
    command = [str(Path.home()/'.local/bin/session-browser'), 'serve', '--host', '127.0.0.1',
               '--port', endpoint.rsplit(':', 1)[1], '--index-dir='+str(base/'session-index')]
    with server(command, base/'session-browser.log', env) as process:
        ready(process, endpoint+'/healthz')
        deadline = time.monotonic()+120
        while time.monotonic() < deadline:
            summary = request(endpoint+'/api/sessions/summary')
            status = json.loads(request(endpoint+'/api/scan-status'))
            if (status.get('status') == 'success' and status.get('processedCount') == 1
                    and status.get('publishedProcessedCount') == 1 and status.get('errorCount') == 0
                    and json.loads(summary).get('totalCount') == 1):
                break
            if status.get('status') == 'failure':
                raise RuntimeError('Session Browser 合成会话扫描失败。')
            if process.poll() is not None:
                raise RuntimeError('Session Browser 扫描期间退出。')
            time.sleep(0.5)
        else:
            raise RuntimeError('Session Browser 未索引合成会话。')
        html = request(endpoint+'/')
        if b'<html' not in html.lower():
            raise RuntimeError('Session Browser 首页不是 HTML。')
        (base/'session-browser.html').write_bytes(html)
        (base/'session-summary.json').write_bytes(summary)
    return {'health': 'ok', 'synthetic_session_indexed': True, 'html_bytes': len(html)}


def omlx(base, environment, models):
    required = ['Qwen3.5-0.8B-MLX-4bit', 'Qwen3-ASR-1.7B-4bit', 'SenseVoiceSmall']
    for name in required:
        if not any((directory/name/'config.json').is_file() for directory in (models, models/'mlx-community')):
            raise RuntimeError('先恢复当前使用的模型：'+name)
    endpoint = 'http://127.0.0.1:'+str(port())
    token = uuid.uuid4().hex
    headers = {'Authorization': 'Bearer '+token}
    state = base/'omlx-state'
    settings_home = Path.home()/'.omlx'
    restored_settings = models == (settings_home/'models').resolve() and (settings_home/'settings.json').is_file()
    if restored_settings:
        # 在隔离副本中读取迁入配置，实际验证原生模型路径解析；不改动用户设置。
        state.mkdir()
        for name in ('settings.json', 'model_settings.json'):
            if (settings_home/name).is_file():
                shutil.copy2(settings_home/name, state/name)
    model_arguments = [] if restored_settings else ['--model-dir', str(models)]
    command = [str(Path.home()/'.local/bin/omlx'), 'serve', '--host', '127.0.0.1',
               '--port', endpoint.rsplit(':', 1)[1], '--base-path', str(state),
               *model_arguments, '--no-cache', '--api-key', token,
               '--max-concurrent-requests', '1']
    with server(command, base/'omlx.log', environment) as process:
        available = json.loads(ready(process, endpoint+'/v1/models', headers))['data']
        ids = [row['id'] for row in available]
        chosen = {}
        for name in required:
            matches = [item for item in ids if item == name or item.endswith('/'+name)]
            if len(matches) != 1:
                raise RuntimeError('模型发现结果缺失或歧义：'+name)
            chosen[name] = matches[0]
        response = json.loads(request(endpoint+'/v1/chat/completions', json.dumps({
            'model': chosen[required[0]], 'messages': [{'role': 'user', 'content': 'Reply with one short greeting.'}],
            'max_tokens': 16, 'temperature': 0}).encode(), dict(headers, **{'Content-Type': 'application/json'}), 180))
        content = response['choices'][0]['message']['content']
        if not content.strip():
            raise RuntimeError('oMLX 文本推理结果为空。')
        (base/'omlx-text.json').write_text(json.dumps(response, indent=2)+'\n')
        # 使用系统语音生成公开的验证句，不读取个人音频。
        subprocess.run(['/usr/bin/say', '-o', str(base/'sample.aiff'), 'Hello, this is a new machine test.'], check=True, timeout=60)
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(base/'sample.aiff'),
                        '-ar', '16000', '-ac', '1', str(base/'sample.wav')], check=True, timeout=60)
        transcriptions = {}
        for name in required[1:]:
            boundary = 'feipi-'+uuid.uuid4().hex
            payload = ('--'+boundary+'\r\nContent-Disposition: form-data; name="model"\r\n\r\n'+chosen[name]+'\r\n').encode()
            payload += ('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="sample.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode()
            payload += (base/'sample.wav').read_bytes()+('\r\n--'+boundary+'--\r\n').encode()
            result = json.loads(request(endpoint+'/v1/audio/transcriptions', payload,
                dict(headers, **{'Content-Type': 'multipart/form-data; boundary='+boundary}), 240))
            text = result.get('text', '')
            if 'hello' not in text.lower() or 'machine' not in text.lower():
                raise RuntimeError('语音验证句识别不符：'+name+'；见私有产物。')
            transcriptions[name] = text
        (base/'omlx-transcriptions.json').write_text(json.dumps(transcriptions, indent=2)+'\n')
    return {'text_inference': True, 'speech_models': list(transcriptions), 'restored_settings': restored_settings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=['all', 'session-browser', 'omlx'], default='all')
    parser.add_argument('--model-dir', type=Path, default=Path.home()/'.omlx/models')
    args = parser.parse_args()
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        parser.error('仅在 Apple Silicon macOS 真实验证。')
    os.umask(0o077)
    root = Path.home()/'.local/state/feipi-workbench/validation'
    root.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix='mac-extras-', dir=root))
    environment = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'LANG') if key in os.environ}
    source = Path(__file__).resolve().parents[3]
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--',
        'components/mac', 'scripts/workbench/main.py'], text=True).strip()
    files = [Path(__file__), Path(__file__).with_name('desktop-extras.sh'),
             Path(__file__).parents[1]/'config/desktop-extras.tsv']
    report = {'artifacts': str(base), 'checks': {}, 'source_commit': commit,
              'source_dirty': bool(dirty), 'system': platform.platform(),
              'source_sha256': {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    try:
        if args.only in ('all', 'session-browser'):
            report['checks']['session-browser'] = session_browser(base, environment)
        if args.only in ('all', 'omlx'):
            report['checks']['omlx'] = omlx(base, environment, args.model_dir.expanduser().resolve())
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (base/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print('实际功能验收产物：'+str(base))


if __name__ == '__main__':
    main()
