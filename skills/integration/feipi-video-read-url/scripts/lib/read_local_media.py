#!/usr/bin/env python3
"""本地视频/音频适配：保留完整首条音轨，复用既有 oMLX 与摘要文本合同。"""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave

from video_identity import clean
from verify_cached_audio import digest_file
from split_audio import audio_properties

HERE = Path(__file__).resolve().parent


def write_json(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as target:
            temporary = Path(target.name)
            json.dump(value, target, ensure_ascii=False, indent=2)
            target.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def read_json(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def extract_audio(media, audio, source_hash, manifest):
    previous = read_json(manifest)
    try:
        rate, frames = audio_properties(audio)
        metadata_matches = (previous.get("schema") == "local-media-v1" and previous.get("frames") == frames
                            and previous.get("sample_rate") == rate
                            and previous.get("duration_seconds") == frames / rate)
    except (OSError, ValueError, wave.Error, EOFError):
        metadata_matches = False
    if (metadata_matches and previous.get("media_sha256") == source_hash
            and previous.get("audio_sha256") == digest_file(audio)):
        if previous.get("input_path") != str(media):
            previous["input_path"] = str(media)
            write_json(manifest, previous)
        return previous, True
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", dir=audio.parent, delete=False) as target:
            temporary = Path(target.name)
        result = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-y", "-i", str(media),
                                 "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                                 str(temporary)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode:
            raise ValueError("local_audio_decode_failed；未替换已有音频")
        rate, frames = audio_properties(temporary)
        if digest_file(media) != source_hash:
            raise ValueError("local_media_changed_during_decode；请等待源文件写入完成")
        record = {"schema": "local-media-v1", "input_path": str(media), "media_sha256": source_hash,
                  "audio_sha256": digest_file(temporary), "audio_path": str(audio),
                  "audio_stream": "0:a:0", "sample_rate": rate, "frames": frames,
                  "duration_seconds": frames / rate}
        os.replace(temporary, audio)
        write_json(manifest, record)
        return record, False
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("mode", choices=("dryrun", "video", "audio", "auto", "whisper", "subtitle"))
    parser.add_argument("profile", choices=("auto", "fast", "accurate"))
    parser.add_argument("--check-deps", action="store_true")
    args = parser.parse_args()
    media = args.media.expanduser().resolve(strict=True)
    if not media.is_file():
        raise ValueError("local_media_requires_regular_file")
    if any(c in str(media) for c in "\r\n"):
        raise ValueError("local_media_path_contains_line_break")
    if args.mode == "subtitle":
        raise ValueError("local_subtitle_not_supported；本地文件请使用 auto 或 whisper 转写首条音轨")
    for name in ("ffmpeg", "ffprobe"):
        if not shutil.which(name):
            raise ValueError("local_media_dependency_missing: " + name)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                            "stream=index", "-of", "json", str(media)], capture_output=True, text=True)
    if probe.returncode or not json.loads(probe.stdout).get("streams"):
        raise ValueError("local_media_has_no_decodable_audio_stream")
    source_hash = digest_file(media)
    root = args.output_root.expanduser().resolve() / ("local-" + source_hash[:32])
    profile = "fast" if args.profile == "auto" else args.profile
    if args.check_deps:
        result = subprocess.run([sys.executable, str(HERE / "omlx_transcribe.py"), "--check", profile])
        if result.returncode:
            return result.returncode
        print(f"dependency_ok=1\nsource=local\nrun_dir={root}\nwhisper_profile={profile}")
        return 0
    if args.mode in ("dryrun", "video"):
        print(f"source=local\nmode={args.mode}\nmedia_path={media}\nmedia_sha256={source_hash}")
        return 0
    root.mkdir(parents=True, exist_ok=True)
    audio, prefix = root / "media.whisper.wav", root / "media"
    source_record, reused = extract_audio(media, audio, source_hash, root / "source_media.json")
    identity = {"schema_version": 1, "input_url": str(media), "platform": "本地文件",
                "video_id": source_hash[:32], "video_title": clean(media.stem), "title_source": "local_filename",
                "suggested_thread_title": "本地文件｜" + clean(media.stem)[:25]}
    write_json(root / "video_identity.json", identity)
    print(f"source=local\nrun_dir={root}\naudio_path={audio}\naudio_reused={int(reused)}\n"
          f"source_manifest={root / 'source_media.json'}\nmedia_sha256={source_hash}\n"
          f"duration_sec={math.ceil(source_record['duration_seconds'])}\n"
          f"audio_duration_seconds={source_record['duration_seconds']}", flush=True)
    for key in ("platform", "video_id", "video_title", "title_source", "suggested_thread_title"):
        print(f"{key}={identity[key]}")
    print(f"identity_path={root / 'video_identity.json'}\nwhisper_profile={profile}", flush=True)
    if args.mode == "audio":
        print("mode=audio")
        return 0
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    log = logs / "local-whisper.log"
    with log.open("w") as target:
        result = subprocess.run([sys.executable, str(HERE / "omlx_transcribe.py"), str(audio), str(prefix),
                                 "auto", profile], stdout=target, stderr=subprocess.STDOUT)
    if result.returncode:
        print(f"failure_stage=transcription\nfailure_log={log}", file=sys.stderr)
        # 客户端只输出状态和认证来源，绝不回显服务错误体或密钥。
        print(log.read_text(), file=sys.stderr)
        return result.returncode
    for line in log.read_text().splitlines():
        if line.startswith(("asr_", "cache_reused=", "model=")):
            print(line)
    print(f"mode=whisper\nstrategy=local_audio_asr\ntext_path={prefix}.txt\nsrt_path={prefix}.srt\nlog_dir={logs}\n"
          f"long_video={int(source_record['duration_seconds'] > 1800)}\nestimated_risk=asr_recognition")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, wave.Error, EOFError) as error:
        print(f"本地媒体处理失败: {error}", file=sys.stderr)
        sys.exit(1)
