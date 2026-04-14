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
```

注意：`litellm_settings:` 不能只写键名和注释、不写任何子项。那样在 YAML 里会被解析为 `null`，LiteLLM 1.81.x 的 Playground/UI 配置读取流程会报 `'NoneType' object has no attribute 'get'`。

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

如果 Playground 或 `/v1/chat/completions` 返回 `500 'NoneType' object has no attribute 'get'`，优先检查 [config/config.yaml](/Users/zhehan/Documents/tools/llm/skills/agent-skills/tools/gateway/litellm/config/config.yaml) 里的 `litellm_settings` 是否被写成了空 YAML 节点。

---

## 修改配置

1. 编辑 `config/config.yaml`
2. 重启服务：`./scripts/litellm.sh restart`
