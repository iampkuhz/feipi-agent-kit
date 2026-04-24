# Crawl4AI Service

> **定位**：Web 内容抓取和提取服务
> **服务地址**：http://localhost:11235

---

## 抗拦截配置结论

当前仓库这套 `crawl4ai:0.8.6`，想降低被反爬虫拦截的概率，优先级建议这样排：

1. **先把服务端默认 `BrowserConfig` 调稳**
   - 这会直接影响 `md`、`html`、`screenshot`、`pdf`、`execute_js` 这些 MCP 工具。
   - 本仓库现在默认挂载 [`config/config.yml`](./config/config.yml)，启用了更稳妥的桌面指纹策略：
     - `enable_stealth: true`
     - `user_agent_mode: random`
     - 固定较真实的桌面 viewport
     - `Accept-Language` 与浏览器语言保持一致

补充：
- `config.yml` 里**不再显式固定** `llm.provider`。
- 对普通 crawl 能力来说，LLM 不是必需项。
- 只有你使用 `/llm/*` 或 `md?f=llm` 时，才需要额外提供 `LLM_PROVIDER` / `LLM_API_KEY`。

2. **敏感站点一定要在调用侧显式传 `crawler_config`**
   - 尤其是 `simulate_user`、`override_navigator`、`magic`、`wait_until`、`wait_for`、`proxy_config` 这些参数。
   - 仅靠服务端默认值不够，因为 `0.8.6` 的服务实现里，`config.yml` 的 `crawler.base_config` 只会覆盖 `None` / `""`，对很多默认值已经是 `False` / 数字的字段并不能真正兜底。

3. **有代理就优先做站点级代理和会话隔离**
   - 比如不同目标域名使用不同 `proxy_config`、`proxy_session_id`、`session_id`。
   - 同一个登录态或挑战态页面，尽量复用同一个会话，不要每次都像“全新浏览器”。
   - `0.8.6` 官方镜像里我已实际验证：直接开启 `use_persistent_context` 会因缺少 Playwright `headless_shell` 而启动失败，所以当前仓库默认不启用它。

## 快速开始

### 前置条件

```bash
# 使用 Docker（推荐）
docker pull unclecode/crawl4ai:latest
```

### 运行服务

```bash
# 进入服务目录
cd tools/crawl/crawl4ai

# 复制环境变量文件
cp ../env/.env.example ../env/.env

# 启动服务
podman compose -f compose/docker-compose.yml up -d
# 或 docker compose up -d
```

说明：

- `compose/docker-compose.yml` 默认项目名仍是 `crawl4ai`，默认容器名仍是 `crawl4ai`，默认宿主机端口仍是 `11235`。
- 该 compose 会自动挂载：
  - `config/config.yml` → `/app/config.yml`

如果需要通过宿主机代理访问外网，请在 `env/.env` 中同时设置 `HTTP_PROXY`、`HTTPS_PROXY` 以及有效的 `NO_PROXY` / `no_proxy`。至少应包含 `127.0.0.1,localhost,0.0.0.0,::1,host.containers.internal`；否则 Crawl4AI 的 MCP handler 在容器内部回调 `/md`、`/crawl` 等本地接口时，可能会误走代理并返回 `502 Bad Gateway`，即使 GUI 页面仍能正常使用。

### 验证服务

```bash
# 健康检查
curl http://localhost:11235/health

# 查看默认浏览器指纹
./scripts/test_crawl4ai_mcp.sh fingerprint

# 测试抓取功能
curl -X POST http://localhost:11235/crawl \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com"]}' | jq .

# 使用测试脚本（推荐）
cd scripts
chmod +x test_crawl4ai_mcp.sh
./test_crawl4ai_mcp.sh fingerprint
./test_crawl4ai_mcp.sh md https://example.com
./test_crawl4ai_mcp.sh html https://example.com
./test_crawl4ai_mcp.sh screenshot https://example.com

# 用调用侧 anti-bot 画像测试敏感站点
CRAWL4AI_REQUEST_PROFILE=anti-bot ./test_crawl4ai_mcp.sh screenshot https://bot.sannysoft.com
```

---

## 测试脚本

Crawl4AI 提供了一套测试脚本，方便快速验证服务功能。

### 用法

