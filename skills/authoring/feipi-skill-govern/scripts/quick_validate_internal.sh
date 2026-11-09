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
ALLOWED_LAYERS="authoring diagram integration"
DISCOURAGED_ACTIONS="web ops automate misc helper utils tools temp tmp skill"
LEGACY_ACTION_HINTS="read write summarize review analyze test debug refactor generate gen configure send plan planning design build deploy translate govern code coding docs"

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

  if printf "%s" "$name" | grep -Eqi '(anthropic|claude)'; then
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
  if printf "%s\n" "$LEGACY_ACTION_HINTS" | tr ' ' '\n' | grep -Exq "$domain"; then
    echo "检测到旧 action-first 命名痕迹：第二段像 action，请先确定 domain 再命名" >&2
    exit 1
  fi
  if printf "%s\n" "$DISCOURAGED_ACTIONS" | tr ' ' '\n' | grep -Exq "$action"; then
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

  if ! printf "%s\n" "$ALLOWED_LAYERS" | tr ' ' '\n' | grep -Exq "$layer"; then
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

EXTRA_KEYS="$(printf "%s\n" "$FRONTMATTER" | sed -nE 's/^([a-zA-Z0-9_-]+):.*$/\1/p' | grep -Ev '^(name|description)$' || true)"
if [[ -n "$EXTRA_KEYS" ]]; then
  echo "Frontmatter 仅允许 name 与 description，发现额外字段：$(echo "$EXTRA_KEYS" | tr '\n' ' ')" >&2
  exit 1
fi

if [[ "$NAME_VALUE" != "$BASE" ]]; then
  echo "name 字段必须与目录名一致：name=$NAME_VALUE, dir=$BASE" >&2
  exit 1
fi

validate_skill_name "$NAME_VALUE"

if printf "%s" "$NAME_VALUE" | grep -Eq '<[^>]+>'; then
  echo "name 不能包含 XML 标签" >&2
  exit 1
fi

if printf "%s" "$DESC_VALUE" | grep -Eq '<[^>]+>'; then
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
  if grep -Fq "$placeholder" "$SKILL_FILE"; then
    echo "SKILL.md 存在未替换模板占位符：$placeholder" >&2
    exit 1
  fi
done

if printf "%s" "$DESC_VALUE" | grep -Eq '(我 | 我们 | 你 | 您)'; then
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

if ! python3 - "$SKILL_FILE" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
if not any("\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff" for char in text):
    raise SystemExit(1)
PY
then
  echo "SKILL.md 必须包含中文内容（检测不到中文字符）" >&2
  exit 1
fi

if ! grep -Eq '验证|校验|测试|验收' "$SKILL_FILE"; then
  echo "SKILL.md 必须包含至少一种验证/校验/测试要求" >&2
  exit 1
fi

if [[ -f "$TARGET_DIR/references/.env.example" ]]; then
  echo "禁止在 skill 目录下维护 references/.env.example，请统一维护到仓库根目录 .env.example" >&2
  exit 1
fi

if [[ "$BASE" == "feipi-skill-govern" ]]; then
  if [[ -d "$TARGET_DIR/assets/governance" ]]; then
    echo "feipi-skill-govern 禁止在 skill 内部提交临时治理产物目录 assets/governance/" >&2
    exit 1
  fi

  if find "$TARGET_DIR" -type f \
    \( \
      -name 'step-1-audit.template.md' -o \
      -name 'step-1-5-rename-review.template.md' -o \
      -name 'step-2-execution-checklist.template.md' -o \
      -name 'rename-plan.template.md' -o \
      -name 'governance-report.template.md' -o \
      -name 'anti-pattern.template.md' \
    \) | grep -q .
  then
    echo "feipi-skill-govern 检测到误提交的临时治理文档模板，请移到 tmp/ 或系统临时目录" >&2
    exit 1
  fi
fi

if grep -Eq '[A-Za-z]:\\|\\[A-Za-z0-9._-]+' "$SKILL_FILE"; then
  echo "SKILL.md 检测到 Windows 风格路径，请统一使用正斜杠" >&2
  exit 1
fi

