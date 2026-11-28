#!/usr/bin/env python3
"""解析严道公开单讲或文章中的视频文件，不读取浏览器凭据。"""
import datetime
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
from urllib.parse import urlsplit


class ArticleVideos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'video':
            self.current = attrs.get('src') or attrs.get('data-src') or ''
        elif tag == 'source' and self.current == '':
            self.current = attrs.get('src') or ''

    def handle_endtag(self, tag):
        if tag == 'video':
            if self.current and self.current not in self.urls:
                self.urls.append(self.current)
            self.current = None


def verified_account_evidence(path, native_id, media):
    """逐例核验已报名账号的完整播放证据；不接受通用放行开关。"""
    with Path(path).open('rb') as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError('账号播放证据超过大小限制')
    proof = json.loads(raw)
    page = urlsplit(proof.get('source_url', ''))
    if (proof.get('schema') != 'drvoice-account-playback-v1'
            or proof.get('source_id') != 'drvoice-speaker-' + native_id
            or page.scheme != 'https' or page.hostname not in ('drvoice.cn', 'www.drvoice.cn')
            or page.path.rstrip('/') != '/v2/speaker/' + native_id
            or page.query or page.fragment or page.username or page.port):
        raise ValueError('账号播放证据与当前单讲身份不一致')
    for field in ('login_confirmed', 'playback_reached_end_observed',
                  'no_registration_or_payment_prompt_seen', 'native_DOM_video_src_observed'):
        if proof.get(field) is not True:
            raise ValueError('账号播放证据缺少完整原生页面核验：' + field)
    checked = datetime.datetime.fromisoformat(proof.get('checked_at', '').replace('Z', '+00:00'))
    if checked.tzinfo is None:
        raise ValueError('账号播放证据时间必须带时区')
    age = (datetime.datetime.now(datetime.timezone.utc) - checked).total_seconds()
    if not -60 <= age <= 86400:
        raise ValueError('账号播放证据已过期或时间无效；需逐例复核')
    parts = urlsplit(media)
    if parts.query or parts.username or parts.fragment or not parts.path.endswith('.m3u8'):
        raise ValueError('账号逐例入口仅接受无凭据参数的已核HLS地址')
    fingerprint = hashlib.sha256(media.encode()).hexdigest()
    if proof.get('media_reference_sha256') != fingerprint:
        raise ValueError('账号播放证据与公开详情媒体指纹不一致')
    manifest_hash = proof.get('manifest_sha256', '')
    if not re.fullmatch(r'[0-9a-f]{64}', manifest_hash):
        raise ValueError('账号播放证据缺少已核清单指纹')
    return dict(evidence_sha256=hashlib.sha256(raw).hexdigest(),
                checked_at=proof['checked_at'], manifest_sha256=manifest_hash)


