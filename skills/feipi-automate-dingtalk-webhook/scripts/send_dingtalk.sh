#!/usr/bin/env bash
# 钉钉 webhook 文本消息发送脚本
# 用法：send_dingtalk.sh <环境变量名> <消息内容> [加签密钥环境变量名]

set -euo pipefail

TIMEOUT_SECONDS=10

usage() {
  cat <<'EOF'
用法：send_dingtalk.sh <环境变量名> <消息内容> [加签密钥环境变量名]

参数：
  环境变量名            存储 webhook URL 的环境变量名称（如 DINGTALK_WEBHOOK_URL）
  消息内容              要发送的文本消息
  加签密钥环境变量名    （可选）存储加签密钥的环境变量名称

示例：
  send_dingtalk.sh DINGTALK_WEBHOOK_URL "部署完成：服务已上线"
  send_dingtalk.sh DINGTALK_WEBHOOK_URL "部署完成：服务已上线" DINGTALK_SECRET
EOF
  exit 1
}

calc_sign() {
  local secret="$1"
  local timestamp
  local string_to_sign
  local sign
  local sign_encoded

  timestamp=$(python3 -c "import time; print(int(time.time() * 1000))" 2>/dev/null || date +%s000)
  string_to_sign="${timestamp}"$'\n'"${secret}"
  sign=$(printf '%s' "$string_to_sign" | openssl dgst -sha256 -hmac "$secret" -binary | base64)
  sign_encoded=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote_plus(sys.stdin.read().strip()))" <<<"$sign" 2>/dev/null || \
    printf '%s' "$sign" | sed 's/+/%2B/g; s/\//%2F/g; s/=/%3D/g')

  printf '&timestamp=%s&sign=%s' "$timestamp" "$sign_encoded"
}

escape_json() {
  local str="$1"
  printf '%s' "$str" | python3 -c 'import json, sys; print(json.dumps(sys.stdin.read())[1:-1])'
}

if [[ $# -lt 2 ]]; then
  echo "错误：参数不足" >&2
  usage
fi

ENV_VAR_NAME="$1"
CONTENT="$2"
SECRET_VAR_NAME="${3:-}"
WEBHOOK_URL="${!ENV_VAR_NAME:-}"

if [[ -z "$WEBHOOK_URL" ]]; then
  echo "错误：环境变量 $ENV_VAR_NAME 未设置或为空" >&2
  exit 1
fi

if [[ ! "$WEBHOOK_URL" =~ ^https://oapi\.dingtalk\.com/robot/send\? ]]; then
  echo "警告：URL 格式可能不正确，预期以 https://oapi.dingtalk.com/robot/send? 开头" >&2
fi

if [[ -n "$SECRET_VAR_NAME" ]]; then
  SECRET="${!SECRET_VAR_NAME:-}"
  if [[ -z "$SECRET" ]]; then
    echo "错误：加签密钥环境变量 $SECRET_VAR_NAME 未设置或为空" >&2
    exit 1
  fi
  WEBHOOK_URL="${WEBHOOK_URL}$(calc_sign "$SECRET")"
fi

CONTENT_ESCAPED="$(escape_json "$CONTENT")"
JSON_PAYLOAD=$(cat <<EOF
{
  "msgtype": "text",
  "text": {
    "content": "$CONTENT_ESCAPED"
  }
}
EOF
)

echo "正在发送文本消息到钉钉..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
  --connect-timeout "$TIMEOUT_SECONDS" \
  -H "Content-Type: application/json" \
  -d "$JSON_PAYLOAD" \
  "$WEBHOOK_URL")

HTTP_CODE="$(printf '%s\n' "$RESPONSE" | tail -n 1)"
BODY="$(printf '%s\n' "$RESPONSE" | sed '$d')"

echo "HTTP 状态码：$HTTP_CODE"
echo "响应内容：$BODY"

if [[ "$HTTP_CODE" -eq 200 ]]; then
  ERRCODE="$(printf '%s' "$BODY" | grep -o '"errcode":[0-9]*' | cut -d':' -f2 || echo "")"
  if [[ "$ERRCODE" == "0" ]]; then
    echo "✓ 消息发送成功"
    exit 0
  fi

  echo "✗ 消息发送失败（钉钉返回错误）" >&2
  exit 1
fi

echo "✗ 消息发送失败（HTTP 错误）" >&2
exit 1
