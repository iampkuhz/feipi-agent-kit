#!/usr/bin/env bash
# 只恢复 Karabiner 和 iTerm2 的小配置；不安装应用、不启动服务、不覆盖已有内容。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-check}"
if [[ $# -gt 1 || ("$MODE" != check && "$MODE" != install) ]]; then
  echo "用法：bash bootstrap/desktop.sh [check|install]" >&2
  exit 2
fi
if [[ -z "${HOME:-}" || "$HOME" != /* || "$HOME" == / ]]; then
  echo "HOME 必须是非根目录的绝对路径。" >&2
  exit 1
fi
if [[ -e "$HOME" && ! -d "$HOME" ]]; then
  echo "HOME 已被文件占用：$HOME" >&2
  exit 1
fi
# 两个固定文件一一对应；数组保留 iTerm2 路径中的空格。
sources=("$REPO_ROOT/desktop/karabiner/karabiner.json" "$REPO_ROOT/desktop/iterm2/profile.json")
targets=("$HOME/.config/karabiner/karabiner.json" "$HOME/Library/Application Support/iTerm2/DynamicProfiles/dotfiles.json")

# 先整体检查目标和所有 HOME 内父目录，再复制任何文件。
for index in "${!sources[@]}"; do
  source_file="${sources[$index]}"
  target_file="${targets[$index]}"
  if [[ ! -f "$source_file" ]]; then
    echo "缺少仓库配置：$source_file" >&2
    exit 1
  fi
  parent_dir="$(dirname "$target_file")"
  while [[ "$parent_dir" != "$HOME" && "$parent_dir" != / ]]; do
    # 不跟随父目录链接，防止配置意外写进其他仓库或外部目录。
    if [[ -L "$parent_dir" || (-e "$parent_dir" && ! -d "$parent_dir") ]]; then
      echo "父目录冲突，请人工检查：$parent_dir" >&2
      exit 1
    fi
    parent_dir="$(dirname "$parent_dir")"
  done
  if [[ -L "$target_file" || (-e "$target_file" && ! -f "$target_file") ]]; then
    echo "目标类型冲突，请人工检查：$target_file" >&2
    exit 1
  fi
  if [[ -f "$target_file" ]] && ! cmp -s "$source_file" "$target_file"; then
    echo "已有配置不同，请先备份并人工合并：$target_file" >&2
    exit 1
  fi
done

if [[ "$MODE" == check ]]; then
  echo "桌面配置预检通过（只读，未安装）。"
  exit 0
fi
for index in "${!sources[@]}"; do
  source_file="${sources[$index]}"
  target_file="${targets[$index]}"
  if [[ -f "$target_file" ]] && cmp -s "$source_file" "$target_file"; then
    continue
  fi
  mkdir -p "$(dirname "$target_file")"
  # Karabiner 要求普通 JSON 文件，单文件软链会影响重载；使用可独立编辑的副本。
  # -n 防止预检后其他进程新建的文件被覆盖，随后核对副本是否一致。
  # 部分 cp 在目标已存在时返回 1；只在内容相同时接受这类并发创建。
  cp -n "$source_file" "$target_file" || cmp -s "$source_file" "$target_file"
  [[ ! -L "$target_file" ]]
  cmp -s "$source_file" "$target_file"
done
echo "桌面配置已恢复。应用内后续修改不会自动回写仓库；请审查后手工同步。"
