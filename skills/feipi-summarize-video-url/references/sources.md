# 相关来源（精简）

路径基准：相对本 skill 的 `SKILL.md` 所在目录。

1. `../feipi-read-youtube-video/SKILL.md`
- 用途：YouTube 链接的字幕/转写提取入口。

2. `../feipi-read-bilibili-video/SKILL.md`
- 用途：Bilibili 链接的字幕/转写提取入口。

3. `scripts/render_summary_prompt.sh`
- 用途：构建“第一次交付”请求包，约束输出为“总述 + 结构化列表 + 附件（原始视频链接 + 转写文本）”，并合并时间线到摘要锚点。

4. `scripts/render_background_prompt.sh`
- 用途：构建“第二次交付”请求包，要求背景以视频外公开资料为主并附来源清单，影响分析精简，且围绕视频关键词展开外部解释。

5. `../../feipi-scripts/video/whispercpp_transcribe.sh`
- 用途：仓库级 whisper.cpp 转写脚本，支持 `fast/accurate` 档位。

6. `../../feipi-scripts/video/yt_dlp_common.sh`
- 用途：仓库级 yt-dlp 公共流程，提供 whisper 模式与字幕转文本能力。
