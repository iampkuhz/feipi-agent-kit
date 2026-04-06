#!/usr/bin/env bash
set -euo pipefail

# 生成“第一次交付（摘要）”请求包。
# 用法：
#   bash scripts/render_summary_prompt.sh <url> <title> <duration_sec> <transcript_path> [max_chars]

URL="${1:-}"
TITLE="${2:-未命名视频}"
DURATION_SEC="${3:-}"
TRANSCRIPT_PATH="${4:-}"
MAX_CHARS="${5:-80000}"

if [[ -z "$URL" || -z "$DURATION_SEC" || -z "$TRANSCRIPT_PATH" ]]; then
  echo "用法: bash scripts/render_summary_prompt.sh <url> <title> <duration_sec> <transcript_path> [max_chars]" >&2
  exit 1
fi

if [[ ! -f "$TRANSCRIPT_PATH" ]]; then
  echo "字幕/转写文件不存在: $TRANSCRIPT_PATH" >&2
  exit 1
fi

if ! [[ "$DURATION_SEC" =~ ^[0-9]+$ ]]; then
  echo "duration_sec 必须是非负整数: $DURATION_SEC" >&2
  exit 1
fi

if ! [[ "$MAX_CHARS" =~ ^[0-9]+$ ]]; then
  echo "max_chars 必须是非负整数: $MAX_CHARS" >&2
  exit 1
fi

raw_chars="$(wc -m < "$TRANSCRIPT_PATH" | tr -d ' ')"
if [[ -z "$raw_chars" ]]; then
  raw_chars=0
fi

line_count="$(wc -l < "$TRANSCRIPT_PATH" | tr -d ' ')"
if [[ -z "$line_count" ]]; then
  line_count=0
fi

truncated="0"
if (( raw_chars > MAX_CHARS && MAX_CHARS > 0 )); then
  truncated="1"
  head_chars=$((MAX_CHARS * 7 / 10))
  tail_chars=$((MAX_CHARS - head_chars))
  head_part="$(LC_ALL=C cut -c1-"$head_chars" "$TRANSCRIPT_PATH")"
  tail_part="$(LC_ALL=C tail -c "$tail_chars" "$TRANSCRIPT_PATH")"
  transcript_payload="${head_part}

[...中间片段已省略，避免上下文过长...]

${tail_part}"
else
  transcript_payload="$(cat "$TRANSCRIPT_PATH")"
fi

cat <<EOF
请基于下面提供的“视频字幕/转写文本”生成中文总结（摘要模式）。
目标：只交付可直接阅读的结构化摘要，不主动扩展到背景、影响或相关新闻。

视频 URL: $URL
视频标题: $TITLE
视频时长(秒): $DURATION_SEC
文本来源: $TRANSCRIPT_PATH
转写文本字符数: $raw_chars
字幕总行数: $line_count
是否截断: $truncated

当前只执行“摘要提取”，必须严格按下面结构输出，标题完全一致：
## 摘要概述
## 附件

摘要模式硬性规则：
1) “摘要概述”先写 1 段总述（3-5 句），必须先总后分，不允许上来就列点。
2) 总述后再写 1-2 级列表整理核心内容：
   - 有明显先后/因果链：用有序列表。
   - 关系并列：用无序列表。
   - 存在总分关系：必须出现二级列表（最多二级）。
3) 每个一级列表项都要以“视频时间”开头，时间格式强制如下：
   - 视频时长未超过 1 小时：使用 [MM:SS]（示例：[03:15]）。
   - 视频时长超过 1 小时：使用 [HH:MM:SS]（示例：[01:03:15]）。
   - 禁止使用 T+00:00:00、禁止附带字幕行号。
4) 不允许输出“## 核心观点时间线”章节；时间信息必须并入摘要列表。
5) 列表内容不能与总述逐句重复，应补充证据、动作、影响或争议。
6) “附件”段只保留两项，且必须同时出现：
   - 原始视频：$URL
   - 转写文本：$TRANSCRIPT_PATH
7) 绝对禁止出现以下表达（或同义空话）：
- 并承接前后文
- 围绕同一主题反复展开
- 文本信息相对连续，已按语义段落做合并
- 补充要点：围绕……展开延伸
8) 信息密度不要显式讨论，由模型阅读文本后自行判断详略。
9) 如果是歌词/重复口播：提炼主题、情绪变化、重复句含义；不要逐句复读。
10) 如果是访谈/科普：优先写“观点-依据-结论”链路。
11) 当前模式禁止主动补充以下内容：
- 视频外背景知识
- 相关影响分析
- 相关新闻、最新进展、外部检索结果
- “如果需要我还可以继续分析背景”之类的附带引导语

若用户后续明确要求扩展分析，再单独执行背景模式；本次不要输出“相关影响和背景分析”或“上下文背景”。

<TRANSCRIPT_START>
${transcript_payload}
<TRANSCRIPT_END>
EOF
