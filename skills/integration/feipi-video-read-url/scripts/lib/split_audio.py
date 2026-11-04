#!/usr/bin/env python3
"""按停顿切分 16kHz 单声道 PCM16 WAV；唯一可调配置为 --max-seconds。"""

import argparse
import csv
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave

CHUNK_POLICY = "pause-center-v2"
DEFAULT_MAX_SECONDS = 30


def validate_max_seconds(value):
    if not math.isfinite(value) or value < 1:
        raise ValueError("max-seconds 必须是至少 1 秒的有限数值")
    return value


def audio_properties(audio):
    """缓存与切分共用 WAV 校验，拒绝空文件、错误格式和截断载荷。"""
    with wave.open(str(audio), "rb") as source:
        rate, frames = source.getframerate(), source.getnframes()
        if (source.getnchannels(), source.getsampwidth(), rate, source.getcomptype()) != (1, 2, 16000, "NONE"):
            raise ValueError("omlx_audio_requires_16khz_mono_pcm_s16le")
        if frames <= 0:
            raise ValueError("omlx_empty_audio")
        # 分块前检查 WAV 载荷，避免把截断输入作为一段更短但正常的音频。
        source.setpos(frames - 1)
        if len(source.readframes(1)) != 2:
            raise ValueError("omlx_truncated_audio")
    return rate, frames


def plan_audio(audio, max_seconds=DEFAULT_MAX_SECONDS):
    """返回连续无重叠的采样范围；停顿只选切口，不删除音频。"""
    validate_max_seconds(max_seconds)
    rate, frames = audio_properties(audio)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("audio_chunk_ffmpeg_missing")
    try:
        result = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-nostats", "-i", str(audio),
                                 "-af", "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=300)
    except subprocess.TimeoutExpired as error:
        raise ValueError("audio_chunk_silence_detection_timeout") from error
    if result.returncode:
        raise ValueError("audio_chunk_silence_detection_failed")
    silences, begin = [], None
    for match in re.finditer(r"silence_(start|end):\s*([-+\d.eE]+)", result.stderr):
        value = round(float(match.group(2)) * rate)
        if match.group(1) == "start":
            begin = max(0, value)
        elif begin is not None:
            silences.append((begin, min(frames, value)))
            begin = None
    if begin is not None:
        silences.append((begin, frames))
    maximum, guard = int(max_seconds * rate), round(0.03 * rate)
    plan, start = [], 0
    while start < frames:
        limit = min(frames, start + maximum)
        end, reason = limit, "end"
        if limit < frames:
            floor = start + int(maximum * 2 / 3)
            candidates = []
            for a, b in silences:
                low, high = max(floor, a + guard), min(limit, b - guard)
                if low <= high:
                    # 普通停顿取中点，为前后语音都留出余量；长静音覆盖窗口时仍尽量保留长块。
                    candidates.append(min(high, max(low, (a + b) // 2)) if a >= floor else high)
            end, reason = (max(candidates), "pause") if candidates else (limit, "forced")
        plan.append({"start_frame": start, "end_frame": end, "cut_reason": reason})
        start = end
    return rate, frames, plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="16kHz 单声道 PCM16 WAV")
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS,
                        help="每段时长上限，默认/推荐30秒；如 --max-seconds 60")
    args = parser.parse_args()
    try:
        audio = args.audio.expanduser().resolve(strict=True)
        rate, frames, plan = plan_audio(audio, args.max_seconds)
        output = Path(tempfile.mkdtemp(prefix="audio-chunks-", dir=audio.parent))
        with wave.open(str(audio), "rb") as source:
            for i, chunk in enumerate(plan, 1):
                a, b = chunk["start_frame"], chunk["end_frame"]
                pcm = source.readframes(b - a)
                if len(pcm) != (b - a) * 2:
                    raise ValueError("omlx_truncated_audio")
                name = f"{i:03d}_{a / rate:010.3f}-{b / rate:010.3f}_{chunk['cut_reason']}.wav"
                with wave.open(str(output / name), "wb") as target:
                    target.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                    target.writeframes(pcm)
                chunk.update(index=i, file=name, start_seconds=a / rate, end_seconds=b / rate)
                print(f"chunk={i}/{len(plan)} start={a / rate:.3f} end={b / rate:.3f}"
                      f" cut={chunk['cut_reason']} file={output / name}", flush=True)
        with (output / "cuts.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(plan[0]))
            writer.writeheader()
            writer.writerows(plan)
        manifest = {"input": str(audio), "max_seconds": args.max_seconds, "chunk_policy": CHUNK_POLICY,
                    "duration_seconds": frames / rate, "chunks": plan}
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print(f"output_dir={output}", flush=True)
    except (OSError, ValueError, wave.Error, subprocess.SubprocessError) as error:
        parser.exit(1, f"错误：{error}\n")


if __name__ == "__main__":
    main()
