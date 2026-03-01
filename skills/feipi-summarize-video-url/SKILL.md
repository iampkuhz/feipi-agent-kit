---
name: feipi-summarize-video-url
description: 用于根据视频 URL 调用来源技能提取带时间戳文本，并生成两阶段远程总结请求包。在需要先交付结构化摘要、再补充背景与影响分析时使用。
---

# 视频 URL 文本总结技能（中文）

## 核心目标

输入视频 URL，默认输出两阶段交付结果，并生成两阶段请求包（提示词 + 字幕文本）。

1. 第一次交付（先返回用户）
- `摘要概述`：先总述，再用 1-2 级列表展开核心内容（仅保留视频时间锚点）。
- `附件`：给出原始视频跳转链接 + 本地转写文本路径。

2. 第二次交付（第一次后继续处理）
- `相关影响和背景分析`：补充背景知识与关键影响（背景为主、影响为辅）。

## 关键原则

1. 不做本地“伪摘要”
- 本 skill 负责提取文本与构建请求包，交付内容必须由大模型基于转写生成。
- 禁止用词频/规则模板直接拼接结论。

2. 执行严格性（强制）
- 只能使用依赖技能提供的 `whisper.cpp` 转写链路（`whisper-cli`）。
- 禁止改用 Python 版 whisper、OpenAI whisper 或其他转写工具。
- 禁止自动下载或切换其他 whisper 模型文件。
- fast 只允许使用已存在的 `ggml-base.bin`（或 `ggml-small.bin` / `ggml-large-v3-turbo-q5_0.bin`）。
- accurate 只允许使用已存在的 `ggml-large-v3-q5_0.bin`。
- 若模型缺失，只能提示用户按仓库脚本/说明手动安装，禁止自作主张联网下载。
- 必须通过依赖脚本调用转写，禁止手写 `whisper-cli` 参数（例如误用 `-ot` 会触发 `stoi` 错误）。

3. 摘要与时间线合并
- 不再单独输出“核心观点时间线”章节。
- 时间线信息必须并入 `摘要概述` 的列表锚点中（仅时间）。
- 时间格式统一：
  - 视频时长未超过 1 小时：`MM:SS`
  - 视频时长超过 1 小时：`HH:MM:SS`
  - 禁止 `T+00:00:00` 与字幕行号。

4. 总分结构强约束
- `摘要概述` 第一段必须是总述（先总后分）。
- 后续列表按关系选型：
  - 有先后/因果链：有序列表。
  - 关系并列：无序列表。
  - 存在总分关系：使用二级列表（最多二级）。

5. 去套话
- 请求包中显式禁用无意义模板句。
- 目标是直接提炼信息，不是点评文本写法。

6. 详略由模型读文本后决定
- 不依赖本地信息密度脚本。
- 仅按时长给建议条目区间，具体详略由远程模型判断。

7. 第二次交付必须可判定
- `相关影响和背景分析` 必须“背景知识为主（约 2/3）+ 关键影响为辅（约 1/3）”。
- 背景必须覆盖本次视频中的关键术语/人物/机构/事件（至少 3-6 个），先列清单再用外部资料逐条补充解释。
- 背景必须基于视频外公开资料（历史/制度/新闻原文/术语解释），禁止仅按视频时间线复述或改写转写内容。
- 背景必须给出来源清单（来源名/机构 + 日期 + 标题/文件名），不少于 3 条，优先官方/主流媒体/研究机构/政策或学术文件，且至少包含 1-2 条新闻原文或原始文件。
- 影响只写最关键 1-2 条，禁止冗长推演与空泛表述。
- 禁止套用与本视频无关的固定条款/模板术语。

8. 背景外部化强约束
- 第二次交付必须以外部背景为主，不以转写内容复述充当背景。
- 如需引用视频内容，仅作为“关联说明”或“对照观点”，不得替代外部背景。

9. 交付节奏强约束
- 两阶段交付必须在同一轮回复连续输出，不等待用户确认。
- 若需要远程模型结果，执行方应直接产出两次交付或自动调用，不得只停留在请求包。

## 依赖技能（强约束）

路径基准：相对 `SKILL.md` 所在目录。

必须依赖：
1. `../feipi-read-youtube-video`
2. `../feipi-read-bilibili-video`

规则：
- YouTube：调用 `../feipi-read-youtube-video/scripts/download_youtube.sh`
- Bilibili：调用 `../feipi-read-bilibili-video/scripts/download_bilibili.sh`
- 依赖缺失：立即停止并提示用户先配置。

## 输入与输出

1. 最少输入
- 视频 URL

2. 可选输入
- 视频标题
- 用户原始指令（用于自动判定提取质量档位）
- 质量档位参数：`--quality auto|fast|accurate`（默认 `auto`）

