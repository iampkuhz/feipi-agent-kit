# SearXNG 私有搜索引擎

> **定位**：私有化、无追踪的元搜索引擎
> **特点**：多引擎聚合、隐私保护、可自托管

---

## 目录结构

```
tools/search/searxng/
├── README.md           # 本文件
├── settings/
│   ├── settings.yml    # SearXNG 主配置
│   └── limiter.toml    # 限流器配置
├── compose/
│   └── docker-compose.yml
├── env/
│   └── .env.example    # 环境变量模板
└── scripts/
    └── searxng.sh      # 启动/停止脚本
```

---

## 快速开始

### 1. 启动服务

```bash
./workbench install services
./workbench service searxng up
```

在仓库根目录运行，服务默认只监听 `127.0.0.1:8873`。Compose 项目名固定为 `searxng`。

### 2. 验证启动

```bash
# 检查容器状态
./workbench service searxng status

# 检查健康端点
curl http://localhost:8873/healthz

# 浏览器访问
# http://localhost:8873
```

### 3. 测试搜索

```bash
curl -s "http://localhost:8873/search?q=hello+world&format=json" | jq .
```

---

## 配置说明

### settings.yml 结构

```yaml
use_default_settings: true

general:
  instance_name: "SearXNG"

server:
  secret_key: "searxng-secret-key"

outgoing:
  proxies:
    http: "http://host.containers.internal:7890"
    https: "http://host.containers.internal:7890"
  verify_ssl: true

engines:
  - name: google
    enabled: true
  - name: bing
    disabled: false
```

### 搜索引擎分类

| 类别 | 引擎 |
|------|------|
| 通用搜索 | google, bing, duckduckgo |
| 图片搜索 | google images |
| 知识库 | wikipedia |
| 代码 | github |

---

## 常用命令

```bash
# 启动
./scripts/searxng.sh up

# 停止
./scripts/searxng.sh down

# 按当前 Compose 配置重建并启动
./scripts/searxng.sh restart

# 查看日志
./scripts/searxng.sh logs

# 查看状态
./scripts/searxng.sh status
```

---

## API 使用

### 搜索 API

```bash
# JSON 格式
curl -s "http://localhost:8873/search?q=<query>&format=json"

# 指定类别
curl -s "http://localhost:8873/search?q=<query>&categories=general&format=json"

# 指定语言
curl -s "http://localhost:8873/search?q=<query>&language=zh-CN&format=json"
```

### 搜索参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 搜索关键词 | `hello+world` |
| `format` | 输出格式 | `json`, `html` |
| `categories` | 搜索类别 | `general`, `images`, `news` |
| `language` | 语言 | `zh-CN`, `en` |
| `pageno` | 页码 | `1`, `2` |

---

## 故障排查

```bash
# 1. 检查容器状态
podman compose -f compose/docker-compose.yml ps

# 2. 查看日志
podman compose -f compose/docker-compose.yml logs --tail 50

# 3. 验证健康端点
curl http://localhost:8873/healthz
```

---

## 修改配置

1. 编辑 `settings/settings.yml`
2. 重启服务：`./scripts/searxng.sh restart`
