#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  bash scripts/validate.sh [skill-dir]

示例:
  bash scripts/validate.sh .
  bash scripts/validate.sh skills/authoring/feipi-patent-generate-innovation-disclosure
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
EXPECTED_ARCH_SKILL="feipi-plantuml-generate-architecture-diagram"
EXPECTED_SEQ_SKILL="feipi-plantuml-generate-sequence-diagram"

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
FORMAT_SCRIPT="$TARGET_DIR/scripts/check_disclosure_format.sh"
TEMPLATE_FILE="$TARGET_DIR/assets/proposal_template.md"
TEST_CASES_FILE="$TARGET_DIR/references/test_cases.txt"
HAPPY_CASE_FILE="$TARGET_DIR/references/cases/happy-case-full.md"

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
  if printf "%s" "$name" | rg -qi '(anthropic|claude)'; then
    echo "name 不能包含保留词 anthropic 或 claude" >&2
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

for required_file in "$SKILL_FILE" "$OPENAI_FILE" "$TEST_SCRIPT" "$FORMAT_SCRIPT" "$TEMPLATE_FILE" "$TEST_CASES_FILE" "$HAPPY_CASE_FILE"; do
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
if [[ ${#DESC_VALUE} -gt 1024 ]]; then
  echo "description 长度不能超过 1024" >&2
  exit 1
fi
if ! rg -Pq '\p{Han}' "$SKILL_FILE"; then
  echo "SKILL.md 必须包含中文内容" >&2
  exit 1
fi
if ! rg -q '验证|校验|测试|验收' "$SKILL_FILE"; then
  echo "SKILL.md 必须包含验证要求" >&2
  exit 1
fi
if rg -n 'make[[:space:]]+(new|test|validate)|bash[[:space:]]+scripts/(init_skill|validate|test)\.sh|^##[[:space:]]*维护与回归' "$SKILL_FILE" >&2; then
  echo "非治理 skill 的 SKILL.md 禁止包含 repo 维护命令" >&2
  exit 1
fi

if ! rg -q '^version:[[:space:]]*[0-9]+[[:space:]]*$' "$OPENAI_FILE"; then
  echo "agents/openai.yaml 缺少顶层整数 version" >&2
  exit 1
fi
if ! rg -q '^interface:' "$OPENAI_FILE"; then
  echo "agents/openai.yaml 缺少 interface 根字段" >&2
  exit 1
fi
for field in display_name short_description default_prompt; do
  if ! rg -q "^[[:space:]]+$field:[[:space:]]*.+$" "$OPENAI_FILE"; then
    echo "agents/openai.yaml 缺少字段：$field" >&2
    exit 1
  fi
done

for placeholder in '{{SKILL_NAME}}' '{{SKILL_DESCRIPTION}}' '{{TITLE}}' '{{DISPLAY_NAME}}' '{{SHORT_DESCRIPTION}}' '{{DEFAULT_PROMPT}}'; do
  if rg -Fq "$placeholder" "$SKILL_FILE" "$OPENAI_FILE" "$TEMPLATE_FILE" "$TEST_SCRIPT"; then
    echo "存在未替换模板占位符：$placeholder" >&2
    exit 1
  fi
done

if rg -Fq 'feipi-gen-innovation-disclosure' "$SKILL_FILE" "$OPENAI_FILE" "$TEMPLATE_FILE" "$TEST_SCRIPT"; then
  echo "检测到旧 skill 名残留：feipi-gen-innovation-disclosure" >&2
  exit 1
fi
if rg -Fq 'feipi-gen-plantuml-code' "$SKILL_FILE" "$OPENAI_FILE" "$TEMPLATE_FILE"; then
  echo "检测到已失效的 PlantUML 依赖名：feipi-gen-plantuml-code" >&2
  exit 1
fi

for required_skill in "$EXPECTED_ARCH_SKILL" "$EXPECTED_SEQ_SKILL"; do
  if ! rg -Fq "$required_skill" "$SKILL_FILE" "$OPENAI_FILE" "$TEMPLATE_FILE"; then
    echo "缺少图示协同依赖说明：$required_skill" >&2
    exit 1
  fi
done

while IFS= read -r resource_path; do
  [[ -z "$resource_path" ]] && continue
  if [[ ! -e "$TARGET_DIR/$resource_path" ]]; then
    echo "SKILL.md 引用了不存在的路径：$resource_path" >&2
    exit 1
  fi
done < <(rg -o 'references/[A-Za-z0-9._/-]+\.md|references/[A-Za-z0-9._/-]+\.txt|assets/[A-Za-z0-9._/-]+(\.md|\.yaml|\.json|\.puml|\.txt)|scripts/[A-Za-z0-9._/-]+\.(sh|py)' "$SKILL_FILE" | sort -u)

while IFS= read -r sh_file; do
  [[ -z "$sh_file" ]] && continue
  bash -n "$sh_file"
done < <(find "$TARGET_DIR/scripts" -type f -name '*.sh' | sort)

if command -v python3 >/dev/null 2>&1; then
  while IFS= read -r py_file; do
    [[ -z "$py_file" ]] && continue
    python3 -m py_compile "$py_file"
  done < <(find "$TARGET_DIR/scripts" -type f -name '*.py' | sort)
fi

bash "$FORMAT_SCRIPT" "$HAPPY_CASE_FILE" >/dev/null

echo "校验通过：$TARGET_DIR"
