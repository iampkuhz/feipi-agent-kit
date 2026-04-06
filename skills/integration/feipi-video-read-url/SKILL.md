---
name: feipi-video-read-url
description: 用于按用户意图下载、提取或总结视频网站 URL，统一覆盖 dryrun、音视频提取、字幕或 whisper 转写、摘要和背景扩展，并为后续新增视频站点预留统一适配入口。
---

# 视频 URL 读取与总结（中文）

## 核心目标

输入视频 URL，根据用户意图走一条统一链路：

1. 直接读取
- `dryrun`：只验证链接和权限，不真实下载。
- `video`：下载视频。
- `audio`：提取音频。
- `subtitle`：优先提取标准字幕并转成带时间戳文本。
- `whisper`：在无可用字幕或用户明确要求时，使用 `whisper.cpp` 转写。

2. 内容总结
- `summary`：只交付结构化摘要。
- `expand`：先交付摘要，再补背景和影响分析。
- `background-only`：只交付上下文背景，不强制先给摘要。

3. 站点扩展
- 当前统一入口已覆盖 YouTube、Bilibili。
- 后续新增站点时，只在当前 skill 内新增来源适配脚本，不再新建平行 skill。

## 适用场景

1. 用户给出视频 URL，希望先验证链接是否可读、可下载或可转写。
2. 用户要下载视频、提取音频、提取字幕、做 whisper 转写。
3. 用户只想先拿到结构化摘要，不希望默认继续做背景分析。
4. 用户明确要求“继续扩展分析”“补充背景/影响/相关新闻/最新进展”。
5. 用户单独追问“这个视频的上下文背景是什么”“这件事的来龙去脉是什么”。

## 不适用场景

1. 用户没有提供视频 URL。
2. 用户只给本地音视频文件，不是 URL 来源。
3. 用户要求跳过当前 skill、手工拼接下载/转写命令。
4. 需要治理、重构或迁移 skill 本身；这类任务应使用 `feipi-skill-govern`。

## 先确认什么

1. 必填
- 视频 URL

2. 按需确认
- 输出目录
- 用户当前目标是 `dryrun`、`video`、`audio`、`subtitle`、`whisper`、`summary`、`expand` 还是 `background-only`
- 用户原始指令中是否明确要求高质量转写
- 用户是否明确要求相关新闻/最新进展/当前影响
- 是否已有视频标题或上下文说明
- 是否允许批量处理（当前默认不自动展开播放列表或合集）

默认策略：
1. 如果用户要摘要、背景或分析，默认从 `summary / expand / background-only` 三类中决策。
2. 如果用户要下载、提取、转写或先验证链接，走 `dryrun / video / audio / subtitle / whisper`。
3. 若用户只给 URL、意图不清，默认先做 `dryrun`，不直接真实下载。
4. 有“高质量/准确/逐字”等明确要求时，转写档位自动走 `accurate`；其他情况默认 `fast`。
5. 未明确要求背景时，不自动进入第二阶段分析。
6. 背景阶段若未明确要求“相关新闻/最新/最近/现状”，默认 `--news off`，优先稳定背景资料，不主动搜索相关新闻。

## 关键原则

1. 执行链路统一
- 下载、字幕提取、whisper 转写、摘要请求包、背景请求包都从当前 skill 本地脚本发起。
- 不再依赖仓库外部共享脚本或其他 video skill。

2. 不做本地“伪摘要”
- 本 skill 负责下载、转写、提取文本与构建请求包。
- 最终摘要或背景内容必须由大模型基于转写和外部资料生成，禁止用词频或模板硬拼结论。

