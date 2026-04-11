# Crawl4AI Service

> **定位**：Web 内容抓取和提取服务
> **服务地址**：http://localhost:11235

---

## 快速开始

### 前置条件

```bash
# 使用 Docker（推荐）
docker pull unclecode/crawl4ai:latest
```

### 运行服务

```bash
# 进入 compose 目录
cd tools/crawl/crawl4ai/compose

# 复制环境变量文件
cp ../env/.env.example ../env/.env

# 启动服务
podman compose up -d
# 或 docker compose up -d
```

### 验证服务

```bash
# 健康检查
curl http://localhost:11235/health

# 测试抓取功能
curl -X POST http://localhost:11235/crawl \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com"]}' | jq .
```

---

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
├── README.md           # 本文件
├── config/             # Crawl4AI 配置
├── compose/            # Docker Compose 配置
├── scripts/            # 启动/停止脚本
└── env/                # 环境变量
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
