#!/usr/bin/env bash
# 复用已经选择的 Node；安装器不运行用户启动文件，也不改写全局 npm prefix。
set -euo pipefail
BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=bootstrap/environment.sh
source "$BOOTSTRAP_DIR/environment.sh"
export PATH="$HOME/.local/bin:$PATH"
python3 "$BOOTSTRAP_DIR/agents.py" "$@"
# 四个依赖阶段先于 Agent CLI；CLI 补装后刷新补全，否则首次终端缺少 Codex 缓存。
# install 保留已有主题/插件版本；plan/check 不执行此发布动作。
if [[ "${1:-check}" == install && -s "${ZSH:-$HOME/.oh-my-zsh}/oh-my-zsh.sh" ]]; then
  bash "$BOOTSTRAP_DIR/ohmyzsh.sh" install
fi
