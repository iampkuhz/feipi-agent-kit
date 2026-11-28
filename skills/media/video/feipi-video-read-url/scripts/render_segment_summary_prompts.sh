#!/usr/bin/env bash
set -euo pipefail

# 生成长视频分段摘要请求包。
# 用法：
#   bash scripts/render_segment_summary_prompts.sh <url> <title> <transcript_path> [segment_max_chars] [output_dir]

URL="${1:-}"
TITLE="${2:-未命名视频}"
TRANSCRIPT_PATH="${3:-}"
SEGMENT_MAX_CHARS="${4:-5000}"
OUTPUT_DIR="${5:-.}"

if [[ -z "$URL" || -z "$TRANSCRIPT_PATH" ]]; then
  echo "用法: bash scripts/render_segment_summary_prompts.sh <url> <title> <transcript_path> [segment_max_chars] [output_dir]" >&2
  exit 1
fi

if [[ ! -f "$TRANSCRIPT_PATH" ]]; then
  echo "转写文件不存在: $TRANSCRIPT_PATH" >&2
  exit 1
fi

if ! [[ "$SEGMENT_MAX_CHARS" =~ ^[0-9]+$ ]]; then
  echo "segment_max_chars 必须是非负整数: $SEGMENT_MAX_CHARS" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR/segments" "$OUTPUT_DIR/segment_prompts"

# --- 时间戳检测 ---
HAS_TIMESTAMPS=0
if grep -Eq '\[[0-9]{2}:[0-9]{2}(:[0-9]{2})?\]' "$TRANSCRIPT_PATH"; then
  HAS_TIMESTAMPS=1
fi

total_chars="$(wc -m < "$TRANSCRIPT_PATH" | tr -d ' ')"
if [[ -z "$total_chars" ]]; then
  total_chars=0
fi

echo "总字符数: $total_chars"
echo "每段最大字符数: $SEGMENT_MAX_CHARS"
echo "是否含时间戳: $HAS_TIMESTAMPS"

segment_idx=0

if [[ "$HAS_TIMESTAMPS" -eq 1 ]]; then
  # 有时间戳：按行读取，尝试按时间戳分组
  current_segment=""
  current_chars=0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line_len="${#line}"
    if (( current_chars + line_len > SEGMENT_MAX_CHARS && current_chars > 0 )); then
      # 输出当前段
      segment_file=$(printf "%s/segments/%04d.txt" "$OUTPUT_DIR" "$segment_idx")
      printf "%s" "$current_segment" > "$segment_file"

      # 生成 segment prompt
      prompt_file=$(printf "%s/segment_prompts/%04d.prompt.md" "$OUTPUT_DIR" "$segment_idx")
      cat > "$prompt_file" <<PROMPT
请基于以下视频转写文本片段生成该段落的摘要。

视频 URL: $URL
$(python3 "$(dirname "${BASH_SOURCE[0]}")/lib/video_identity.py" --prompt "$URL" "$TITLE" "$(dirname "$TRANSCRIPT_PATH")")
段落范围: 第 $segment_idx 段（最多 ${SEGMENT_MAX_CHARS} 字符）

要求：
1. 提炼该段的核心内容和关键结论
2. 如果文本包含时间戳，保留真实时间锚点 [MM:SS] 或 [HH:MM:SS]
3. 使用结构化格式输出（列表形式）
4. 输出段落编号和范围信息
5. 不输出"## 摘要概述"或"## 来源状态"等顶层结构，只输出该段的核心内容

<TRANSCRIPT_START>
${current_segment}
<TRANSCRIPT_END>
PROMPT

      segment_idx=$((segment_idx + 1))
      current_segment="$line"
      current_chars="$line_len"
    else
      if [[ -n "$current_segment" ]]; then
        current_segment="${current_segment}
${line}"
      else
        current_segment="$line"
      fi
      current_chars=$((current_chars + line_len))
    fi
  done < "$TRANSCRIPT_PATH"

  # 输出最后一段
  if [[ -n "$current_segment" ]]; then
    segment_file=$(printf "%s/segments/%04d.txt" "$OUTPUT_DIR" "$segment_idx")
    printf "%s" "$current_segment" > "$segment_file"

    prompt_file=$(printf "%s/segment_prompts/%04d.prompt.md" "$OUTPUT_DIR" "$segment_idx")
    cat > "$prompt_file" <<PROMPT
请基于以下视频转写文本片段生成该段落的摘要。

视频 URL: $URL
$(python3 "$(dirname "${BASH_SOURCE[0]}")/lib/video_identity.py" --prompt "$URL" "$TITLE" "$(dirname "$TRANSCRIPT_PATH")")
段落范围: 第 $segment_idx 段（最多 ${SEGMENT_MAX_CHARS} 字符）

要求：
1. 提炼该段的核心内容和关键结论
2. 如果文本包含时间戳，保留真实时间锚点 [MM:SS] 或 [HH:MM:SS]
3. 使用结构化格式输出（列表形式）
4. 输出段落编号和范围信息
5. 不输出"## 摘要概述"或"## 来源状态"等顶层结构，只输出该段的核心内容

<TRANSCRIPT_START>
${current_segment}
<TRANSCRIPT_END>
PROMPT
    segment_idx=$((segment_idx + 1))
  fi
else
  # 没有时间戳：按字符数切片
  offset=0
  while (( offset < total_chars )); do
    segment_text="$(LC_ALL=C cut -c$((offset + 1))-$((offset + SEGMENT_MAX_CHARS)) "$TRANSCRIPT_PATH")"
    if [[ -z "$segment_text" ]]; then
      break
    fi

    segment_file=$(printf "%s/segments/%04d.txt" "$OUTPUT_DIR" "$segment_idx")
    printf "%s" "$segment_text" > "$segment_file"

    prompt_file=$(printf "%s/segment_prompts/%04d.prompt.md" "$OUTPUT_DIR" "$segment_idx")
    cat > "$prompt_file" <<PROMPT
请基于以下视频转写文本片段生成该段落的摘要。

视频 URL: $URL
$(python3 "$(dirname "${BASH_SOURCE[0]}")/lib/video_identity.py" --prompt "$URL" "$TITLE" "$(dirname "$TRANSCRIPT_PATH")")
段落范围: 第 $segment_idx 段（字符偏移 ${offset}~$((offset + SEGMENT_MAX_CHARS))）

要求：
1. 提炼该段的核心内容和关键结论
2. 当前转写不含时间戳，禁止编造 [MM:SS] 或 [HH:MM:SS] 格式的时间标记
3. 使用结构化格式输出（列表形式）
4. 输出段落编号和范围信息
5. 不输出"## 摘要概述"或"## 来源状态"等顶层结构，只输出该段的核心内容

<TRANSCRIPT_START>
${segment_text}
<TRANSCRIPT_END>
PROMPT

    segment_idx=$((segment_idx + 1))
    offset=$((offset + SEGMENT_MAX_CHARS))
  done
fi

echo "共生成 $segment_idx 个分段"
echo "分段文件: $OUTPUT_DIR/segments/"
echo "分段 prompt: $OUTPUT_DIR/segment_prompts/"
