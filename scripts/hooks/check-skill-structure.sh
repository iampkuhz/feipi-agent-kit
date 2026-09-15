#!/usr/bin/env bash
# pre-commit hook: 校验 skill 结构
# 检查范围: 所有被修改的 SKILL.md
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHANGED_FILES="$(git diff --cached --name-only --diff-filter=AM 2>/dev/null | grep -E '(^|/)SKILL\.md$' || true)"

if [[ -z "$CHANGED_FILES" ]]; then
  exit 0
fi

FAIL=0
while IFS= read -r skill_file; do
  skill_dir="$(dirname "$REPO_ROOT/$skill_file")"
  echo "[hook] 校验 skill 结构: $skill_dir"

  # 检查 agents/openai.yaml 存在
  if [[ ! -f "$skill_dir/agents/openai.yaml" ]]; then
    echo "[FAIL] 缺少 agents/openai.yaml" >&2
    FAIL=1
  fi

  # 开发测试与运行脚本分离；安装器会排除 tests/。
  if [[ ! -x "$skill_dir/tests/run.sh" ]]; then
    echo "[FAIL] 缺少可执行测试脚本 tests/run.sh" >&2
    FAIL=1
  fi

  # 检查 frontmatter name/description
  if ! head -5 "$skill_dir/SKILL.md" | grep -q '^name:'; then
    echo "[FAIL] SKILL.md 缺少 frontmatter name 字段" >&2
    FAIL=1
  fi
  if ! head -5 "$skill_dir/SKILL.md" | grep -q '^description:'; then
    echo "[FAIL] SKILL.md 缺少 frontmatter description 字段" >&2
    FAIL=1
  fi

done <<< "$CHANGED_FILES"

if [[ $FAIL -ne 0 ]]; then
  echo "[hook] skill 结构校验失败" >&2
  exit 1
fi

echo "[hook] skill 结构校验通过"
