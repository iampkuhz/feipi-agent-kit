"""通用证据清单；只登记提取与宿主读取结果，不合成内容结论。"""

import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
from urllib.parse import urlsplit

CHANNELS = ("source", "body", "subtitles", "asr", "images", "frames", "ocr", "visual_observation")
MANIFEST = "extraction_manifest.json"


def external_output(path):
    root = Path(path).expanduser().resolve()
    skill = Path(__file__).resolve().parents[2]
    container = skill.parent.parent if skill.parent.name == "integration" else skill.parent
    if root.is_relative_to(container):
        raise ValueError("output_inside_skill_installation")
    # 源码目录与安装目录同样禁止写入，含任意 sibling skill。
    for parent in (root, *root.parents):
        if (parent / "SKILL.md").is_file():
            raise ValueError("output_inside_skill")
    return root


def prepare_output(path):
    root = external_output(path)
    if root.exists() and any(root.iterdir()):
        raise ValueError("output_directory_not_empty")
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_manifest(url, platform="unknown", content_type="unknown"):
    return {"schema": "feipi-content-extraction-v1", "version": 1,
            "platform": platform, "content_id": None, "original_url": url,
            "canonical_url": url, "content_type": content_type,
            "status": "failed", "reasons": [],
            "metadata": {"title": None, "author": None, "published_at": None},
            "channels": {k: {"status": "not_applicable", "reasons": []} for k in CHANNELS},
            "artifacts": []}


def channel(m, key, status, *reasons, **extra):
    m["channels"][key] = {"status": status, "reasons": list(reasons), **extra}


def safe_path(root, path):
    if not isinstance(path, str) or Path(path).is_absolute():
        raise ValueError("artifact_path_invalid")
    dest = (root / path).resolve()
    if not dest.is_relative_to(root.resolve()):
        raise ValueError("artifact_path_escape")
    return dest


def artifact(m, root, ident, kind, path, anchor, source_url=None, **extra):
    relative = Path(path).resolve().relative_to(root.resolve()).as_posix()
    if any(a["id"] == ident for a in m["artifacts"]):
        raise ValueError("duplicate_artifact_id")
    item = {"id": ident, "kind": kind, "path": relative,
            "source_url": source_url, "anchor": anchor,
            "read_status": "pending" if kind in ("image", "frame") else "extracted", **extra}
    m["artifacts"].append(item)
    return item


def write_json(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def finish(m, root):
    """只依据证据和渠道状态计算完成度；元数据或页面不能充当正文。"""
    channels = m["channels"]
    video = m["content_type"] in ("video", "video_note")
    has_text = any(a["kind"] in ("subtitles", "asr") for a in m["artifacts"])
    required = ["source"]
    if m["platform"] == "xiaohongshu" and m["content_type"] in ("image_note", "video_note"):
        required.append("body")
        if channels["images"]["status"] != "not_applicable":
            required.append("images")
    if video:
        required.append("frames")
    elif m["content_type"] == "image_note" and "images" not in required:
        required.append("images")
    reasons = [r for k in required for r in channels[k]["reasons"]
               if channels[k]["status"] != "complete"]
    incomplete = any(channels[k]["status"] != "complete" for k in required)
    if video and not has_text:
        reasons += channels["subtitles"]["reasons"] + channels["asr"]["reasons"] + ["video_text_unavailable"]
        incomplete = True
    pending = any(a["read_status"] == "pending" for a in m["artifacts"] if a["kind"] in ("image", "frame"))
    if pending:
        incomplete = True
        reasons.append("visual_reading_pending")
    evidence = any(a["kind"] in ("body", "subtitles", "asr", "image", "frame") for a in m["artifacts"])
    if not incomplete and evidence:
        status = "complete"
    elif evidence:
        status = "partial"
    else:
        status = "blocked" if channels["source"]["status"] == "blocked" else "failed"
        if not reasons:
            reasons = channels["source"]["reasons"] or ["content_unavailable"]
    m["status"], m["reasons"] = status, list(dict.fromkeys(reasons))
    write_json(root / MANIFEST, m)
    return {"complete": 0, "partial": 2}.get(status, 1)


def visual_pending(m):
    if any(a["kind"] in ("image", "frame") for a in m["artifacts"]):
        channel(m, "ocr", "pending", "host_reading_required")
        channel(m, "visual_observation", "pending", "host_reading_required")


def public_env():
    env = os.environ.copy()
    for k in ("AGENT_CHROME_PROFILE", "AGENT_YOUTUBE_COOKIE_FILE", "AGENT_BILIBILI_COOKIE_FILE"):
        env[k] = ""
    env["AGENT_VIDEO_CONTENT_EXTRACTION"] = "1"
    return env


def run_logged(args, log, timeout=90):
    with Path(log).open("wb") as f:
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=f,
                                       env=public_env(), start_new_session=True)
            try:
                stdout, _ = process.communicate(timeout=timeout)
                return process.returncode, stdout
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                f.write(b"\ncontent_extraction_timeout\n")
                return 124, b""
        except OSError:
            f.write(b"\ncontent_extraction_dependency_missing\n")
            return 127, b""


def ytdlp_binary(scripts, log):
    code, output = run_logged(["bash", "-c",
        'source "$1"; yt_common_select_ytdlp >/dev/null || exit; printf "%s" "$YT_DLP_BIN"',
        "content-extraction", str(scripts / "lib/yt_dlp_common.sh")], log, 30)
    if code or not output.strip():
        raise ValueError("yt_dlp_unavailable")
    return output.decode().strip()


def resolve_media(url, scripts, root):
    binary = ytdlp_binary(scripts, root / "ytdlp-selection.log")
    args = [binary, "--ignore-config", "--no-playlist", "--skip-download", "--dump-single-json",
            "--socket-timeout", "15", "--retries", "1", "--extractor-retries", "1", url]
    code, data = run_logged(args, root / "media-resolution.log")
    if code:
        raise ValueError("media_resolution_failed")
    try:
        info = json.loads(data)
        if not isinstance(info, dict) or info.get("_type") in ("playlist", "multi_video"):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("media_metadata_invalid") from None
    return info


def finite_seconds(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("invalid_timestamp")
    return number


def platform(url):
    host = urlsplit(url).hostname or ""
    for name, domains in {"bilibili": ("bilibili.com", "b23.tv"),
                          "youtube": ("youtube.com", "youtu.be"),
                          "xiaohongshu": ("xiaohongshu.com", "xhslink.cn", "xhslink.com")}.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return name
    return "unknown"


def diagnostic(log):
    text = Path(log).read_text(errors="replace") if Path(log).exists() else ""
    codes = re.findall(r"diagnostic_code=([a-z0-9_]+)", text)
    return codes[-1] if codes else "text_extraction_failed"
