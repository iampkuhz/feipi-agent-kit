#!/usr/bin/env bash
# Node 优先复用 nvm 默认版本或已有系统版本；全新环境才安装 nvm 与 Node LTS。
set -euo pipefail

MODE="${1:-install}"
if [[ "$MODE" != install && "$MODE" != upgrade ]]; then
  echo "用法：bash bootstrap/node.sh [install|upgrade]（upgrade 仅升级 npm 工具）" >&2
  exit 2
fi
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ ! -s "$NVM_DIR/nvm.sh" ]] && ! command -v node >/dev/null 2>&1; then
  # 固定 nvm 发布标签；直接克隆不运行会修改启动文件的安装器。
  if [[ -e "$NVM_DIR" || -L "$NVM_DIR" ]]; then
    echo "nvm 目录存在但缺少 nvm.sh，请人工检查：$NVM_DIR" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$NVM_DIR")"
  git clone --depth=1 --branch v0.40.8 https://github.com/nvm-sh/nvm.git "$NVM_DIR"
fi
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # 只加载函数，不自动选版本；nvm 外部代码不使用本脚本的 nounset 检查。
  set +u
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh" --no-use
  if [[ "$(nvm version default)" == N/A ]]; then
    # 若已安装其他版本却没有可用 default，不能擅自换用新的 LTS。
    if [[ -d "$NVM_DIR/versions/node" || -e "$NVM_DIR/alias/default" ]]; then
      echo "nvm default 不可用，请先用 nvm alias default <已安装版本> 修复。" >&2
      exit 1
    fi
    nvm install --lts
    nvm alias default "$(nvm current)"
  fi
  nvm use --silent default
  set -u
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node/npm 不完整；请修复现有 Node 安装后重试。" >&2
  exit 1
fi

# npm 包按当前 Node 的全局目录检查，不能用其他版本 PATH 中的同名命令代替。
# 只补缺包；已有包升级需要显式 upgrade。Yarn classic 用于 markdown-preview 构建。
NPM_ROOT="$(npm root -g)"
NPM_PREFIX="$(npm prefix -g)"
for package_spec in prettier @fsouza/prettierd yarn@1; do
  package_name="${package_spec%@1}"
  package_command="${package_name##*/}"
  # 旧机可能通过 Homebrew 安装同名工具；不让 npm 覆盖其全局 bin 链接。
  # 只检查所选 Node 的安装前缀，不把 PATH 中其他 Node 版本的工具当作已安装。
  if [[ ! -f "$NPM_ROOT/$package_name/package.json" &&
    (-e "$NPM_PREFIX/bin/$package_command" || -L "$NPM_PREFIX/bin/$package_command") ]]; then
    echo "保留非 npm 管理的工具：$NPM_PREFIX/bin/${package_command}（请通过所属安装方式升级）"
    continue
  fi
  if [[ "$MODE" == upgrade || ! -f "$NPM_ROOT/$package_name/package.json" ]]; then
    npm install -g "$package_spec"
  else
    echo "保留 npm 工具：$package_name"
  fi
done
echo "Node 与 npm 工具准备完成；新装 nvm 后请新开终端。"
