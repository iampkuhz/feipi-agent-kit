#!/usr/bin/env bash
set -euo pipefail

# 生成背景请求包。
# 用法：
#   bash scripts/render_background_prompt.sh <url> <title> <summary_path_or_-> <transcript_path> [max_chars] [--mode expand|background-only] [--news off|on]

URL="${1:-}"
TITLE="${2:-未命名视频}"
SUMMARY_PATH="${3:-}"
TRANSCRIPT_PATH="${4:-}"
MAX_CHARS="60000"
MODE="expand"
NEWS_MODE="off"

if [[ -z "$URL" || -z "$TRANSCRIPT_PATH" ]]; then
  echo "用法: bash scripts/render_background_prompt.sh <url> <title> <summary_path_or_-> <transcript_path> [max_chars] [--mode expand|background-only] [--news off|on]" >&2
  exit 1
fi

shift 4
if [[ $# -gt 0 && "${1:-}" != --* ]]; then
  MAX_CHARS="$1"
  shift
fi

if [[ ! -f "$TRANSCRIPT_PATH" ]]; then
  echo "字幕/转写文件不存在: $TRANSCRIPT_PATH" >&2
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --news)
      NEWS_MODE="${2:-}"
      shift 2
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 1
      ;;
  esac
done

if ! [[ "$MAX_CHARS" =~ ^[0-9]+$ ]]; then
  echo "max_chars 必须是非负整数: $MAX_CHARS" >&2
  exit 1
fi

if [[ "$MODE" != "expand" && "$MODE" != "background-only" ]]; then
  echo "mode 仅支持 expand 或 background-only: $MODE" >&2
  exit 1
fi

if [[ "$NEWS_MODE" != "off" && "$NEWS_MODE" != "on" ]]; then
  echo "news 仅支持 off 或 on: $NEWS_MODE" >&2
  exit 1
fi

summary_payload="无现成摘要，本轮需直接从转写中提取关键术语与背景线索。"
summary_chars=0
if [[ -n "$SUMMARY_PATH" && "$SUMMARY_PATH" != "-" ]]; then
  if [[ ! -f "$SUMMARY_PATH" ]]; then
    echo "摘要文件不存在: $SUMMARY_PATH" >&2
    exit 1
  fi
  summary_payload="$(cat "$SUMMARY_PATH")"
  summary_chars="$(printf "%s" "$summary_payload" | wc -m | tr -d ' ')"
  if [[ -z "$summary_chars" ]]; then
    summary_chars=0
  fi
elif [[ "$MODE" == "expand" ]]; then
  echo "expand 模式必须提供摘要文件，background-only 模式可使用 -" >&2
  exit 1
fi

transcript_payload_raw="$(cat "$TRANSCRIPT_PATH")"
transcript_chars="$(printf "%s" "$transcript_payload_raw" | wc -m | tr -d ' ')"
if [[ -z "$transcript_chars" ]]; then
  transcript_chars=0
fi

truncated="0"
if (( transcript_chars > MAX_CHARS && MAX_CHARS > 0 )); then
  truncated="1"
  head_chars=$((MAX_CHARS * 7 / 10))
  tail_chars=$((MAX_CHARS - head_chars))
  head_part="$(printf "%s" "$transcript_payload_raw" | LC_ALL=C cut -c1-"$head_chars")"
  tail_part="$(printf "%s" "$transcript_payload_raw" | LC_ALL=C tail -c "$tail_chars")"
  transcript_payload="${head_part}

[...中间片段已省略，避免上下文过长...]

${tail_part}"
else
  transcript_payload="$transcript_payload_raw"
fi

news_scope_line="默认不要主动搜索相关新闻、最新进展或额外时效信息；优先补制度沿革、术语解释、历史事件、官方基础文件和研究资料。"
source_rule_line="来源清单不少于 3 条，优先官方/主流媒体/研究机构/学术或政策文件；不强制补近期新闻。"
if [[ "$NEWS_MODE" == "on" ]]; then
  news_scope_line="用户已明确要求相关新闻/最新进展，可补充与视频主题直接相关的时效性材料；涉及时效信息时必须核对日期与来源。"
  source_rule_line="来源清单不少于 3 条，优先官方/主流媒体/研究机构/学术或政策文件，且至少包含 1-2 条新闻原文或原始文件。"
fi

if [[ "$MODE" == "expand" ]]; then
  cat <<EOF
你正在执行“扩展分析模式”：用户已经拿到视频摘要，现在要在摘要基础上继续补充相关影响和背景分析。
本轮不要重复第一轮内容，不要复述原文。

视频 URL: $URL
视频标题: $TITLE
摘要参考文件: $SUMMARY_PATH
转写文件: $TRANSCRIPT_PATH
摘要参考字符数: $summary_chars
转写字符数: $transcript_chars
转写是否截断: $truncated
背景模式: $MODE
新闻范围: $NEWS_MODE

只允许输出一个章节，标题必须完全一致：
## 相关影响和背景分析

硬性规则：
1) 篇幅分配强约束：
   - “背景知识补充”约占 2/3。
   - “关键影响”约占 1/3。
   - 影响只写最重要的 1-2 条，不做冗长推演。
