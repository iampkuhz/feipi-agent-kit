#!/bin/bash
# 补齐没有纳入共享 Homebrew 清单的原生发布包；只使用 macOS 自带工具，可先安装代理。
set -euo pipefail
bootstrap_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-check}"
selection="${2:-all}"
if [[ $# -gt 2 || ("${mode}" != plan && "${mode}" != check && "${mode}" != install) ]]; then
  echo '用法：bash bootstrap/desktop-extras.sh plan|check|install [all|flclash|omlx|session-browser]' >&2
  exit 2
fi
case "${selection}" in all | flclash | omlx | session-browser) ;; *)
  echo '未知应用。' >&2
  exit 2
  ;;
esac
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 || "$(id -u)" == 0 ]]; then
  echo '这些固定发布包仅供 Apple Silicon macOS 普通用户安装。' >&2
  exit 1
fi
os_major="$(sw_vers -productVersion | cut -d. -f1)"
case "${os_major}" in 15 | 26 | 27) ;; *)
  echo '当前固定 oMLX 包只覆盖 macOS 15、26、27。' >&2
  exit 1
  ;;
esac
cache_dir="${XDG_CACHE_HOME:-${HOME}/Library/Caches}/feipi-workbench/downloads"
temp_dir=""
mount_dir=""
cleanup() {
  if [[ -n "${mount_dir}" ]]; then hdiutil detach -quiet "${mount_dir}" || true; fi
  if [[ -n "${temp_dir}" ]]; then rm -rf "${temp_dir}"; fi
}
trap cleanup EXIT

digest_matches() {
  [[ -f "$1" ]] && [[ "$(shasum -a 256 "$1" | awk '{print $1}')" == "$2" ]]
}

app_version() {
  /usr/libexec/PlistBuddy -c Print:CFBundleShortVersionString "$1/Contents/Info.plist"
}

check_app() {
  local app="$1" expected_id="$2" actual_id
  # 身份不符或损坏的目录明确失败，不能把同名目录当作安装完成。
  actual_id="$(/usr/libexec/PlistBuddy -c Print:CFBundleIdentifier "${app}/Contents/Info.plist")" || return 1
  [[ "${actual_id}" == "${expected_id}" ]] || {
    echo "应用身份不符：${app}" >&2
    return 1
  }
  # 函数在命令替换中执行，不能依赖 Bash 的隐式 errexit 传播检查失败。
  codesign --verify --deep --strict "${app}" || return 1
  app_version "${app}"
}

