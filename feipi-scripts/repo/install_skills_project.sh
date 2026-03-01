#!/usr/bin/env bash
set -euo pipefail

# 将当前仓库的 skills 目录下所有技能复制到指定项目目录。
# 与 install_skills_links.sh 不同：这里是实际拷贝，不是软链接。
# 默认目标目录：<project>/.agents/skills
# 可选 agent：codex | qwen | qoder | coder | claudecode | openclaw

usage() {
  cat <<'USAGE'
用法:
  feipi-scripts/repo/install_skills_project.sh <project_path> [--agent <name>]
  feipi-scripts/repo/install_skills_project.sh <project_path> [agent]

说明:
  把仓库内 skills/* 复制安装到指定项目目录。
  - 必传: project_path（项目根目录）
  - 可选: agent（codex | qwen | qoder | coder | claudecode | openclaw）
  - 默认目标: <project>/.agents/skills（未设置 agent 时）
  - codex -> <project>/.codex/skills
  - qwen -> <project>/.qwen/skills
  - qoder -> <project>/.qoder/skills
  - coder -> <project>/.coder/skills
  - claudecode -> <project>/.claude/skills
  - openclaw -> <project>/.openclaw/skills
  - 安装时会覆盖同名 skill（先删除后复制）
  - 自动检测 skill 中通过 $REPO_ROOT/xxx 引用的共享路径，并复制到目标根目录
USAGE
}

PROJECT_PATH=""
AGENT_NAME="${AGENT:-}"

if [[ $# -eq 0 ]]; then
  echo "缺少项目路径参数。" >&2
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --agent)
      shift
      if [[ $# -eq 0 ]]; then
        echo "--agent 缺少参数。" >&2
        usage
        exit 1
      fi
      AGENT_NAME="$1"
      ;;
    -* )
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ -z "$PROJECT_PATH" ]]; then
        PROJECT_PATH="$1"
      elif [[ -z "$AGENT_NAME" ]]; then
        AGENT_NAME="$1"
      else
        echo "多余参数: $1" >&2
        usage
        exit 1
      fi
      ;;
  esac
  shift
done

if [[ -z "$PROJECT_PATH" ]]; then
  echo "缺少项目路径参数。" >&2
  usage
  exit 1
fi

if [[ ! -d "$PROJECT_PATH" ]]; then
  echo "项目路径不存在或不是目录: $PROJECT_PATH" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_ROOT="$REPO_ROOT/skills"

if [[ ! -d "$SRC_ROOT" ]]; then
  echo "未找到 skills 目录: $SRC_ROOT" >&2
  exit 1
fi

PROJECT_ROOT="$(cd "$PROJECT_PATH" && pwd)"
DEST_ROOT=""

case "$AGENT_NAME" in
  "")
    DEST_ROOT="$PROJECT_ROOT/.agents/skills"
    ;;
  codex)
    DEST_ROOT="$PROJECT_ROOT/.codex/skills"
    ;;
  qoder)
    DEST_ROOT="$PROJECT_ROOT/.qoder/skills"
    ;;
  qwen)
    DEST_ROOT="$PROJECT_ROOT/.qwen/skills"
    ;;
  coder)
    DEST_ROOT="$PROJECT_ROOT/.coder/skills"
    ;;
  claudecode)
    DEST_ROOT="$PROJECT_ROOT/.claude/skills"
    ;;
  openclaw)
    DEST_ROOT="$PROJECT_ROOT/.openclaw/skills"
    ;;
  *)
    echo "未知 AGENT: ${AGENT_NAME}（支持 codex | qwen | qoder | coder | claudecode | openclaw）" >&2
    usage
    exit 1
    ;;
esac

if [[ "$DEST_ROOT" != "$PROJECT_ROOT"/* ]]; then
  echo "目标路径不在项目目录内，已拒绝: $DEST_ROOT" >&2
  exit 1
fi

mkdir -p "$DEST_ROOT"
DEST_BASE="$(cd "$DEST_ROOT/.." && pwd)"

echo "源目录: $SRC_ROOT"
echo "项目目录: $PROJECT_ROOT"
echo "目标目录($AGENT_NAME): $DEST_ROOT"
echo "目标根目录: $DEST_BASE"

copy_dir() {
  local src="$1"
  local dest="$2"
  local label="$3"

  if [[ -e "$dest" ]]; then
    rm -rf "$dest"
  fi

  cp -R -p "$src" "$dest"
  echo "已安装: $label"
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
  copy_dir "$src" "$dest" "$name"
  INSTALLED=$((INSTALLED + 1))
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

    copy_dir "$src" "$dest" "$root_name"
    INSTALLED=$((INSTALLED + 1))
  done <<< "$SHARED_ROOTS_TEXT"
fi

echo "完成。安装/更新: ${INSTALLED}，跳过: ${SKIPPED}"
