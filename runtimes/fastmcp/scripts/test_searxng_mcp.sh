#!/usr/bin/env bash
# SearXNG MCP 测试脚本
# 用法：./test_searxng_mcp.sh [搜索查询] [最大结果数]

set -e

MCP_URL="${MCP_URL:-http://localhost:18080/mcp}"
QUERY="${1:-Python MCP}"
MAX_RESULTS="${2:-5}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== SearXNG MCP 测试 ===${NC}"
echo "MCP URL: $MCP_URL"
echo "查询：$QUERY"
echo "最大结果数：$MAX_RESULTS"
echo ""

# 1. 获取 Session ID
echo -e "${YELLOW}Step 1: 获取 Session ID${NC}"
RESPONSE=$(curl -s -v -X GET "$MCP_URL" \
  -H "Accept: application/json, text/event-stream" 2>&1)

SESSION_ID=$(echo "$RESPONSE" | grep -i "mcp-session-id:" | \
  sed 's/.*mcp-session-id: *//' | tr -d '\r\n')

if [ -z "$SESSION_ID" ]; then
    echo -e "${RED}错误：无法获取 Session ID${NC}"
    echo "完整响应:"
    echo "$RESPONSE"
    exit 1
fi
echo "Session ID: $SESSION_ID"
echo ""

# 2. Initialize
echo -e "${YELLOW}Step 2: Initialize${NC}"
INIT_RESP=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}')

if echo "$INIT_RESP" | grep -q '"error"'; then
    echo -e "${RED}Initialize 失败：$INIT_RESP${NC}"
    exit 1
fi
echo "Initialize 成功"
echo ""

# 3. Call Tool
echo -e "${YELLOW}Step 3: 调用 search_web${NC}"
RESULT=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"searxng_search_web\",\"arguments\":{\"query\":\"$QUERY\",\"max_results\":$MAX_RESULTS}}}")

# 检查错误
if echo "$RESULT" | grep -q '"isError":true'; then
    echo -e "${RED}调用失败：$RESULT${NC}"
    exit 1
fi

# 用 Python 解析完整响应并提取结果
echo -e "${GREEN}=== 搜索结果 ===${NC}"
echo "$RESULT" | python3 -c "
import sys
import json
import re

raw = sys.stdin.read()

# 提取 data: 后面的 JSON
match = re.search(r'data:\s*(\{.*\})', raw, re.DOTALL)
if not match:
    print('无法解析响应:', raw)
    sys.exit(1)

data_json = match.group(1)
data = json.loads(data_json)

# 检查是否有错误
if data.get('error'):
    print(f\"错误：{data['error']}\")
    sys.exit(1)

# 获取结果
result = data.get('result', {})
structured = result.get('structuredContent')
text_content = None

# 如果没有 structuredContent，尝试从 text 字段解析
if not structured:
    content_list = result.get('content', [])
    for item in content_list:
        if item.get('type') == 'text':
            text_content = item.get('text')
            break

# 优先使用 structuredContent
if structured:
    output_data = structured
elif text_content:
    output_data = json.loads(text_content)
else:
    print('无法获取结果数据')
    sys.exit(1)

query = output_data.get('query', 'N/A')
results = output_data.get('results', [])
total = output_data.get('total_returned', 0)

print(f'查询：{query}')
print(f'返回结果数：{total}')
print('')

for i, item in enumerate(results, 1):
    title = item.get('title', 'No title')
    url = item.get('url', 'N/A')
    engine = item.get('engine', 'unknown')
    snippet = item.get('snippet', 'No description')

    print(f'{i}. {title}')
    print(f'   URL: {url}')
    print(f'   引擎：{engine}')
    if len(snippet) > 100:
        snippet = snippet[:100] + '...'
    print(f'   摘要：{snippet}')
    print('')
"

echo -e "${GREEN}=== 测试完成 ===${NC}"
