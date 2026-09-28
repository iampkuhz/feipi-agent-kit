#!/usr/bin/env bash
set -euo pipefail

# 生成"第一次交付（摘要）"请求包。
# 用法：
#   bash scripts/render_summary_prompt.sh <url> <title> <duration_sec> <transcript_path> [max_chars] \
#     [--summary-style strict|structured|review|tutorial|action] \
#     [--user-intent "<原文>"]

URL="${1:-}"
TITLE="${2:-未命名视频}"
DURATION_SEC="${3:-}"
TRANSCRIPT_PATH="${4:-}"

# 保存第5个位置参数（兼容旧版 max_chars），然后处理可选参数
shift 4 || true
MAX_CHARS="80000"
SUMMARY_STYLE="structured"
USER_INTENT=""

# 处理剩余参数：第一个非选项参数作为 max_chars，其余为 --* 选项
while [[ $# -gt 0 ]]; do
  case "$1" in
    --summary-style)
      SUMMARY_STYLE="${2:-structured}"
      shift 2
      ;;
    --user-intent)
      USER_INTENT="${2:-}"
      shift 2
      ;;
    *)
      # 第一个非选项参数作为 max_chars（兼容旧版调用）
      if [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_CHARS="$1"
      fi
      shift
      ;;
  esac
done

# 验证 summary_style
case "$SUMMARY_STYLE" in
  strict|structured|review|tutorial|action) ;;
  *)
    echo "summary_style 仅支持 strict/structured/review/tutorial/action: $SUMMARY_STYLE" >&2
    exit 1
    ;;
esac

if [[ -z "$URL" || -z "$DURATION_SEC" || -z "$TRANSCRIPT_PATH" ]]; then
  echo "用法: bash scripts/render_summary_prompt.sh <url> <title> <duration_sec> <transcript_path> [max_chars] [--summary-style ...] [--user-intent ...]" >&2
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

# --- 时间戳检测 ---
HAS_TIMESTAMPS=0
if grep -Eq '\[[0-9]{2}:[0-9]{2}(:[0-9]{2})?\]' "$TRANSCRIPT_PATH"; then
  HAS_TIMESTAMPS=1
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

# --- 摘要风格规则 ---
style_rules=""
case "$SUMMARY_STYLE" in
  strict)
    style_rules="12) 当前为 strict 模式（只总结，不扩展）硬性规则：
    - 只基于视频转写文本，不输出任何外部背景资料
    - 不输出模型评价、模型分析、模型启发
    - 不输出相关新闻、最新进展、外部检索结果
    - 可以做结构化整理，但不能额外扩展视频外的内容
    - 禁止输出'如果需要我还可以继续分析背景'之类的附带引导语"
    ;;
  structured)
    style_rules="12) 当前为 structured 模式（默认结构化总结）规则：
    - 不主动扩展背景，不主动搜索新闻
    - 可以基于视频内容提炼结构、主线、观点、案例、结论
    - 必须暴露来源状态
    - 禁止输出'如果需要我还可以继续分析背景'之类的附带引导语"
    ;;
  review)
    style_rules="12) 当前为 review 模式（总结 + 评价）规则：
    - 允许模型分析、启发、局限、可借鉴之处
    - 如果输出模型分析，必须使用 '### 模型分析' 三级标题明确标记
    - 不得把模型评价伪装成视频原话
    - 默认不使用外部资料，除非用户明确要求背景或最新进展
    - 可以输出'可信之处 / 局限之处 / 可借鉴之处 / 需要额外核验'"
    ;;
  tutorial)
    style_rules="12) 当前为 tutorial 模式（教程/操作指南）规则：
    - 优先输出步骤、命令、配置、注意事项、验证方式
    - 不强行写'核心观点 / 论证结构 / 局限性'
    - 对命令、参数、配置保守，不确定时标明需要二次确认
    - 可输出可执行清单"
    ;;
  action)
    style_rules="12) 当前为 action 模式（可执行清单）规则：
    - 输出 checklist 格式
    - 对命令、参数保守，不确定时标明需要二次确认
    - 不确定的参数不要伪装为确定值"
    ;;
esac

# --- 时间锚点规则 ---
if [[ "$HAS_TIMESTAMPS" -eq 1 ]]; then
  timestamp_rules="3) 每个一级列表项都要以'视频时间'开头，时间格式强制如下：
   - 视频时长未超过 1 小时：使用 [MM:SS]（示例：[03:15]）。
   - 视频时长超过 1 小时：使用 [HH:MM:SS]（示例：[01:03:15]）。
   - 禁止使用 T+00:00:00、禁止附带字幕行号。"
else
  timestamp_rules="3) 当前转写文本不含可靠时间戳（HAS_TIMESTAMPS=0）硬性规则：
   - 禁止编造 [MM:SS] 或 [HH:MM:SS] 格式的时间标记。
   - 一级列表可以使用 [无时间戳] 前缀，或者直接取消时间前缀。
   - 必须在'## 来源状态'中说明'当前文本不含可靠时间戳'。"
fi

