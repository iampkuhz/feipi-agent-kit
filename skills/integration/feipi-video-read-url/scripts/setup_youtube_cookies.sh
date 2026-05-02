#!/usr/bin/env bash
set -euo pipefail

# YouTube Cookie 配置向导。
# 只负责生成 shell export 建议，不读取或上传 Cookie 内容。

DEFAULT_COOKIE_FILE="$HOME/.config/yt-dlp/cookies.youtube.txt"
DEFAULT_PROFILE="chrome:Default"

usage() {
  cat <<'USAGE'
用法:
  bash scripts/setup_youtube_cookies.sh [--check]

说明:
  --check  只检查当前 AGENT_YOUTUBE_COOKIE_FILE / AGENT_CHROME_PROFILE 是否可用
USAGE
}

normalize_path() {
  local raw="$1"
  if [[ "$raw" == "~" ]]; then
    echo "$HOME"
    return 0
  fi
  if [[ "$raw" == "~/"* ]]; then
    echo "$HOME/${raw:2}"
    return 0
  fi
  echo "$raw"
}

check_current_config() {
  local cookie_file
  cookie_file="$(normalize_path "${AGENT_YOUTUBE_COOKIE_FILE:-}")"

  echo "当前配置检查:"
  if [[ -n "$cookie_file" ]]; then
    if [[ -r "$cookie_file" ]]; then
      echo "[OK] AGENT_YOUTUBE_COOKIE_FILE=$cookie_file"
    else
      echo "[WARN] AGENT_YOUTUBE_COOKIE_FILE 不可读或不存在: $cookie_file"
    fi
  else
    echo "[INFO] 未设置 AGENT_YOUTUBE_COOKIE_FILE"
  fi

  if [[ -n "${AGENT_CHROME_PROFILE:-}" ]]; then
    echo "[OK] AGENT_CHROME_PROFILE=$AGENT_CHROME_PROFILE"
  else
    echo "[INFO] 未设置 AGENT_CHROME_PROFILE"
  fi
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--check" ]]; then
  check_current_config
  exit 0
fi

if [[ $# -gt 0 ]]; then
  usage >&2
  exit 1
fi

cat <<'INTRO'
YouTube Cookie 配置向导

推荐方式：导出 Netscape cookies.txt 文件，然后设置 AGENT_YOUTUBE_COOKIE_FILE。
常见浏览器扩展可以导出当前站点 Cookie，导出时请选择 youtube.com，并保存为 Netscape Cookie File 格式。

注意：Cookie 属于敏感凭据，只保存在本机，不要提交到 git，也不要贴到聊天窗口。
INTRO

printf "\nCookie 文件路径 [%s]: " "$DEFAULT_COOKIE_FILE"
IFS= read -r cookie_input
cookie_input="${cookie_input:-$DEFAULT_COOKIE_FILE}"
cookie_file="$(normalize_path "$cookie_input")"

printf "浏览器 profile 备用值 [%s]（可直接回车跳过）: " "$DEFAULT_PROFILE"
IFS= read -r profile_input
profile_input="${profile_input:-$DEFAULT_PROFILE}"

mkdir -p "$(dirname "$cookie_file")"

cat <<GUIDE

请完成以下步骤:

1. 在浏览器中登录 YouTube。
2. 使用 Cookie 导出扩展导出 youtube.com 的 Cookie。
3. 保存到:
   $cookie_file
4. 在当前 shell 中执行:

export AGENT_YOUTUBE_COOKIE_FILE="$cookie_file"
export AGENT_CHROME_PROFILE="$profile_input"

5. 验证:

bash skills/integration/feipi-video-read-url/scripts/setup_youtube_cookies.sh --check
bash skills/integration/feipi-video-read-url/scripts/download_video.sh "https://www.youtube.com/watch?v=BaW_jenozKc" ./tmp/video-cookie-check dryrun

若同时设置 Cookie 文件和浏览器 profile，YouTube 脚本在需要登录态时优先使用 Cookie 文件。
GUIDE