```bash
cd scripts
chmod +x test_crawl4ai_mcp.sh

# 用法：./test_crawl4ai_mcp.sh [操作] [URL]

# 查看服务端默认浏览器指纹
./test_crawl4ai_mcp.sh fingerprint

# 提取 Markdown
./test_crawl4ai_mcp.sh md https://example.com

# 提取 HTML
./test_crawl4ai_mcp.sh html https://example.com

# 截取截图
./test_crawl4ai_mcp.sh screenshot https://example.com

# 生成 PDF
./test_crawl4ai_mcp.sh pdf https://example.com

# 用显式 anti-bot 请求画像测试
CRAWL4AI_REQUEST_PROFILE=anti-bot ./test_crawl4ai_mcp.sh md https://example.com
```

### 输出示例

```
╔════════════════════════════════════════╗
║     Crawl4AI 测试脚本                  ║
╚════════════════════════════════════════╝

服务地址：http://localhost:11235
操作：md
目标 URL: https://example.com

Step 1: 健康检查
健康状态：{"status":"ok","version":"0.8.6"}

Step 2: 默认浏览器指纹探针
{
  "webdriver": false,
  "languages": [
    "en-US"
  ],
  "plugins": 5,
  "platform": "Linux x86_64",
  "userAgent": "Mozilla/5.0 (...)"
}
```

```
Step 2: 抓取页面
=== 结果 ===
URL: https://example.com
状态码：200

--- Markdown 内容 ---
# Example Domain
This domain is for use in documentation examples...

--- 外部链接 (1 个) ---
  - Learn more: https://iana.org/domains/example

--- 性能 ---
服务器处理时间：0.38 秒
```

---

## 旁路验证建议

如果你已经有一个 `crawl4ai` 容器在跑，不要直接重建它。推荐这样做：

```bash
cd tools/crawl/crawl4ai

podman run -d \
  --name crawl4ai-verify \
  -p 12235:11235 \
  --env-file env/.env \
  -e NO_PROXY=127.0.0.1,localhost,0.0.0.0,::1,host.containers.internal \
  -e no_proxy=127.0.0.1,localhost,0.0.0.0,::1,host.containers.internal \
  -v /dev/shm:/dev/shm \
  -v "$(pwd)/config/config.yml:/app/config.yml:ro" \
  docker.io/unclecode/crawl4ai:0.8.6

CRAWL4AI_URL=http://localhost:12235 ./scripts/test_crawl4ai_mcp.sh fingerprint
CRAWL4AI_URL=http://localhost:12235 ./scripts/test_crawl4ai_mcp.sh md https://example.com
CRAWL4AI_URL=http://localhost:12235 CRAWL4AI_REQUEST_PROFILE=anti-bot \
  ./scripts/test_crawl4ai_mcp.sh screenshot https://bot.sannysoft.com
```

验证结束后，单独下掉验证容器即可：

```bash
podman rm -f crawl4ai-verify
```

仓库默认配置始终保留 `crawl4ai` / `11235`，你可以后续自行择机部署主容器。

---

## 在其他仓库中调用时的注意事项

### 1. 先区分“服务端默认值”和“调用侧显式参数”

| 场景 | 推荐方式 |
|------|----------|
| 普通网页转 Markdown | 直接用 `md` |
| 对反爬敏感、需要等待、代理、会话、滚动 | 用 `crawl`，显式传 `browser_config` + `crawler_config` |
| 需要登录态/多步交互 | 用 `crawl` + `session_id` / `storage_state` / `cookies` |
| 需要点按钮、跑前端脚本 | 用 `execute_js` 或 `crawl` + `js_code` |

关键点：

- `md` / `html` / `screenshot` / `pdf` / `execute_js` 这些 MCP 工具**不暴露** `browser_config` / `crawler_config` 入参。
- 所以它们更依赖服务端默认 `BrowserConfig`。
- 只要站点稍微敏感，就应该改用 `crawl` 工具。

### 2. 建议的 `crawl` anti-bot 请求模板

