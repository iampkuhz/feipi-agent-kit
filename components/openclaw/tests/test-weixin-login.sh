#!/bin/bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/feipi-weixin-test.XXXXXX")"
trap 'find "$TEST_ROOT" -depth -delete 2>/dev/null || true' EXIT
TEST_HOME="$TEST_ROOT/home"
mkdir -p "$TEST_HOME/.local/env-vault"
printf 'test-only\n' >"$TEST_HOME/.local/env-vault/.env"
ln -s "$TEST_HOME/.local/env-vault/.env" "$TEST_HOME/.env"
HOME="$TEST_HOME" bash "$REPO_DIR/scripts/weixin-login.sh" --prepare-only >/dev/null
account_dir="$TEST_HOME/.openclaw/openclaw-weixin/accounts"
expected_dir="$TEST_HOME/.local/env-vault/openclaw-weixin/accounts"
[[ "$(readlink "$account_dir")" == "$expected_dir" ]]
[[ "$(stat -f '%Lp' "$expected_dir")" == "700" ]]
printf 'preserve\n' >"$account_dir/test.json"
HOME="$TEST_HOME" bash "$REPO_DIR/scripts/weixin-login.sh" --prepare-only >/dev/null
[[ "$(cat "$expected_dir/test.json")" == "preserve" ]]

# 已存在的真实目录必须保留，不能被自动覆盖或偷偷移动。
unlink "$account_dir"
mkdir "$account_dir"
printf 'original\n' >"$account_dir/existing.json"
if HOME="$TEST_HOME" bash "$REPO_DIR/scripts/weixin-login.sh" --prepare-only >/dev/null 2>&1; then
  echo "未拒绝已有凭据目录。" >&2
  exit 1
fi
[[ "$(cat "$account_dir/existing.json")" == "original" ]]
[[ "$(cat "$expected_dir/test.json")" == "preserve" ]]
echo "微信凭据 vault 链接、重复执行和冲突保护测试通过。"

# 使用隔离仓库和假 CLI 验证：新增第二人、重复标签、误扫已绑定账号。
FIXTURE="$TEST_ROOT/repo"
mkdir -p "$FIXTURE/scripts" "$TEST_ROOT/bin"
cp "$REPO_DIR/scripts/weixin-login.sh" "$FIXTURE/scripts/"
cat >"$FIXTURE/scripts/install-runtime.sh" <<'SH'
#!/bin/bash
exit 0
SH
chmod +x "$FIXTURE/scripts/install-runtime.sh"
cat >"$TEST_ROOT/bin/openclaw" <<'SH'
#!/bin/bash
set -euo pipefail
[[ "${1:-}" == channels && "${2:-}" == login ]] || exit 0
state="$HOME/.openclaw/openclaw-weixin"
if [[ "${WEIXIN_TEST_LOGIN:-new}" == new ]]; then
  printf '["first-im-bot","second-im-bot"]\n' >"$state/accounts.json"
  printf '{"token":"fake-second","userId":"second-user"}\n' >"$state/accounts/second-im-bot.json"
fi
SH
chmod +x "$TEST_ROOT/bin/openclaw"
LABEL_HOME="$TEST_ROOT/label-home"
mkdir -p "$LABEL_HOME/.openclaw/openclaw-weixin/accounts"
printf 'test-only\n' >"$LABEL_HOME/.env"
# 准备只允许新建 vault 链接，移除空目录后交给实际准备流程。
rmdir "$LABEL_HOME/.openclaw/openclaw-weixin/accounts"
HOME="$LABEL_HOME" bash "$FIXTURE/scripts/weixin-login.sh" --prepare-only >/dev/null
printf '["first-im-bot"]\n' >"$LABEL_HOME/.openclaw/openclaw-weixin/accounts.json"
printf '{"token":"fake-first","userId":"first-user"}\n' >"$LABEL_HOME/.openclaw/openclaw-weixin/accounts/first-im-bot.json"
cat >"$FIXTURE/openclaw.json" <<'JSON'
{"channels":{"openclaw-weixin":{"enabled":true,"accounts":{"first-im-bot":{"name":"hanzhe"}}}},"session":{"dmScope":"per-channel-peer"}}
JSON
cp "$FIXTURE/openclaw.json" "$FIXTURE/original.json"
HOME="$LABEL_HOME" PATH="$TEST_ROOT/bin:$PATH" bash "$FIXTURE/scripts/weixin-login.sh" --name xuzan >/dev/null
jq -e '.channels["openclaw-weixin"].accounts["first-im-bot"].name == "hanzhe"
  and .channels["openclaw-weixin"].accounts["second-im-bot"].name == "xuzan"
  and .session.dmScope == "per-account-channel-peer"' "$FIXTURE/openclaw.json" >/dev/null
cp "$FIXTURE/openclaw.json" "$FIXTURE/labeled.json"
if HOME="$LABEL_HOME" PATH="$TEST_ROOT/bin:$PATH" bash "$FIXTURE/scripts/weixin-login.sh" --name xuzan >/dev/null 2>&1; then
  echo "未拒绝重复账号标签。" >&2; exit 1
fi
cmp -s "$FIXTURE/openclaw.json" "$FIXTURE/labeled.json"
cp "$FIXTURE/original.json" "$FIXTURE/openclaw.json"
printf '["first-im-bot"]\n' >"$LABEL_HOME/.openclaw/openclaw-weixin/accounts.json"
if HOME="$LABEL_HOME" PATH="$TEST_ROOT/bin:$PATH" WEIXIN_TEST_LOGIN=existing \
  bash "$FIXTURE/scripts/weixin-login.sh" --name xuzan >/dev/null 2>&1; then
  echo "误将已有用户标记为新增用户。" >&2; exit 1
fi
cmp -s "$FIXTURE/openclaw.json" "$FIXTURE/original.json"
# 从零部署时允许把尚未登录的旧标签迁移到新扫码得到的账号 ID。
jq '.channels["openclaw-weixin"].accounts["stale-im-bot"] = {name:"xuzan"}' \
  "$FIXTURE/original.json" >"$FIXTURE/openclaw.json"
HOME="$LABEL_HOME" PATH="$TEST_ROOT/bin:$PATH" bash "$FIXTURE/scripts/weixin-login.sh" --name xuzan >/dev/null
jq -e '.channels["openclaw-weixin"].accounts | .["second-im-bot"].name == "xuzan"
  and (has("stale-im-bot") | not) and .["first-im-bot"].name == "hanzhe"' "$FIXTURE/openclaw.json" >/dev/null
echo "微信新增账号标签、原用户保留和误扫码保护测试通过。"
