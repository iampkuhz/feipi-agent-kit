#!/usr/bin/env python3
"""远程输入端 seek 抽帧。仅允许 Range 媒体或 HLS；不缓存完整原视频。"""

import argparse
import copy
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from content_manifest import (artifact, channel, finite_seconds, new_manifest, prepare_output,
                              resolve_media, run_logged, visual_pending, finish, write_json, safe_path)
from validate_extraction import validate


def frame_times(duration, requested=None, count=6):
    if requested is not None:
        values = sorted(set(finite_seconds(v) for v in requested))
        if not values or len(values) > 24:
            raise ValueError("frame_count_out_of_range")
        if duration and any(t >= duration for t in values):
            raise ValueError("timestamp_outside_duration")
        return values
    if not duration:
        return [0.0]
    # 均匀覆盖，避开视频尾部；短片不重复采样。
    return sorted(set(round(duration * i / count, 3) for i in range(count)))


def media_candidate(info):
    candidates = info.get("formats") or [info]
    valid = [f for f in candidates if f.get("url") and f.get("vcodec") != "none"
             and urlsplit(f["url"]).scheme in ("http", "https")
             and f.get("ext") in ("mp4", "webm", "m3u8")
             and f.get("protocol") in (None, "https", "http", "m3u8_native", "m3u8")]
    if not valid:
        raise ValueError("on_demand_video_stream_unavailable")
    # 优先足够读字的分辨率，避免选择纯音频或分片专有协议。
    return min(valid, key=lambda f: (abs((f.get("height") or 720) - 720), f.get("tbr") or 0))


def request_headers(info, media):
    headers = {**info.get("http_headers", {}), **media.get("http_headers", {})}
    allowed = ("user-agent", "referer", "origin", "accept")
    return {k: str(v) for k, v in headers.items()
            if k.lower() in allowed and not re.search(r"[\r\n]", str(v))}


def check_seekable(media, headers, opener=urlopen):
    url = media["url"]
    if "m3u8" in (media.get("protocol") or "") or urlsplit(url).path.endswith(".m3u8"):
        # ffmpeg 的 HLS demuxer 读取清单后仅 seek 到目标分片。
        return "hls_segments"
    req = Request(url, headers={**headers, "Range": "bytes=0-0"})
    with opener(req, timeout=15) as response:
        if response.status != 206 or not re.fullmatch(r"bytes 0-0/\d+", response.headers.get("Content-Range", "")):
            raise ValueError("http_range_not_supported")
        response.read(1)
    return "http_range"


def ffmpeg_args(media, headers, second, path):
    header_text = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-protocol_whitelist", "https,http,httpproxy,tls,tcp,crypto", "-rw_timeout", "15000000"]
    if header_text:
        args += ["-headers", header_text]
    # 必须在 -i 之前；输出端 seek 会从片头顺序读取媒体。
    args += ["-ss", str(second), "-i", media["url"], "-map", "0:v:0",
             "-frames:v", "1", "-an", "-sn", "-vf", "scale=min(1600\\,iw):-2",
             "-q:v", "2", "-update", "1", str(path)]
    return args


def extract_frames(url, root, manifest, scripts, info=None, times=None, count=6):
    previous = [a for a in manifest["artifacts"] if a["kind"] == "frame"]
    start = max([int(a["id"].replace("frame-", "", 1)) for a in previous] or [0])
    previous_sampling = manifest["channels"]["frames"].get("sampling") if previous else None
    failures, saved = [], []
    sampling = {"strategy": "explicit" if times is not None else "uniform",
                "requested_times_seconds": [], "range_seconds": None,
                "coverage": "sampled_only", "failures": failures}
    try:
        if not shutil.which("ffmpeg"):
            raise ValueError("ffmpeg_unavailable")
        info = info or resolve_media(url, scripts, root)
        duration = finite_seconds(info["duration"]) if info.get("duration") else None
        sampling["range_seconds"] = [0, duration]
        sample = frame_times(duration, times, count)
        sampling["requested_times_seconds"] = sample
        if not duration:
            sampling["limitation"] = "duration_unknown_only_opening_sample"
        media = media_candidate(info)
        headers = request_headers(info, media)
        sampling["transport"] = check_seekable(media, headers)
        dest = root / "frames"
        dest.mkdir(exist_ok=True)
        for i, second in enumerate(sample, start + 1):
            path = dest / f"{i:03d}-{second:.3f}s.jpg"
            code, _ = run_logged(ffmpeg_args(media, headers, second, path),
                                  dest / f"{i:03d}.log", timeout=45)
            if code or not path.is_file() or path.stat().st_size == 0:
                path.unlink(missing_ok=True)
                failures.append({"seconds": second,
                                 "reason": "frame_decode_timeout" if code == 124 else "frame_decode_failed",
                                 "exit_code": code, "log_path": f"frames/{i:03d}.log"})
                continue
            artifact(manifest, root, f"frame-{i:03d}", "frame", path,
                     {"type": "time", "seconds": second}, source_url=manifest["canonical_url"])
            saved.append(second)
        status = "complete" if not failures and duration else "partial" if saved else "unavailable"
        reasons = (["frame_sampling_incomplete"] if failures else [])
        if not duration:
            reasons.append("duration_unknown")
        channel(manifest, "frames", status, *reasons, sampling=sampling)
    except (ValueError, OSError) as error:
        reason = str(error) if isinstance(error, ValueError) else "frame_stream_request_failed"
        channel(manifest, "frames", "unavailable", reason, sampling=sampling)
    if previous_sampling:
        sampling["previous_sampling"] = previous_sampling
        sampling["coverage"] = "sampled_only"
        if manifest["channels"]["frames"]["status"] == "unavailable":
            manifest["channels"]["frames"]["status"] = "partial"
    visual_pending(manifest)
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("output_dir")
    parser.add_argument("--times", help="逗号分隔的秒数，最多24个；省略则均匀抽6帧")
    parser.add_argument("--base-dir", help="已验证的同一来源提取目录；复制其证据到新目录后补帧，不重新转写")
    args = parser.parse_args()
    m = new_manifest(args.url, content_type="video")
    if args.base_dir:
        base = Path(args.base_dir).resolve()
        m = copy.deepcopy(validate(base))
        if args.url not in (m["original_url"], m["canonical_url"]):
            raise ValueError("base_source_url_mismatch")
        if m["content_type"] not in ("video", "video_note") or not args.times:
            raise ValueError("base_video_and_explicit_times_required")
    root = prepare_output(args.output_dir)
    if args.base_dir:
        for item in m["artifacts"]:
            dest = safe_path(root, item["path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_path(base, item["path"]), dest)
    extract_frames(args.url, root, m, Path(__file__).resolve().parent,
                   times=args.times.split(",") if args.times else None)
    if not args.base_dir:
        channel(m, "source", "complete")
    code = finish(m, root)
    print(f"manifest_path={root / 'extraction_manifest.json'}\nstatus={m['status']}")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
