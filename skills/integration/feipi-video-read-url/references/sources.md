# 来源与合并说明

## 已归档严道音频与循环稿对照

严道统一入口遇到既有`audio.whisper.wav`时，先流式重解码当前完整视频，核对16kHz单声道16-bit PCM的长度与SHA256。完全相同才复用并保存`audio_cache_validation.json`；参数不符、截断、解码失败或内容不同时停止并保留原件。校验不落地新的音频副本，也不替代视频来源身份检查。

既有循环稿可在独立输出目录中设置`AGENT_VIDEO_RECOVERY_NO_CONTEXT=1`，仍通过`extract_video_text.sh`调用内置whisper.cpp，以`-mc 0`限制前段文字上下文。默认值为`0`，其他值报错；模型、语言、质量档位及原始记录保持明确。只在终止后核对新稿，不能因为循环减少便认定医学文字准确，不直接覆盖主稿或提升整理状态。

本技能由以下三类历史能力合并而来：

1. 旧 YouTube 读取链路
- 历史 skill：`feipi-read-youtube-video`
- 继承内容：YouTube 下载、代理回退、Cookie 或浏览器认证回退、字幕与 whisper 转写策略。

2. 旧 Bilibili 读取链路
- 历史 skill：`feipi-read-bilibili-video`
- 继承内容：Bilibili 下载、直连优先、登录态与字幕限制处理、字幕与 whisper 转写策略。

3. 旧视频摘要链路
- 历史 skill：`feipi-summarize-video-url`
- 继承内容：自动选档、带时间戳文本提取、摘要请求包、扩展背景请求包、背景单问请求包。

## 当前本地化资源

1. `scripts/download_video.sh`
- 用途：统一下载入口；按 URL 来源路由到站点适配脚本。

2. `scripts/download_youtube.sh`
- 用途：YouTube 专用适配脚本。

3. `scripts/download_bilibili.sh`
- 用途：Bilibili 专用适配脚本。

4. `scripts/extract_video_text.sh`
- 用途：统一提取带时间戳文本，并对接摘要或背景流程。

5. `scripts/render_summary_prompt.sh`
- 用途：构建默认摘要请求包，约束输出为“总述 + 结构化列表 + 附件”。

6. `scripts/render_background_prompt.sh`
- 用途：构建背景请求包，支持 `expand` 与 `background-only` 两种模式。

7. `scripts/lib/whispercpp_transcribe.sh`
- 用途：当前 skill 内置的 whisper.cpp 转写脚本，支持 `fast/accurate` 档位。

8. `scripts/lib/yt_dlp_common.sh`
- 用途：当前 skill 内置的 yt-dlp 公共流程，提供通用下载模式、字幕转文本和 whisper 模式公共逻辑。

9. `scripts/lib/video_identity.py`
- 用途：离线整理同次请求的最小视频元数据、提供命名候选和请求包身份展示；缓存仅按完全匹配的输入 URL 复用。
- 使用 yt-dlp 的 `--print-to-file` 在原请求中捕获 ID 和标题，不增加视频请求。

## 上游参考

1. GitHub: daymade/claude-code-skills（`youtube-downloader` 技能方向）
   - https://github.com/daymade/claude-code-skills
2. yt-dlp 官方文档
   - https://github.com/yt-dlp/yt-dlp
3. yt-dlp 支持站点说明
   - https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md
4. whisper.cpp 官方仓库
   - https://github.com/ggml-org/whisper.cpp
5. whisper.cpp 模型发布（large-v3 q5_0）
   - https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin

## 严道单讲适配

- `scripts/download_drvoice.sh` 与 `scripts/lib/drvoice_metadata.py`：公开详情接口核验单讲身份、未加密历史回放，使用同一内置转写引擎。支持 dryrun/video/audio/subtitle/whisper；无字幕返回明确诊断。
- 支持范围：`https://www.drvoice.cn/v2/speaker/<编号>`，及 `https://www.drvoice.cn/v2/article/<编号>` 中的直接视频文件。不读取浏览器 Cookie；报名默认停止并逐例处理，付费、加密或实时直播停止；集合页先选单讲。

严道适配支持 video/videoEn 媒体字段及已核验的 video.drvoice.cn、videobj.drvoice.cn、videosz.drvoice.cn、drvoiceke.oss-cn-beijing.aliyuncs.com；后两个域名已由2026-10-20官网单讲详情及同址HTTPS响应头核验，旧HTTP仅升级同域HTTPS。语音语言默认 auto，可通过 AGENT_VIDEO_LANGUAGE=zh/en 限定。未发现字幕字段不表示画面没有硬字幕，应先检查原始画面。

文章多视频用 `AGENT_DRVOICE_VIDEO_INDEX=1/2/...` 选择，身份为 article-<页面编号>-video-<序号>，不与单讲编号混淆。文章资源接受上述四个域名及drvoicedev.oss-cn-beijing.aliyuncs.com、drvoice201608.oss-cn-beijing.aliyuncs.com；旧HTTP资源仅向同域HTTPS升级。iframe未解析时明确停止，不把介绍算作内容。

### 已报名账号的逐例播放证据

当正常登录页面已实际播放到结尾，可用 `AGENT_DRVOICE_ACCOUNT_EVIDENCE=/绝对路径/账号播放证据.json` 将该单讲接回原统一入口；先运行 `dryrun`。证据须来自本次原生页面核查，不能用题名、接口报名标记或短片预览代替完整播放。

证据格式为 `schema=drvoice-account-playback-v1`，含 `source_id`、`source_url`、带时区的 `checked_at`，以及严格布尔值 `login_confirmed`、`playback_reached_end_observed`、`no_registration_or_payment_prompt_seen`、`native_DOM_video_src_observed`。`media_reference_sha256` 必须匹配当前公开详情媒体地址，`manifest_sha256` 必须匹配实际HLS清单；证据有效期24小时。

该路径仅适用于单讲、无付费标记、无凭据参数的HLS地址。原公开报名标记保存在输出中，其他来源仍逐例停止；加密、实时清单、来源或指纹变化均停止。它不读取Cookie、账号存储或认证请求头。通过预检不等于完成媒体下载、字幕提取或内容解读，正式提取仍执行独立存储预检。