2) 在该章节内必须使用以下小标题，且顺序固定：
   - ### 背景知识补充（约2/3）
   - ### 关键影响（约1/3）
3) “背景知识补充”必须基于视频外公开资料（历史背景、制度沿革、术语解释、必要时的外部报道），禁止仅按视频时间线复述或改写转写内容。
4) “背景知识补充”必须先列出 3-6 个“关键术语/人物/机构/事件”（来自视频关键词，列表形式），随后按清单逐条补充外部背景，每条必须包含：
   - 是什么（定义/角色） + 至少 1 个外部历史/新闻事实（含日期） + 与视频观点的关系。
5) 新闻范围约束：
   - $news_scope_line
6) “背景知识补充”末尾必须追加“来源清单”（列表形式），每条至少包含：
   - 来源名/机构 + 日期 + 原文标题/文件名（不得只写“网络资料/媒体报道”）。
   - $source_rule_line
7) “关键影响”每条都要写清：
   - 触发点 -> 作用机制 -> 受影响对象 -> 可观察结果。
   - 禁止只写“会有波动/会受影响”等空话。
8) 如引用视频证据，时间锚点格式只能是：
   - 时长未超过 1 小时： [MM:SS]
   - 时长超过 1 小时： [HH:MM:SS]
   禁止使用 T+00:00:00，禁止使用字幕行号。
9) 禁止重复第一轮的同义改写；每个列表项都必须新增信息价值。
10) 禁止套用固定条款/模板术语（如无关条款号或政策名），必须围绕本次视频关键词展开。
11) 禁止输出“关键不确定性”“后续观察点是否有诉讼”等空洞小节。
12) 禁止出现“转写误差、不确定、信息不足、仅供参考”等质量豁免表达。

<SUMMARY_REFERENCE_START>
${summary_payload}
<SUMMARY_REFERENCE_END>

<TRANSCRIPT_START>
${transcript_payload}
<TRANSCRIPT_END>
EOF
else
  cat <<EOF
你正在执行“背景单问模式”：用户当前只想知道这个视频的上下文背景，不需要先看摘要。
本轮聚焦解释来龙去脉、关键概念和与视频的关系；除非用户额外要求，否则不要展开“关键影响”或相关新闻综述。

视频 URL: $URL
视频标题: $TITLE
摘要参考文件: ${SUMMARY_PATH:--}
转写文件: $TRANSCRIPT_PATH
摘要参考字符数: $summary_chars
转写字符数: $transcript_chars
转写是否截断: $truncated
背景模式: $MODE
新闻范围: $NEWS_MODE

只允许输出一个章节，标题必须完全一致：
## 上下文背景

硬性规则：
1) 在该章节内必须使用以下小标题，且顺序固定：
   - ### 关键背景脉络
   - ### 与视频的关联
   - ### 来源清单
2) “关键背景脉络”开头必须先列出 3-6 个“关键术语/人物/机构/事件”（来自视频关键词，列表形式），再逐条解释它们的背景、彼此关系与必要时间节点。
3) 背景说明必须基于视频外公开资料（历史背景、制度沿革、术语解释、必要时的外部报道），禁止只把转写内容换一种说法。
4) 新闻范围约束：
   - $news_scope_line
5) “与视频的关联”需要说明：
   - 这些背景为什么是理解该视频所必需的。
   - 视频里哪些观点、争议或判断依赖这些背景。
   - 如引用视频证据，时间锚点只能使用 [MM:SS] 或 [HH:MM:SS]，禁止 T+00:00:00 和字幕行号。
6) “来源清单”必须是列表形式，每条至少包含：
   - 来源名/机构 + 日期 + 原文标题/文件名（不得只写“网络资料/媒体报道”）。
   - $source_rule_line
7) 除非用户额外要求，不要扩写“关键影响”“投资建议”“后续观察点”等无关小节。
8) 禁止出现“转写误差、不确定、信息不足、仅供参考”等质量豁免表达。

<SUMMARY_REFERENCE_START>
${summary_payload}
<SUMMARY_REFERENCE_END>

<TRANSCRIPT_START>
${transcript_payload}
<TRANSCRIPT_END>
EOF
fi
