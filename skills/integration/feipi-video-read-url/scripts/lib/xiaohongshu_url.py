#!/usr/bin/env python3
"""解析小红书分享短链，保留原分享参数；不读取浏览器凭据。"""

import re
import sys
from urllib.error import URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


NOTE_HOSTS = {"www.xiaohongshu.com", "xiaohongshu.com"}
SHARE_HOSTS = {"xhslink.com", "www.xhslink.com", "xhslink.cn", "www.xhslink.cn"}
NOTE_PATH = re.compile(r"/(?:explore|discovery/item)/([0-9a-f]{24})/?$")


class SourceError(ValueError):
    pass


def validate(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in ("http", "https") or parsed.username or parsed.password
            or parsed.port not in (None, 80, 443)
            or parsed.hostname not in NOTE_HOSTS | SHARE_HOSTS):
        raise SourceError("xiaohongshu_invalid_url")
    return parsed


def note_url(url):
    parsed = validate(url)
    if parsed.hostname in NOTE_HOSTS:
        if parsed.path.startswith(("/login", "/website-login")):
            raise SourceError("xiaohongshu_login_required")
        match = NOTE_PATH.fullmatch(parsed.path)
        if not match:
            raise SourceError("xiaohongshu_unsupported_note_url")
        return urlunsplit(("https", "www.xiaohongshu.com", "/explore/" + match[1],
                           parsed.query, ""))
    return ""


class NoteFound(Exception):
    def __init__(self, url):
        self.url = url


class ShareRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        normalized = note_url(target)
        if normalized:
            # 在笔记页前停止，交给站点提取器；旧 HTTP 分享目标只向同站 HTTPS 升级。
            raise NoteFound(normalized)
        parsed = validate(target)
        target = urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
        return super().redirect_request(req, fp, code, msg, headers, target)


def resolve(url, opener=None):
    normalized = note_url(url)
    if normalized:
        return normalized
    parsed = validate(url)
    secure = urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
    request = Request(secure, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with (opener or build_opener(ShareRedirects())).open(request, timeout=15):
            raise SourceError("xiaohongshu_share_unresolved")
    except NoteFound as found:
        return found.url
    except (URLError, TimeoutError, OSError) as error:
        raise SourceError("xiaohongshu_share_request_failed") from error


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise SourceError("xiaohongshu_invalid_url")
        print(resolve(sys.argv[1]))
    except ValueError as error:
        code = str(error) if isinstance(error, SourceError) else "xiaohongshu_invalid_url"
        print("diagnostic_code=" + code, file=sys.stderr)
        sys.exit(1)
