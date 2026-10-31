#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
STATE_DIR="$HOME/.openclaw"
WORKSPACE_MANIFEST="$REPO_DIR/templates/workspace/manifest.json"
MODE="check"
ASSUME_YES=0

usage() {
  cat <<'EOF'
用法：
  scripts/install-runtime.sh --check
  scripts/install-runtime.sh --write [--yes]

检查或安装 Git 管理的运行文件。~/.openclaw/.env 软链接到 ~/.env；
配置、workspace 模板和 adapter 复制到运行目录，避免 macOS LaunchAgent
读取 Documents 软链接时被系统文件访问控制阻塞。
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      shift
      ;;
    --write)
      MODE="write"
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for command_name in cmp jq readlink stat; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "未检测到命令：$command_name" >&2
    exit 1
  fi
done

if [[ ! -f "$HOME/.env" ]]; then
  echo "全局环境文件不存在：$HOME/.env" >&2
  exit 1
fi
if ! jq -e '
  .version == 1
  and .target == "~/.openclaw/workspace"
  and (.files | type == "array" and length > 0)
  and all(.files[];
    type == "string"
    and length > 0
    and (startswith("/") | not)
    and (contains("\\") | not)
    and (split("/") | all(. != ".."))
  )
  and (.files | length == (unique | length))
' "$WORKSPACE_MANIFEST" >/dev/null; then
  echo "无效的 workspace manifest：$WORKSPACE_MANIFEST" >&2
  exit 1
fi

sources=(
  "$REPO_DIR/openclaw.json"
  "$REPO_DIR/scripts/transcribe-audio-whispercpp-openclaw.sh"
)
targets=(
  "$STATE_DIR/openclaw.json"
  "$STATE_DIR/scripts/transcribe-audio-whispercpp-openclaw.sh"
)
modes=(600 755)

while IFS= read -r relative_path; do
  sources+=("$REPO_DIR/templates/workspace/$relative_path")
  targets+=("$STATE_DIR/workspace/$relative_path")
  modes+=(644)
done < <(jq -r '.files[]' "$WORKSPACE_MANIFEST")

if [[ -L "$STATE_DIR/.env" && "$(readlink "$STATE_DIR/.env")" == "$HOME/.env" ]]; then
  env_action="skip"
  echo "[ok]      $STATE_DIR/.env -> $HOME/.env"
elif [[ -e "$STATE_DIR/.env" || -L "$STATE_DIR/.env" ]]; then
  env_action="error"
  echo "[conflict] $STATE_DIR/.env 不是指向 $HOME/.env 的软链接" >&2
else
  env_action="add"
  echo "[add]     $STATE_DIR/.env -> $HOME/.env"
fi

add_count=0
update_count=0
ok_count=0
error_count=0
actions=()

if [[ "$env_action" == "skip" ]]; then
  ok_count=$((ok_count + 1))
elif [[ "$env_action" == "add" ]]; then
  add_count=$((add_count + 1))
else
  error_count=$((error_count + 1))
fi

for index in "${!sources[@]}"; do
  source_file="${sources[$index]}"
  target_file="${targets[$index]}"
  expected_mode="${modes[$index]}"
  actual_mode=""
  if [[ -f "$target_file" && ! -L "$target_file" ]]; then
    actual_mode="$(stat -f '%Lp' "$target_file")"
  fi

  if [[ ! -f "$source_file" ]]; then
    echo "[error] 来源文件不存在：$source_file" >&2
    actions+=("error")
    error_count=$((error_count + 1))
  elif [[ "$actual_mode" == "$expected_mode" ]] && cmp -s "$source_file" "$target_file"; then
    echo "[ok]      $target_file"
    actions+=("skip")
    ok_count=$((ok_count + 1))
  elif [[ -e "$target_file" || -L "$target_file" ]]; then
    echo "[update]  $target_file"
    actions+=("update")
    update_count=$((update_count + 1))
  else
    echo "[add]     $target_file"
    actions+=("add")
    add_count=$((add_count + 1))
  fi
done

printf '运行文件汇总：已就绪 %d，待新增 %d，待更新 %d，错误 %d。\n' \
  "$ok_count" "$add_count" "$update_count" "$error_count"

if [[ "$error_count" -gt 0 ]]; then
  exit 1
fi
if [[ "$MODE" == "check" || $((add_count + update_count)) -eq 0 ]]; then
  exit 0
fi

if [[ "$ASSUME_YES" -eq 0 ]]; then
  if [[ ! -t 0 ]]; then
    echo "非交互写入必须显式添加 --yes。" >&2
    exit 2
  fi
  read -r -p "确认安装以上运行文件？[y/N] " answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *)
      echo "已取消。"
      exit 0
      ;;
  esac
fi

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
if [[ "$env_action" == "add" ]]; then
  ln -s "$HOME/.env" "$STATE_DIR/.env"
fi

for index in "${!sources[@]}"; do
  [[ "${actions[$index]}" != "skip" ]] || continue
  source_file="${sources[$index]}"
  target_file="${targets[$index]}"
  target_mode="${modes[$index]}"
  target_dir="$(dirname "$target_file")"
  mkdir -p "$target_dir"
  temp_file="$(mktemp "$target_dir/.runtime-install.XXXXXX")"
  cp "$source_file" "$temp_file"
  chmod "$target_mode" "$temp_file"
  mv -f "$temp_file" "$target_file"
done

echo "运行文件已安装。"