while IFS= read -r resource_path; do
  [[ -z "$resource_path" ]] && continue
  if [[ ! -e "$TARGET_DIR/$resource_path" ]]; then
    echo "SKILL.md 引用了不存在的路径：$resource_path" >&2
    exit 1
  fi
done < <(grep -Eo '(\.\./[A-Za-z0-9._-]+/)?(references|assets|scripts)/[A-Za-z0-9._/-]+\.(md|txt|yaml|yml|json|puml|svg|png|sh|bash|py|js|mjs|cjs)' "$SKILL_FILE" | sort -u)

if [[ "$BASE" != "feipi-skill-govern" ]]; then
  if grep -En 'make[[:space:]]+(new|test|validate)|bash[[:space:]]+scripts/(init_skill|validate|test)\.sh|^##[[:space:]]*维护与回归' "$SKILL_FILE" >&2; then
    echo "非 feipi-skill-govern 的 SKILL.md 禁止包含 repo 维护命令或“维护与回归”章节" >&2
    exit 1
  fi
fi

OPENAI_FILE="$TARGET_DIR/agents/openai.yaml"
if [[ ! -f "$OPENAI_FILE" ]]; then
  echo "缺少文件：$OPENAI_FILE" >&2
  exit 1
fi

if ! grep -Eq '^version:[[:space:]]*[0-9]+[[:space:]]*$' "$OPENAI_FILE"; then
  echo "agents/openai.yaml 缺少顶层整数 version 字段" >&2
  exit 1
fi

if ! grep -Eq '^interface:' "$OPENAI_FILE"; then
  echo "agents/openai.yaml 缺少 interface 根字段" >&2
  exit 1
fi

for k in display_name short_description default_prompt; do
  if ! grep -Eq "^[[:space:]]+$k:" "$OPENAI_FILE"; then
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
  if grep -Fq "$placeholder" "$OPENAI_FILE"; then
    echo "agents/openai.yaml 存在未替换模板占位符：$placeholder" >&2
    exit 1
  fi
done

if ! python3 - "$OPENAI_FILE" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
if not any("\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff" for char in text):
    raise SystemExit(1)
PY
then
  echo "agents/openai.yaml 必须包含中文描述字段" >&2
  exit 1
fi

TEST_SCRIPT="$TARGET_DIR/tests/run.sh"
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
  if grep -Fq "$placeholder" "$TEST_SCRIPT"; then
    echo "tests/run.sh 存在未替换模板占位符：$placeholder" >&2
    exit 1
  fi
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "缺少依赖：python3（用于可移植路径与平台检查）" >&2
  exit 1
fi
python3 "$SCRIPT_DIR/check_portability.py" "$TARGET_DIR"

while IFS= read -r script_path; do
  [[ -z "$script_path" ]] && continue
  bash -n "$script_path"
done < <(find "$TARGET_DIR" \( -type d -name node_modules -prune \) -o \( -type f -name '*.sh' -print \) | sort)
echo "[PASS] 全部 Bash 脚本语法检查通过"

python3 - "$TARGET_DIR" <<'PY'
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
skip = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build"}
for current, directories, files in os.walk(root):
    directories[:] = [name for name in directories if name not in skip]
    for name in files:
        if name.endswith(".py"):
            path = Path(current) / name
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
PY
echo "[PASS] 全部 Python 脚本语法检查通过"

NODE_FILES="$(find "$TARGET_DIR" \( -type d -name node_modules -prune \) -o \
  \( -type f \( -name '*.js' -o -name '*.mjs' -o -name '*.cjs' \) -print \) | sort)"
if [[ -n "$NODE_FILES" ]]; then
  if ! command -v node >/dev/null 2>&1; then
    echo "[SKIP] 未安装 node，无法执行 JavaScript 语法检查"
  else
    while IFS= read -r script_path; do
      [[ -z "$script_path" ]] && continue
      node --check "$script_path"
    done <<< "$NODE_FILES"
    echo "[PASS] 全部 JavaScript 脚本语法检查通过"
  fi
fi

echo "[PASS] 路径与 macOS/Linux 兼容静态检查通过"
