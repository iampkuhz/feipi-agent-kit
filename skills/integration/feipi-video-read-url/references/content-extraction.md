# 通用内容提取合同 v1

用于集成调用方解析结果；新增可选字段不破坏 v1。

## 调用

```bash
python3 <feipi-xiaohongshu-read-note>/scripts/extract_note.py '<URL>' '<OUTPUT_DIR>'
python3 <feipi-video-read-url>/scripts/extract_content.py '<URL>' '<OUTPUT_DIR>'
```

输出目录必须由调用方指定且不能位于任意 skill 安装目录内。每次调用使用独立目录；重复调用已存在 manifest 的目录拒绝覆盖。默认视频字幕优先、内置 whisper.cpp fast 回退，并按需远程抽帧；不下载完整原视频。图文逐图保存。两个入口均输出 `<OUTPUT_DIR>/extraction_manifest.json`；stdout 仅输出 manifest 路径与状态。退出码 0=complete，2=partial（已有证据或等待宿主读图），1=failed/blocked；manifest 始终是业务状态真源（参数或文件系统错误除外）。

## JSON 结构

可机读形状见 [JSON Schema](content-extraction.schema.json)。`scripts/validate_extraction.py OUTPUT_DIR` 另检查文件存在、相对路径边界与观察来源引用。

```json
{
  "schema": "feipi-content-extraction-v1",
  "version": 1,
  "platform": "xiaohongshu",
  "content_id": "6adc39ca000000002a0381a5",
  "original_url": "https://xhslink.cn/o/4fVBDGJn6Rk",
  "canonical_url": "https://www.xiaohongshu.com/explore/6adc39ca000000002a0381a5",
  "content_type": "image_note",
  "status": "partial",
  "reasons": ["visual_reading_pending"],
  "metadata": {"title": null, "author": null, "published_at": null},
  "channels": {
    "source": {"status": "complete", "reasons": []},
    "body": {"status": "complete", "reasons": []},
    "subtitles": {"status": "not_applicable", "reasons": []},
    "asr": {"status": "not_applicable", "reasons": []},
    "images": {"status": "complete", "reasons": []},
    "frames": {"status": "not_applicable", "reasons": []},
    "ocr": {"status": "pending", "reasons": ["host_reading_required"]},
    "visual_observation": {"status": "pending", "reasons": ["host_reading_required"]}
  },
  "artifacts": [
    {"id": "body", "kind": "body", "path": "body.txt", "source_url": null,
     "anchor": {"type": "note", "content_id": "6adc39ca000000002a0381a5"}, "read_status": "extracted"},
    {"id": "image-001", "kind": "image", "path": "images/001.jpg", "source_url": "https://example.invalid/image",
     "anchor": {"type": "image", "index": 1}, "read_status": "pending"}
  ]
}
```

`content_type`: `image_note|video_note|video|unknown`。`status`: `complete|partial|blocked|failed`。
channel 状态另允许 `pending|not_applicable|unavailable`。`reasons` 是机器可读字符串列表，登录/验证码/失效/网络/图片失败/无法按需抽帧分别标识；未知正文保持 unavailable，不能宣称无正文。已确认正文为空时才是 complete + 空 body.txt。

artifact `kind`: `source|body|subtitles|asr|image|frame|ocr|visual_observation`。所有 path 相对 manifest 父目录且不得越界。source 保存原页面/元数据；body 是笔记文案，subtitles 是字幕，asr 是语音转写，三者绝不混用。视频文字文件保留原始时间戳；frame anchor 为 `{"type":"time","seconds":12.0}`；OCR/视觉观察 artifact 同时保留 `source_artifact_id` 和原图/帧锚点。frames channel 另记录 sampling（范围、时间列表、策略），每个失败点单独记录。

元数据不是内容证据。只获得标题、文案或封面不能宣称已读取视频。短链解析后的带分享参数访问 URL 可保存在 source 取证内，canonical_url 去掉分享参数；不得读取浏览器凭据或打印 ~/.env。

## 宿主完成读图

宿主按 artifacts 顺序实际打开 image/frame，将可见文字和视觉观察分别写为 JSON，再调用：

```bash
python3 <feipi-video-read-url>/scripts/record_observations.py '<OUTPUT_DIR>' '<OBSERVATIONS_JSON>'
```

JSON 为 `[{"source_artifact_id":"image-001","ocr_text":"…","observation":"…","uncertainties":["品牌不清晰"]}]`。每条只指向实际读取的图/帧；空 OCR 字符串表示实际看过但未读到文字。脚本仅登记宿主提交的证据，不执行 OCR、不生成摘要。摘要和关键词由宿主根据这些独立证据生成，建议写调用方目录 `summary.md`、`keywords.json`，不作为提取成功的脚本伪造产物。

## 安装依赖

提取完成不表示摘要充分。摘要集成另按 [摘要覆盖复核](summary-coverage.md) 清点子主题、保留比较与选择依据；宿主生成覆盖清单，`scripts/review_summary.py` 校验实际来源和摘要片段。追加画面可用 `extract_frames.py URL NEW_DIR --base-dir OLD_DIR --times '142,145,150'`，复制既有证据到新目录后补帧，不重新转写或覆盖旧目录。

两个 skill 作为同一 Git ref 的同级目录安装；笔记入口通过 sibling 位置发现视频 skill，也可用 `--video-skill <PATH>` 指定。运行 Python 3.9+ 标准库，视频另需要现有 yt-dlp/ffmpeg/whisper.cpp；tests/evals 不安装。

## 可选的正常浏览器取证输入（兼容 v1）

匿名访问受限、已有正常浏览器会话能显示笔记时，宿主可读取可见 DOM/轮播图与实际页面资源，并保存最小取证 JSON 后传 `extract_note.py URL OUTPUT_DIR --rendered-note INPUT_JSON`；不导出 Cookie 或登录凭据。输出 schema、字段与退出码不变。source artifact 增加 provenance=browser_dom。输入包详见笔记 skill 的 references/rendered-note.md；脚本校验原链接、source_url 和 noteId 一致。匿名失败目录与浏览器成功目录分开保留。

可选 `--quality fast|accurate` 复用既有转写档位，默认 fast；不改变 v1 的输出字段和默认字幕优先行为。accurate 沿用既有语音优先的高质量策略。