```json
{
  "urls": ["https://target.example"],
  "browser_config": {
    "type": "BrowserConfig",
    "params": {
      "headless": true,
      "enable_stealth": true,
      "viewport_width": 1440,
      "viewport_height": 900,
      "user_agent_mode": "random",
      "user_agent_generator_config": {
        "browsers": ["Chrome"],
        "os": ["Linux"],
        "platforms": ["desktop"],
        "min_version": 120.0
      },
      "headers": {
        "Accept-Language": "en-US,en;q=0.9"
      }
    }
  },
  "crawler_config": {
    "type": "CrawlerRunConfig",
    "params": {
      "cache_mode": "bypass",
      "wait_until": "networkidle",
      "page_timeout": 90000,
      "wait_for_images": true,
      "delay_before_return_html": 1.0,
      "simulate_user": true,
      "override_navigator": true,
      "magic": true,
      "remove_overlay_elements": true
    }
  }
}
```

### 3. 不要把多域名大批量混在一个请求里

- 一个站点一个策略。
- 同域名、多页面、同登录态，才适合共享 `session_id` / proxy session。
- 不同域名混跑，最容易把 cookies、会话、指纹和重试节奏搞乱。
- 如果是同站点多步会话，优先传固定 `user_agent`；`user_agent_mode=random` 更适合无状态抓取。

### 4. 有验证码或挑战页时，不要只会“重试”

更有效的顺序通常是：

1. 切到 `crawl`
2. 显式传 anti-bot `browser_config` / `crawler_config`
3. 补 `wait_for` / `js_code`
4. 需要时切代理或单独会话
5. 最后再考虑重试次数和并发

### 5. 代理注意事项

- 优先使用 `proxy_config`，不要继续依赖旧的 `proxy` 字段。
- 如果代理提供 sticky session，建议和目标站点会话绑定。
- 容器环境变量里的 `HTTP_PROXY` / `HTTPS_PROXY` 更适合“全局出站代理”；站点级策略仍建议写在请求体里。

## MCP 服务配置

Crawl4AI 自带 MCP (Model Context Protocol) 服务，可直接在 Claude Code 中使用。

### 可用工具

| 工具 | 描述 |
|------|------|
| `md` | 将网页转换为 Markdown 格式 |
| `html` | 抓取并清理 HTML 内容 |
| `screenshot` | 截取网页截图（PNG） |
| `pdf` | 生成网页 PDF 文档 |
| `execute_js` | 执行 JavaScript 脚本 |
| `crawl` | 批量抓取多个 URL |
| `ask` | 查询 Crawl4AI 相关文档 |

### 配置方法

在项目目录的 `.mcp.json` 中添加：

```json
{
  "mcpServers": {
    "crawl4ai": {
      "type": "sse",
      "url": "http://localhost:11235/mcp/sse"
    }
  }
}
```

### 使用示例

在 Claude Code 中直接使用：

```
/md https://example.com
```

```
/screenshot https://example.com --output_path ./screenshot.png
```

```
/crawl --urls ["https://example.com", "https://example.org"]
```

---

## 目录结构

```
tools/crawl/crawl4ai/
├── README.md               # 本文件
├── config/
│   └── config.yml          # 服务端默认配置（挂载到 /app/config.yml）
├── compose/                # Docker Compose 配置
│   └── docker-compose.yml
├── scripts/                # 测试脚本
│   ├── crawl4ai.sh         # 服务管理脚本（占位）
│   └── test_crawl4ai_mcp.sh  # 测试脚本（支持 fingerprint/md/html/screenshot/pdf）
└── env/                    # 环境变量
    └── .env.example
```

---

## 与 searxng-mcp 的协同

| 服务 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `searxng-mcp` | **搜索** - 发现相关 URL | 搜索关键词 | URL 列表 + 摘要 |
| `crawl4ai` (MCP) | **提取** - 抓取页面内容 | 具体 URL | Markdown/HTML/截图等 |

**协同使用示例：**

```
1. 使用 searxng-mcp 搜索 "Python 异步编程教程"
   → 返回 10 个相关 URL

2. 选择最有价值的 URL

3. 使用 crawl4ai MCP 工具提取内容
   /md https://example.com/tutorial
   → 返回清理后的 Markdown 内容
```

---

## 参考

- [Crawl4AI GitHub](https://github.com/unclecode/crawl4ai)
- [Crawl4AI 官方文档](https://docs.crawl4ai.com/)
- `tools/search/searxng/` - 搜索引擎参考
- `tools/search/searxng-mcp/` - MCP 服务参考
