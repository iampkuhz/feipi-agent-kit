---
name: feipi-read-youtube-video
description: 用于下载 YouTube 视频或音频并保存到本地目录，支持 dryrun、字幕提取与 whisper.cpp 转写。在需要验证链接可下载、提取音频或批量保存视频素材时使用。
---

# YouTube 下载技能（中文）

## 核心目标

稳定下载 YouTube 视频/音频，输出可验证结果，并在失败时给出可执行修复路径。
脚本会优先使用本地代理（若端口存在），代理失败再回退直连；若未检测到代理，先直连再回退 `127.0.0.1:7890`。

## 触发条件

当用户出现以下意图时触发：
- 下载 YouTube 视频到本地
- 提取 YouTube 音频（如 mp3）
- 先验证链接可下载再执行
- 批量处理播放列表（需用户明确允许）

## 边界与合规

1. 仅处理用户有权下载和使用的内容。
2. 默认关闭播放列表批量下载，避免误下载大量内容。
3. 若用户未提供 URL，不执行下载，先索取链接。

## 依赖

1. `yt-dlp`
2. `ffmpeg`（下载合并高质量视频、音频转码时需要）
3. `whisper.cpp`（`whisper-cli`，`whisper` 模式需要）

依赖安装入口：
```bash
bash scripts/install_deps.sh
```
仅检查：
```bash
bash scripts/install_deps.sh --check
```

## whisper.cpp 模型约定（质量优先）

1. 固定模型路径（脚本内置）：
- `/Users/<用户名>/Library/Caches/whisper.cpp/models/ggml-large-v3-q5_0.bin`
2. 模型策略：
- 默认使用 `large-v3 q5_0`，优先质量，不追求速度。
3. 维护方式：
- 转写逻辑统一由仓库级脚本 `feipi-scripts/video/whispercpp_transcribe.sh` 维护，本 skill 只负责下载音频并调用。
- 依赖安装逻辑统一由仓库级脚本 `feipi-scripts/video/install_video_deps.sh` 维护，本 skill 的 `scripts/install_deps.sh` 仅作转发入口。
- `yt-dlp` 通用命令组装与基础模式统一由仓库级脚本 `feipi-scripts/video/yt_dlp_common.sh` 维护，本 skill 仅维护 YouTube 特有策略（如 bot 重试与字幕语言策略）。
4. 一次性下载（如需手动）：
```bash
mkdir -p "$HOME/Library/Caches/whisper.cpp/models"
curl -L --fail \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin" \
  -o "$HOME/Library/Caches/whisper.cpp/models/ggml-large-v3-q5_0.bin"
```

## 环境变量配置（用于应对 bot 检测与网络回退）

1. 统一模板文件：仓库根目录 `.env.example`
2. 关键变量：
- `AGENT_CHROME_PROFILE`：从浏览器 profile 读取登录态
- `AGENT_YOUTUBE_COOKIE_FILE`：使用 cookies.txt 文件登录态（Netscape Cookie File 格式）
- `AGENT_VIDEO_PROXY_PORT`：可选代理端口（检测到端口可用即优先代理；默认 `7890`）

说明：
- 脚本默认不提示配置；仅在遇到 bot 检测时才提醒配置认证参数。
- `AGENT_CHROME_PROFILE` 与 `AGENT_YOUTUBE_COOKIE_FILE` 同时存在时，默认优先使用 cookie 文件。  
- 仅读取当前 shell 环境变量；`.env.example` 仅作为模板，不自动加载。

## 工作流（Explore -> Plan -> Implement -> Verify）

1. Explore
- 确认 URL、输出目录、目标格式（视频/音频）。
- 若需求不明确，默认：下载单视频到 `./downloads`。

2. Plan
- 选择模式：`video`、`audio`、`dryrun`、`subtitle`、`whisper`。
- 明确输出路径与命名。

3. Implement
- 运行脚本：`scripts/download_youtube.sh`。
- 对未知站点或异常链接，先 `dryrun` 再实下载。

4. Verify
- 检查命令退出码为 0。
- 检查输出目录存在新增文件。
- 记录验证结果（文件名、大小、路径）。

## 标准命令

1. 下载视频（默认）：
```bash
bash scripts/download_youtube.sh "<youtube_url>" "./downloads" video
```

2. 提取音频（mp3）：
```bash
bash scripts/download_youtube.sh "<youtube_url>" "./downloads" audio
```

3. 仅验证可下载（不真正下载）：
```bash
bash scripts/download_youtube.sh "<youtube_url>" "./downloads" dryrun
```
说明：`dryrun` 只输出标题和视频 ID，不生成下载文件。适合先验证链接与权限，再执行真实下载。

3.1 指定代理端口（检测到端口可用即优先代理）：
```bash
AGENT_VIDEO_PROXY_PORT=7891 bash scripts/download_youtube.sh "<youtube_url>" "./downloads" dryrun
```
说明：脚本若检测到代理端口可用会优先使用代理；代理失败才回退直连。未检测到代理时，才先直连后回退默认端口。

4. 提取字幕文本（优先中英字幕，保留时间戳）：
```bash
bash scripts/download_youtube.sh "<youtube_url>" "./downloads" subtitle
```
说明：输出 `.txt` 为时间线格式（如 `- [00:12] ...`），便于后续摘要与观点定位。

5. 强制语音转写（whisper，保留时间戳）：
```bash
bash scripts/download_youtube.sh "<youtube_url>" "./downloads" whisper
```
说明：
- 可选第 4 参数：`auto|fast|accurate`（示例：`whisper fast`、`whisper accurate`）。
- `auto` 策略：先读取视频时长；短视频（<= 480 秒）选 `accurate`，长视频选 `fast`，若时长不可得默认 `fast`。
- 转写先尝试 Metal（GPU），失败自动回退 CPU，再把 `srt` 转为带时间戳 `.txt`。

## 失败处理

1. 缺少依赖
- 提示安装 `yt-dlp`、`ffmpeg`、`whisper-cpp`，并确保 `q5_0` 模型文件存在。

2. 地区/权限限制 / bot 检测
- 先执行 `dryrun`，返回错误摘要给用户。
- 参考仓库根 `.env.example` 手动 export `AGENT_CHROME_PROFILE` 或 `AGENT_YOUTUBE_COOKIE_FILE` 后重试。

3. 网络不通（YouTube 直连失败）
- 若本地代理端口可用，脚本会优先走代理；代理失败才回退直连。
- 未检测到代理端口时，脚本会先直连，再回退到 `http://127.0.0.1:7890` 代理重试。
- 若仍失败，按提示设置 `AGENT_VIDEO_PROXY_PORT=<你的端口>` 后重试。

4. 下载成功但无音频/无视频
- 优先改用默认 `video` 模式重试。

5. `whisper` 模式失败
- 检查 `whisper-cli` 是否存在（建议 `brew install whisper-cpp`）。
- 检查模型文件是否存在于 `$HOME/Library/Caches/whisper.cpp/models/ggml-large-v3-q5_0.bin`。

## 验收标准

1. 至少执行一次 `dryrun` 或真实下载。
2. 输出包含：执行命令、结果状态、文件路径。
3. 若失败，输出明确错误与下一步建议。

## 参考

- 来源与改造记录：`references/sources.md`
