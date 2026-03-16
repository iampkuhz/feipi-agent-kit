# 变更记录

## 2026-03-16
- `feipi-gen-skills` v2：统一版本与同日合并规则。
- `feipi-gen-innovation-disclosure` v2：重构交底书流程与验收规则。

## 2026-03-01
- 安装脚本支持 `AGENT=qwen`。
- 完善 `feipi-gen-skills` 变更记录要求并更新 README 安装说明。
- `feipi-gen-skills` 文档结构重构，规则下沉到 `references/`。
- `feipi-gen-skills` 目录标准合并结构与说明。
- 优化 `feipi-summarize-video-url`：背景分析改为视频关键词驱动、交付节奏改为同轮连续输出、转写产物去空格并更新路径表述与校验规则。
- 优化 `feipi-summarize-video-url`：第二次交付强制使用视频外背景资料并附来源清单（含新闻原文/原始文件），同步更新背景请求包与测试校验。
- 优化 `feipi-summarize-video-url`：YouTube 认证失败时自动无 Cookie 重试，新增 noauth 日志提示。
- 优化 `feipi-read-youtube-video`：检测到本地代理端口时优先使用代理下载，失败回退直连。
- 优化 `feipi-summarize-video-url`：新增转写执行严格性约束，禁止自动下载或切换 whisper 模型。
- 优化 `feipi-summarize-video-url`：禁止手写 whisper-cli 参数并提示 `-ot` 误用会触发 `stoi` 错误。
- 优化 `feipi-read-bilibili-video`：默认直连，直连失败且代理端口可用时才使用代理。
- 优化 `feipi-summarize-video-url`：强制经 `extract_video_text.sh` 取转写并校验四个产物非空，避免直接调用依赖脚本。
- 修复 `feipi-summarize-video-url`：无 Cookie 重试时避免 `cmd_prefix` 未定义导致脚本失败。
- `feipi-gen-skills`：变更记录规则极简化。
