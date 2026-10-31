#!/usr/bin/env bash
# 只检查文件、语法与命令路径；不加载 .zshrc，不安装、不启动服务、不访问网络。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -gt 0 ]]; then
  echo "用法：bash bootstrap/check.sh；安装计划用 bash bootstrap/run.sh plan。" >&2
  exit 2
fi
if [[ -z "${HOME:-}" || "$HOME" != /* || "$HOME" == / ]]; then
  echo "HOME 必须是非根目录的绝对路径。" >&2
  exit 1
fi
result=0
# Bash 的 -n 每次只检查一个脚本，因此不能简单传入 bootstrap/*.sh。
for script_file in "$REPO_ROOT"/bootstrap/*.sh; do
  bash -n "$script_file" || result=1
done
# ShellCheck 只读取脚本，发现问题时累积失败状态，不在检查入口安装工具。
if command -v shellcheck >/dev/null 2>&1; then
  # 子 shell 固定源码查找目录；从其他目录调用时也能解析 source 注释。
  (cd "$REPO_ROOT" && shellcheck bootstrap/*.sh) || result=1
fi
for required_command in git brew stow nvim tree-sitter shellcheck shfmt python3 uv node npm prettier prettierd yarn rustup rustfmt; do
  if command -v "$required_command" >/dev/null 2>&1; then
    echo "入口已发现：$required_command ($(command -v "$required_command"))；未运行核验版本。"
  else
    echo "PATH 中未发现：$required_command（不等于机器上一定未安装）" >&2
    result=1
  fi
done
# 与链接入口共用默认包范围；校验 Git 跟踪的全部配置，而不是四个样本。
bash "$REPO_ROOT/bootstrap/macosinit.sh" verify || result=1
if [[ ! -s "$HOME/.oh-my-zsh/oh-my-zsh.sh" ]]; then
  echo "缺少 oh-my-zsh；执行 bash bootstrap/ohmyzsh.sh install。" >&2
  result=1
fi
echo "共享/单机软件清单另用 bash bootstrap/brew.sh check 检查；Java/GUI 按需人工检查。"
echo "需要处理缺项时见 docs/maintenance.md；不自动安装或改写配置。"
echo "人工验收：新终端、Neovim 插件/预览、HHKB/iTerm2 与业务服务不由本检查证明。"
exit "$result"
