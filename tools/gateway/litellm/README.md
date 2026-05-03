# LiteLLM 轻量代理

> **定位**：本地 AI 模型网关，提供统一的 OpenAI 兼容接口
> **特点**：轻量、低内存（< 500MB）、单容器、本地可运行

---

## 目录结构

```
tools/gateway/litellm/
├── README.md           # 本文件
├── config/
│   └── config.yaml     # LiteLLM 主配置
├── compose/
│   └── docker-compose.yml
├── env/
│   └── .env.example    # 环境变量模板
└── scripts/
    └── litellm.sh      # 启动/停止脚本
```

---

## 快速开始

### 1. 准备环境变量

```bash
cp tools/gateway/litellm/env/.env.example tools/gateway/litellm/env/.env
```

编辑 `.env` 文件，填入真实值。

### 2. 启动服务

```bash
cd tools/gateway/litellm
./scripts/litellm.sh up
```

说明：`compose/docker-compose.yml` 已固定 Compose 项目名为 `litellm`，这样即使你人在 `compose/` 子目录下直接执行 `podman compose up -d`，也不会和仓库里其它同名 `compose/` 目录的服务混到一个项目里。

PostgreSQL 固定绑定到宿主机目录 `/Users/zhehan/Documents/service-data/postgres`，容器删除重建后只要这个目录不删，账号、密码和业务数据都会保留。

### 3. 验证启动

```bash
# 检查容器状态
podman compose -f compose/docker-compose.yml ps

# 检查就绪状态（无需鉴权）
curl -s http://localhost:4000/health/readiness

# 检查模型列表
curl -s http://localhost:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" | jq .
```

### 4. 测试对话

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -X POST \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "'"$LITELLM_CODE_MODEL_OPENAI"'",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }' | jq .
```

---

## 配置说明

### 环境变量

| 变量名 | 用途 | 是否必需 |
|--------|------|----------|
| `LITELLM_MASTER_KEY` | LiteLLM 访问密钥 | 必需 |
| `LITELLM_CODE_MODEL_OPENAI` | OpenAI 协议逻辑模型名 | 必需 |
| `LITELLM_UPSTREAM_CODE_MODEL_OPENAI_NAME` | 上游 OpenAI 模型 ID | 必需 |
| `LITELLM_UPSTREAM_CODE_MODEL_OPENAI_BASE` | 上游 OpenAI 端点 | 必需 |
| `LITELLM_UPSTREAM_CODE_MODEL_OPENAI_KEY` | 上游 OpenAI 密钥 | 必需 |
| `LITELLM_CODE_MODEL_ANTHROPIC` | Anthropic 协议逻辑模型名 | 必需 |
| `LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_NAME` | 上游 Anthropic 模型 ID | 必需 |
| `LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_BASE` | 上游 Anthropic 端点 | 必需 |
| `LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_KEY` | 上游 Anthropic 密钥 | 必需 |
| `LITELLM_AUTOCOMPLETE_MODEL_OPENAI` | 补全逻辑模型名 | 可选 |
| `LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_NAME` | 上游补全模型 ID | 可选 |
| `LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_BASE` | 上游补全端点 | 可选 |
| `LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_KEY` | 上游补全密钥 | 可选 |
| `SPEND_LOG_CLEANUP_BATCH_SIZE` | spend logs 清理任务每批处理行数，调小可降低内存峰值 | 可选 |
| `SPEND_LOG_RUN_LOOPS` | spend logs 清理任务单轮最多执行批次数，调小可降低单轮压力 | 可选 |

### config.yaml 结构

```yaml
model_list:
  - model_name: <逻辑模型名>
    litellm_params:
      model: <provider/model-id>
      api_base: <端点>
      api_key: <密钥>

litellm_settings:
  success_callback: []
  failure_callback: []
  default_team_settings: {}

general_settings:
  master_key: <访问密钥>
  store_prompts_in_spend_logs: true
  maximum_spend_logs_retention_period: "1d"
  maximum_spend_logs_retention_interval: "1d"