# --- 来源状态要求 ---
source_status_rule="5) 必须输出 '## 来源状态' 章节，且包含以下字段：
   - 文本来源：标准字幕 / 自动字幕 / Whisper 转写 / 已有文本 / 未知
   - 是否完整：完整 / 已截断 / 仅局部片段 / 分段摘要
   - 是否带时间戳：是 / 否
   - 是否使用外部资料：否 / 是，仅用于背景
   - 主要风险：无 / 自动字幕误差 / Whisper 误识别 / 中段截断 / 无时间戳 / 其他"

# --- 视频类型识别 ---
video_type_rule="6) 请根据视频标题和转写内容判断 video_type，并在'## 摘要概述'内使用对应的三级标题组织内容：
   - speech（演讲/主题发言）：### 核心观点 / ### 论证结构 / ### 关键案例
   - interview（访谈/对话）：### 嘉宾观点 / ### 分歧点 / ### 共识结论
   - tutorial（教程/操作指南）：### 操作步骤 / ### 参数/配置 / ### 常见错误 / ### 可执行清单
   - news_commentary（新闻评论）：### 事件概述 / ### 各方观点 / ### 事实核查
   - product_review（产品测评）：### 评测维度 / ### 优点 / ### 缺点 / ### 适用场景
   - podcast_or_meeting（播客/会议）：### 议题概览 / ### 主要观点 / ### 待决事项
   - vlog（个人记录）：### 主题主线 / ### 关键事件 / ### 情感/态度变化
   - music_or_lyrics（歌词/MV）：### 主题 / ### 情绪变化 / ### 重复句含义
   - other（无法判断）：### 核心内容 / ### 结构判断
   不需要输出冗长分类理由，在'### 结构判断'中简要标注 video_type 即可。无法判断时使用 other。"

# --- 截断披露 ---
truncation_disclosure="7) 若转写已截断（是否截断=${truncated}），必须在'## 来源状态'的'是否完整'字段标注'已截断'，且不得声称'完整覆盖全片'或'全面总结'。"

# --- 反套话约束（保留原有） ---
anti_cliche_rule="9) 绝对禁止出现以下表达（或同义空话）：
- 并承接前后文
- 围绕同一主题反复展开
- 文本信息相对连续，已按语义段落做合并
- 补充要点：围绕……展开延伸"

# --- 证据披露规则 ---
evidence_disclosure="10) 禁止空泛免责；必须披露真实证据状态：
    - 允许并要求说明：文本是否截断、字幕是否自动生成、Whisper 是否可能存在转写误差、哪些结论来自视频、哪些结论来自模型提炼、哪些结论来自外部背景、哪些信息无法从当前材料确认
    - 禁止：用'可能不准确，仅供参考'作为结尾套话；明明材料不足却输出确定性事实；把外部背景伪装成视频内观点；把模型判断伪装成视频原话"

cat <<EOF
请基于下面提供的"视频字幕/转写文本"生成中文总结（摘要模式）。
目标：只交付可直接阅读的结构化摘要，不主动扩展到背景、影响或相关新闻。

视频 URL: $URL
$(python3 "$(dirname "${BASH_SOURCE[0]}")/lib/video_identity.py" --prompt "$URL" "$TITLE" "$(dirname "$TRANSCRIPT_PATH")")
视频时长(秒): $DURATION_SEC
文本来源: $TRANSCRIPT_PATH
转写文本字符数: $raw_chars
字幕总行数: $line_count
是否截断: $truncated
是否含时间戳: $HAS_TIMESTAMPS
摘要风格: $SUMMARY_STYLE

当前只执行"摘要提取"，必须严格按下面结构输出，标题完全一致：
## 摘要概述
## 来源状态
## 附件

摘要模式硬性规则：
1) "摘要概述"先写 1 段总述（3-5 句），必须先总后分，不允许上来就列点。
2) 总述后再写 1-2 级列表整理核心内容：
   - 有明显先后/因果链：用有序列表。
   - 关系并列：用无序列表。
   - 存在总分关系：必须出现二级列表（最多二级）。
${timestamp_rules}
4) 不允许输出"## 核心观点时间线"章节；时间信息必须并入摘要列表。
${source_status_rule}
${video_type_rule}
${truncation_disclosure}
8) 列表内容不能与总述逐句重复，应补充证据、动作、影响或争议。
${anti_cliche_rule}
11) 信息密度不要显式讨论，由模型阅读文本后自行判断详略。
13) 如果是歌词/重复口播：提炼主题、情绪变化、重复句含义；不要逐句复读。
14) 如果是访谈/科普：优先写"观点-依据-结论"链路。
${style_rules}
${evidence_disclosure}
15) "附件"段只保留两项，且必须同时出现：
   - 原始视频：$URL
   - 转写文本：$TRANSCRIPT_PATH

若用户后续明确要求扩展分析，再单独执行背景模式；本次不要输出"相关影响和背景分析"或"上下文背景"。

<TRANSCRIPT_START>
${transcript_payload}
<TRANSCRIPT_END>
EOF
