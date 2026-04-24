#!/usr/bin/env bash
# Crawl4AI 测试脚本
# 用法：./test_crawl4ai_mcp.sh [操作] [URL]
# 示例：
#   ./test_crawl4ai_mcp.sh fingerprint
#   ./test_crawl4ai_mcp.sh md https://example.com
#   CRAWL4AI_REQUEST_PROFILE=anti-bot ./test_crawl4ai_mcp.sh screenshot https://bot.sannysoft.com

set -e

CRAWL4AI_URL="${CRAWL4AI_URL:-http://localhost:11235}"
ACTION="${1:-md}"
TARGET_URL="${2:-https://example.com}"
REQUEST_PROFILE="${CRAWL4AI_REQUEST_PROFILE:-default}"
export CRAWL4AI_URL TARGET_URL

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

create_crawl_payload() {
    ACTION="$1" TARGET_URL="$2" REQUEST_PROFILE="$3" python3 - <<'PY'
import json
import os

action = os.environ["ACTION"]
target_url = os.environ["TARGET_URL"]
request_profile = os.environ["REQUEST_PROFILE"]

payload = {
    "urls": [target_url],
}

browser_params = {}
crawler_params = {}

if request_profile == "anti-bot":
    browser_params = {
        "headless": True,
        "enable_stealth": True,
        "viewport_width": 1440,
        "viewport_height": 900,
        "user_agent_mode": "random",
        "user_agent_generator_config": {
            "browsers": ["Chrome"],
            "os": ["Linux"],
            "platforms": ["desktop"],
            "min_version": 120.0,
        },
        "headers": {
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    crawler_params = {
        "cache_mode": "bypass",
        "wait_until": "networkidle",
        "page_timeout": 90000,
        "wait_for_images": True,
        "delay_before_return_html": 1.0,
        "simulate_user": True,
        "override_navigator": True,
        "magic": True,
        "remove_overlay_elements": True,
    }

if action == "md":
    crawler_params["markdown_generator"] = {
        "type": "DefaultMarkdownGenerator",
        "params": {},
    }
elif action == "html":
    pass
elif action == "screenshot":
    crawler_params["screenshot"] = True
    crawler_params["screenshot_wait_for"] = 2
elif action == "pdf":
    crawler_params["pdf"] = True
else:
    raise SystemExit(f"未知 crawl 操作：{action}")

if browser_params:
    payload["browser_config"] = {
        "type": "BrowserConfig",
        "params": browser_params,
    }
if crawler_params:
    payload["crawler_config"] = {
        "type": "CrawlerRunConfig",
        "params": crawler_params,
    }

print(json.dumps(payload, ensure_ascii=False))
PY
}

probe_fingerprint() {
    python3 - <<'PY'
import json
import os
import re
import sys
from urllib import request

base_url = os.environ["CRAWL4AI_URL"]
target_url = os.environ.get("TARGET_URL") or "https://example.com"

script = """
(() => {
  const data = {
    webdriver: navigator.webdriver,
    languages: navigator.languages,
    plugins: navigator.plugins.length,
    platform: navigator.platform,
    userAgent: navigator.userAgent,
    chrome: !!window.chrome,
    outerWidth: window.outerWidth,
    outerHeight: window.outerHeight,
    hardwareConcurrency: navigator.hardwareConcurrency,
  };
  document.body.innerHTML = '<pre id="probe">' + JSON.stringify(data) + '</pre>';
  return data;
})()
""".strip()

payload = json.dumps({"url": target_url, "scripts": [script]}).encode()
req = request.Request(
    f"{base_url}/execute_js",
    data=payload,
    headers={"Content-Type": "application/json"},
)
with request.urlopen(req, timeout=180) as resp:
    body = json.load(resp)

html = body.get("html", "")
match = re.search(r'<pre id="probe">(.*?)</pre>', html)
if not match:
    print("未能从页面中提取指纹探针结果", file=sys.stderr)
    sys.exit(1)

probe = json.loads(match.group(1))
print(json.dumps(probe, ensure_ascii=False, indent=2))
PY
}

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Crawl4AI 测试脚本                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""
echo "服务地址：$CRAWL4AI_URL"
echo "操作：$ACTION"
echo "目标 URL: $TARGET_URL"
echo "请求画像：$REQUEST_PROFILE"
echo ""

# 1. 健康检查
echo -e "${YELLOW}Step 1: 健康检查${NC}"
HEALTH_STATUS=$(curl -s --max-time 10 "$CRAWL4AI_URL/health" 2>&1 || echo "")
if [ -z "$HEALTH_STATUS" ]; then
    echo -e "${RED}错误：服务无响应${NC}"
    exit 1
fi
echo "健康状态：$HEALTH_STATUS"
echo ""

if [ "$ACTION" = "fingerprint" ]; then
    echo -e "${YELLOW}Step 2: 默认浏览器指纹探针${NC}"
    probe_fingerprint
    echo ""
    echo -e "${GREEN}=== 测试完成 ===${NC}"
    exit 0
fi

# 2. 调用 API
echo -e "${YELLOW}Step 2: 抓取页面${NC}"

case "$ACTION" in
  md)
    PAYLOAD=$(create_crawl_payload "$ACTION" "$TARGET_URL" "$REQUEST_PROFILE")
    ;;
  html)
    PAYLOAD=$(create_crawl_payload "$ACTION" "$TARGET_URL" "$REQUEST_PROFILE")
    ;;
  screenshot)
    PAYLOAD=$(create_crawl_payload "$ACTION" "$TARGET_URL" "$REQUEST_PROFILE")
    ;;
  pdf)
    PAYLOAD=$(create_crawl_payload "$ACTION" "$TARGET_URL" "$REQUEST_PROFILE")
    ;;
  *)
    echo -e "${RED}未知操作：$ACTION${NC}"
    echo "支持的操作：fingerprint, md, html, screenshot, pdf"
    exit 1
    ;;
