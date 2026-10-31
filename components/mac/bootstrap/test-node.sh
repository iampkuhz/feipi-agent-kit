#!/usr/bin/env bash
# 离线验证 NVM 懒加载，不加载真实 .zshrc，不执行下载安装。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-node.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT
mkdir -p "$TEST_ROOT/.nvm/bin" "$TEST_ROOT/system"

# 替身只定义 nvm 函数和 Node 的 PATH，以检测占位函数是否误删真正的 nvm。
cat >"$TEST_ROOT/.nvm/nvm.sh" <<'EOF'
export PATH="$NVM_DIR/bin:$PATH"
nvm() { print -r -- "nvm $*"; }
EOF
for node_command in node npm npx; do
  # 测试可执行文件输出自己的名称，不访问网络或安装目录。
  cat >"$TEST_ROOT/.nvm/bin/$node_command" <<'EOF'
#!/bin/sh
printf '%s\n' "${0##*/} $*"
EOF
  chmod +x "$TEST_ROOT/.nvm/bin/$node_command"
  cp "$TEST_ROOT/.nvm/bin/$node_command" "$TEST_ROOT/system/$node_command"
done

for first_command in nvm node npm npx; do
  HOME="$TEST_ROOT" NVM_DIR="$TEST_ROOT/.nvm" \
    zsh -f -c '
      source "$1/zsh/.zsh_config/62-nvm.zsh"
      [[ "$("$2" --version)" == "$2 --version" ]] || exit 1
      # 首次命令在子 shell 中验证后，再在当前 shell 真正触发懒加载。
      "$2" --version >/dev/null || exit 1
      (( $+functions[nvm] )) || exit 1
      [[ "$(nvm current)" == "nvm current" ]] || exit 1
      [[ "$(node --version)" == "node --version" ]] || exit 1
    ' -- "$REPO_ROOT" "$first_command"
  echo "通过：首次调用 ${first_command} 后仍可使用 nvm 与 node。"
done

# 没有 nvm 时，node/npm/npx 仍应落到系统版本；nvm 自身要明确报缺失。
HOME="$TEST_ROOT" NVM_DIR="$TEST_ROOT/missing-nvm" PATH="$TEST_ROOT/system:$PATH" \
  zsh -f -c '
    source "$1/zsh/.zsh_config/62-nvm.zsh"
    [[ "$(node --version)" == "node --version" ]] || exit 1
    [[ "$(npm --version)" == "npm --version" ]] || exit 1
    [[ "$(npx --version)" == "npx --version" ]] || exit 1
  ' -- "$REPO_ROOT"
echo "通过：无 nvm 时复用系统 Node/npm/npx。"

# nvm 缺失应返回明确的 127，而不是加载后把函数误删导致命令失踪。
HOME="$TEST_ROOT" NVM_DIR="$TEST_ROOT/missing-nvm" \
  zsh -f -c '
    source "$1/zsh/.zsh_config/62-nvm.zsh"
    nvm --version >/dev/null 2>&1
    [[ $? -eq 127 ]]
  ' -- "$REPO_ROOT"
echo "通过：无 nvm 时明确返回未安装。"

# 模拟旧机 Homebrew 在所选 Node 前缀中提供的同名命令，npm 不应抢占链接。
mkdir -p "$TEST_ROOT/npm-prefix/bin" "$TEST_ROOT/npm-prefix/lib/node_modules" "$TEST_ROOT/npm-driver"
cp "$TEST_ROOT/system/node" "$TEST_ROOT/npm-driver/node"
for tool_command in prettier prettierd yarn; do
  cp "$TEST_ROOT/system/node" "$TEST_ROOT/npm-prefix/bin/$tool_command"
done
cat >"$TEST_ROOT/npm-driver/npm" <<'EOF'
#!/bin/sh
case "$1" in
  root) printf '%s\n' "$TEST_NPM_PREFIX/lib/node_modules" ;;
  prefix) printf '%s\n' "$TEST_NPM_PREFIX" ;;
  *) echo "不应接管已有工具：$*" >&2; exit 99 ;;
esac
EOF
chmod +x "$TEST_ROOT/npm-driver/npm"
for node_mode in install upgrade; do
  HOME="$TEST_ROOT" NVM_DIR="$TEST_ROOT/missing-nvm" \
    TEST_NPM_PREFIX="$TEST_ROOT/npm-prefix" PATH="$TEST_ROOT/npm-driver:$PATH" \
    bash "$REPO_ROOT/bootstrap/node.sh" "$node_mode"
done
echo "通过：安装与升级均不接管所选 Node 前缀中的非 npm 工具。"
