#!/usr/bin/env python3
"""流式核对完整视频的16kHz单声道PCM和既有WAV，禁止改写媒体。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave
from datetime import datetime


def digest_file(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for part in iter(lambda: source.read(1024 * 1024), b''):
            result.update(part)
    return result.hexdigest()


def verify(video, audio):
    with wave.open(str(audio), 'rb') as cached:
        if (cached.getnchannels(), cached.getframerate(), cached.getsampwidth(),
                cached.getcomptype()) != (1, 16000, 2, 'NONE'):
            raise ValueError('既有音频必须为16kHz单声道16-bit PCM WAV')
        expected_bytes = cached.getnframes() * 2
        old_hash, old_bytes = hashlib.sha256(), 0
        for part in iter(lambda: cached.readframes(65536), b''):
            old_hash.update(part)
            old_bytes += len(part)
    if not old_bytes or old_bytes != expected_bytes:
        raise ValueError('既有WAV为空或PCM数据截断')
    new_hash, new_bytes = hashlib.sha256(), 0
    process = subprocess.Popen(
        ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video), '-vn', '-ac', '1',
         '-ar', '16000', '-c:a', 'pcm_s16le', '-f', 's16le', '-'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for part in iter(lambda: process.stdout.read(1024 * 1024), b''):
            new_hash.update(part)
            new_bytes += len(part)
    finally:
        process.stdout.close()
        code = process.wait()
    if code:
        raise ValueError(f'完整视频音轨解码失败，ffmpeg退出码{code}')
    if (new_bytes, new_hash.digest()) != (old_bytes, old_hash.digest()):
        raise ValueError('既有音频与当前视频重新解码的PCM不一致；未改写原件')
    return dict(checked_at=datetime.now().astimezone().isoformat(timespec='seconds'),
                video_sha256=digest_file(video), audio_sha256=digest_file(audio),
                channels=1, sample_rate=16000, sample_width=2,
                pcm_bytes=old_bytes, pcm_sha256=old_hash.hexdigest(),
                decode_exit_code=code, decoded_pcm_identical=True,
                media_modified=False, media_payload_files_created=False)


def main():
    if len(sys.argv) != 4:
        raise SystemExit('用法: verify_cached_audio.py <video> <wav> <validation.json>')
    try:
        result = verify(Path(sys.argv[1]), Path(sys.argv[2]))
    except (ValueError, OSError, wave.Error, EOFError) as error:
        print(f'diagnostic_code=drvoice_audio_cache_mismatch\n{error}', file=sys.stderr)
        return 1
    output = Path(sys.argv[3])
    temporary = output.with_name(output.name + '.partial')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(output)
    print('audio_pcm_verified=true')
    return 0


if __name__ == '__main__':
    sys.exit(main())