3. 转写严格性（强制）
- 只允许使用当前 skill 内置的 `whisper.cpp` 链路（`scripts/lib/whispercpp_transcribe.sh`）。
- 禁止改用 Python 版 whisper、OpenAI whisper 或其他转写工具。
- fast 只允许使用已存在的 `ggml-base.bin`（或 `ggml-small.bin` / `ggml-large-v3-turbo-q5_0.bin`）。
- accurate 只允许使用已存在的 `ggml-large-v3-q5_0.bin`。
- 运行时若模型缺失，只能提示用户显式执行 `scripts/install_deps.sh`，禁止脚本静默切换其他模型。
- 必须通过 `scripts/extract_video_text.sh` 获取带时间戳文本，禁止手写 `whisper-cli` 参数。

4. 分段触发强约束
- 未显式要求背景时，不得自动补第二阶段。
- 只有 `expand` 才允许同一轮连续输出“摘要 + 背景”。
- `background-only` 只输出背景，不强制先给摘要。
- 默认摘要模式禁止主动补充视频外背景、相关影响和相关新闻。

5. 摘要与时间线合并
- 不再单独输出“核心观点时间线”章节。
- 时间线信息必须并入 `摘要概述` 的列表锚点中。
- 时间格式统一：
  - 视频时长未超过 1 小时：`MM:SS`
  - 视频时长超过 1 小时：`HH:MM:SS`
  - 禁止 `T+00:00:00` 与字幕行号。

6. 总分结构强约束
- `摘要概述` 第一段必须是总述（先总后分）。
- 后续列表按关系选型：
  - 有先后/因果链：有序列表。
  - 关系并列：无序列表。
  - 存在总分关系：使用二级列表（最多二级）。

7. 背景模式外部化约束
- 背景内容必须以视频外公开资料为主，不以转写复述冒充背景。
- 如需引用视频内容，仅作为“关联说明”或“对照观点”，不得替代外部背景。
- 未明确要求相关新闻时，优先历史背景、制度沿革、术语解释、官方基础文件、研究资料，不主动搜索相关新闻。
- 明确要求“相关新闻/最新进展/现状”时，才允许补充时效性材料，并在来源中写清日期。

## 来源支持与扩展边界

1. 当前来源
- YouTube：由 `scripts/download_youtube.sh` 适配。
- Bilibili：由 `scripts/download_bilibili.sh` 适配。

2. 统一入口
- 用户态统一入口：`scripts/download_video.sh` 与 `scripts/extract_video_text.sh`。
- 当前 skill 内部允许保留站点适配脚本，但这些脚本不再作为独立 skill 对外暴露。

3. 后续新增站点的约束
- 只在当前 skill 内新增 `scripts/download_<source>.sh`。
- 同步更新 `scripts/download_video.sh`、`scripts/extract_video_text.sh`、`SKILL.md`、`agents/openai.yaml`、`references/test_cases.txt` 和 `scripts/test.sh`。
- 不再为单一站点新建平行 skill。

## 输入与输出

1. 最少输入
- 视频 URL

2. 可选输入
- 视频标题
- 输出目录
- 用户原始指令（用于自动判定提取质量档位与交付意图）
- 直接读取模式：`dryrun|video|audio|subtitle|whisper`
- 质量档位参数：`--quality auto|fast|accurate`（默认 `auto`）
- 总结模式：`summary|expand|background-only`
- 新闻范围：`--news off|on`（默认 `off`）

3. 输出
- `extract_video_text.sh` 会在 `output_dir` 下按 `source-url_key` 自动建子目录。
- 子目录内包含本次 URL 的音频、字幕、转写与日志，避免多视频文件平铺。
- 产物文件名自动去空格（空格替换为下划线）。
- 直接读取模式会额外产出：
  - `dryrun`：标题、视频 ID、网络或认证状态日志。
  - `video`：视频文件。
  - `audio`：音频文件。
  - `subtitle` / `whisper`：带时间戳文本。
- `summary_request.md`：`summary` 或 `expand` 模式使用的摘要请求包。
- `summary_result.md`：`summary` 或 `expand` 模式的摘要结果。
- `background_request.md`：`expand` 或 `background-only` 模式使用的背景请求包。
- `background_result.md`：背景结果；`expand` 模式标题为 `相关影响和背景分析`，`background-only` 模式标题为 `上下文背景`。

