#!/usr/bin/env bash
# 桌面安装集中使用已有的一次 sudo 授权；不保存密码，也不修改 sudoers。
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-check}"
if [[ $# -gt 1 || ("$MODE" != check && "$MODE" != install) ]]; then
  echo "用法：bash bootstrap/apps.sh check|install" >&2
  exit 2
fi
if [[ "$(uname -s)" != Darwin || "$(id -u)" == 0 ]]; then
  echo "请在 macOS 普通用户下安装桌面应用。" >&2
  exit 1
fi
brew_command="$(command -v brew || true)"
if [[ -z "$brew_command" ]]; then
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "$candidate" ]]; then
      brew_command="$candidate"
      break
    fi
  done
fi
if [[ -z "$brew_command" ]]; then
  echo "缺少 Homebrew。" >&2
  exit 1
fi
export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1
if "$brew_command" bundle check --file "$REPO_ROOT/Brewfile.apps"; then
  echo "桌面应用清单已齐备；保留现有安装。"
  exit 0
fi
if [[ "$MODE" == check ]]; then exit 1; fi
if ! /usr/bin/sudo -n -v >/dev/null 2>&1; then
  echo "桌面安装需要一次管理员授权：先 sudo -v，再重跑；未开始下载。" >&2
  exit 1
fi
install_pid=$$
(
  while kill -0 "$install_pid" 2>/dev/null; do
    /usr/bin/sudo -n -v || exit 1
    sleep 45
  done
) &
keepalive_pid=$!
cleanup() {
  kill "$keepalive_pid" 2>/dev/null || true
  wait "$keepalive_pid" 2>/dev/null || true
}
trap cleanup EXIT
# 当前 Homebrew 的 sudo 可用性探测会主动 reset timestamp；上面已实际验证授权，
# 告知它已完成检查，避免清掉本轮凭据。false askpass 使授权失效时明确失败而不挂起。
HOMEBREW_SUDO_CHECKED=1 SUDO_ASKPASS=/usr/bin/false \
  "$brew_command" bundle install --no-upgrade --file "$REPO_ROOT/Brewfile.apps"
"$brew_command" bundle check --file "$REPO_ROOT/Brewfile.apps"
