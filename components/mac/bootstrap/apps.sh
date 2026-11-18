#!/usr/bin/env bash
# 批量安装禁用 Homebrew 的 sudo 路径，管理员安装包只列出待审核的条目。
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
export HOMEBREW_NO_SUDO=1
check_apps() {
  # 和安装使用相同的版本策略，列出实际缺少的应用。
  "$brew_command" bundle check --no-upgrade --verbose --file "$REPO_ROOT/Brewfile.apps"
}
if ! check_apps; then
  [[ "$MODE" == install ]] || exit 1
  # 让 Homebrew 实时显示下载和安装子命令的输出。
  "$brew_command" bundle install --no-upgrade --verbose --file "$REPO_ROOT/Brewfile.apps"
  check_apps
fi

# 用 Homebrew 配方的绝对路径验证，避免误用菜单栏应用的同名 CLI。
omlx_prefix="$("$brew_command" --prefix jundot/omlx/omlx)"
if ! omlx_version="$(PYTHONDONTWRITEBYTECODE=1 "$omlx_prefix/bin/omlx" --version)" ||
  ! "$omlx_prefix/libexec/bin/python" -B - <<'PY'
from omlx.custom_kernels import native_kernel_status

kernels = native_kernel_status()
if not kernels:
    raise SystemExit('oMLX 没有报告原生内核。')
for name, kernel in kernels.items():
    if not kernel['available']:
        print(f"oMLX 内核 {name} 无法加载：{kernel.get('import_error')}")
raise SystemExit(not all(kernel['available'] for kernel in kernels.values()))
PY
then
  echo 'oMLX 验证失败。请确认 Metal 编译器可用，再运行 brew reinstall jundot/omlx/omlx --with-custom-kernel。' >&2
  exit 1
fi
echo "oMLX ${omlx_version}：原生内核加载通过。"
echo '需要启动 oMLX 后台服务时，运行 brew services start jundot/omlx/omlx。'
echo '批量桌面清单已齐备。'

echo '以下 PKG 由本人审核后逐项运行 brew install --cask，不参与批量安装：'
"$brew_command" bundle list --cask --file "$REPO_ROOT/Brewfile.apps.admin"
# 向用户显示可复制的命令，检查时也不打开 Finder。
# shellcheck disable=SC2016
echo '搜狗输入法由 Homebrew 准备原厂安装器。运行 open "$(brew --caskroom sogouinput)" 查看安装器。'