## 自动选档规则

1. 默认策略（`--quality auto`）
- 指令明确要求高质量（如“高质量/高精度/准确/逐字”）时，选择 `accurate`。
- 其他情况默认选择 `fast`。

2. `mode=auto` 的执行顺序
- `accurate`：先 `whisper`，失败再回退 `subtitle`。
- `fast`：先 `subtitle`，失败再回退 `whisper`。

3. 观测字段
- `extract_video_text.sh` 输出中包含：
  - `run_dir`
  - `whisper_profile`
  - `selection_reason`
  - `strategy`

## 工作流（Explore -> Plan -> Implement -> Verify）

1. Explore
- `scripts/download_video.sh` 与 `scripts/extract_video_text.sh` 内部识别来源（当前为 YouTube/Bilibili）。
- `scripts/install_deps.sh --check` 或 `scripts/extract_video_text.sh --check-deps` 校验依赖与自动选档结果。
- 先判断用户意图属于直接读取还是总结模式。
- 再判断背景阶段是否明确要求“相关新闻/最新进展”；未明确时默认 `--news off`。
- 若检测到 YouTube 在 Cookie 或浏览器认证下失败，会自动以“无 Cookie”重试，并输出 `*-noauth.log` 便于排查。
- 若转写失败，只能回到当前 skill 的本地脚本排查网络、认证或模型缺失；禁止切换转写工具。

2. Plan
- 直接读取模式：确定 `dryrun / video / audio / subtitle / whisper`。
- 总结模式：根据用户指令选择质量档位，再经 `scripts/extract_video_text.sh` 获取带时间戳文本。
- `summary`：只生成摘要请求包并交付摘要结果。
- `expand`：先交付摘要，再生成背景请求包并继续交付背景分析。
- `background-only`：直接生成背景请求包并交付上下文背景，不强制先展示摘要。

3. Implement
- 直接读取模式：使用 `scripts/download_video.sh` 执行。
- `summary`：使用 `scripts/render_summary_prompt.sh` 生成 `summary_request.md`，并只产出 `summary_result.md`。
- `expand`：先生成并交付 `summary_result.md`，再使用 `scripts/render_background_prompt.sh --mode expand` 生成 `background_request.md`，继续产出 `background_result.md`。
- `background-only`：直接使用 `scripts/render_background_prompt.sh --mode background-only` 生成 `background_request.md`；若没有现成摘要，第三个参数传 `-`。
- 只有在用户明确要求相关新闻或最新进展时，背景脚本才传 `--news on`；其他情况保持 `--news off`。

4. Verify
- 直接读取模式：
  - `dryrun` 成功返回标题或 ID，且不生成媒体文件。
  - `video` / `audio` / `subtitle` / `whisper` 至少生成对应产物。
- 摘要请求包包含 `<TRANSCRIPT_START>` 与 `<TRANSCRIPT_END>`。
- 摘要请求包包含反套话约束、列表结构约束与时间锚点约束。
- 摘要请求包明确“当前只做摘要，不扩展背景/影响/相关新闻”。
- `expand` 请求包明确要求输出 `## 相关影响和背景分析`。
- `background-only` 请求包明确要求输出 `## 上下文背景`。
- 转写文本与产物文件名不包含空格。

## 常见失败与修复

1. 用户只给 URL，却直接开始真实下载
- 处理：回到默认策略；若意图不清，先做 `dryrun`。

2. 执行方默认把摘要和背景一起做完
- 处理：回到意图判断；未显式要求背景时，只执行 `summary`。

3. 用户单独问背景时仍被迫先看摘要
- 处理：改用 `background-only`，并允许 `summary_path` 传 `-`。

4. 摘要模式主动补了相关新闻
- 处理：回到摘要请求包边界，删除背景、影响和相关新闻扩写，只保留内容摘要。

