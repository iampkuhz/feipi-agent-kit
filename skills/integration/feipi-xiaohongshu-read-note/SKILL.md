---
name: feipi-xiaohongshu-read-note
description: 读取小红书图文或视频笔记及分享短链，保存正文与顺序原图，并对视频复用字幕、语音与关键帧证据；用于提取笔记内容，不用于发布、登录或独立处理其他平台视频。
---

# 小红书笔记读取

给定小红书 `/explore/<ID>`、`/discovery/item/<ID>` 长链或 xhslink.com / xhslink.cn 分享短链，将原链接、页面来源、笔记文案、原图及视频证据保存在调用方指定目录。两个 skill 安装为同级目录；视频依赖 `feipi-video-read-url`，不引入外部解析服务。

## 执行

```bash
python3 <本 skill>/scripts/extract_note.py '<URL>' '<OUTPUT_DIR>'
```

安装路径不同可传 `--video-skill '<feipi-video-read-url 目录>'`。视频默认字幕优先、whisper.cpp fast 回退、均匀抽取6个关键帧；需要复查具体画面可传 `--frame-times '0,12,30'`（秒，最多24个）。高质量转写可传 `--quality accurate`。完整视频从不作为提取回退，只有独立音频流才能转写；只有合流视频而无独立音频时明确保留部分结果。结果写入非空目录或 skill 安装目录会被拒绝。

脚本 stdout 返回 `manifest_path` 和 `status`。退出码 0=complete、2=partial、1=failed/blocked。即使返回非零也先读取 manifest；错误参数、目录不可写或缺少视频 skill 时可能尚无 manifest。输出合同由同级 `feipi-video-read-url` 中的 `content-extraction.md` 提供；路径也可由 `--video-skill` 确认。

匿名请求受限但正常浏览器会话可读时，保留失败目录，然后按 [浏览器可见页面取证](references/rendered-note.md) 生成最小取证包，以 `--rendered-note` 导入新目录；不导出凭据。

## 实际读图与 OCR

1. 读取 manifest 的 metadata、channels 与 artifacts；页面、正文、字幕、ASR 是独立证据。标题只用于身份，正文只作为笔记文案，不得代替视频转写。
2. 按 image 的 `anchor.index` 顺序实际打开保存的图片，再按 frame 的 `anchor.seconds` 打开关键帧。保存图片不等于已读取图片。可用本机 OCR 辅助，但核对原图；不引入未经验证的外部解析服务。
3. 对每张实际读取的图片/帧分别写 `source_artifact_id`、`ocr_text`、`observation`、`uncertainties`。模糊品牌、数字、尺寸明确保留不确定；没读到文字使用空字符串，不推断不存在文字。视频封面标为 video_cover，不视为视频帧。
4. 将 JSON 数组交给视频 skill 的 `scripts/record_observations.py '<OUTPUT_DIR>' '<JSON_FILE>'`，将 OCR 和视觉观察分别登记；未读图片保持 pending。
5. 宿主模型仅根据 body/subtitles/asr 和实际读取的图片/帧生成摘要、关键词，分别标注文案、语音、图号/时间点；不得用搜索摘要补齐。可写调用方目录 `summary.md`、`keywords.json`，无需把内容带回 skill。
6. 先读同级 `feipi-video-read-url` 的 `SKILL.md`，按其中“摘要覆盖复核”指引清点全文及每张图的主题/子主题，逐项保留比较、建议、理由、代价和适用条件；生成 `summary_coverage.json`，调用该视频 skill 中的摘要复核脚本（`review_summary.py MANIFEST SUMMARY COVERAGE`）。图片保存和提取 complete 不代表摘要充分；无法确认的内容在摘要明确待核验。校验只检查引用可追溯，不能替代实际语义复核。

## 状态与交付

- `source.status=blocked` + reason 区分 login_required、verification_required、access_denied、rate_limited、note_unavailable；不自动读取浏览器登录凭据、不尝试绕过验证码。
- `note_data_unavailable` 表示匿名页面未提供目标笔记数据，不能断言“无正文”或“用户未登录”。正文缺失为 body_not_exposed/body_not_read；只有页面明确提供空 desc 才保存空正文。
- 某图片失败保留原始序号、expected_count、failures 和其余成功原图；视频不能按需抽帧时记录 frames 的原因和已有文字，不下载整片补救。
- `frames.sampling` 仅代表已抽样范围，不表示逐帧覆盖；时长未知只抽开头并明确 partial。需要精细画面时按具体时间扩展采样。
- 交付原始链接、manifest、原文、摘要和实际用到的图片/帧路径，并说明未取得/未读取的证据。不暴露本地凭据、授权参数或环境变量值。
