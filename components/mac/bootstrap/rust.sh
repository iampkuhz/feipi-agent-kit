#!/usr/bin/env bash
# 安装只补缺失项；升级必须显式传入 upgrade，不写入任何 shell 启动文件。
set -euo pipefail

MODE="${1:-install}"
if [[ "$MODE" != install && "$MODE" != upgrade ]]; then
  echo "用法：bash bootstrap/rust.sh [install|upgrade]" >&2
  exit 2
fi
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export PATH="$CARGO_HOME/bin:$PATH"
if ! command -v rustup >/dev/null 2>&1; then
  # 禁止安装器改写 .zshrc/.profile；PATH 已由受管的 50-dev-paths.zsh 提供。
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs |
    sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable
elif [[ "$MODE" == upgrade ]]; then
  rustup update
else
  echo "保留已有 rustup 和工具链版本。"
fi

# 从 HOME 运行以免业务目录的 rust-toolchain 覆盖文件触发隐式下载。
cd "$HOME"
if ! rustup show active-toolchain >/dev/null 2>&1; then
  # 已有工具链却没有默认版本时交给用户选择；install stable 会刷新已有 stable。
  installed_toolchains="$(rustup toolchain list)"
  if [[ -n "$installed_toolchains" && "$installed_toolchains" != "no installed toolchains" ]]; then
    echo "已有 Rust 工具链但无可用默认版本，请先执行 rustup default <已安装版本>。" >&2
    exit 1
  fi
  rustup toolchain install stable --profile minimal --no-self-update
  rustup default stable
fi
# 对当前工具链仅补装 rustfmt；已有组件保持版本。
if ! rustup component list --installed | grep -E '^rustfmt(-|$)' >/dev/null; then
  rustup component add rustfmt
fi
echo "Rust 准备完成。"
