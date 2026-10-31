#!/bin/bash
# 固定范围的停写归档；原生 archive 在当前版本拒绝 ~/.openclaw/.env 绝对链接。
# 保留标准 tar 与 SQLite 完整性检查，不实现新的迁移格式或原地数据库恢复。
set -euo pipefail
umask 077
backup_root="$HOME/.local/state/feipi-workbench/openclaw-backups"
mkdir -p "$backup_root"
batch="$(mktemp -d "$backup_root/offline-$(date +%Y%m%d-%H%M%S).XXXXXX")"
was_running=0
if launchctl print "gui/$(id -u)/ai.openclaw.gateway" >/dev/null 2>&1; then
  was_running=1
fi
resume() {
  local result=$?
  if [[ "$was_running" == 1 ]]; then
    if ! openclaw gateway start >"$batch/restart.log" 2>&1; then
      echo "Gateway 自动恢复失败：请执行 openclaw gateway start；见 $batch/restart.log" >&2
      result=1
    fi
  fi
  exit "$result"
}
trap resume EXIT
if [[ "$was_running" == 1 ]]; then
  openclaw gateway stop --force >"$batch/stop.log" 2>&1
fi
# 保存会话/记忆/插件状态、运行声明、浏览器与 env vault；排除可重建缓存/依赖。
# tar 保留符号链接本身，绝不跟随到不可控目录；vault 单独明确加入归档。
python3 - "$batch" <<'PY'
import json, pathlib, sqlite3, sys
home = pathlib.Path.home()
paths = [home/'.openclaw/state/openclaw.sqlite', *sorted((home/'.openclaw/agents').glob('*/agent/openclaw-agent.sqlite')),
         home/'.openclaw/openclaw-weixin/ref-messages.sqlite']
checks = {}
for path in paths:
    if not path.exists(): continue
    with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
        result = db.execute('PRAGMA integrity_check').fetchall()
    if result != [('ok',)]: raise SystemExit('SQLite 完整性失败：'+str(path))
    checks[str(path.relative_to(home))] = 'ok'
pathlib.Path(sys.argv[1], 'sqlite-integrity.json').write_text(json.dumps(checks, indent=2)+'\n')
PY
tar -czf "$batch/state.tar.gz" \
  --exclude='node_modules' --exclude='.openclaw/cache' --exclude='.openclaw/tmp' --exclude='.openclaw/logs' \
  -C "$HOME" .openclaw
vault_file="$(python3 -c 'from pathlib import Path; print((Path.home()/".env").resolve())')"
# 只保存当前配置实际引用的 env 文件；~/.env 是普通文件时也不能递归归档整个 HOME。
tar -czf "$batch/env-vault.tar.gz" -C "$(dirname "$vault_file")" "$(basename "$vault_file")"
python3 - "$batch" "$vault_file" <<'PY'
import json, pathlib, sys
pathlib.Path(sys.argv[1], 'env-location.json').write_text(json.dumps({'original_path': sys.argv[2]}, indent=2)+'\n')
PY
(cd "$batch" && shasum -a 256 state.tar.gz env-vault.tar.gz env-location.json sqlite-integrity.json >SHA256SUMS)
tar -tzf "$batch/state.tar.gz" >/dev/null
echo "停写归档及 SQLite 校验通过：$batch"
echo "恢复前先停 Gateway；解到新目录检查，再替换所需数据，勿在线覆盖 SQLite。"
