#!/usr/bin/env bash
# 配置链接的唯一入口；Stow 根据包内目录层级定位 ~/.config/nvim 等目标。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-install}"
if [[ $# -gt 1 || ("$MODE" != install && "$MODE" != check && "$MODE" != verify) ]]; then
  echo "用法：bash bootstrap/macosinit.sh [install|check|verify]" >&2
  exit 2
fi
if [[ -z "${HOME:-}" || "$HOME" != /* || "$HOME" == / ]]; then
  echo "HOME 必须是非根目录的绝对路径。" >&2
  exit 1
fi
# 默认包范围只有这一处定义；安装、冲突模拟和安装后的来源验证共用。
packages=(zsh neovim)
if [[ "$MODE" == verify ]]; then
  command -v git >/dev/null 2>&1 || {
    echo "未核实：来源验证需要 Git。" >&2
    exit 1
  }
  # Git 是配置清单的来源，不再手工抽查四个文件。缓存/日志不应纳入 Git；
  # 若 Stow 忽略了某个已跟踪配置，此处应报缺失，不能把它当成已安装。
  # NUL 分隔兼容带空格的路径；pipefail 保证 Git 读取失败也会传递为非零。
  git -C "$REPO_ROOT" -c core.fsmonitor=false ls-files -z -- "${packages[@]}" | (
    result=0
    count=0
    while IFS= read -r -d '' source_path; do
      count=$((count + 1))
      target_path="$HOME/${source_path#*/}"
      if [[ ! -f "$REPO_ROOT/$source_path" ]]; then
        echo "来源缺失或类型异常：$source_path" >&2
        result=1
      elif [[ "$target_path" -ef "$REPO_ROOT/$source_path" ]]; then
        echo "来源正确：${source_path#*/}"
      else
        result=1
        if [[ -L "$target_path" ]]; then
          echo "链接来源不符或断链：$target_path -> $(readlink "$target_path")" >&2
        elif [[ -e "$target_path" ]]; then
          echo "来源不符（独立副本或父目录指向别处）：$target_path" >&2
        else
          echo "配置缺失：$target_path" >&2
        fi
        echo "  预期来源：$REPO_ROOT/$source_path" >&2
      fi
    done
    if [[ "$count" == 0 ]]; then
      echo "未核实：没有读到受 Git 跟踪的默认包配置。" >&2
      result=1
    fi
    echo "已核对 $count 个受 Git 跟踪的配置来源；不验证运行时效果。"
    if [[ "$result" != 0 ]]; then
      echo "下一步：核对并人工处理冲突，再执行 bash bootstrap/macosinit.sh install；未改动文件。" >&2
    fi
    exit "$result"
  )
  exit $?
fi
if ! command -v stow >/dev/null 2>&1; then
  echo "缺少 stow，请先执行 bash bootstrap/brew.sh install。" >&2
  exit 1
fi
# 新 HOME 可以尚不存在；只读检查不创建目录，安装模式才准备父目录。
if [[ "$MODE" == install ]]; then
  mkdir -p "$HOME"
elif [[ ! -d "$HOME" ]]; then
  echo "HOME 尚不存在：$HOME" >&2
  exit 1
fi

# Stow 不接管绝对路径链接；已经指向正确配置的链接直接保留，包括旧式目录链接。
# 数组让每项参数独立传递，HOME 或仓库路径带空格时也不会被拆开。
stow_args=(--dir="$REPO_ROOT" --target="$HOME" --no-folding)
preserve_correct_link() {
  local target_path="$1" source_path="$2" ignore_pattern="$3"
  if [[ -L "$HOME/$target_path" && "$HOME/$target_path" -ef "$REPO_ROOT/$source_path" ]]; then
    stow_args+=("--ignore=$ignore_pattern")
  fi
}
preserve_correct_link .zshrc zsh/.zshrc '^\.zshrc$'
preserve_correct_link .zsh_config zsh/.zsh_config '^\.zsh_config$'
preserve_correct_link bin zsh/bin '^bin$'
preserve_correct_link .config neovim/.config '^\.config$'
preserve_correct_link .config/nvim neovim/.config/nvim '^\.config/nvim$'

# 固定工作目录和目标，覆盖 .stowrc 中的默认 HOME；不使用 --adopt/--override。
# 先整体模拟，任一真实文件或错误链接冲突时退出，避免只链接了一半。
cd "$REPO_ROOT"
# 仅向 Stow 子进程移除 HOME，屏蔽用户级 ~/.stowrc 的 adopt/override/ignore 设置。
# 仓库 .stowrc 仍生效；链接目标始终由上面显式的 --target 指定。
env -u HOME stow "${stow_args[@]}" --simulate "${packages[@]}"
if [[ "$MODE" == install ]]; then
  # 不折叠目录：缺失的 .config/nvim 等父目录由 Stow 创建，文件逐个链接。
  env -u HOME stow "${stow_args[@]}" "${packages[@]}"
  echo "配置链接完成；重复执行不会覆盖已有文件。"
else
  echo "配置链接预检通过（仅模拟；不代表配置已安装）。"
fi
