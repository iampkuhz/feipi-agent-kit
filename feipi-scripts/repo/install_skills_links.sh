#!/usr/bin/env bash
set -euo pipefail

# 将当前仓库的 skills 目录下所有技能，以软链接方式安装到用户目录。
# 同时自动检测 skill 对仓库根目录共享脚本（如 feipi-scripts/）的依赖，并安装同级软链接。
# 默认目标目录：~/.agents/skills
# 通过环境变量 AGENT 选择目标：codex | qwen | qoder | claudecode | openclaw

usage() {
  cat <<'USAGE'
用法:
  feipi-scripts/repo/install_skills_links.sh

说明:
  把仓库内 skills/* 安装到目标目录。
  - 默认目标：~/.agents/skills（AGENT 未设置时）
  - 通过环境变量 AGENT 指定 agent：codex | qwen | qoder | claudecode | openclaw
  - 自动补齐 skill 中通过 $REPO_ROOT/xxx 引用的仓库共享路径软链接
  - codex -> $CODEX_HOME/skills（默认 ~/.codex/skills）
  - qwen -> ~/.qwen/skills
  - qoder -> ~/.qoder/skills
  - claudecode -> ~/.claude/skills
  - openclaw -> $OPENCLAW_HOME/skills（默认 ~/.openclaw/skills）
USAGE
}

if [[ $# -ne 0 ]]; then
  echo "本脚本不接受任何参数。" >&2
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_ROOT="$REPO_ROOT/skills"

if [[ ! -d "$SRC_ROOT" ]]; then
  echo "未找到 skills 目录: $SRC_ROOT" >&2
  exit 1
fi

AGENT_NAME="${AGENT:-}"
DEST_ROOT=""

case "$AGENT_NAME" in
  "")
    DEST_ROOT="$HOME/.agents/skills"
    ;;
  codex)
    CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
    DEST_ROOT="$CODEX_HOME_DIR/skills"
    ;;
  qoder)
    DEST_ROOT="$HOME/.qoder/skills"
    ;;
  qwen)
    DEST_ROOT="$HOME/.qwen/skills"
    ;;
  claudecode)
    DEST_ROOT="$HOME/.claude/skills"
    ;;
  openclaw)
    OPENCLAW_HOME_DIR="${OPENCLAW_HOME:-$HOME/.openclaw}"
    DEST_ROOT="$OPENCLAW_HOME_DIR/skills"
    ;;
  *)
    echo "未知 AGENT: ${AGENT_NAME}（支持 codex | qwen | qoder | claudecode | openclaw）" >&2
    usage
    exit 1
    ;;
esac

mkdir -p "$DEST_ROOT"
DEST_BASE="$(cd "$DEST_ROOT/.." && pwd)"

echo "源目录: $SRC_ROOT"
echo "目标目录($AGENT_NAME): $DEST_ROOT"
echo "目标根目录: $DEST_BASE"

link_item() {
  local src="$1"
  local dest="$2"
  local label="$3"
  local current_target=""

  if [[ -L "$dest" ]]; then
    # 若已是指向同一路径的链接则跳过。
    current_target="$(readlink "$dest")"
    if [[ "$current_target" == "$src" ]]; then
      echo "已存在且正确，跳过: $label"
      return 0
    fi
    rm -f "$dest"
  elif [[ -e "$dest" ]]; then
    # 为降低风险，不覆盖非软链接目录/文件。
    echo "警告: 目标已存在且非软链接，跳过: $dest" >&2
    return 1
  fi

  ln -s "$src" "$dest"
  echo "已安装: $label"
  return 0
}

collect_shared_roots() {
  rg -o --no-filename '\$REPO_ROOT/[A-Za-z0-9._/-]+' "$SRC_ROOT" -g '*.sh' 2>/dev/null \
    | sed -E 's#^\$REPO_ROOT/##' \
    | cut -d'/' -f1 \
    | rg -v '^[[:space:]]*$' \
    | sort -u || true
}

FOUND=0
INSTALLED=0
SKIPPED=0
for src in "$SRC_ROOT"/*; do
  if [[ ! -d "$src" ]]; then
    continue
  fi
  FOUND=1

  name="$(basename "$src")"
  dest="$DEST_ROOT/$name"
  if link_item "$src" "$dest" "$name"; then
    INSTALLED=$((INSTALLED + 1))
  else
    SKIPPED=$((SKIPPED + 1))
  fi
done

if [[ "$FOUND" -eq 0 ]]; then
  echo "未发现可安装 skill（$SRC_ROOT 下没有目录）。"
  exit 0
fi

SHARED_ROOTS_TEXT="$(collect_shared_roots)"
if [[ -n "$SHARED_ROOTS_TEXT" ]]; then
  echo "检测到共享路径依赖: $(printf '%s\n' "$SHARED_ROOTS_TEXT" | tr '\n' ' ')"
  while IFS= read -r root_name; do
    [[ -z "$root_name" ]] && continue
    src="$REPO_ROOT/$root_name"
    dest="$DEST_BASE/$root_name"

    if [[ "$dest" == "$DEST_ROOT" ]]; then
      continue
    fi

    if [[ ! -e "$src" ]]; then
      echo "警告: 共享路径不存在，跳过: $src" >&2
      SKIPPED=$((SKIPPED + 1))
      continue
    fi

    if link_item "$src" "$dest" "$root_name"; then
      INSTALLED=$((INSTALLED + 1))
    else
      SKIPPED=$((SKIPPED + 1))
    fi
  done <<< "$SHARED_ROOTS_TEXT"
fi

echo "完成。安装/更新: ${INSTALLED}，跳过: ${SKIPPED}"
