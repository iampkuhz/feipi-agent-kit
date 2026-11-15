#!/bin/bash
# 裸机前置阶段只依赖 macOS 自带工具；准备 CLT、Homebrew、Git 和 Python，再进入工作台。
set -euo pipefail
mode="${1:-check}"
if [[ $# -gt 1 || ("$mode" != plan && "$mode" != check && "$mode" != install) ]]; then
  echo "用法：bash scripts/bootstrap/prerequisites.sh plan|check|install" >&2
  exit 2
fi
if [[ "$(uname -s)" != Darwin || "$(id -u)" == 0 ]]; then
  echo "请在 macOS 普通管理员账号下运行，不要 sudo 整个入口。" >&2
  exit 1
fi
if [[ -z "${HOME:-}" || "$HOME" != /* || "$HOME" == / || ! -d "$HOME" ]]; then
  echo "HOME 必须是已有用户目录。" >&2
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
clt_ready=0
if xcode-select -p >/dev/null 2>&1 && xcrun --find clang >/dev/null 2>&1; then clt_ready=1; fi
if [[ "$mode" == plan ]]; then
  echo "前置阶段：CLT 状态=${clt_ready}；Homebrew=${brew_command:-待安装}。"
  echo "安装将使用已固定版本并校验摘要的 Homebrew 官方安装器，随后补装 Git/Python，不升级已有包。"
  echo "首次安装前一次执行 sudo -v；后续保持已有授权，不在安装中逐项提问。"
  exit 0
fi
if [[ "$mode" == check ]]; then
  if [[ "$clt_ready" == 0 || -z "$brew_command" ]]; then
    echo "CLT/Homebrew 尚未齐备；运行前置 install 阶段。" >&2
    exit 1
  fi
  command -v git >/dev/null
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || {
    echo "需要可用的 Python 3.10+；运行前置 install 阶段。" >&2
    exit 1
  }
  echo "CLT、Homebrew、Git 与 Python 前置检查通过。"
  exit 0
fi

bootstrap_temp="$(mktemp -d "${TMPDIR:-/tmp}/feipi-mac-prerequisites.XXXXXX")"
sudo_keepalive_pid=""
cleanup() {
  if [[ -n "$sudo_keepalive_pid" ]]; then
    kill "$sudo_keepalive_pid" 2>/dev/null || true
    wait "$sudo_keepalive_pid" 2>/dev/null || true
  fi
  rm -rf "$bootstrap_temp"
}
trap cleanup EXIT
if [[ -z "$brew_command" || "$clt_ready" == 0 ]]; then
  if ! sudo -n -v >/dev/null 2>&1; then
    echo "需要一次管理员授权。请执行 sudo -v 后重跑同一入口；没有开始安装。" >&2
    exit 1
  fi
  # 仅在此次安装期间维持已有 sudo 授权，不写密码、不修改 sudoers。
  bootstrap_pid=$$
  (
    while kill -0 "$bootstrap_pid" 2>/dev/null; do
      sudo -n -v || exit 1
      sleep 45
    done
  ) &
  sudo_keepalive_pid=$!
  installer_url=https://raw.githubusercontent.com/Homebrew/install/e5b3c5834e3932c8aaa42deef4794076c9b0cbf0/install.sh
  installer_sha=5f333bbe53bc490e51e7ccb1df8779b3dd6ee73a1a7379efda216edb08ccb148
  # 下载失败直接停止；先确认新机网络/代理，再重跑，不执行半截安装器。
  curl -fL --retry 2 --connect-timeout 15 --max-time 180 "$installer_url" -o "$bootstrap_temp/homebrew-install.sh"
  printf '%s  %s\n' "$installer_sha" "$bootstrap_temp/homebrew-install.sh" | shasum -a 256 -c -
  NONINTERACTIVE=1 /bin/bash "$bootstrap_temp/homebrew-install.sh"
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "$candidate" ]]; then
      brew_command="$candidate"
      break
    fi
  done
fi
if [[ -z "$brew_command" ]]; then
  echo "Homebrew 安装后未发现入口。" >&2
  exit 1
fi
brew_environment="$("$brew_command" shellenv)"
eval "$brew_environment"
# 工作台自身需要 Git/Python；最小清单先于 Python 编排运行，不重复全量安装。
printf 'brew "git"\nbrew "python"\n' >"$bootstrap_temp/Brewfile"
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1 "$brew_command" bundle install --no-upgrade --file "$bootstrap_temp/Brewfile"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
echo "裸机前置阶段完成；完整环境继续执行工作台部署与功能验收。"