esac

RESPONSE=$(curl -s --max-time 120 -X POST "$CRAWL4AI_URL/crawl" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

# 3. 解析结果
echo -e "${GREEN}=== 结果 ===${NC}"
echo "$RESPONSE" | python3 -c "
import sys
import json

try:
    data = json.loads(sys.stdin.read())

    if not data.get('success'):
        print('抓取失败')
        for result in data.get('results', []):
            error_message = result.get('error_message')
            if error_message:
                print(f'错误详情：{error_message}')
        sys.exit(1)

    results = data.get('results', [])
    if not results:
        print('无结果')
        sys.exit(1)

    result = results[0]

    # 基本信息
    url = result.get('url', 'N/A')
    status = result.get('status_code', 'N/A')
    print(f'URL: {url}')
    print(f'状态码：{status}')

    # Markdown 内容
    markdown = result.get('markdown', {})
    raw_md = markdown.get('raw_markdown', '')
    if raw_md:
        print(f'\n--- Markdown 内容 ---')
        if len(raw_md) > 1000:
            print(raw_md[:1000] + '...')
            print(f'\n[总长度：{len(raw_md)} 字符]')
        else:
            print(raw_md)

    # HTML 内容
    html = result.get('html', '')
    if html and not raw_md:
        print(f'\n--- HTML 内容 ---')
        if len(html) > 1000:
            print(html[:1000] + '...')
            print(f'\n[总长度：{len(html)} 字符]')
        else:
            print(html)

    # 截图信息
    screenshot = result.get('screenshot')
    if screenshot:
        print(f'\n--- 截图 ---')
        print(f'格式：PNG')
        print(f'大小：{len(screenshot)} 字节')
        print(f'保存路径：/tmp/screenshot.png')

    # PDF 信息
    pdf = result.get('pdf')
    if pdf:
        print(f'\n--- PDF ---')
        print(f'格式：PDF')
        print(f'大小：{len(pdf)} 字节')
        print(f'保存路径：/tmp/page.pdf')

    # 链接信息
    links = result.get('links', {})
    external = links.get('external', [])
    if external:
        print(f'\n--- 外部链接 ({len(external)} 个) ---')
        for link in external[:5]:
            href = link.get('href', 'N/A')
            text = link.get('text', '')
            print(f'  - {text}: {href}')
        if len(external) > 5:
            print(f'  ... 还有 {len(external) - 5} 个')

    # 元数据
    metadata = result.get('metadata', {})
    if metadata:
        print(f'\n--- 元数据 ---')
        for key, value in metadata.items():
            if value:
                print(f'  {key}: {value}')

    # 性能信息
    print(f'\n--- 性能 ---')
    print(f'服务器处理时间：{data.get(\"server_processing_time_s\", \"N/A\")} 秒')
    print(f'内存增量：{data.get(\"server_memory_delta_mb\", \"N/A\")} MB')

except json.JSONDecodeError as e:
    print(f'JSON 解析错误：{e}')
    print(f'原始响应：{sys.stdin.read()[:500]}')
"

echo ""
echo -e "${GREEN}=== 测试完成 ===${NC}"
