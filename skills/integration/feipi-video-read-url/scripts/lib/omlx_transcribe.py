#!/usr/bin/env python3
"""调用 oMLX ASR；按音频块保留时间范围，完成全部识别后才发布结果。"""

import argparse
import hashlib
import http.client
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import wave

MODELS = {"fast": "sensevoicesmall", "accurate": "qwen3-asr-1.7b"}
CHUNK_SECONDS = 30
CACHE_SCHEMA = "omlx-asr-v1"


def effective_profile(profile):
    return "fast" if profile == "auto" else profile


def request_json(base, path, body=None, content_type=None):
    headers = {}
    key = os.environ.get("AGENT_OMLX_API_KEY", "")
    if key:
        headers["Authorization"] = "Bearer " + key
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(base + path, data=body, headers=headers)
    # 本地推理不走系统 HTTP 代理，避免音频发往代理或被代理环境变量干扰。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=180 if body is not None else 10) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        # 服务错误体可能包含上传内容或凭据，日志仅保留状态码。
        hint = "，请设置 AGENT_OMLX_API_KEY" if error.code == 401 else ""
        raise ValueError("omlx_http_error: HTTP {}{}".format(error.code, hint)) from error
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise ValueError("omlx_service_unavailable_or_invalid_json") from error
    if not isinstance(result, dict):
        raise ValueError("omlx_invalid_response")
    return result


def resolve_model(base, profile):
    family = re.sub(r"[^a-z0-9]", "", MODELS[profile])
    candidates = []
    data = request_json(base, "/models").get("data")
    if not isinstance(data, list):
        raise ValueError("omlx_invalid_model_list")
    for item in data:
        model = item.get("id", "") if isinstance(item, dict) else ""
        if not isinstance(model, str):
            continue
        normalized = re.sub(r"[^a-z0-9]", "", model.rsplit("/", 1)[-1].lower())
        if re.fullmatch(family + r"(?:bf16|fp16|4bit|8bit)?", normalized):
            candidates.append(model)
    if len(candidates) != 1:
        raise ValueError("omlx_model_{}: {}，请在 oMLX 中提供唯一对应模型".format(
            "missing" if not candidates else "ambiguous", MODELS[profile]))
    return candidates[0]


def fingerprint(audio, profile, language):
    digest = hashlib.sha256()
    with audio.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return {"schema": CACHE_SCHEMA, "backend": "omlx", "profile": profile,
            "model_family": MODELS[profile], "language": language,
            "audio_sha256": digest.hexdigest(), "chunk_seconds": CHUNK_SECONDS}


def cached(prefix, expected):
    try:
        record = json.loads(Path(str(prefix) + ".asr.json").read_text())
        if not isinstance(record, dict):
            return None
        if not isinstance(record.get("model"), str) or not record["model"]:
            return None
        if not all(record.get(key) == value for key, value in expected.items()):
            return None
        data = Path(str(prefix) + ".srt").read_bytes()
        if not data or hashlib.sha256(data).hexdigest() != record.get("srt_sha256"):
            return None
        # TXT 是派生产物，中断造成缺失或半份时从完整 SRT 恢复，无需重复识别。
        target = Path(str(prefix) + ".txt")
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != record.get("text_sha256"):
            from subtitle_to_text import convert
            convert(Path(str(prefix) + ".srt"), target)
        return record
    except (OSError, ValueError):
        return None


def multipart(model, language, payload):
    boundary = "feipi" + uuid.uuid4().hex
    fields = {"model": model, "response_format": "json"}
    if language != "auto":
        fields["language"] = language
    body = bytearray()
    for name, value in fields.items():
        body.extend(('--{}\r\nContent-Disposition: form-data; name="{}"\r\n\r\n{}\r\n'
                     .format(boundary, name, value)).encode())
    body.extend(('--{}\r\nContent-Disposition: form-data; name="file"; filename="chunk.wav"\r\n'
                 'Content-Type: audio/wav\r\n\r\n'.format(boundary)).encode())
    body.extend(payload)
    body.extend(('\r\n--{}--\r\n'.format(boundary)).encode())
    return bytes(body), "multipart/form-data; boundary=" + boundary


def stamp(seconds):
    milliseconds = round(seconds * 1000)
    whole, ms = divmod(milliseconds, 1000)
    minutes, second = divmod(whole, 60)
    hour, minute = divmod(minutes, 60)
    return "{:02d}:{:02d}:{:02d},{:03d}".format(hour, minute, second, ms)


