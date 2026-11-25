#!/usr/bin/env python3
"""匿名读取小红书笔记及顺序原图，视频转写和关键帧复用同级视频 skill。"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


def load_video_skill(path=None):
    skill = Path(path).expanduser().resolve() if path else Path(__file__).resolve().parents[2] / "feipi-video-read-url"
    if not (skill / "scripts/lib/content_manifest.py").is_file():
        raise ValueError("missing_dependency_feipi_video_read_url")
    sys.path.insert(0, str(skill / "scripts/lib"))
    sys.path.insert(0, str(skill / "scripts"))
    return skill


class FetchError(ValueError):
    pass


def public_url(url, image=False):
    p = urlsplit(url)
    hosts = ("xhscdn.com", "xiaohongshu.com") if image else ("xiaohongshu.com",)
    if (p.scheme not in ("http", "https") or p.username or p.password
            or p.port not in (None, 80, 443)
            or not any(p.hostname == h or (p.hostname or "").endswith("." + h) for h in hosts)):
        raise FetchError("image_host_not_allowed" if image else "note_redirect_not_allowed")
    return urlunsplit(("https", p.netloc, p.path, p.query, ""))


class PublicRedirects(HTTPRedirectHandler):
    def __init__(self, image=False):
        super().__init__()
        self.image = image

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = public_url(urljoin(req.full_url, newurl), self.image)
        return super().redirect_request(req, fp, code, msg, headers, target)


def fetch(url, limit, image=False):
    req = Request(public_url(url, image), headers={"User-Agent": "Mozilla/5.0",
                  "Referer": "https://www.xiaohongshu.com/", "Accept-Encoding": "identity"})
    try:
        with build_opener(PublicRedirects(image)).open(req, timeout=20) as r:
            data = r.read(limit + 1)
            if len(data) > limit:
                raise FetchError("response_size_limit")
            return data, r.geturl(), r.headers.get("Content-Type", "")
    except HTTPError as e:
        reason = {401: "login_required", 403: "access_denied", 404: "note_unavailable", 410: "note_unavailable",
                  429: "rate_limited", 461: "verification_required", 471: "verification_required"}.get(e.code, "http_request_failed")
        raise FetchError(reason) from None
    except (URLError, TimeoutError, OSError):
        raise FetchError("network_request_failed") from None


def normalize_state(raw):
    # SSR 使用 undefined，逐 token 替换而不执行 JS，也不改动字符串原文。
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|\bundefined\b', re.S)
    return tokens.sub(lambda m: "null" if m[0] == "undefined" else m[0], raw)


def parse_note(html, note_id):
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*", html)
    if not match:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(normalize_state(html[match.end():]))
        detail = data.get("note", {}).get("noteDetailMap", {}).get(note_id, {})
        note = detail.get("note")
        if not isinstance(note, dict) or str(note.get("noteId", "")) != note_id:
            return None
        return note
    except (ValueError, AttributeError, TypeError):
        return None


def missing_note_reason(html, final_url):
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    title = title[1] if title else ""
    if any(x in urlsplit(final_url).path for x in ("/login", "/website-login")) or "登录后查看" in html:
        return "login_required"
    if any(x in title for x in ("验证码", "安全验证")) or "请完成验证" in html:
        return "verification_required"
    if any(x in html for x in ("笔记不存在", "笔记已删除", "当前笔记暂时无法浏览", "页面不见了")):
        return "note_unavailable"
    return "note_data_unavailable"


def image_url(item):
    # 使用页面实际提供的原始 CDN 文件，不裁切、不二次压缩。
    choices = [item.get("url"), item.get("urlDefault")]
    choices += [v.get("url") for v in item.get("infoList", []) if isinstance(v, dict)
                and v.get("imageScene") == "WB_DFT"]
    return next((u for u in choices if isinstance(u, str) and u), None)


def image_extension(data):
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if len(data) > 12 and data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis", b"heic", b"heix", b"mif1"):
        return ".avif" if data[8:12] in (b"avif", b"avis") else ".heic"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    raise FetchError("image_response_invalid")


def published_at(value):
    if isinstance(value, (int, float)) and value > 0:
        try:
            return datetime.fromtimestamp(value / 1000 if value > 10**11 else value, timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return None
    return value if isinstance(value, str) and value else None


def extract(url, root, times=None, rendered=None):
    from content_manifest import (artifact, channel, finish, new_manifest, visual_pending, write_json)
    from xiaohongshu_url import resolve, SourceError, NOTE_PATH
    from extract_content import collect_video
    m = new_manifest(url, "xiaohongshu")
    try:
        access_url = resolve(url)
        match = NOTE_PATH.fullmatch(urlsplit(access_url).path)
        note_id = match[1]
        m["content_id"] = note_id
        m["canonical_url"] = "https://www.xiaohongshu.com/explore/" + note_id
        media_info = None
        if rendered is not None:
            # 仅接受宿主从可见 DOM/页面资源取得的明确取证包，不接受 Cookie。
            if not isinstance(rendered, dict) or rendered.get("schema") != "feipi-xiaohongshu-rendered-note-v1":
                raise FetchError("invalid_rendered_note_schema")
            rendered_url = public_url(rendered.get("source_url", ""))
            target = NOTE_PATH.fullmatch(urlsplit(rendered_url).path)
            note = rendered.get("note")
            if not target or target[1] != note_id or not isinstance(note, dict) or note.get("noteId") != note_id:
                raise FetchError("rendered_note_identity_mismatch")
            source = root / "rendered-source.json"
            write_json(source, rendered)
            artifact(m, root, "note-source", "source", source, {"type": "note", "content_id": note_id},
                     provenance="browser_dom")
            video = rendered.get("video")
            if isinstance(video, dict) and video.get("url"):
                media_url = public_url(video["url"], image=True)
                media_info = {"id": note_id, "title": note.get("title"), "duration": video.get("duration"),
                              "formats": [{"url": media_url, "ext": "mp4", "protocol": "https", "vcodec": "unknown"}],
                              "http_headers": {"Referer": "https://www.xiaohongshu.com/"}, "provenance": "browser_page_asset"}
        else:
            data, final_url, mime = fetch(access_url, 8 * 1024 * 1024)
            source = root / "source.html"
            source.write_bytes(data)
            write_json(root / "source-request.json", {"original_url": url, "access_url": access_url,
                                                      "final_url": final_url, "content_type": mime})
            artifact(m, root, "note-source", "source", source, {"type": "note", "content_id": note_id})
            html = data.decode("utf-8", errors="replace")
            note = parse_note(html, note_id)
            if note is None:
                raise FetchError(missing_note_reason(html, final_url))
        m["metadata"] = {"title": note.get("title"), "author": note.get("user"),
                          "published_at": published_at(note.get("time"))}
        if note.get("timeDisplay"):
            m["metadata"]["published_at_display"] = note["timeDisplay"]
        m["content_type"] = {"video": "video_note", "normal": "image_note"}.get(note.get("type"), "unknown")
        write_json(root / "note-source.json", note)
        artifact(m, root, "note-data", "source", root / "note-source.json", {"type": "note", "content_id": note_id})
        channel(m, "source", "complete")
        if isinstance(note.get("desc"), str):
            body = root / "body.txt"
            body.write_text(note["desc"], encoding="utf-8")
            artifact(m, root, "body", "body", body, {"type": "note", "content_id": note_id})
            channel(m, "body", "complete")
        else:
            channel(m, "body", "unavailable", "body_not_exposed")
        image_list = note.get("imageList")
        if isinstance(image_list, list):
            failures = []
            (root / "images").mkdir()
            for i, item in enumerate(image_list, 1):
                try:
                    target = image_url(item) if isinstance(item, dict) else None
                    if target is None:
                        raise FetchError("image_url_unavailable")
                    data, _, mime = fetch(target, 25 * 1024 * 1024, image=True)
                    if not mime.lower().startswith("image/"):
                        raise FetchError("image_content_type_invalid")
                    path = root / "images" / (f"{i:03d}" + image_extension(data))
                    path.write_bytes(data)
                    artifact(m, root, f"image-{i:03d}", "image", path, {"type": "image", "index": i},
                             source_url=target, role="video_cover" if m["content_type"] == "video_note" else "note_image")
                except (FetchError, ValueError, TypeError) as e:
                    failures.append({"index": i, "reason": str(e)})
            channel(m, "images", "partial" if failures else "complete",
                    *(["image_download_incomplete"] if failures else []), expected_count=len(image_list), failures=failures)
        else:
            channel(m, "images", "unavailable", "image_list_not_exposed")
        visual_pending(m)
        finish(m, root)
        if m["content_type"] == "video_note":
            collect_video(access_url, root, m, times, media_info=media_info)
        elif m["content_type"] == "unknown":
            channel(m, "source", "partial", "unsupported_note_type")
    except (SourceError, FetchError, ValueError) as e:
        reason = str(e)
        blocked = reason in ("login_required", "verification_required", "access_denied", "rate_limited", "note_unavailable",
                             "xiaohongshu_login_required")
        channel(m, "source", "blocked" if blocked else "unavailable", reason)
        channel(m, "body", "unavailable", "body_not_read")
    code = finish(m, root)
    return code, m


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("url")
    p.add_argument("output_dir")
    p.add_argument("--video-skill", help="已安装 feipi-video-read-url 目录；默认同级目录")
    p.add_argument("--frame-times", help="视频按指定秒数抽帧，逗号分隔")
    p.add_argument("--rendered-note", help="宿主通过已有浏览器会话保存的可见 DOM 取证 JSON；不含凭据")
    a = p.parse_args()
    load_video_skill(a.video_skill)
    from content_manifest import prepare_output, MANIFEST
    root = prepare_output(a.output_dir)
    rendered = json.loads(Path(a.rendered_note).read_text(encoding="utf-8")) if a.rendered_note else None
    code, m = extract(a.url, root, a.frame_times.split(",") if a.frame_times else None, rendered=rendered)
    print(f"manifest_path={root / MANIFEST}\nstatus={m['status']}")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
