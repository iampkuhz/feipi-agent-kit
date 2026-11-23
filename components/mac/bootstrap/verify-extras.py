#!/usr/bin/env python3
"""在隔离数据目录验证 oMLX 的文本与语音推理。"""
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


def omlx(base, environment, models):
    required = ['Qwen3.5-0.8B-MLX-4bit', 'Qwen3-ASR-1.7B-4bit', 'SenseVoiceSmall']
    for name in required:
        if not any((directory/name/'config.json').is_file() for directory in (models, models/'mlx-community')):
            raise RuntimeError('先从 Hugging Face 下载模型：mlx-community/'+name)
    endpoint = 'http://127.0.0.1:'+str(port())
    token = uuid.uuid4().hex
    headers = {'Authorization': 'Bearer '+token}
    state = base/'omlx-state'
    settings_home = Path.home()/'.omlx'
    model_settings = {}
    restored_settings = models == (settings_home/'models').resolve() and (settings_home/'settings.json').is_file()
    if restored_settings:
        # 在隔离副本中读取迁入配置，实际验证原生模型路径解析；不改动用户设置。
        state.mkdir()
        for name in ('settings.json', 'model_settings.json'):
            if (settings_home/name).is_file():
                shutil.copy2(settings_home/name, state/name)
        if (state/'model_settings.json').is_file():
            model_settings = json.loads((state/'model_settings.json').read_text()).get('models', {})
    model_arguments = [] if restored_settings else ['--model-dir', str(models)]
    command = [str(Path.home()/'.local/bin/omlx'), 'serve', '--host', '127.0.0.1',
               '--port', endpoint.rsplit(':', 1)[1], '--base-path', str(state),
               *model_arguments, '--no-cache', '--api-key', token,
               '--max-concurrent-requests', '1']
    with server(command, base/'omlx.log', environment) as process:
        available = json.loads(ready(process, endpoint+'/v1/models', headers))['data']
        (base/'omlx-models.json').write_text(json.dumps(available, indent=2)+'\n')
        ids = [row['id'] for row in available]
        chosen = {}
        for name in required:
            settings = next((value for key, value in model_settings.items()
                             if key == name or key.endswith('/'+name)), {})
            expected = settings.get('model_alias') or name
            matches = [item for item in ids if item == expected or item.endswith('/'+expected)]
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
    return {'text_inference': True, 'speech_models': list(transcriptions),
            'restored_settings': restored_settings, 'model_ids': chosen}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
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
        report['checks']['omlx'] = omlx(base, environment, args.model_dir.expanduser().resolve())
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (base/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print('实际功能验收产物：'+str(base))


if __name__ == '__main__':
    main()
