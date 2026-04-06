#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/validate.sh [skill-dir]

示例:
  bash scripts/validate.sh .
  bash scripts/validate.sh skills/integration/feipi-video-read-url
USAGE
}

if [[ $# -gt 1 ]]; then
  usage
  exit 1
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
TARGET_INPUT="${1:-$SKILL_DIR}"
TARGET_DIR="$TARGET_INPUT"
ALLOWED_LAYERS="authoring diagram integration platform"
DISCOURAGED_ACTIONS="web ops automate misc helper utils tools temp tmp skill"
LEGACY_ACTION_HINTS="read write summarize review analyze test debug refactor generate gen configure send plan planning design build deploy migrate translate govern code coding docs"

if [[ ! -d "$TARGET_DIR" && -d "$REPO_ROOT/$TARGET_INPUT" ]]; then
  TARGET_DIR="$REPO_ROOT/$TARGET_INPUT"
fi

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "目录不存在：$TARGET_INPUT" >&2
  exit 1
fi

TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
BASE="$(basename "$TARGET_DIR")"
SKILL_FILE="$TARGET_DIR/SKILL.md"
OPENAI_FILE="$TARGET_DIR/agents/openai.yaml"
TEST_SCRIPT="$TARGET_DIR/scripts/test.sh"

validate_skill_name() {
  local name="$1"
  local domain=""
  local action=""

  if [[ ! "$name" =~ ^[a-z0-9-]{1,64}$ ]]; then
    echo "无效目录名：$name" >&2
    exit 1
  fi
  if [[ "$name" != feipi-* ]]; then
    echo "目录名必须以 feipi- 开头：$name" >&2
    exit 1
  fi

  IFS='-' read -r -a parts <<< "$name"
  if [[ ${#parts[@]} -lt 4 ]]; then
    echo "目录名必须符合 feipi-<domain>-<action>-<object...>：$name" >&2
    exit 1
  fi

  domain="${parts[1]}"
  action="${parts[2]}"
  if printf "%s\n" "$LEGACY_ACTION_HINTS" | tr ' ' '\n' | rg -qx "$domain"; then
    echo "检测到旧 action-first 命名痕迹：第二段像 action，请先确定 domain 再命名" >&2
    exit 1
  fi
  if printf "%s\n" "$DISCOURAGED_ACTIONS" | tr ' ' '\n' | rg -qx "$action"; then
    echo "action 不能使用低语义词：$action" >&2
    exit 1
  fi
}

validate_repo_layer() {
  local path="$1"
  local rel=""
  local layer=""
  local rest=""

  if [[ "$path" != "$REPO_ROOT/skills/"* ]]; then
    return 0
  fi

  rel="${path#$REPO_ROOT/skills/}"
  layer="${rel%%/*}"
  rest="${rel#*/}"

  if [[ "$rest" != "$BASE" ]]; then
    echo "repo 内 skill 必须位于 skills/<layer>/<skill-name>/：$rel" >&2
    exit 1
  fi

  if ! printf "%s\n" "$ALLOWED_LAYERS" | tr ' ' '\n' | rg -qx "$layer"; then
    echo "不支持的 layer：$layer" >&2
    exit 1
  fi
}

validate_skill_name "$BASE"
validate_repo_layer "$TARGET_DIR"

for required_file in \
  "$SKILL_FILE" \
  "$OPENAI_FILE" \
  "$TARGET_DIR/scripts/download_video.sh" \
  "$TARGET_DIR/scripts/download_youtube.sh" \
  "$TARGET_DIR/scripts/download_bilibili.sh" \
  "$TARGET_DIR/scripts/extract_video_text.sh" \
  "$TARGET_DIR/scripts/render_summary_prompt.sh" \
  "$TARGET_DIR/scripts/render_background_prompt.sh" \
  "$TARGET_DIR/scripts/install_deps.sh" \
  "$TARGET_DIR/scripts/lib/yt_dlp_common.sh" \
  "$TARGET_DIR/scripts/lib/whispercpp_transcribe.sh" \
  "$TEST_SCRIPT" \
  "$TARGET_DIR/references/test_cases.txt" \
  "$TARGET_DIR/references/sources.md"; do
  if [[ ! -f "$required_file" ]]; then
    echo "缺少文件：$required_file" >&2
    exit 1
  fi
done

if [[ ! -x "$TEST_SCRIPT" ]]; then
  echo "缺少可执行测试脚本：$TEST_SCRIPT" >&2
  exit 1
fi

FRONTMATTER="$(awk '
  NR==1 && $0=="---" { in_yaml=1; start=1; next }
  in_yaml && $0=="---" { end=1; in_yaml=0; exit }
  in_yaml { print }
  END {
    if (start!=1 || end!=1) exit 2
  }
' "$SKILL_FILE")" || {
  echo "Frontmatter 必须以 --- 包裹" >&2
  exit 1
}

NAME_VALUE="$(printf "%s\n" "$FRONTMATTER" | sed -nE 's/^name:[[:space:]]*(.+)[[:space:]]*$/\1/p' | head -n1)"
DESC_VALUE="$(printf "%s\n" "$FRONTMATTER" | sed -nE 's/^description:[[:space:]]*(.+)[[:space:]]*$/\1/p' | head -n1)"
EXTRA_KEYS="$(printf "%s\n" "$FRONTMATTER" | sed -nE 's/^([a-zA-Z0-9_-]+):.*$/\1/p' | rg -v '^(name|description)$' || true)"

if [[ "$NAME_VALUE" != "$BASE" ]]; then
  echo "name 字段必须与目录名一致：$NAME_VALUE != $BASE" >&2
  exit 1
fi
if [[ -z "$DESC_VALUE" ]]; then
  echo "description 不能为空" >&2
  exit 1
fi
if [[ -n "$EXTRA_KEYS" ]]; then
  echo "Frontmatter 仅允许 name 与 description" >&2
  exit 1
fi

if ! rg -Pq '\p{Han}' "$SKILL_FILE"; then
  echo "SKILL.md 必须包含中文内容" >&2
  exit 1
fi
if ! rg -q '下载|转写|摘要|背景|验证|校验|测试|验收' "$SKILL_FILE"; then
  echo "SKILL.md 必须覆盖执行边界与验证要求" >&2
  exit 1
fi

if ! rg -q '^version:[[:space:]]*[0-9]+[[:space:]]*$' "$OPENAI_FILE"; then
  echo "agents/openai.yaml 缺少顶层整数 version" >&2
  exit 1
fi
for field in display_name short_description default_prompt; do
  if ! rg -q "^[[:space:]]+$field:[[:space:]]*.+$" "$OPENAI_FILE"; then
    echo "agents/openai.yaml 缺少字段：$field" >&2
    exit 1
  fi
done

for placeholder in '{{SKILL_NAME}}' '{{SKILL_DESCRIPTION}}' '{{TITLE}}' '{{DISPLAY_NAME}}' '{{SHORT_DESCRIPTION}}' '{{DEFAULT_PROMPT}}'; do
  if rg -Fq "$placeholder" "$SKILL_FILE" "$OPENAI_FILE" "$TEST_SCRIPT"; then
    echo "存在未替换模板占位符：$placeholder" >&2
    exit 1
  fi
done

if rg -n 'feipi-scripts/video|feipi-read-youtube-video|feipi-read-bilibili-video|feipi-summarize-video-url' \
  "$SKILL_FILE" "$OPENAI_FILE" \
  "$TARGET_DIR/scripts/download_video.sh" \
  "$TARGET_DIR/scripts/download_youtube.sh" \
  "$TARGET_DIR/scripts/download_bilibili.sh" \
  "$TARGET_DIR/scripts/extract_video_text.sh" \
  "$TARGET_DIR/scripts/install_deps.sh" \
  "$TARGET_DIR/scripts/test.sh" \
  "$TARGET_DIR/scripts/lib/yt_dlp_common.sh" \
  "$TARGET_DIR/scripts/lib/whispercpp_transcribe.sh" >&2; then
  echo "检测到旧依赖或旧 skill 名残留" >&2
  exit 1
fi

while IFS= read -r sh_file; do
  [[ -z "$sh_file" ]] && continue
  bash -n "$sh_file"
done < <(find "$TARGET_DIR/scripts" -type f -name '*.sh' | sort)

echo "校验通过：$TARGET_DIR"
