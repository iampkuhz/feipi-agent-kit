#!/usr/bin/env bash
set -euo pipefail

# feipi-skill-govern 的本地校验封装（标准入口）。
# 目标：使用当前 skill 本地脚本校验目标 skill 目录，不依赖仓库级共享实现。

usage() {
  cat <<'USAGE'
用法:
  bash scripts/validate.sh <skill-dir>

示例:
  bash scripts/validate.sh skills/authoring/feipi-skill-govern
  bash scripts/validate.sh ../skills/authoring/feipi-skill-govern
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
VALIDATE_INTERNAL="$SCRIPT_DIR/quick_validate_internal.sh"

if [[ ! -x "$VALIDATE_INTERNAL" ]]; then
  echo "缺少内部校验脚本：$VALIDATE_INTERNAL" >&2
  exit 1
fi

SKILL_INPUT="${1:-.}"
DIR="$SKILL_INPUT"

if [[ ! -d "$DIR" && -d "$REPO_ROOT/$SKILL_INPUT" ]]; then
  DIR="$REPO_ROOT/$SKILL_INPUT"
fi

if [[ ! -d "$DIR" ]]; then
  echo "错误：目录不存在：$SKILL_INPUT" >&2
  exit 1
fi

TARGET_DIR="$(cd "$DIR" && pwd)"
SKILL_FILE="$TARGET_DIR/SKILL.md"
OPENAI_FILE="$TARGET_DIR/agents/openai.yaml"
TEST_SCRIPT="$TARGET_DIR/scripts/test.sh"

echo "=== 校验 skill 目录：$TARGET_DIR ==="

bash "$VALIDATE_INTERNAL" "$TARGET_DIR" >/dev/null
echo "[PASS] 结构与规则校验通过"

if [[ ! -f "$OPENAI_FILE" ]]; then
  echo "[FAIL] 缺少 agents/openai.yaml" >&2
  exit 1
fi
echo "[PASS] agents/openai.yaml 存在"

if ! rg -q '^version:[[:space:]]*[0-9]+[[:space:]]*$' "$OPENAI_FILE"; then
  echo "[FAIL] agents/openai.yaml 的 version 必须是顶层整数" >&2
  exit 1
fi
echo "[PASS] version 字段为顶层整数"

for field in display_name short_description default_prompt; do
  if ! rg -q "^[[:space:]]+$field:[[:space:]]*.+$" "$OPENAI_FILE"; then
    echo "[FAIL] agents/openai.yaml 缺少非空字段：$field" >&2
    exit 1
  fi
done
echo "[PASS] interface 关键字段齐全"

if [[ ! -x "$TEST_SCRIPT" ]]; then
  echo "[FAIL] 缺少可执行测试脚本：$TEST_SCRIPT" >&2
  exit 1
fi
echo "[PASS] scripts/test.sh 可执行"

placeholders=()
for placeholder_name in \
  SKILL_NAME \
  SKILL_DESCRIPTION \
  TITLE \
  DISPLAY_NAME \
  SHORT_DESCRIPTION \
  DEFAULT_PROMPT
do
  placeholders+=("$(printf '%s%s%s' '{{' "$placeholder_name" '}}')")
done

for placeholder in "${placeholders[@]}"; do
  for file in "$TARGET_DIR/SKILL.md" "$TARGET_DIR/agents/openai.yaml" "$TARGET_DIR/scripts/test.sh"; do
    if [[ -f "$file" ]] && rg -Fq "$placeholder" "$file"; then
      echo "[FAIL] 检测到未替换模板占位符：$placeholder (文件：$file)" >&2
      rg -Fn "$placeholder" "$file" >&2 || true
      exit 1
    fi
  done
done
echo "[PASS] 无未替换模板占位符"

while IFS= read -r script_path; do
  [[ -z "$script_path" ]] && continue
  bash -n "$script_path"
done < <(find "$TARGET_DIR/scripts" -maxdepth 1 -type f -name '*.sh' | sort)
echo "[PASS] scripts/*.sh 语法检查通过"

while IFS= read -r resource_path; do
  [[ -z "$resource_path" ]] && continue
  if [[ ! -e "$TARGET_DIR/$resource_path" ]]; then
    echo "[FAIL] SKILL.md 引用了不存在的路径：$resource_path" >&2
    exit 1
  fi
done < <(rg -o 'references/[A-Za-z0-9._/-]+\.md|assets/[A-Za-z0-9._/-]+\.md|scripts/[A-Za-z0-9._/-]+\.sh' "$SKILL_FILE" | sort -u)
echo "[PASS] SKILL.md 中的资源路径可解析"

echo "校验通过：$TARGET_DIR"