```

注意：`litellm_settings:` 不能只写键名和注释、不写任何子项。那样在 YAML 里会被解析为 `null`，LiteLLM 1.81.x 的 Playground/UI 配置读取流程会报 `'NoneType' object has no attribute 'get'`。

本地网关默认保存完整请求体和响应体到 spend logs，并将保留期限制为 1 天。`maximum_spend_logs_retention_period: "1d"` 控制保留窗口，`maximum_spend_logs_retention_interval: "1d"` 控制清理任务运行间隔。Podman VM 内存较小时，可通过 `SPEND_LOG_CLEANUP_BATCH_SIZE` 和 `SPEND_LOG_RUN_LOOPS` 降低清理任务的单轮内存峰值。

### PostgreSQL 数据持久化

当前配置使用宿主机绑定挂载，而不是 Podman 命名卷：

```yaml
volumes:
  - type: bind
    source: /Users/zhehan/Documents/service-data/postgres
    target: /var/lib/postgresql/data
```

LiteLLM 容器本身当前没有单独的业务数据卷，只有配置文件只读挂载：

```bash
../config/config.yaml:/app/config.yaml:ro
```

如果你后续想给 LiteLLM 额外挂载日志或导出目录，可以再单独加到 `/Users/zhehan/Documents/service-data/litellm`，但按当前配置并不是必需项。

---

## 常用命令

```bash
# 启动
./scripts/litellm.sh up

# 停止
./scripts/litellm.sh down

# 重启
./scripts/litellm.sh restart

# 查看日志
./scripts/litellm.sh logs

# 查看状态
./scripts/litellm.sh status
```

---

## 客户端接入

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:4000/v1",
    api_key="你的 LITELLM_MASTER_KEY"
)

response = client.chat.completions.create(
    model="qwen-openai",  # 对应 LITELLM_CODE_MODEL_OPENAI
    messages=[{"role": "user", "content": "Hello"}]
)
```

---

## 故障排查

```bash
# 1. 检查容器状态
podman compose -f compose/docker-compose.yml ps

# 2. 查看日志
podman compose -f compose/docker-compose.yml logs --tail 50 litellm

# 3. 验证就绪端点
curl -s http://localhost:4000/health/readiness
```

如果日志里出现 `P1001: Can't reach database server at litellm-db:5432`，优先检查 `compose/docker-compose.yml` 中 PostgreSQL 服务是否带有 `litellm-db` 的网络别名；Podman Compose 不能像部分 Docker 场景那样稳定依赖 `container_name` 做服务发现。

如果 Playground 或 `/v1/chat/completions` 返回 `500 'NoneType' object has no attribute 'get'`，优先检查 [config/config.yaml](/Users/zhehan/Documents/tools/llm/feipi-agent-kit/tools/gateway/litellm/config/config.yaml) 里的 `litellm_settings` 是否被写成了空 YAML 节点。

如果容器状态显示 `Exited (137)`，并且 `podman inspect litellm-proxy-podman` 中 `OOMKilled` 为 `true`，说明 LiteLLM 被 Podman VM 的内存压力杀掉。优先检查：

```bash
podman machine inspect
podman stats --no-stream
podman exec litellm-db-podman psql -U litellm -d litellm \
  -c "select relname, pg_size_pretty(pg_total_relation_size(relid)) from pg_catalog.pg_statio_user_tables order by pg_total_relation_size(relid) desc limit 10;"
```

当前 compose 已对 LiteLLM 设置 `mem_limit: 2048m`，并保留完整 prompt 持久化；通过 1 天 spend logs 保留期、较小清理批次、较小 DB 连接池和请求/响应体大小限制降低内存峰值。修改 compose 或镜像版本后，使用 `./scripts/litellm.sh restart`，脚本会重新创建 LiteLLM 容器以应用资源限制和镜像变更。

如果 `podman compose up -d` 一开始就打印 `no container with name or ID ... found`、`not all containers could be removed from pod ...`、`compose_default has associated containers with it` 这类报错，通常不是 LiteLLM 配置本身坏了，而是多个服务都曾从各自的 `compose/` 目录启动，默认项目名都变成了 `compose`。当前配置已固定项目名为 `litellm`；若本机还残留旧的 `compose` 项目，可先在对应目录执行一次 `podman compose down`，或手动清理旧的 `pod_compose` / `compose_default` 资源后再重启。

如果你删除的是容器，但保留了宿主机数据目录，数据库账号、密码和业务数据都会保留；如果把宿主机数据目录一并删掉，PostgreSQL 下次启动时就会重新初始化。

---

## 修改配置

1. 编辑 `config/config.yaml`
2. 重启服务：`./scripts/litellm.sh restart`
