#!/usr/bin/env bash
set -euo pipefail

# 使用真实统一入口和来源脚本，只有外部程序被替换；不访问网络或运行转写。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIT_TMP="$(mktemp -d)"
trap 'rm -rf "$AUDIT_TMP"' EXIT
mkdir -p "$AUDIT_TMP/bin"
cat > "$AUDIT_TMP/bin/yt-dlp" <<'MOCK'
#!/usr/bin/env bash
case " $* " in
  *' --version '*) echo '2026.03.17-test'; exit 0 ;;
  *'%(duration)s'*) echo 60; exit 0 ;;
  *' --write-subs '*|*' --write-auto-subs '*) exit 0 ;;
esac
case " $* " in
  *'player_client=ios'*) echo 'ERROR: ios requires GVS PO Token; ios-marker' >&2 ;;
  *'player_client='*) echo 'ERROR: Requested format is not available; client-marker' >&2 ;;
  *) echo 'ERROR: HTTP Error 403: Forbidden; first-marker https://media.invalid/audio?token=secret-marker' >&2 ;;
esac
exit 1
MOCK
for tool in curl nc ffmpeg; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "$AUDIT_TMP/bin/$tool"
done
# 允许非 macOS 的 CI 覆盖下载失败路径；不会调用真实转写器。
printf '#!/usr/bin/env bash\necho Darwin\n' > "$AUDIT_TMP/bin/uname"
chmod +x "$AUDIT_TMP/bin/"*

if env PATH="$AUDIT_TMP/bin:$PATH" AGENT_CHROME_PROFILE= AGENT_YOUTUBE_COOKIE_FILE= \
  bash "$SCRIPT_DIR/extract_video_text.sh" 'https://www.youtube.com/watch?v=a4RcpaTccFc' \
  "$AUDIT_TMP/output" auto --instruction '总结视频' > "$AUDIT_TMP/result.log" 2>&1; then
  echo 'FAIL: 全部下载失败却报告成功' >&2
  exit 1
fi
log_file="$AUDIT_TMP/output/youtube-a4RcpaTccFc/logs/youtube-whisper.log"
for expected in first-marker ios-marker client-marker 'format=18' \
  'yt_dlp_attempt_exit=1' 'yt_dlp_version=2026.03.17-test' '<url-redacted>'; do
  if ! grep -Fq "$expected" "$log_file"; then
    echo "FAIL: 来源日志缺少 $expected" >&2
    cat "$log_file" >&2
    exit 1
  fi
done
grep -Fq "yt_dlp_path=$AUDIT_TMP/bin/yt-dlp" "$log_file"
if grep -q secret-marker "$log_file"; then
  echo 'FAIL: 日志泄漏媒体 URL 查询参数' >&2
  exit 1
fi

# 后续重试成功也必须保留首次失败；验证真实公共函数不会改变返回码。
(
  source "$SCRIPT_DIR/lib/yt_dlp_common.sh"
  yt_common_init "$AUDIT_TMP/recovered"
  yt_common_on_error() { yt_common_run_cmd "$1" --version; }
  PATH="$AUDIT_TMP/bin:$PATH"
  yt_common_run_with_success_log 'https://www.youtube.com/watch?v=test' \
    > "$AUDIT_TMP/recovered.out" 2> "$AUDIT_TMP/recovered.err"
)
grep -q first-marker "$AUDIT_TMP/recovered.err"
grep -q 2026.03.17-test "$AUDIT_TMP/recovered.out"
echo '错误诊断回归通过：真实入口全失败、重试成功、依赖记录、URL 脱敏'