while IFS=$'\t' read -r name version kind payload bundle_id sha url; do
  [[ -n "${name}" && "${name}" != \#* ]] || continue
  actual_name="${name}"
  if [[ "${name}" == omlx-macos15 ]]; then
    [[ "${os_major}" == 15 ]] || continue
    actual_name=omlx
  elif [[ "${name}" == omlx && "${os_major}" == 15 ]]; then
    continue
  fi
  [[ "${selection}" == all || "${selection}" == "${actual_name}" ]] || continue
  if [[ "${kind}" == dmg ]]; then
    target="/Applications/${payload}"
  else
    target="${HOME}/.local/share/feipi-session-browser/releases/${version}"
  fi
  if [[ "${mode}" == plan ]]; then
    echo "${actual_name}：固定新装 ${version} → ${target}；已有安装保留。"
    continue
  fi
  if [[ -e "${target}" || -L "${target}" ]]; then
    if [[ "${kind}" == dmg ]]; then
      installed_version="$(check_app "${target}" "${bundle_id}")"
    else
      [[ -x "${target}/bin/run" && -x "${target}/runtime/bin/java" && -f "${target}/VERSION" ]]
      installed_version="$(cat "${target}/VERSION")"
      [[ "${installed_version}" == "${version}" ]]
    fi
    echo "${actual_name}：保留现有版本 ${installed_version}。"
  elif [[ "${mode}" == check ]]; then
    echo "缺少 ${actual_name}：${target}" >&2
    exit 1
  else
    # 应用目录不可写时提前停止，避免沿用调用者终端的 sudo 缓存。
    if [[ "${kind}" == dmg && ! -w /Applications ]]; then
      echo "当前用户无法写入 /Applications，请单独处理 ${actual_name} 的安装。" >&2
      exit 1
    fi
    mkdir -p "${cache_dir}"
    archive="${cache_dir}/${name}-${version}.${kind}"
    if ! digest_matches "${archive}" "${sha}"; then
      # 只发布摘要正确的完整缓存；中断留下的 .partial 下次重新下载。
      curl -fL --retry 2 --connect-timeout 15 --max-time 1800 "${url}" -o "${archive}.partial"
      digest_matches "${archive}.partial" "${sha}" || {
        echo "摘要不符：${actual_name}" >&2
        exit 1
      }
      mv "${archive}.partial" "${archive}"
    fi
    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/feipi-desktop-extra.XXXXXX")"
    if [[ "${kind}" == dmg ]]; then
      mount_dir="${temp_dir}/mount"
      mkdir "${mount_dir}"
      hdiutil attach -quiet -nobrowse -readonly -mountpoint "${mount_dir}" "${archive}"
      [[ "$(check_app "${mount_dir}/${payload}" "${bundle_id}")" == "${version}" ]] || {
        echo "发布包版本不符：${actual_name}" >&2
        exit 1
      }
      # 先复制到本次唯一目录，再移动到最终路径；无需关闭 Gatekeeper 或移除隔离属性。
      ditto "${mount_dir}/${payload}" "${temp_dir}/${payload}"
      hdiutil detach -quiet "${mount_dir}"
      mount_dir=""
      mv "${temp_dir}/${payload}" "${target}"
    else
      # 固定摘要先于解包；仍拒绝绝对路径和父目录跳转。
      if tar -tzf "${archive}" | awk '/^\// || /(^|\/)\.\.(\/|$)/ {bad=1} END {exit !bad}'; then
        echo '归档包含越界路径。' >&2
        exit 1
      fi
      tar -xzf "${archive}" -C "${temp_dir}"
      [[ "$(cat "${temp_dir}/${payload}/VERSION")" == "${version}" ]]
      mkdir -p "$(dirname "${target}")"
      mv "${temp_dir}/${payload}" "${target}"
    fi
    rm -rf "${temp_dir}"
    temp_dir=""
    echo "${actual_name}：已安装 ${version}（SHA-256 已校验）。"
  fi
  if [[ "${actual_name}" == omlx ]]; then
    # 当前固定 DMG 的应用没有附带公证票据；从 Apple 附加原有票据，
    # 不重新签名、不降低 Gatekeeper，也不删除隔离属性。只读 check 不修复。
    if ! xcode-select -p >/dev/null 2>&1 || ! xcrun --find stapler >/dev/null 2>&1; then
      echo 'oMLX 公证票据检查需要 CLT；先运行 scripts/bootstrap/prerequisites.sh install。' >&2
      exit 1
    fi
    if ! xcrun stapler validate "${target}" >/dev/null 2>&1; then
      if [[ "${mode}" == check ]]; then
        echo 'oMLX 缺少有效公证票据；运行 desktop-extras.sh install omlx 后复验。' >&2
        exit 1
      fi
      xcrun stapler staple "${target}"
    fi
  fi
  # 原生 runtime 用 $0 定位自身，不能直接将 bin/run 符号链接到另一个目录。
  if [[ "${actual_name}" == session-browser || "${actual_name}" == omlx ]]; then
    launcher="${HOME}/.local/bin/${actual_name}"
    if [[ "${actual_name}" == omlx ]]; then
      executable="${target}/Contents/MacOS/omlx-cli"
    else
      executable="${target}/bin/run"
    fi
    [[ -x "${executable}" ]]
    expected="$(printf '#!/bin/bash\nexec %q "$@"\n' "${executable}")"
    if [[ "${mode}" == install ]]; then
      mkdir -p "$(dirname "${launcher}")"
      if [[ -e "${launcher}" || -L "${launcher}" ]]; then
        [[ -f "${launcher}" && ! -L "${launcher}" && "$(cat "${launcher}")" == "${expected}" ]] || {
          echo "保留已有入口，请先审查冲突：${launcher}" >&2
          exit 1
        }
      else
        printf '%s\n' "${expected}" >"${launcher}"
        chmod 755 "${launcher}"
      fi
    fi
    [[ -x "${launcher}" && -f "${launcher}" && ! -L "${launcher}" && "$(cat "${launcher}")" == "${expected}" ]] || {
      echo "缺少或冲突的入口：${launcher}" >&2
      exit 1
    }
  fi
done <"${bootstrap_dir}/../config/desktop-extras.tsv"
