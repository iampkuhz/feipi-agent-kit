#!/usr/bin/env bash
set -euo pipefail

# 基于分段摘要生成最终汇总请求包。
# 用法：
#   bash scripts/render_final_summary_from_segments_prompt.sh <url> <title> <output_dir>

URL="${1:-}"
TITLE="${2:-未命名视频}"
OUTPUT_DIR="${3:-.}"

if [[ -z "$URL" ]]; then
  echo "用法: bash scripts/render_final_summary_from_segments_prompt.sh <url> <title> <output_dir>" >&2
  exit 1
fi

SEGMENT_PROMPTS_DIR="$OUTPUT_DIR/segment_prompts"
SEGMENTS_DIR="$OUTPUT_DIR/segments"

if [[ ! -d "$SEGMENT_PROMPTS_DIR" ]]; then
  echo "分段 prompt 目录不存在: $SEGMENT_PROMPTS_DIR" >&2
  exit 1
fi

# 收集所有分段摘要（假设已执行并保存为 summary 文件）
segment_summaries=""
segment_count=0
for prompt_file in "$SEGMENT_PROMPTS_DIR"/*.prompt.md; do
  [[ -f "$prompt_file" ]] || continue
  segment_basename="$(basename "$prompt_file" .prompt.md)"
  summary_file="$SEGMENTS_DIR/${segment_basename}.summary.md"
  if [[ -f "$summary_file" ]]; then
    segment_summaries="${segment_summaries}
--- 第 ${segment_count} 段摘要 ---
$(cat "$summary_file")
"
  else
    segment_summaries="${segment_summaries}
--- 第 ${segment_count} 段（待摘要） ---
段落范围: ${segment_basename}
状态: 尚未生成摘要
"
  fi
  segment_count=$((segment_count + 1))
done

output_file="$OUTPUT_DIR/final_summary_request.md"

cat > "$output_file" <<EOF
请基于以下分段摘要汇总为完整的视频摘要。

视频 URL: $URL
$(python3 "$(dirname "${BASH_SOURCE[0]}")/lib/video_identity.py" --prompt "$URL" "$TITLE" "$OUTPUT_DIR")
分段数量: $segment_count

当前只执行"摘要汇总"，必须严格按下面结构输出，标题完全一致：
## 摘要概述
## 来源状态
## 附件

汇总模式硬性规则：
1) "摘要概述"先写 1 段总述（3-5 句），必须先总后分，不允许上来就列点。
2) 总述后再写 1-2 级列表整理核心内容：
   - 有明显先后/因果链：用有序列表。
   - 关系并列：用无序列表。
   - 存在总分关系：必须出现二级列表（最多二级）。
3) 如果原始分段包含时间戳，保留真实时间锚点 [MM:SS] 或 [HH:MM:SS]：
   - 视频时长未超过 1 小时：使用 [MM:SS]
   - 视频时长超过 1 小时：使用 [HH:MM:SS]
   - 禁止使用 T+00:00:00、禁止附带字幕行号
   - 如果原始分段不含时间戳，禁止编造
4) 必须合并去重，保留整体结构，避免遗漏中段内容。
5) 请根据视频标题和分段内容判断 video_type，并在"## 摘要概述"内使用对应的三级标题组织内容。
6) 必须输出"## 来源状态"章节，且包含以下字段：
   - 文本来源：分段摘要汇总
   - 是否完整：完整 / 已截断 / 分段摘要
   - 是否带时间戳：是 / 否
   - 是否使用外部资料：否
   - 主要风险：分段汇总可能遗漏细节 / 无
7) "附件"段保留：
   - 原始视频：$URL
   - 转写文本：见 segments 目录

<SEGMENT_SUMMARIES_START>
${segment_summaries}
<SEGMENT_SUMMARIES_END>
EOF

echo "已生成最终汇总请求包: $output_file"
