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

# 新机原生 nvm 会把 default 写成 24.22.3；新终端应直接找到全局 CLI，
# 不需要先执行 node 来触发懒加载。也保留带 v 的旧配置和多级 LTS 别名。
mkdir -p "$TEST_ROOT/.nvm/alias/lts" "$TEST_ROOT/.nvm/versions/node/v24.22.3/bin"
cp "$TEST_ROOT/system/node" "$TEST_ROOT/.nvm/versions/node/v24.22.3/bin/openclaw"
printf 'lts/krypton\n' >"$TEST_ROOT/.nvm/alias/lts/*"
printf '24.22.3\n' >"$TEST_ROOT/.nvm/alias/lts/krypton"
for default_alias in 24.22.3 v24.22.3 'lts/*'; do
  printf '%s\n' "$default_alias" >"$TEST_ROOT/.nvm/alias/default"
  HOME="$TEST_ROOT" NVM_DIR="$TEST_ROOT/.nvm" zsh -f -c '
    source "$1/zsh/.zsh_config/00-core.zsh"
    source "$1/zsh/.zsh_config/09-nvm-path.zsh"
    source "$1/zsh/.zsh_config/62-nvm.zsh"
    [[ "$(command -v openclaw)" == "$NVM_DIR/versions/node/v24.22.3/bin/openclaw" ]] || exit 1
    [[ "$(openclaw --version)" == "openclaw --version" ]] || exit 1
    [[ "$NVM_BIN" == "$NVM_DIR/versions/node/v24.22.3/bin" ]] || exit 1
  ' -- "$REPO_ROOT"
done
echo "通过：新终端直接使用带 v、不带 v 和多级别名的 nvm 默认全局 CLI。"

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

# 新机不能跟随 --lts 漂移到尚未兼容当前 CLI 网络库的主版本。
mkdir -p "$TEST_ROOT/fresh-nvm" "$TEST_ROOT/runtime/bin"
cp "$TEST_ROOT/system/node" "$TEST_ROOT/runtime/bin/node"
cp "$TEST_ROOT/npm-driver/npm" "$TEST_ROOT/runtime/bin/npm"
for tool_package in prettier @fsouza/prettierd yarn; do
  mkdir -p "$TEST_ROOT/npm-prefix/lib/node_modules/$tool_package"
  touch "$TEST_ROOT/npm-prefix/lib/node_modules/$tool_package/package.json"
done
cat >"$TEST_ROOT/fresh-nvm/nvm.sh" <<'EOF'
nvm() {
  printf '%s\n' "$*" >> "$TEST_NVM_CALLS"
  case "$*" in
    'version default')
      if [[ -f "$TEST_NVM_STATE" ]]; then cat "$TEST_NVM_STATE"; else echo N/A; fi ;;
    'install 24.22.3')
      echo v24.22.3 > "$TEST_NVM_STATE"
      export PATH="$TEST_RUNTIME_BIN:$PATH" ;;
    current) cat "$TEST_NVM_STATE" ;;
    'alias default v24.22.3') : ;;
    'use --silent default')
      [[ -f "$TEST_NVM_STATE" ]] || return 3
      export PATH="$TEST_RUNTIME_BIN:$PATH" ;;
    *) echo "不应调用 nvm $*" >&2; return 99 ;;
  esac
}
EOF
HOME="$TEST_ROOT" NVM_DIR="$TEST_ROOT/fresh-nvm" \
  TEST_NVM_CALLS="$TEST_ROOT/nvm-calls" TEST_NVM_STATE="$TEST_ROOT/nvm-state" \
  TEST_RUNTIME_BIN="$TEST_ROOT/runtime/bin" TEST_NPM_PREFIX="$TEST_ROOT/npm-prefix" \
  bash -c '
    set -euo pipefail
    source "$1/bootstrap/environment.sh"
    [[ "$-" == *u* ]]
    bash "$1/bootstrap/node.sh" install
  ' -- "$REPO_ROOT"
grep -qx 'install 24.22.3' "$TEST_ROOT/nvm-calls"
grep -qx 'alias default v24.22.3' "$TEST_ROOT/nvm-calls"
echo "通过：nvm 下载后中断仍可激活环境并继续安装 Node 24.22.3，保留 nounset。"

# 已有 default 损坏时仍须停止，不能把用户选择当成全新安装悄悄替换。
mv "$TEST_ROOT/nvm-state" "$TEST_ROOT/nvm-state.saved"
mkdir -p "$TEST_ROOT/fresh-nvm/alias"
echo v0.missing >"$TEST_ROOT/fresh-nvm/alias/default"
status=0
HOME="$TEST_ROOT" NVM_DIR="$TEST_ROOT/fresh-nvm" \
  TEST_NVM_CALLS="$TEST_ROOT/nvm-calls" TEST_NVM_STATE="$TEST_ROOT/nvm-state" \
  TEST_RUNTIME_BIN="$TEST_ROOT/runtime/bin" \
  bash -c 'set -euo pipefail; source "$1/bootstrap/environment.sh"' -- "$REPO_ROOT" || status=$?
[[ "$status" == 3 && "$(cat "$TEST_ROOT/fresh-nvm/alias/default")" == v0.missing ]]
rm "$TEST_ROOT/fresh-nvm/alias/default"
mv "$TEST_ROOT/nvm-state.saved" "$TEST_ROOT/nvm-state"
echo "通过：已有无效 default 仍然失败并保留原配置。"

: >"$TEST_ROOT/nvm-calls"
echo v26.13.1 >"$TEST_ROOT/nvm-state"
HOME="$TEST_ROOT" NVM_DIR="$TEST_ROOT/fresh-nvm" \
  TEST_NVM_CALLS="$TEST_ROOT/nvm-calls" TEST_NVM_STATE="$TEST_ROOT/nvm-state" \
  TEST_RUNTIME_BIN="$TEST_ROOT/runtime/bin" TEST_NPM_PREFIX="$TEST_ROOT/npm-prefix" \
  bash "$REPO_ROOT/bootstrap/node.sh" install
[[ "$(cat "$TEST_ROOT/nvm-state")" == v26.13.1 ]]
if grep -Eq '^(install|alias)' "$TEST_ROOT/nvm-calls"; then
  echo "不应替换已有 nvm default。" >&2
  exit 1
fi
echo "通过：已有 nvm default 不被新机兼容基线替换。"
