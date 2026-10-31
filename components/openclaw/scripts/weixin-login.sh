#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MODE="login"
ACCOUNT_NAME=""
case "${1:-}" in
  "") ;;
  --prepare-only) MODE="prepare" ;;
  --name)
    [[ $# -eq 2 && "$2" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || {
      echo "--name 需要一个由字母、数字、下划线或短横线组成的账号标签。" >&2; exit 2;
    }
    ACCOUNT_NAME="$2"
    shift ;;
  -h|--help)
    echo "用法：scripts/weixin-login.sh [--prepare-only | --name NAME]"
    echo "将微信凭据目录链接到 ~/.env 所在 vault，然后扫码登录、恢复受管配置并重启。"
    echo "--name 为新微信用户添加标签，或恢复尚未登录的同名配置；已有账号重新登录时不带此参数。"
    exit 0 ;;
  *) echo "未知参数：$1" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || exit 2
[[ "$(uname -s)" == "Darwin" ]] || { echo "本仓库只支持 macOS。" >&2; exit 1; }
umask 077

# 插件不提供 token/SecretRef 配置字段；扫码凭据直接写入现有 env vault，
# 不复制 Token 到 openclaw.json 或另一个 .env。账号索引和消息缓存仍属运行态。
node --input-type=module <<'JS'
import fs from 'node:fs';
import path from 'node:path';
const home = process.env.HOME;
const envDir = path.dirname(fs.realpathSync(path.join(home, '.env')));
const vault = envDir === home ? path.join(home, '.local/env-vault') : envDir;
const target = path.join(vault, 'openclaw-weixin/accounts');
const state = path.join(home, '.openclaw/openclaw-weixin');
const link = path.join(state, 'accounts');
let existing;
try { existing = fs.lstatSync(link); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (existing && (!existing.isSymbolicLink() || path.resolve(state, fs.readlinkSync(link)) !== target)) {
  throw new Error(`微信凭据目录已存在且不指向 env vault；保留原件，请先迁移：${link}`);
}
fs.mkdirSync(target, { recursive: true, mode: 0o700 });
fs.chmodSync(path.dirname(target), 0o700);
fs.chmodSync(target, 0o700);
fs.mkdirSync(state, { recursive: true, mode: 0o700 });
fs.chmodSync(state, 0o700);
if (!existing) fs.symlinkSync(target, link);
console.log(`微信凭据：${link} -> ${target}`);
JS

[[ "$MODE" == "login" ]] || exit 0
SNAPSHOT_FILE="$(mktemp "$HOME/.openclaw/openclaw-weixin/.login-accounts.XXXXXX")"
trap 'unlink "$SNAPSHOT_FILE"' EXIT
node --input-type=module - "$SNAPSHOT_FILE" "$REPO_DIR/openclaw.json" "$ACCOUNT_NAME" <<'JS'
import fs from 'node:fs';
import path from 'node:path';
const [snapshot, configPath, name] = process.argv.slice(2);
const state = path.join(process.env.HOME, '.openclaw/openclaw-weixin');
const index = path.join(state, 'accounts.json');
const ids = fs.existsSync(index) ? JSON.parse(fs.readFileSync(index, 'utf8')) : [];
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
if (name && Object.entries(config.channels?.['openclaw-weixin']?.accounts ?? {}).some(([id, a]) => a.name === name && ids.includes(id))) {
  throw new Error(`账号标签 ${name} 已存在；新增用户请用不同标签。`);
}
const before = ids.map(id => {
  if (typeof id !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(id)) throw new Error('微信账号 ID 格式无效。');
  const account = JSON.parse(fs.readFileSync(path.join(state, 'accounts', `${id}.json`), 'utf8'));
  return { id, userId: account.userId };
});
fs.writeFileSync(snapshot, JSON.stringify(before), { mode: 0o600 });
if (name) console.log(`请只使用 ${name} 的微信扫码；不要使用已经绑定的微信账号。`);
JS
env -u OPENCLAW_CONFIG_PATH openclaw channels login --channel openclaw-weixin

# 无登录账号或缺少扫码者 ID 时，不把 CLI 正常退出误报为接入成功。
node --input-type=module - "$SNAPSHOT_FILE" "$REPO_DIR/openclaw.json" "$ACCOUNT_NAME" <<'JS'
import fs from 'node:fs';
import path from 'node:path';
const [snapshot, configPath, name] = process.argv.slice(2);
const state = path.join(process.env.HOME, '.openclaw/openclaw-weixin');
const ids = JSON.parse(fs.readFileSync(path.join(state, 'accounts.json'), 'utf8'));
if (!Array.isArray(ids) || ids.length === 0) throw new Error('未保存微信登录账号，请重新扫码。');
for (const id of ids) {
  if (typeof id !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(id)) throw new Error('微信账号 ID 格式无效。');
  const file = path.join(state, 'accounts', `${id}.json`);
  const account = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!account.token?.trim() || !account.userId?.trim()) {
    throw new Error('微信凭据缺少 Token 或扫码者 ID，不能确认登录与私聊访问边界。');
  }
  fs.chmodSync(file, 0o600);
}
if (name) {
  const before = JSON.parse(fs.readFileSync(snapshot, 'utf8'));
  const added = ids.filter(id => !before.some(a => a.id === id));
  if (added.length !== 1 || before.some(a => !ids.includes(a.id))) {
    throw new Error('没有新增一个独立微信账号，或原账号被重新绑定；不写入新用户标签。');
  }
  const id = added[0];
  const account = JSON.parse(fs.readFileSync(path.join(state, 'accounts', `${id}.json`), 'utf8'));
  if (before.some(a => a.userId === account.userId)) throw new Error('扫码者已绑定，不能标记成另一位用户。');
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const channel = config.channels['openclaw-weixin'];
  channel.accounts ??= {};
  if (channel.accounts[id] || Object.entries(channel.accounts).some(([key, a]) => a.name === name && ids.includes(key))) {
    throw new Error('账号或标签已存在，保留已有配置。');
  }
  for (const [key, entry] of Object.entries(channel.accounts)) {
    if (entry.name === name) delete channel.accounts[key];
  }
  channel.accounts[id] = { name };
  config.session.dmScope = 'per-account-channel-peer';
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n');
  console.log(`已在仓库配置中标记微信账号：${name} (${id})`);
}
console.log(`微信登录凭据与扫码者 ID 检查通过：${ids.length} 个账号。`);
JS

# 登录器会写 channelConfigUpdatedAt；仓库仍是配置唯一入口。
"$REPO_DIR/scripts/install-runtime.sh" --write --yes
env -u OPENCLAW_CONFIG_PATH openclaw gateway restart
env -u OPENCLAW_CONFIG_PATH openclaw channels status --probe
echo "请在微信 ClawBot 会话发送：请只回复：微信接入成功"
