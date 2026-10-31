#!/usr/bin/env bash
# 开发验证入口：不运行真实 HOME 初始化，不自动补装测试依赖。
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -gt 0 ]]; then
  echo "用法：bash bootstrap/test.sh" >&2
  exit 2
fi
for required in bash zsh git stow shellcheck shfmt; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "缺少测试工具：$required；未自动安装。" >&2
    exit 2
  }
done
for script_file in "$REPO_ROOT"/bootstrap/*.sh; do bash -n "$script_file"; done
# 固定到仓库目录，让 ShellCheck 的 source 注释在任意调用目录下都能解析。
cd "$REPO_ROOT"
shellcheck bootstrap/*.sh
shfmt -i 2 -d bootstrap/*.sh
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-tests.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT
mkdir -p "$TEST_ROOT/home" "$TEST_ROOT/tmp"
for suite in test-links test-node test-bootstrap test-completion-cache; do
  echo "验证：$suite"
  # 只给测试子进程传入隔离目录；清除凭据、代理、BASH_ENV 与 Git 用户钩子配置。
  env -i HOME="$TEST_ROOT/home" TMPDIR="$TEST_ROOT/tmp" PATH="$PATH" \
    NVM_DIR="$TEST_ROOT/home/.nvm" CARGO_HOME="$TEST_ROOT/home/.cargo" \
    RUSTUP_HOME="$TEST_ROOT/home/.rustup" ZSH="$TEST_ROOT/home/.oh-my-zsh" \
    XDG_CONFIG_HOME="$TEST_ROOT/home/.config" XDG_CACHE_HOME="$TEST_ROOT/home/.cache" \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
    bash "$REPO_ROOT/bootstrap/$suite.sh"
done
echo "离线验证通过；真实下载、终端启动与 GUI/业务功能仍需在新机验收。"
