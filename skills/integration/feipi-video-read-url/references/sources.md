# 来源与合并说明

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
