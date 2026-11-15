#!/usr/bin/env bash
# 配置发布后显式准备编辑器；使用当前 nvm/Cargo 环境，不加载用户启动文件。
set -euo pipefail
BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# != 0 ]]; then
  echo "用法：bash bootstrap/neovim.sh（联网恢复锁定插件、构建并验收）" >&2
  exit 2
fi
# shellcheck source=bootstrap/environment.sh
source "$BOOTSTRAP_DIR/environment.sh"
for required in nvim git node npm yarn python3; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "缺少 ${required}；请先完成依赖安装和 workbench apply mac。" >&2
    exit 1
  }
done
export FEIPI_NVIM_BOOTSTRAP="$BOOTSTRAP_DIR/neovim.lua" GIT_TERMINAL_PROMPT=0
# 两次启动分开：先恢复锁文件，再用恢复后的插件代码进行配置、构建和真实能力检查。
# 外层限制整个阶段；超时清理本次进程组，不留下后台下载或编辑器。
python3 - <<'PY'
import os
import signal
import subprocess
import sys

for phase in ('restore', 'prepare'):
    env = dict(os.environ, FEIPI_NVIM_PHASE=phase)
    process = subprocess.Popen(['nvim', '--headless', '--cmd',
        'lua dofile(vim.env.FEIPI_NVIM_BOOTSTRAP)'], env=env, start_new_session=True)
    try:
        result = process.wait(timeout=1800)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        if isinstance(error, KeyboardInterrupt):
            sys.exit(130)
        sys.exit('Neovim 准备超时，保留已安装内容；修复网络后可重新执行。')
    if result:
        sys.exit(result)
PY
