#!/usr/bin/env bash
set -euo pipefail

# 使用真实统一入口和来源脚本，只有外部程序被替换；不访问网络或运行转写。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="$SKILL_DIR/scripts"
AUDIT_TMP="$(mktemp -d)"
trap 'rm -rf "$AUDIT_TMP"' EXIT
mkdir -p "$AUDIT_TMP/bin"
cat > "$AUDIT_TMP/bin/yt-dlp" <<'MOCK'
#!/usr/bin/env bash
case " $* " in
  *' --version '*) echo '2020.01.01-test'; exit 0 ;;
  *'%(duration)s'*) echo 60; exit 0 ;;
  *' --write-subs '*|*' --write-auto-subs '*) exit 0 ;;
esac
if [[ "${TEST_AUTH_SIGNAL:-0}" == "1" ]]; then
  echo "ERROR: Sign in to confirm you are not a bot" >&2
fi
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
# 隔离宿主 Homebrew，确保本例只验证 PATH 中的 mock 版本。
printf '#!/usr/bin/env bash\nexit 1\n' > "$AUDIT_TMP/bin/brew"
RG_BIN="$(command -v rg)"
ln -s "$RG_BIN" "$AUDIT_TMP/bin/rg"
# 允许非 macOS 的 CI 覆盖下载失败路径；不会调用真实转写器。
printf '#!/usr/bin/env bash\necho Darwin\n' > "$AUDIT_TMP/bin/uname"
chmod +x "$AUDIT_TMP/bin/"*

mkdir -p "$AUDIT_TMP/output/youtube-a4RcpaTccFc/logs"
printf 'pipeline_stage=transcription\n' > "$AUDIT_TMP/output/youtube-a4RcpaTccFc/logs/youtube-whisper-noauth.log"
if env PATH="$AUDIT_TMP/bin:/usr/bin:/bin" AGENT_CHROME_PROFILE= AGENT_YOUTUBE_COOKIE_FILE= \
  bash "$RUNTIME_DIR/extract_video_text.sh" 'https://www.youtube.com/watch?v=a4RcpaTccFc' \
  "$AUDIT_TMP/output" auto --instruction '总结视频' > "$AUDIT_TMP/result.log" 2>&1; then
  echo 'FAIL: 全部下载失败却报告成功' >&2
  exit 1
fi
log_file="$AUDIT_TMP/output/youtube-a4RcpaTccFc/logs/youtube-whisper.log"
if [[ ! -f "$log_file" ]]; then
  echo 'FAIL: 真实入口未生成预期来源日志' >&2
  cat "$AUDIT_TMP/result.log" >&2
  exit 1
fi
for expected in first-marker ios-marker client-marker 'format=18' \
  'yt_dlp_attempt_exit=1' 'yt_dlp_version=2020.01.01-test' 'yt_dlp_stale=1' '<url-redacted>'; do
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

for expected in 'diagnostic_code=youtube_media_download_blocked' 'yt_dlp_stale=1' \
  'gvs_po_token_observed=1' 'retry_action=update_yt_dlp_then_rerun_same_unified_command'; do
  if ! grep -Fq "$expected" "$AUDIT_TMP/result.log"; then
    echo "FAIL: 统一入口缺少 YouTube 终态诊断 $expected" >&2
    cat "$AUDIT_TMP/result.log" >&2
    exit 1
  fi
done

grep -Fq "failure_log=$log_file" "$AUDIT_TMP/result.log"

# 后续重试成功也必须保留首次失败；验证真实公共函数不会改变返回码。
(
  source "$RUNTIME_DIR/lib/yt_dlp_common.sh"
  yt_common_init "$AUDIT_TMP/recovered"
  yt_common_on_error() { yt_common_run_cmd "$1" --version; }
  PATH="$AUDIT_TMP/bin:/usr/bin:/bin"
  yt_common_run_with_success_log 'https://www.youtube.com/watch?v=test' \
    > "$AUDIT_TMP/recovered.out" 2> "$AUDIT_TMP/recovered.err"
)
grep -q first-marker "$AUDIT_TMP/recovered.err"
grep -q 2020.01.01-test "$AUDIT_TMP/recovered.out"

# 通过真实入口产生无 Cookie 重试，最终诊断必须指向该次日志。
if env PATH="$AUDIT_TMP/bin:/usr/bin:/bin" AGENT_CHROME_PROFILE=Default AGENT_YOUTUBE_COOKIE_FILE= TEST_AUTH_SIGNAL=1 \
  bash "$RUNTIME_DIR/extract_video_text.sh" 'https://www.youtube.com/watch?v=a4RcpaTccFc' \
  "$AUDIT_TMP/noauth-output" whisper --instruction '总结视频' > "$AUDIT_TMP/noauth-result.log" 2>&1; then
  echo 'FAIL: 无 Cookie 重试全失败却报告成功' >&2
  exit 1
fi
grep -Fq "failure_log=$AUDIT_TMP/noauth-output/youtube-a4RcpaTccFc/logs/youtube-whisper-noauth.log" "$AUDIT_TMP/noauth-result.log"
grep -Fq 'failure_stage=media_download' "$AUDIT_TMP/noauth-result.log"
grep -Fq 'mode_calls=2' "$AUDIT_TMP/noauth-result.log"

# PATH 中的旧版本与 Homebrew formula 的新版同时存在时，必须选后者而不是依赖 PATH 顺序。
mkdir -p "$AUDIT_TMP/homebrew/bin"
cat > "$AUDIT_TMP/homebrew/bin/yt-dlp" <<'MOCK'
#!/usr/bin/env bash
if [[ " ${*} " == *' --version '* ]]; then
  echo '2026.08.19'
fi
MOCK
cat > "$AUDIT_TMP/bin/brew" <<MOCK
#!/usr/bin/env bash
if [[ "\${1:-}" == "--prefix" && "\${2:-}" == "yt-dlp" ]]; then
  echo "$AUDIT_TMP/homebrew"
  exit 0
fi
exit 1
MOCK
chmod +x "$AUDIT_TMP/homebrew/bin/yt-dlp" "$AUDIT_TMP/bin/brew"
(
  PATH="$AUDIT_TMP/bin:/usr/bin:/bin"
  source "$RUNTIME_DIR/lib/yt_dlp_common.sh"
  yt_common_require_tools dryrun
  [[ "$YT_DLP_BIN" == "$AUDIT_TMP/homebrew/bin/yt-dlp" ]]
  [[ "$YT_DLP_VERSION" == "2026.08.19" ]]
  [[ "$YT_DLP_SELECTION_REASON" == "highest_detected_version" ]]
) > "$AUDIT_TMP/selection.out" 2>&1
grep -Fq "yt_dlp_candidate=$AUDIT_TMP/bin/yt-dlp|2020.01.01-test" "$AUDIT_TMP/selection.out"
grep -Fq "yt_dlp_candidate=$AUDIT_TMP/homebrew/bin/yt-dlp|2026.08.19" "$AUDIT_TMP/selection.out"
grep -Fq "yt_dlp_path=$AUDIT_TMP/homebrew/bin/yt-dlp" "$AUDIT_TMP/selection.out"
echo '错误诊断回归通过：真实入口全失败、重试成功、依赖记录、URL 脱敏'
