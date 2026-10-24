#!/usr/bin/env python3
"""字幕/ASR + 按需关键帧，输出统一 extraction manifest。"""

import argparse
import json
from pathlib import Path
import shutil
import sys
from urllib.parse import urlsplit

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS / "lib"))
from content_manifest import (artifact, channel, diagnostic, finish, new_manifest, platform,
                              prepare_output, resolve_media, run_logged, safe_path, write_json)
from extract_frames import extract_frames


def collect_video(url, root, manifest, times=None, media_info=None, quality="fast"):
    info = media_info
    try:
        info = info or resolve_media(url, SCRIPTS, root)
        source = root / "video-source.json"
        write_json(source, info)
        artifact(manifest, root, "video-source", "source", source, {"type": "metadata"})
        manifest["content_id"] = manifest["content_id"] or info.get("id")
        if manifest["metadata"]["title"] is None:
            manifest["metadata"]["title"] = info.get("title")
        manifest["metadata"]["duration_seconds"] = info.get("duration")
        if manifest["platform"] != "xiaohongshu":
            manifest["canonical_url"] = info.get("webpage_url") or url
        channel(manifest, "source", "complete")
    except ValueError as error:
        if manifest["channels"]["source"]["status"] != "complete":
            channel(manifest, "source", "unavailable", str(error))
    # 复用统一字幕优先/内置 whisper.cpp。公共模式禁止配置文件与浏览器凭据，
    # 只准独立音频流；平台只有合流视频时不下载原片来换取语音。
    log = root / "text-extraction.log"
    code, output = run_logged(["bash", str(SCRIPTS / "extract_video_text.sh"), url,
                              str(root / "text"), "auto", "--instruction", "提取视频原文", "--quality", quality],
                             log, timeout=1800)
    (root / "text-entrypoint.txt").write_bytes(output)
    fields = dict(line.split("=", 1) for line in output.decode(errors="replace").splitlines() if "=" in line)
    text = Path(fields.get("text_path", root / "missing"))
    if code == 0 and text.is_file() and text.resolve().is_relative_to(root):
        kind = "asr" if fields.get("mode") == "whisper" else "subtitles"
        target = root / f"{kind}.txt"
        shutil.copyfile(text, target)
        anchor = {"type": "time_range", "start_seconds": 0,
                  "end_seconds": info.get("duration") if info else None, "timestamps": "inline"}
        artifact(manifest, root, kind, kind, target, anchor, source_url=manifest["canonical_url"])
        channel(manifest, kind, "complete", provenance="whisper.cpp" if kind == "asr" else "platform_subtitles",
                requested_quality=quality)
        if kind == "asr":
            channel(manifest, "subtitles", "unavailable", "subtitles_unavailable_used_asr")
    else:
        reason = diagnostic(log)
        subtitle_logs = list((root / "text").glob("*/logs/*subtitle*.log"))
        whisper_logs = list((root / "text").glob("*/logs/*whisper*.log"))
        sub_reason = diagnostic(subtitle_logs[-1]) if subtitle_logs else reason
        asr_reason = diagnostic(whisper_logs[-1]) if whisper_logs else reason
        if whisper_logs and "Requested format is not available" in whisper_logs[-1].read_text(errors="replace"):
            asr_reason = "independent_audio_stream_unavailable"
        channel(manifest, "subtitles", "unavailable", sub_reason)
        channel(manifest, "asr", "unavailable", asr_reason, "audio_only_required_no_full_video_fallback")
    finish(manifest, root)
    extract_frames(url, root, manifest, SCRIPTS, info=info, times=times)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("output_dir")
    parser.add_argument("--frame-times", help="逗号分隔的抽帧秒数；默认均匀6帧")
    parser.add_argument("--quality", choices=("fast", "accurate"), default="fast", help="复用既有转写档位；默认fast")
    args = parser.parse_args()
    if platform(args.url) == "xiaohongshu":
        # 图文/视频判断、文案证据和登录诊断均复用笔记入口。
        entry = SCRIPTS.parent.parent / "feipi-xiaohongshu-read-note/scripts/extract_note.py"
        if not entry.is_file():
            parser.error("小红书请同时安装 feipi-xiaohongshu-read-note")
        import subprocess
        command = [sys.executable, str(entry), args.url, args.output_dir, "--quality", args.quality]
        if args.frame_times:
            command += ["--frame-times", args.frame_times]
        return subprocess.call(command)
    if platform(args.url) == "unknown":
        parser.error("通用 manifest 入口当前支持 YouTube/Bilibili/小红书；其他既有来源继续使用原入口")
    root = prepare_output(args.output_dir)
    manifest = new_manifest(args.url, platform(args.url), "video")
    collect_video(args.url, root, manifest, args.frame_times.split(",") if args.frame_times else None, quality=args.quality)
    code = finish(manifest, root)
    print(f"manifest_path={root / 'extraction_manifest.json'}\nstatus={manifest['status']}")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