def resolve(url, output):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/v2/(speaker|article)/(\d+)/?", parsed.path)
    if parsed.scheme != "https" or parsed.hostname not in ("www.drvoice.cn", "drvoice.cn") or not match:
        raise ValueError("仅支持严道单讲或文章视频；集合请先选单讲")
    source_type, native_id = match.groups()
    index_text = os.environ.get('AGENT_DRVOICE_VIDEO_INDEX', '1')
    if not re.fullmatch(r'[1-9][0-9]*', index_text):
        raise ValueError('AGENT_DRVOICE_VIDEO_INDEX 必须是从1开始的整数')
    video_index = int(index_text)
    endpoint = ("https://gwapi.drvoice.cn/drvoice/api/article/" + native_id if source_type == 'article' else
                "https://gwapi.drvoice.cn/drvoice/api/speaker/getSpeakerPageInfoBySpeakerId?speakerId=" + native_id)
    with urllib.request.urlopen(endpoint, timeout=30) as response:
        data = json.load(response)
    if data.get("success") is not True:
        raise ValueError("公开详情不可用；停止并按个例处理，不读取浏览器凭据")
    speaker = data.get('data') or {}
    if source_type == 'speaker':
        speaker = speaker.get('speakerInfo') or {}
    if str(speaker.get('id')) != native_id:
        raise ValueError('公开详情编号与请求不一致')
    course = speaker.get("courseInfo") or {}
    evidence_path = os.environ.get('AGENT_DRVOICE_ACCOUNT_EVIDENCE', '')
    if course.get("isOpenPayWatch"):
        raise ValueError("课程存在付费或报名限制；停止并按个例处理")
    if course.get("isOpenSign") and not evidence_path:
        raise ValueError("课程存在付费或报名限制；停止并按个例处理")
    if evidence_path and (source_type != 'speaker' or speaker.get('paymentType') not in (None, 0, '0')):
        raise ValueError('账号逐例证据不适用于此来源或付费单讲')
    if source_type == 'article':
        parser = ArticleVideos()
        parser.feed(speaker.get('content') or '')
        videos = [dict(playURL=media) for media in parser.urls]
        if not videos:
            raise ValueError('文章没有独立视频文件；嵌入播放器需逐例解析，不能把介绍当转写')
        if video_index > len(videos):
            raise ValueError('文章视频序号超出公开详情提供的范围')
    else:
        videos = json.loads(speaker.get("video") or speaker.get("videoEn") or "[]")
    if not videos or any(str(v.get("encrypt", 0)) not in ("0", "False", "None") for v in videos):
        raise ValueError("无回放或媒体加密；停止并按个例处理")
    video = videos[video_index-1] if source_type == 'article' else videos[0]
    media = next((video[k] for k in ("playURL", "PlayURL", "playUrl", "playurl") if video.get(k)), "")
    media_parts = urlsplit(media)
    # 已由官网单讲详情及同址HTTPS响应头核验的当前/历史媒体域名。
    hosts = {"video.drvoice.cn", "videobj.drvoice.cn", "videosz.drvoice.cn",
             "drvoiceke.oss-cn-beijing.aliyuncs.com"}
    if source_type == 'article':
        hosts |= {'drvoicedev.oss-cn-beijing.aliyuncs.com', 'drvoice201608.oss-cn-beijing.aliyuncs.com'}
    if media_parts.scheme == 'http' and media_parts.hostname in hosts:
        media = 'https://' + media[len('http://'):]
        media_parts = urlsplit(media)
    if media_parts.scheme != "https" or media_parts.hostname not in hosts:
        raise ValueError("媒体来源不在已核验的严道视频域名，需人工核对")
    if not media_parts.path.lower().endswith(('.mp4','.m4v','.m3u8')):
        raise ValueError('不是已支持的公开视频文件或HLS清单')
    evidence = verified_account_evidence(evidence_path, native_id, media) if evidence_path else None
    if media_parts.path.endswith(".m3u8"):
        with urllib.request.urlopen(media, timeout=30) as response:
            manifest = response.read().decode("utf-8")
        if "#EXT-X-KEY" in manifest or "#EXT-X-ENDLIST" not in manifest:
            raise ValueError("加密或仍在直播的清单，停止并按个例处理")
        if evidence and hashlib.sha256(manifest.encode()).hexdigest() != evidence['manifest_sha256']:
            raise ValueError('账号逐例清单与原生核验指纹不一致')
    output.mkdir(parents=True, exist_ok=True)
    video_id = 'article-'+native_id+'-video-'+str(video_index) if source_type=='article' else native_id
    record = dict(schema_version=1, platform="DrVoice", input_url=url, video_id=video_id,
                  video_title=speaker.get("title", ""), title_source="drvoice_public_api",
                  duration_sec=float(video.get("Duration") or video.get("duration") or 0),
                  course_id=str(course.get("id", "")), course_title=course.get("title", ""),
                  start_time=speaker.get("startTime") or speaker.get('createDate'), end_time=speaker.get("endTime"),
                  source_type=source_type, native_page_id=native_id,
                  embedded_video_index=video_index if source_type=='article' else None,
                  embedded_video_count=len(videos) if source_type=='article' else None,
                  captured_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  media_reference_sha256=hashlib.sha256(media.encode()).hexdigest(),
                  metadata_endpoint=endpoint, media_encrypted=False, subtitles_status="独立字幕及画面硬字幕需另行核验")
    if evidence:
        record.update(account_playback_verified=True, account_evidence=evidence,
                      public_watch_flags={k: course.get(k) for k in ('isOpenSign', 'isOpenPayWatch')})
    (output / "video_identity.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    (output / "source_metadata.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    # Temporary transport file, removed by caller; do not log media URL.
    (output / ".drvoice-media-url").write_text(media)
    print("video_id=" + video_id)
    print("duration_sec=" + str(record["duration_sec"]))
    print("title_source=drvoice_public_api")


if __name__ == "__main__":
    try:
        resolve(sys.argv[1], Path(sys.argv[2]))
    except Exception as error:
        print("drvoice_metadata_failed=" + str(error), file=sys.stderr)
        sys.exit(1)
