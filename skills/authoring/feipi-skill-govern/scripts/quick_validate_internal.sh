#!/usr/bin/env bash
set -euo pipefail

# 按仓库规则校验单个 skill 目录：
# - 命名规范 v2（feipi-<domain>-<action>-<object...>）
# - layer 路径归位
# - frontmatter 约束
# - 中文内容约束
# - 基础结构与元数据完整性

usage() {
  cat <<'USAGE'
用法:
  bash scripts/quick_validate_internal.sh <path-to-skill-folder>

示例:
  bash scripts/quick_validate_internal.sh skills/authoring/feipi-skill-govern
USAGE
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
DIR_INPUT="$1"
DIR="$DIR_INPUT"
ALLOWED_LAYERS="authoring diagram integration platform"
DISCOURAGED_ACTIONS="web ops automate misc helper utils tools temp tmp skill"
LEGACY_ACTION_HINTS="read write summarize review analyze test debug refactor generate gen configure send plan planning design build deploy migrate translate govern code coding docs"

if [[ ! -d "$DIR" && -d "$REPO_ROOT/$DIR_INPUT" ]]; then
  DIR="$REPO_ROOT/$DIR_INPUT"
fi

if [[ ! -d "$DIR" ]]; then
  echo "不是目录：$DIR" >&2
  exit 1
fi

TARGET_DIR="$(cd "$DIR" && pwd)"
BASE="$(basename "$TARGET_DIR")"

validate_skill_name() {
  local name="$1"
  local domain=""
  local action=""

  if [[ ! "$name" =~ ^[a-z0-9-]{1,64}$ ]]; then
    echo "无效目录名：$name (需匹配 ^[a-z0-9-]{1,64}$)" >&2
    exit 1
  fi

  if [[ "$name" != feipi-* ]]; then
    echo "目录名必须以 feipi- 开头：$name" >&2
    exit 1
  fi

  if printf "%s" "$name" | rg -qi '(anthropic|claude)'; then
    echo "name 不能包含保留词 anthropic 或 claude" >&2
    exit 1
  fi

  if [[ "$name" == "feipi-skill-govern" ]]; then
    return 0
  fi

  IFS='-' read -r -a name_tokens <<< "$name"
  if [[ ${#name_tokens[@]} -lt 4 ]]; then
    echo "目录名必须符合 feipi-<domain>-<action>-<object...>: $name" >&2
    exit 1
  fi

  domain="${name_tokens[1]}"
  action="${name_tokens[2]}"
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
  if [[ "$rel" == "$layer" ]]; then
    echo "repo 内 skills 目录必须使用 skills/<layer>/<skill-name>/：$rel" >&2
    exit 1
  fi

  rest="${rel#*/}"
  if [[ "$rest" != "$BASE" ]]; then
    echo "校验目标必须是 skill 根目录，且位于 skills/<layer>/<skill-name>/：$rel" >&2
    exit 1
  fi

  if ! printf "%s\n" "$ALLOWED_LAYERS" | tr ' ' '\n' | rg -qx "$layer"; then
    echo "不支持的 layer: $layer" >&2
    echo "允许的 layer: $ALLOWED_LAYERS" >&2
    exit 1
  fi
}

validate_skill_name "$BASE"
validate_repo_layer "$TARGET_DIR"

SKILL_FILE="$TARGET_DIR/SKILL.md"
if [[ ! -f "$SKILL_FILE" ]]; then
  echo "缺少文件：$SKILL_FILE" >&2
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
  echo "Frontmatter 必须以 --- 开始并以 --- 结束" >&2
  exit 1
}

NAME_VALUE="$(printf "%s\n" "$FRONTMATTER" | sed -nE 's/^name:[[:space:]]*(.+)[[:space:]]*$/\1/p' | head -n1)"
DESC_VALUE="$(printf "%s\n" "$FRONTMATTER" | sed -nE 's/^description:[[:space:]]*(.+)[[:space:]]*$/\1/p' | head -n1)"

if [[ -z "$NAME_VALUE" || -z "$DESC_VALUE" ]]; then
  echo "Frontmatter 必须包含非空的 name 与 description" >&2
  exit 1
fi

EXTRA_KEYS="$(printf "%s\n" "$FRONTMATTER" | sed -nE 's/^([a-zA-Z0-9_-]+):.*$/\1/p' | rg -v '^(name|description)$' || true)"
if [[ -n "$EXTRA_KEYS" ]]; then
  echo "Frontmatter 仅允许 name 与 description，发现额外字段：$(echo "$EXTRA_KEYS" | tr '\n' ' ')" >&2
  exit 1
fi

if [[ "$NAME_VALUE" != "$BASE" ]]; then
  echo "name 字段必须与目录名一致：name=$NAME_VALUE, dir=$BASE" >&2
  exit 1
fi

validate_skill_name "$NAME_VALUE"

if printf "%s" "$NAME_VALUE" | rg -q '<[^>]+>'; then
  echo "name 不能包含 XML 标签" >&2
  exit 1
fi

if printf "%s" "$DESC_VALUE" | rg -q '<[^>]+>'; then
  echo "description 不能包含 XML 标签" >&2
  exit 1
fi

if [[ ${#DESC_VALUE} -gt 1024 ]]; then
  echo "description 长度不能超过 1024 字符" >&2
  exit 1
fi

for placeholder in \
  '{{SKILL_NAME}}' \
  '{{SKILL_DESCRIPTION}}' \
  '{{TITLE}}' \
  '{{DISPLAY_NAME}}' \
  '{{SHORT_DESCRIPTION}}' \
  '{{DEFAULT_PROMPT}}'
do
  if rg -Fq "$placeholder" "$SKILL_FILE"; then
    echo "SKILL.md 存在未替换模板占位符：$placeholder" >&2
    exit 1
  fi
done

if printf "%s" "$DESC_VALUE" | rg -q '(我 | 我们 | 你 | 您)'; then
  echo "description 建议使用第三人称，避免“我/我们/你/您”" >&2
  exit 1
fi

BODY_LINES="$(awk '
  NR==1 && $0=="---" { in_yaml=1; next }
  in_yaml && $0=="---" { in_yaml=0; body=1; next }
  body { c++ }
  END { print c+0 }
' "$SKILL_FILE")"

if [[ "$BODY_LINES" -gt 500 ]]; then
  echo "SKILL.md 正文建议 <= 500 行，当前：$BODY_LINES" >&2
  exit 1
fi

if ! rg -Pq '\p{Han}' "$SKILL_FILE"; then
  echo "SKILL.md 必须包含中文内容（检测不到中文字符）" >&2
  exit 1
fi

if ! rg -q '验证|校验|测试|验收' "$SKILL_FILE"; then
  echo "SKILL.md 必须包含至少一种验证/校验/测试要求" >&2
  exit 1
fi

if [[ -f "$TARGET_DIR/references/.env.example" ]]; then
  echo "禁止在 skill 目录下维护 references/.env.example，请统一维护到仓库根目录 .env.example" >&2
  exit 1
fi

if rg -q '[A-Za-z]:\\|\\[A-Za-z0-9._-]+' "$SKILL_FILE"; then
  echo "SKILL.md 检测到 Windows 风格路径，请统一使用正斜杠" >&2
  exit 1
fi

while IFS= read -r resource_path; do
  [[ -z "$resource_path" ]] && continue
  if [[ ! -e "$TARGET_DIR/$resource_path" ]]; then
    echo "SKILL.md 引用了不存在的路径：$resource_path" >&2
    exit 1
  fi
done < <(rg -o 'references/[A-Za-z0-9._/-]+\.md|assets/[A-Za-z0-9._/-]+\.md|scripts/[A-Za-z0-9._/-]+\.sh' "$SKILL_FILE" | sort -u)

if [[ "$BASE" != "feipi-skill-govern" ]]; then
  if rg -n 'make[[:space:]]+(new|test|validate)|bash[[:space:]]+scripts/(init_skill|validate|test)\.sh|^##[[:space:]]*维护与回归' "$SKILL_FILE" >&2; then
    echo "非 feipi-skill-govern 的 SKILL.md 禁止包含 repo 维护命令或“维护与回归”章节" >&2
    exit 1
  fi
fi

OPENAI_FILE="$TARGET_DIR/agents/openai.yaml"
if [[ ! -f "$OPENAI_FILE" ]]; then
  echo "缺少文件：$OPENAI_FILE" >&2
  exit 1
fi

if ! rg -q '^version:[[:space:]]*[0-9]+[[:space:]]*$' "$OPENAI_FILE"; then
  echo "agents/openai.yaml 缺少顶层整数 version 字段" >&2
  exit 1
fi

if ! rg -q '^interface:' "$OPENAI_FILE"; then
  echo "agents/openai.yaml 缺少 interface 根字段" >&2
  exit 1
fi

for k in display_name short_description default_prompt; do
  if ! rg -q "^[[:space:]]+$k:" "$OPENAI_FILE"; then
    echo "agents/openai.yaml 缺少 $k 字段" >&2
    exit 1
  fi
done

for placeholder in \
  '{{SKILL_NAME}}' \
  '{{SKILL_DESCRIPTION}}' \
  '{{TITLE}}' \
  '{{DISPLAY_NAME}}' \
  '{{SHORT_DESCRIPTION}}' \
  '{{DEFAULT_PROMPT}}'
do
  if rg -Fq "$placeholder" "$OPENAI_FILE"; then
    echo "agents/openai.yaml 存在未替换模板占位符：$placeholder" >&2
    exit 1
  fi
done

if ! rg -Pq '\p{Han}' "$OPENAI_FILE"; then
  echo "agents/openai.yaml 必须包含中文描述字段" >&2
  exit 1
fi

TEST_SCRIPT="$TARGET_DIR/scripts/test.sh"
if [[ ! -x "$TEST_SCRIPT" ]]; then
  echo "缺少可执行测试脚本：$TEST_SCRIPT" >&2
  exit 1
fi

for placeholder in \
  '{{SKILL_NAME}}' \
  '{{SKILL_DESCRIPTION}}' \
  '{{TITLE}}' \
  '{{DISPLAY_NAME}}' \
  '{{SHORT_DESCRIPTION}}' \
  '{{DEFAULT_PROMPT}}'
do
  if rg -Fq "$placeholder" "$TEST_SCRIPT"; then
    echo "scripts/test.sh 存在未替换模板占位符：$placeholder" >&2
    exit 1
  fi
done

bash -n "$TEST_SCRIPT"