5. 背景分析只是复述视频
- 处理：回到背景模式要求，补充视频外公开资料与来源清单。

6. 站点不受支持
- 处理：明确告知当前支持范围，并把新增来源记录为当前 skill 的后续适配任务，而不是新建独立 skill。

## 标准命令

执行前可先设置：
```bash
SKILL_DIR="/Users/zhehan/Documents/tools/llm/skills/agent-skills/skills/integration/feipi-video-read-url"
```

1. 检查依赖：
```bash
bash "$SKILL_DIR/scripts/install_deps.sh" --check
```

2. 仅验证链接可读（不真实下载）：
```bash
bash "$SKILL_DIR/scripts/download_video.sh" "<video_url>" "./tmp/video-read" dryrun
```

3. 提取字幕文本：
```bash
bash "$SKILL_DIR/scripts/download_video.sh" "<video_url>" "./tmp/video-read" subtitle
```

4. 强制 whisper 转写：
```bash
bash "$SKILL_DIR/scripts/download_video.sh" "<video_url>" "./tmp/video-read" whisper fast
```

5. 自动选档提取（默认快档）：
```bash
bash "$SKILL_DIR/scripts/extract_video_text.sh" "<video_url>" "./tmp/video-text" auto \
  --instruction "请快速提取并总结重点"
```

6. 高质量提取（触发慢档）：
```bash
bash "$SKILL_DIR/scripts/extract_video_text.sh" "<video_url>" "./tmp/video-text" auto \
  --instruction "请高质量逐字转写，准确优先"
```

7. 检查依赖并输出选档结果：
```bash
bash "$SKILL_DIR/scripts/extract_video_text.sh" "<video_url>" "./tmp/video-text" auto \
  --instruction "请快速总结" \
  --check-deps
```

8. 生成默认摘要请求包：
```bash
bash "$SKILL_DIR/scripts/render_summary_prompt.sh" \
  "<video_url>" \
  "示例视频标题" \
  1500 \
  "./tmp/video-text/xxx.txt" \
  80000 \
  > "./tmp/video-text/summary_request.md"
```

9. 生成“扩展分析”背景请求包：
```bash
bash "$SKILL_DIR/scripts/render_background_prompt.sh" \
  "<video_url>" \
  "示例视频标题" \
  "./tmp/video-text/summary_result.md" \
  "./tmp/video-text/xxx.txt" \
  --mode expand \
  --news off \
  > "./tmp/video-text/background_request.md"
```

10. 生成“单独问背景”请求包：
```bash
bash "$SKILL_DIR/scripts/render_background_prompt.sh" \
  "<video_url>" \
  "示例视频标题" \
  "-" \
  "./tmp/video-text/xxx.txt" \
  --mode background-only \
  --news off \
  > "./tmp/video-text/background_request.md"
```

## 验收标准

1. 命令入口统一收敛到当前 skill 本地脚本，不依赖其他 video skill 或外部共享脚本。
2. 当前至少支持 YouTube 与 Bilibili，两者都能经统一入口触发。
3. 直接读取模式能清楚区分 `dryrun / video / audio / subtitle / whisper`。
4. 总结模式能清楚区分 `summary / expand / background-only`，且不会误触发第二阶段。
5. 结构校验、行为校验和旧引用残留搜索均能在当前 skill 本地闭环完成。

## 资源说明

- 统一下载入口：`scripts/download_video.sh`
- 统一提取入口：`scripts/extract_video_text.sh`
- 依赖安装入口：`scripts/install_deps.sh`
- 请求包模板脚本：`scripts/render_summary_prompt.sh`、`scripts/render_background_prompt.sh`
- 本地公共库：`scripts/lib/yt_dlp_common.sh`、`scripts/lib/whispercpp_transcribe.sh`
- 测试用例：`references/test_cases.txt`
- 来源说明：`references/sources.md`
