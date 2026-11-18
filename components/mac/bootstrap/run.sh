#!/usr/bin/env bash
# 由 workbench install mac 调用，按固定依赖顺序补装。
set -euo pipefail

BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -ne 0 || "$(uname -s)" != Darwin || "$(id -u)" == 0 ]]; then
  echo '请以 macOS 普通用户运行 ./workbench install mac。' >&2
  exit 2
fi

stages=(brew node rust agents ohmyzsh apps desktop-extras)
labels=(Homebrew Node/npm Rust "Agent CLI" oh-my-zsh 桌面清单 原生桌面应用)
for index in "${!stages[@]}"; do
  stage="${stages[$index]}"
  printf '[%s/%s] %s\n' "$((index + 1))" "${#stages[@]}" "${labels[$index]}"
  if [[ "$stage" == agents ]]; then
    # Node 和 Rust 的安装子进程不能更新父进程环境，在生成补全前重新激活。
    # shellcheck source=bootstrap/environment.sh
    source "$BOOTSTRAP_DIR/environment.sh"
  fi
  # 已完成阶段可重用，失败通过 Bash 的退出码返回工作台。
  bash "$BOOTSTRAP_DIR/$stage.sh" install
done