3. 输出
- `extract_video_text.sh` 会在 `output_dir` 下按 `source-url_key` 自动建子目录（如 `youtube-5Foo8VUZlFM`、`bilibili-BV1Q5fgBfExq`）。
- 子目录内包含本次 URL 的音频/字幕/转写与日志，避免多视频文件平铺。
- 产物文件名自动去空格（空格替换为下划线）。
- `summary_request.md`：第一次交付请求包（`摘要概述` + `附件`）。
- `summary_result.md`：第一次交付结果（`摘要概述` + `附件`）。
- `background_request.md`：第二次交付请求包（`相关影响和背景分析`）。
- `background_result.md`：第二次交付结果（`相关影响和背景分析`）。

## 自动选档规则（提速重点）

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
- `scripts/extract_video_text.sh` 内部识别来源（YouTube/Bilibili）。
- `scripts/extract_video_text.sh --check-deps` 校验依赖与自动选档结果。
- 若检测到 YouTube 在 Cookie/浏览器认证下失败，会自动以“无 Cookie”重试，并输出 `*-noauth.log` 便于排查。
- 若转写失败，只能回到依赖技能排查网络/认证/模型缺失；禁止切换转写工具或自动下载模型。

2. Plan
- 根据用户指令选择质量档位（默认快档，显式高质量则慢档）。
- `scripts/extract_video_text.sh` 获取带时间戳文本。
- 第一次交付：合并“摘要+时间线”，时间仅用 `MM:SS/HH:MM:SS`。
- 第二次交付：输出“背景知识补充（约 2/3）+ 关键影响（约 1/3）”，背景必须用视频外公开资料补充（历史/制度/新闻原文或原始文件/术语解释）并给出来源清单，避免复述第一次内容。

3. Implement
- 使用 `scripts/render_summary_prompt.sh` 生成第一次请求包（`summary_request.md`）。
- 根据 `summary_request.md` 直接产出第一次结果（`summary_result.md`），并在同一回复交付。
- 继续使用 `scripts/render_background_prompt.sh` 生成第二次请求包（`background_request.md`）。
- 根据 `background_request.md` 直接产出第二次结果（`background_result.md`），背景内容必须引用视频外资料并列出来源清单，紧接第一次交付输出。

4. Verify
- 请求包包含 `<TRANSCRIPT_START>` 与 `<TRANSCRIPT_END>`。
- 第一次请求包包含反套话约束与列表结构约束。
- 第一次请求包要求锚点格式：`[MM:SS]` 或 `[HH:MM:SS]`。
- 第一次请求包明确禁止单独输出 `核心观点时间线` 章节。
- 第一次请求包明确“附件为原始视频链接 + 转写文本路径”。
- 第二次请求包明确要求输出 `相关影响和背景分析` 且不复述第一次内容。
- 第二次请求包明确要求“背景知识约 2/3 + 关键影响约 1/3”，且必须使用视频外背景资料并提供来源清单（含新闻原文/原始文件）。
- 转写文本与产物文件名不包含空格。

## 标准命令

1. 检查依赖：
```bash
bash scripts/extract_video_text.sh "<video_url>" "./tmp/video-text" auto \
  --instruction "请快速总结" \
  --check-deps
```

2. 自动选档提取（默认快档）：
```bash
bash scripts/extract_video_text.sh "<video_url>" "./tmp/video-text" auto \
  --instruction "请快速提取并总结重点"
```

3. 高质量提取（触发慢档）：
```bash
bash scripts/extract_video_text.sh "<video_url>" "./tmp/video-text" auto \
  --instruction "请高质量逐字转写，准确优先"
```

4. 显式指定档位（可绕过自动判定）：
```bash
bash scripts/extract_video_text.sh "<video_url>" "./tmp/video-text" whisper \
  --quality accurate
```

5. 生成第一次请求包：
```bash
bash scripts/render_summary_prompt.sh \
  "<video_url>" \
  "示例视频标题" \
  1500 \
  "./tmp/video-text/xxx.txt" \
  80000 \
  > "./tmp/video-text/summary_request.md"
```

6. 生成第二次请求包：
```bash
bash scripts/render_background_prompt.sh \
  "<video_url>" \
  "示例视频标题" \
  "./tmp/video-text/summary_result.md" \
  "./tmp/video-text/xxx.txt" \
  > "./tmp/video-text/background_request.md"
```

## 验收标准

1. 依赖缺失时失败退出。
2. 输出文本带时间戳。
3. 多 URL 场景下，文件按 `source-url_key` 子目录分组，不在根目录平铺。
4. 自动选档结果可观察（`run_dir`、`whisper_profile`、`selection_reason`、`strategy`）。
5. 第一次请求包包含字幕文本、反套话约束、总分结构约束、时间锚点约束（无行号）。
6. 第一次请求包要求输出 `摘要概述` 与 `附件`，且禁止单独“核心观点时间线”章节。
7. 第一次请求包中 `附件` 包含“原始视频链接 + 转写文本路径”。
8. 第二次请求包要求输出 `相关影响和背景分析`，且显式要求“背景优先、影响精简、新增信息”。
9. 第二次请求包明确要求背景使用视频外公开资料，并给出来源清单（来源名/机构 + 日期 + 标题/文件名，≥3，含新闻原文或原始文件）。
10. 两阶段交付在同一轮回复连续完成，不等待用户确认。
11. 产物文件名不包含空格。

## 渐进式披露

- 来源：`references/sources.md`