def transcribe(audio, prefix, language, profile, base):
    expected = fingerprint(audio, profile, language)
    record = cached(prefix, expected)
    if record:
        return record, True
    model = resolve_model(base, profile)
    rows, chunks = [], []
    with wave.open(str(audio), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, 16000, "NONE"):
            raise ValueError("omlx_audio_requires_16khz_mono_pcm_s16le")
        frames = source.getnframes()
        if frames <= 0:
            raise ValueError("omlx_empty_audio")
        for offset in range(0, frames, CHUNK_SECONDS * 16000):
            count = min(CHUNK_SECONDS * 16000, frames - offset)
            pcm = source.readframes(count)
            if len(pcm) != count * 2:
                raise ValueError("omlx_truncated_audio")
            payload = io.BytesIO()
            with wave.open(payload, "wb") as target:
                target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                target.writeframes(pcm)
            body, content_type = multipart(model, language, payload.getvalue())
            result = request_json(base, "/audio/transcriptions", body, content_type)
            text = result.get("text")
            if not isinstance(text, str):
                raise ValueError("omlx_invalid_transcription_text")
            # SenseVoice 的语言/情绪标签属于控制信息，不混入摘要正文。
            text = re.sub(r"<\|[^|]*\|>", "", text).strip()
            start, end = offset / 16000, (offset + count) / 16000
            chunks.append({"start": start, "end": end, "text": text})
            if text:
                rows.append((start, end, " ".join(text.split())))
            print("asr_chunk={}/{}".format(len(chunks), math.ceil(frames / (CHUNK_SECONDS * 16000))), file=sys.stderr)
    if not rows:
        raise ValueError("omlx_empty_transcript")
    srt = "\n\n".join("{}\n{} --> {}\n{}".format(i, stamp(a), stamp(b), text)
                          for i, (a, b, text) in enumerate(rows, 1)) + "\n"
    text = "".join("- [{}] {}\n".format(stamp(a).split(",")[0], text) for a, _, text in rows)
    record = dict(expected, model=model, timestamp_source="audio_chunk", duration_seconds=frames / 16000,
                  chunks=chunks, srt_sha256=hashlib.sha256(srt.encode()).hexdigest(),
                  text_sha256=hashlib.sha256(text.encode()).hexdigest())
    prefix.parent.mkdir(parents=True, exist_ok=True)
    # JSON 最后发布作为完成标记；任何请求失败均不会发布半份文本或缓存标记。
    for suffix, data in ((".srt", srt), (".txt", text),
                         (".asr.json", json.dumps(record, ensure_ascii=False, indent=2) + "\n")):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=prefix.parent, delete=False) as target:
                temporary = Path(target.name)
                target.write(data)
            os.replace(temporary, str(prefix) + suffix)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    return record, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", nargs="?")
    parser.add_argument("output_prefix", nargs="?")
    parser.add_argument("language", nargs="?", default="auto", choices=("auto", "zh", "en", "ja", "ko", "yue"))
    parser.add_argument("profile", nargs="?", default="auto", choices=("auto", "fast", "accurate"))
    parser.add_argument("--check", choices=("fast", "accurate"))
    parser.add_argument("--check-cache", action="store_true")
    args = parser.parse_args()
    base = os.environ.get("AGENT_OMLX_BASE_URL", "http://127.0.0.1:8037/v1").rstrip("/")
    # 明确限制本机，保留用户期望的本地服务边界。
    from urllib.parse import urlsplit
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1") or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("AGENT_OMLX_BASE_URL 必须是无凭据的本机 HTTP(S) 地址")
    if args.check:
        print("asr_backend=omlx\nmodel=" + resolve_model(base, args.check))
        return 0
    if not args.audio or not args.output_prefix:
        parser.error("需要 audio 和 output_prefix")
    profile = effective_profile(args.profile)
    audio, prefix = Path(args.audio), Path(args.output_prefix)
    if args.check_cache:
        return 0 if cached(prefix, fingerprint(audio, profile, args.language)) else 1
    record, reused = transcribe(audio, prefix, args.language, profile, base)
    print("requested_profile={}\nprofile={}\nmodel={}\ndevice=omlx\nasr_backend=omlx\nasr_model={}\nasr_timestamps=audio_chunk\ncache_reused={}\nsrt={}\ntext={}".format(
        args.profile, profile, record["model"], record["model"], int(reused), str(prefix) + ".srt", str(prefix) + ".txt"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, wave.Error, EOFError) as error:
        print("oMLX 转写失败: {}".format(error), file=sys.stderr)
        sys.exit(1)
