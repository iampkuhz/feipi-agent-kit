#!/bin/bash
set -euo pipefail

dotenv="$HOME/.env"
runtime_dotenv="$HOME/.openclaw/.env"
if [[ ! -L "$runtime_dotenv" || "$(readlink "$runtime_dotenv")" != "$dotenv" ]]; then
  runtime_dotenv=""
fi

audit="$(openclaw secrets audit --json)"
printf '%s\n' "$audit"
# 新版会审计 dotenv 中的其他应用变量。密钥集中在用户的 .env，
# 配置文件或其他位置发现明文，以及无法解析的引用，仍应使校验失败。
jq -e --arg dotenv "$dotenv" --arg runtime_dotenv "$runtime_dotenv" '
  (.findings | type == "array")
  and all(.findings[];
    .code == "PLAINTEXT_FOUND"
    and .severity == "warn"
    and (.jsonPath | startswith("$env."))
    and (.file == $dotenv or ($runtime_dotenv != "" and .file == $runtime_dotenv))
  )
' <<<"$audit" >/dev/null
