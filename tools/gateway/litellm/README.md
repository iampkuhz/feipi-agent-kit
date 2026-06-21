# LiteLLM 本地 AI 网关

本地运行的 AI 模型代理，将多个上游模型统一成 OpenAI 兼容接口，供 Codex、Cursor、Continue 等客户端直接调用。

---

## 1. 快速开始

### 1.1 按需准备环境变量

```bash
cd tools/gateway/litellm
```

脚本只读取当前 shell 环境变量，不读取仓库根目录、LiteLLM 目录或 `env/` 目录下的 `.env` 文件。默认配置可直接启动；需要覆盖配置时，把变量放到你自己的 `~/.env`，并确保 zsh 启动时已经加载。

### 1.2 启动服务

```bash
./scripts/litellm.sh up
```

### 1.3 验证是否启动成功

```bash
# 健康检查
curl -s http://localhost:4000/health/readiness

# 查看可用模型列表（未配置 LITELLM_MASTER_KEY 时默认 key 为 sk-litellm-local-dev）
curl -s http://localhost:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-sk-litellm-local-dev}" | jq .
```

---

## 2. 使用 ChatGPT 订阅运行 Codex（重点）

Codex CLI 默认需要 OpenAI API Key，但如果你只有 **ChatGPT 订阅**（Plus / Pro / Team），可以通过本网关转发请求，用订阅额度运行 Codex。

### 2.1 工作原理

```
Codex CLI
  → http://localhost:4000/v1/responses   (本网关)
  → LiteLLM chatgpt/ provider
  → ChatGPT Subscription 后端（通过 OAuth 登录）
```

> **注意**：此链路需要 ChatGPT 订阅（Plus / Pro / Team），普通账号无法使用。

### 2.2 配置步骤

#### 2.2.1 在 `~/.env` 配置本地变量

Codex / Responses API 默认只走 ChatGPT 订阅，并按标准模型名严格转发：客户端请求 `gpt-5.5` 就调用 `chatgpt/gpt-5.5`，请求 `gpt-5.4` 就调用 `chatgpt/gpt-5.4`。因此 `~/.env` 不需要配置普通 OpenAI provider，也不需要配置 `LITELLM_UPSTREAM_CODEX_API_BASE`、`LITELLM_UPSTREAM_CODEX_API_KEY`、`LITELLM_CODEX_MODEL` 或 `LITELLM_UPSTREAM_CODEX_MODEL`。

本地建议只配置网关管理 key 和客户端 private key。这里使用 `export`，保证 zsh 加载后子进程和 compose 都能拿到。

```bash
# ~/.env
export LITELLM_MASTER_KEY=<运行 openssl rand -hex 16 生成>

# 客户端访问 LiteLLM 的 private key，来自 Dashboard -> Virtual Keys 手工创建。
export LITELLM_API_KEY_OPENAI=<key-for-openai 的 secret key>
export LITELLM_API_KEY_ANTHROPIC=<key-for-claude-code 的 secret key>
```

容器访问宿主机代理默认使用 `http://host.containers.internal:7890`。只有你的宿主机代理端口不是 `7890`，或需要禁用代理时，才额外配置：

```bash
export LITELLM_CONTAINER_HTTP_PROXY=http://host.containers.internal:7890
export LITELLM_CONTAINER_HTTPS_PROXY=http://host.containers.internal:7890
```

严格转发会让不受当前 ChatGPT 账号支持的模型真实失败。例如 `gpt-5.3-codex` 会转发到 `chatgpt/gpt-5.3-codex`，如果账号侧不支持该上游，Responses API 会直接返回 `model is not supported`；`gpt-5.3-codex-spark` 也可能因为 Codex CLI 发送的工具不被该上游支持而失败。

这些 Codex deployment 都使用 LiteLLM 的 `chatgpt/` provider。ChatGPT OAuth token 持久化在同一个 `CHATGPT_TOKEN_DIR/auth.json`，所以只需要完成一次 device code 绑定；不同标准模型只是转发时传入不同的上游 model 字符串。

`LITELLM_MASTER_KEY` 是网关管理 key，用于 Dashboard 登录、脚本诊断和管理接口。客户端不要直接使用 master key；你在 LiteLLM Dashboard 的 Virtual Keys 里手工创建的 private key，按客户端协议分别放到：

| 客户端类型 | 环境变量 | 典型模型 |
|------|------|------|
| OpenAI / Codex / OpenAI-compatible | `LITELLM_API_KEY_OPENAI` | `gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini`、`gpt-5.3-codex`、`gpt-5.3-codex-spark`、`gpt-5.2`、`litellm-code-openai` |
| Anthropic / Claude-code / Anthropic-compatible | `LITELLM_API_KEY_ANTHROPIC` | `litellm-code-anthropic` |

这两个客户端 private key 不参与容器启动。如果是首次搭建、还没有创建 Virtual Keys，可以先只配置 `LITELLM_MASTER_KEY`，启动 Dashboard 后创建 private key，再补进 `~/.env` 并打开新的 zsh。

在 Dashboard -> Virtual Keys 里创建 `key-for-openai` 时，允许模型至少包含你希望 Codex CLI/App 能选择的客户端模型名。推荐一次性允许：

```txt
gpt-5.5
gpt-5.4
gpt-5.4-mini
gpt-5.3-codex
gpt-5.3-codex-spark
gpt-5.2
litellm-code-openai
litellm-autocomplate-openai
```

这里的 `gpt-5.5`、`gpt-5.4` 等是 Codex 客户端看到和请求的模型名；LiteLLM 后端会把它们转发到同名 `chatgpt/...` 上游。如果 Virtual Key 没有允许 Codex 客户端实际选择的标准模型名，Codex CLI 会被 LiteLLM 拦截为 `key not allowed to access model`。

保存后打开一个新的 zsh，或用你现有的 zsh 启动加载机制重新加载 `~/.env`。脚本不会主动读取任何仓库内 `.env` 文件。

> 百炼和本地补全的逻辑模型名固定在 `config/config.yaml`。上游模型、base URL 和 API key 有默认值，也可以通过 `~/.env` 覆盖。

#### 2.2.2 检查 ChatGPT 订阅有效配置

```bash
./scripts/litellm.sh check-chatgpt-env
```

脚本会使用内置默认值检查当前有效配置。如果你在 `~/.env` 覆盖了不合法的上游模型，脚本会直接提示。

#### 2.2.3 在 ChatGPT 安全设置中启用 Codex 设备代码授权

LiteLLM 的 `chatgpt/` provider 会打开 `https://auth.openai.com/codex/device`，这属于 Codex device code 登录链路。你的 ChatGPT 账号需要先允许 Codex 使用设备代码授权。

操作步骤：

1. 打开 ChatGPT 网页端。
2. 进入账号的安全设置。
3. 找到 Codex 相关的设备代码授权开关，并启用它。
4. 如果你已经打开过 `auth.openai.com/codex/device` 且页面提示无法继续，启用后不要复用旧 code，回到终端重新生成新的 device code。

如果授权页显示“在 ChatGPT 安全设置中为 Codex 启用设备代码授权”，且“继续”按钮是灰色，就说明这一步还没有完成。

#### 2.2.4 重启网关，让容器读取当前 zsh 环境

```bash
./scripts/litellm.sh restart-chatgpt
```

只执行 `up` 不一定会重建已存在的容器，环境变量可能不会生效。修改 `~/.env` 后需要打开新的 zsh，再执行 `restart-chatgpt`。

启动脚本会自动创建 PostgreSQL 数据目录和 ChatGPT OAuth token 持久化目录。启用 `chatgpt/` provider 后，LiteLLM 可能会在启动阶段就触发 OAuth device flow；如果健康检查暂时没有 ready，先看日志并完成登录：

```bash
./scripts/litellm.sh logs litellm
```

日志中出现 device code 后，打开提示的 URL，使用 ChatGPT 订阅账号登录并输入 code。

#### 2.2.5 确认 Codex 标准模型名已被当前容器加载

先检查 compose、容器配置和 `/v1/models` 暴露状态是否一致：

```bash
./scripts/litellm.sh check-chatgpt-runtime
```

预期最后几行包含：

```txt
✅ Codex CLI/App 可见模型名均为标准模型名：gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.3-codex-spark gpt-5.2
✅ 容器运行态已加载 Codex 严格转发配置
```

再检查 LiteLLM 对外暴露的模型列表：

```bash
curl -s http://localhost:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" | jq -r '.data[].id'
```

预期输出中必须包含：

```txt
gpt-5.5
gpt-5.4
gpt-5.4-mini
gpt-5.3-codex
gpt-5.3-codex-spark
gpt-5.2
```

如果缺少上述任意标准模型名，说明当前容器还没有按当前 compose/config 重建，或 ChatGPT OAuth 初始化失败。先检查有效配置，再重建：

```bash
./scripts/litellm.sh check-chatgpt-env
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh check-chatgpt-runtime
```

如果 `/v1/models` 仍暴露非标准内部名，说明当前运行中的 LiteLLM 还没加载最新配置。先检查容器网络，再重启：

```bash
./scripts/litellm.sh check-chatgpt-network
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh logs litellm
```

#### 2.2.6 调用 Responses API，完成或验证 ChatGPT 授权

先确认 OpenAI/Codex 客户端 private key 已在当前 zsh 中生效：

```bash
./scripts/litellm.sh check-client-env openai
```

```bash
curl -s http://localhost:4000/v1/responses \
  -H "Authorization: Bearer ${LITELLM_API_KEY_OPENAI}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.5",
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": "只返回 hello"
          }
        ]
      }
    ],
    "stream": false
  }' | jq -r '
    if .error then
      .error.message
    else
      (.output_text // ([.output[]?.content[]?.text] | join("")))
    end
  '
```

预期输出：

```txt
hello
```

再用另一个标准模型名验证严格转发。这个请求会被 LiteLLM 转发到 `chatgpt/gpt-5.4`，因此 Dashboard -> Virtual Keys 中的 `key-for-openai` 必须允许 `gpt-5.4`：

```bash
curl -s http://localhost:4000/v1/responses \
  -H "Authorization: Bearer ${LITELLM_API_KEY_OPENAI}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.4",
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": "只返回 hello"
          }
        ]
      }
    ],
    "stream": false
  }' | jq -r '
    if .error then
      .error.message
    else
      (.output_text // ([.output[]?.content[]?.text] | join("")))
    end
  '
```

如果尚未登录，查看网关日志，会看到类似输出：

```
Please visit the following URL to authenticate:
https://auth.openai.com/activate?user_code=XXXX-XXXX
Device code: XXXX-XXXX
```

打开浏览器访问该 URL，用你的 ChatGPT 账号登录并输入 device code 完成授权。授权成功后，OAuth token 会自动保存到本地，后续请求无需重复登录。

如果浏览器页面提示需要在 ChatGPT 安全设置里为 Codex 启用设备代码授权，先完成 `2.2.3`，然后重新执行 `./scripts/litellm.sh restart-chatgpt` 获取新的 device code。

#### 2.2.7 为什么 LiteLLM Playground 看不到 ChatGPT 候选

`http://localhost:4000/ui/?login=success&page=llm-playground` 是 LiteLLM 的聊天 Playground，主要面向 chat/completions 类模型。Codex 标准模型在 `config/config.yaml` 中声明为：

```yaml
model_info:
  mode: responses
```

所以它们可能不会出现在聊天 Playground 的模型下拉里。这个现象不代表 ChatGPT 订阅链路失败。

验证 ChatGPT 订阅链路是否可用，以这三个结果为准：

1. `./scripts/litellm.sh check-chatgpt-runtime` 显示 Codex 严格转发配置已加载。
2. `/v1/models` 输出包含 `gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini`、`gpt-5.3-codex`、`gpt-5.3-codex-spark`、`gpt-5.2`，且不包含内部逻辑模型名。
3. `2.2.6` 的 `/v1/responses` 调用返回 `hello`。

另外，Playground 不会展示 `chatgpt/gpt-5.3-codex-spark`、`chatgpt/gpt-5.5` 这类上游候选值。LiteLLM 对客户端暴露的是标准模型名，例如 `gpt-5.5`、`gpt-5.4`、`gpt-5.3-codex`；具体上游在 `config/config.yaml` 中逐项写成同名 `chatgpt/...`。

#### 2.2.8 配置 Codex CLI 使用本地网关

先生成一份 Codex 本地模型候选元数据，避免 Codex CLI/App 去请求 LiteLLM 的 OpenAI 兼容 `/v1/models` 并把它误当成 Codex 模型目录解析：

```bash
./scripts/litellm.sh write-codex-model-catalog
```

再查看推荐配置：

```bash
./scripts/litellm.sh print-codex-config
```

在 `~/.codex/config.toml` 中修改（或新增）以下配置。注意：`model`、`model_provider`、`model_catalog_json` 这些根级配置必须写在 `[model_providers.litellm-local]` 表之前。

```toml
model = "gpt-5.5"
model_provider = "litellm-local"
model_reasoning_effort = "xhigh"
service_tier = "priority"
model_catalog_json = "/Users/zhehan/.codex/model-catalogs/litellm-local.json"

[features]
fast_mode = true

[model_providers.litellm-local]
name = "LiteLLM Local"
base_url = "http://localhost:4000/v1"
env_key = "LITELLM_API_KEY_OPENAI"
wire_api = "responses"
```

同时设置客户端 private key 环境变量（建议放入 `~/.env`，并由 zsh 启动时自动加载）：

```bash
export LITELLM_API_KEY_OPENAI=<LiteLLM Virtual Keys 中 key-for-openai 的 secret key>
```

`model_reasoning_effort` 是 Codex 客户端的 thinking effort 配置；当前本地 Codex catalog 中这些模型支持 `low`、`medium`、`high`、`xhigh`。Fast mode 也属于 Codex 客户端配置；当前本地 Codex catalog 中 `gpt-5.5` / `gpt-5.4` 的 Fast tier id 是 `priority`，所以推荐用 `service_tier = "priority"` 并开启 `[features].fast_mode = true`。不要把这些配置写进 LiteLLM 的 `litellm_params`，否则会覆盖客户端每次请求里的选择。

之后运行 Codex CLI 即可通过 LiteLLM 网关调用 ChatGPT 订阅链路。这份 `~/.codex/config.toml` 是 Codex 用户级配置；CLI 会读取它，Codex App / IDE 也使用同一套配置层，但 GUI App 是否能拿到 `LITELLM_API_KEY_OPENAI` 取决于 App 进程启动时的环境变量。后续如果要让 Codex App 也稳定走这条链路，重点是确保 Codex App 进程也能看到同名环境变量，并在改完配置后重启 App 或开新线程。

#### 2.2.9 控制 Codex CLI/App 的模型候选

这里有三层名单，不要混在一起：

1. `~/.codex/model-catalogs/litellm-local.json` 控制 Codex CLI/App 本地候选列表和模型元数据。用 `./scripts/litellm.sh write-codex-model-catalog` 生成。当前推荐候选是 `gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini`、`gpt-5.3-codex`、`gpt-5.2`。
2. LiteLLM Dashboard -> Virtual Keys 控制某个 private key 能访问哪些客户端模型名。`key-for-openai` 至少要允许你希望 Codex 能选择的候选模型名，否则会报 `key not allowed to access model`。
3. `config/config.yaml` 控制这些客户端模型名实际路由到哪里。当前逐项严格转发到同名 `chatgpt/...` 上游，不再使用内部逻辑模型名或 alias。

也就是说，Codex CLI 里选择 `gpt-5.5`，LiteLLM 对外收到的是 `gpt-5.5`，后端调用的是 `chatgpt/gpt-5.5`；选择 `gpt-5.4`，后端调用的是 `chatgpt/gpt-5.4`。如果你以后只想让 Codex App/CLI 显示更少候选，同时改两处：本地 `model_catalog_json` 和 Virtual Key 允许模型；`config/config.yaml` 可以保留更多标准模型 deployment。

### 2.3 Token 过期处理

如果 ChatGPT 登录态失效，网关会自动重新触发 OAuth 授权流程。若出现异常，可手动清除 token 后重启：

```bash
rm /Users/zhehan/Documents/service-data/litellm/chatgpt-tokens/auth.json
./scripts/litellm.sh restart
```

---

## 3. 环境变量说明

### 3.1 常用覆盖变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `LITELLM_MASTER_KEY` | 网关管理密钥，用于 Dashboard、脚本诊断和管理接口 | `sk-litellm-local-dev` |
| `LITELLM_API_KEY_OPENAI` | OpenAI / Codex / OpenAI-compatible 客户端访问 LiteLLM 的 private key | 无 |
| `LITELLM_API_KEY_ANTHROPIC` | Anthropic / Claude-code / Anthropic-compatible 客户端访问 LiteLLM 的 private key | 无 |
| `LITELLM_UPSTREAM_CODE_MODEL_OPENAI_NAME` | `litellm-code-openai` 的百炼 OpenAI 兼容上游模型 | `openai/qwen-plus` |
| `LITELLM_UPSTREAM_CODE_MODEL_OPENAI_BASE` | `litellm-code-openai` 的百炼 OpenAI 兼容 base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LITELLM_UPSTREAM_CODE_MODEL_OPENAI_KEY` | `litellm-code-openai` 的百炼 API key；脚本会优先复用 `BAILIAN_CODING_PLAN_API_KEY` 或 `BAILIAN_API_KEY` | `dummy-key` |
| `LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_NAME` | `litellm-code-anthropic` 的百炼 Anthropic 兼容上游模型 | `anthropic/qwen-plus` |
| `LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_BASE` | `litellm-code-anthropic` 的百炼 Anthropic 兼容 base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LITELLM_UPSTREAM_CODE_MODEL_ANTHROPIC_KEY` | `litellm-code-anthropic` 的百炼 API key；脚本会优先复用 `BAILIAN_CODING_PLAN_API_KEY` 或 `BAILIAN_API_KEY` | `dummy-key` |
| `LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_NAME` | 本地补全 OpenAI 兼容上游模型 | `openai/qwen-turbo` |
| `LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_BASE` | 本地补全 OpenAI 兼容 base URL | `http://host.containers.internal:11434/v1` |
| `LITELLM_UPSTREAM_AUTOCOMPLETE_MODEL_OPENAI_KEY` | 本地补全 OpenAI 兼容 API key | `dummy-key` |
| `LITELLM_CONTAINER_HTTP_PROXY` / `LITELLM_CONTAINER_HTTPS_PROXY` | 容器访问外网的代理地址 | `http://host.containers.internal:7890` |
| `POSTGRES_PASSWORD` | 沿用旧 PostgreSQL 数据库密码时才需要配置 | `litellm_password` |

### 3.2 固定默认路径和默认 deployment

| 项目 | 默认值 |
|------|--------|
| PostgreSQL 数据目录 | `/Users/zhehan/Documents/service-data/postgres` |
| ChatGPT OAuth token 目录 | `/Users/zhehan/Documents/service-data/litellm/chatgpt-tokens` |
| LiteLLM 镜像 | `docker.litellm.ai/berriai/litellm:v1.89.0` |
| OpenAI 兼容逻辑模型 | `litellm-code-openai` |
| Anthropic 兼容逻辑模型 | `litellm-code-anthropic` |
| 本地补全逻辑模型 | `litellm-autocomplate-openai` |

这些逻辑模型名在 `compose/docker-compose.yml` 和 `config/config.yaml` 中维护，不要求写入 `~/.env`。如果只是切换百炼上游模型、base URL 或 API key，优先使用上面的环境变量覆盖，不需要修改 `config.yaml`。

---

## 4. 常用命令

```bash
# 打印 ChatGPT 订阅所需的 ~/.env 配置模板
./scripts/litellm.sh print-chatgpt-env

# 打印客户端 private key 的 ~/.env 配置模板
./scripts/litellm.sh print-client-env

# 检查当前 shell 是否已有 ChatGPT 订阅所需变量
./scripts/litellm.sh check-chatgpt-env

# 检查当前 shell 是否已有客户端 private key
./scripts/litellm.sh check-client-env openai
./scripts/litellm.sh check-client-env anthropic

# 检查当前容器是否真的加载了 ChatGPT 订阅变量
./scripts/litellm.sh check-chatgpt-runtime

# 检查容器内是否能访问 ChatGPT OAuth 地址
./scripts/litellm.sh check-chatgpt-network

# 诊断 Dashboard 是否在使用已失效的浏览器 token
./scripts/litellm.sh check-dashboard-auth

# 启动
./scripts/litellm.sh up

# 停止
./scripts/litellm.sh down

# 重启（修改配置后使用）
./scripts/litellm.sh restart

# 按 ChatGPT 订阅模式检查环境变量并重启
./scripts/litellm.sh restart-chatgpt

# 查看日志
./scripts/litellm.sh logs

# 查看状态
./scripts/litellm.sh status
```

---

## 5. 客户端接入示例

### 5.1 Python（OpenAI SDK）

```python
from openai import OpenAI
import os

client = OpenAI(
    base_url="http://127.0.0.1:4000/v1",
    api_key=os.environ["LITELLM_API_KEY_OPENAI"]
)

response = client.chat.completions.create(
    model="litellm-code-openai",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

### 5.2 curl

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer ${LITELLM_API_KEY_OPENAI}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "litellm-code-openai",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }' | jq .
```

### 5.3 Anthropic-compatible 客户端

Anthropic 协议客户端使用 `LITELLM_API_KEY_ANTHROPIC`。示例：

```bash
curl -s http://localhost:4000/v1/messages \
  -H "x-api-key: ${LITELLM_API_KEY_ANTHROPIC}" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "litellm-code-anthropic",
    "max_tokens": 256,
    "messages": [{"role": "user", "content": "你好"}]
  }' | jq .
```

---

## 6. 故障排查

### 6.1 容器无法启动，日志报 `Can't reach database server`

等待几秒后重试，PostgreSQL 容器需要先完成初始化。若持续报错，运行 `./scripts/litellm.sh recreate` 重建容器。

### 6.2 返回 500 错误，日志含 `'NoneType' object has no attribute 'get'`

检查 `config/config.yaml` 中 `litellm_settings:` 不能为空，至少要保留 `success_callback: []`。

### 6.3 容器被 OOM Killed（状态码 137）

运行 `podman stats --no-stream` 查看内存占用。当前限制为 2GB，若仍不够，可在 `compose/docker-compose.yml` 中调大 `mem_limit`。

### 6.4 Codex 转发返回 403 或 HTML 页面

通常是网络问题。检查当前 zsh 环境中的 `LITELLM_CONTAINER_HTTP_PROXY` / `LITELLM_CONTAINER_HTTPS_PROXY` 是否设置正确，且宿主机代理服务正在运行。

### 6.5 Responses API 报标准 Codex 模型不存在

先运行 `/v1/models` 确认模型列表；如果缺少 `gpt-5.5`、`gpt-5.4` 等 Codex 候选，说明容器还没有按当前配置重建，或 ChatGPT OAuth 初始化失败。执行：

```bash
./scripts/litellm.sh check-chatgpt-env
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh check-chatgpt-runtime
```

如果 `/v1/models` 只返回 `litellm-code-openai`、`litellm-code-anthropic`、`litellm-autocomplate-openai` 这 3 个模型，说明当前运行中的 LiteLLM 进程没有加载 Codex/Responses 那条配置。直接执行：

```bash
./scripts/litellm.sh check-chatgpt-network
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh check-chatgpt-runtime
```

如果模型列表仍缺少标准 Codex 模型，看日志中是否有下面这类错误：

```txt
Error creating deployment ... chatgpt/... Polling failed ... timed out
Initialized Model List ['litellm-code-openai', ...]
```

这表示 LiteLLM 启动时访问 ChatGPT OAuth 地址超时，于是跳过了 Codex Responses deployment。先确保宿主机代理可用，再执行：

```bash
./scripts/litellm.sh check-chatgpt-network
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh logs litellm
```

### 6.6 Responses API 报 `gpt-5.3-codex model is not supported`

症状：

```txt
The 'gpt-5.3-codex' model is not supported when using Codex with a ChatGPT account.
```

这表示 ChatGPT 登录态已经成功，但严格转发后的同名上游 `chatgpt/gpt-5.3-codex` 不被当前账号支持。切换 Codex CLI/App 到 `gpt-5.5` 或 `gpt-5.4`，或者在 `config/config.yaml` 中移除不希望客户端选择的标准模型 deployment。

### 6.7 Codex CLI 报 `key not allowed` 或 `image_generation is not supported`

症状 1：

```txt
key not allowed to access model ... Tried to access gpt-5.5
```

这表示 Codex CLI/App 发出了 `gpt-5.5`、`gpt-5.4` 或 `gpt-5.3-codex` 这类原生模型名，但当前 LiteLLM 配置或 Virtual Key 没有允许它。按顺序检查：

```bash
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh check-chatgpt-runtime
```

`check-chatgpt-runtime` 需要显示 `gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.3-codex-spark gpt-5.2` 均已作为标准模型名暴露。如果配置已经加载但仍然 403，到 Dashboard -> Virtual Keys 编辑当前 `LITELLM_API_KEY_OPENAI` 对应的 key，把 Codex 客户端会选择的模型名加入允许列表。

症状 2：

```txt
Tool 'image_generation' is not supported with gpt-5.3-codex-spark.
```

这表示严格转发已经进入上游调用阶段，但 `chatgpt/gpt-5.3-codex-spark` 不支持 Codex CLI 当前发送的工具。切换 Codex CLI/App 到 `gpt-5.5` 或 `gpt-5.4`，或者从 Virtual Key / 本地模型目录中移除不希望用户选择的 spark 模型。

### 6.8 ChatGPT 授权页提示需要启用 Codex 设备代码授权

症状：打开 `https://auth.openai.com/codex/device` 后，页面提示“在 ChatGPT 安全设置中为 Codex 启用设备代码授权”，并且“继续”按钮是灰色。

这不是 LiteLLM 配置错误，也不是代理错误。原因是 ChatGPT 账号还没有允许 Codex device code 登录。

处理步骤：

1. 回到 ChatGPT 网页端，进入账号安全设置。
2. 启用 Codex 的设备代码授权。
3. 回到终端，重新执行：

```bash
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh logs litellm
```

4. 使用日志中新生成的 device code 重新打开授权页。不要复用旧 code。

### 6.9 Dashboard 日志页报 `Invalid proxy server token passed`

症状：`http://localhost:4000/ui/?login=success&page=logs` 能打开，但 Request Logs 一直加载，浏览器控制台出现：

```txt
Authentication Error, Invalid proxy server token passed
Unable to find token in cache or LiteLLM_VerificationTokenTable
```

这不是 ChatGPT OAuth token 失效，而是浏览器里保存的 LiteLLM Dashboard 虚拟 key 已经不在当前数据库中。常见触发方式是重建 PostgreSQL 数据目录、换过 `LITELLM_MASTER_KEY`、或浏览器沿用了旧的 Dashboard 登录态。

先诊断：

```bash
./scripts/litellm.sh check-dashboard-auth

# 如果控制台里有 Key Hash，也可以带上 hash 检查是否存在于 DB
./scripts/litellm.sh check-dashboard-auth 5d75c9ad3a99f4644b5827c87b7324b3cc5c7346b459bfd2d8a667a81c6ca51f
```

修复方式：

1. 关闭 `http://localhost:4000/ui` 页面。
2. 重新打开 `http://localhost:4000/ui`，如果仍自动进入旧登录态，在该站点 DevTools Console 执行：

```js
localStorage.clear();
sessionStorage.clear();
["/", "/ui"].forEach((path) => {
  document.cookie.split(";").forEach((cookie) => {
    document.cookie = cookie
      .replace(/^ +/, "")
      .replace(/=.*/, `=;expires=${new Date(0).toUTCString()};path=${path}`);
  });
});
location.href = "/ui";
```

3. 用当前 `LITELLM_MASTER_KEY` 重新登录 Dashboard。
4. 如果刚改过 `LITELLM_MASTER_KEY`，先执行 `./scripts/litellm.sh restart`，再重新登录。

### 6.10 客户端调用报 `Invalid proxy server token passed`

如果 curl、Codex、Claude-code 等客户端调用时报：

```txt
Authentication Error, Invalid proxy server token passed
Unable to find token in cache or LiteLLM_VerificationTokenTable
```

这表示当前 `LITELLM_API_KEY_OPENAI` 或 `LITELLM_API_KEY_ANTHROPIC` 对应的 Virtual Key 不在当前 PostgreSQL 数据库里，和百炼或 ChatGPT 上游配置无关。常见原因是换过数据库目录、重建过数据、或 `~/.env` 里还保留着旧 key。

处理方式：

1. 用当前 `LITELLM_MASTER_KEY` 登录 Dashboard。
2. 在 Virtual Keys 重新创建对应 key。
3. 把新的 secret key 更新到 `~/.env` 的 `LITELLM_API_KEY_OPENAI` 或 `LITELLM_API_KEY_ANTHROPIC`。
4. 打开新的 zsh 后重试客户端调用。

### 6.11 `check-chatgpt-env` 报覆盖变量不合法

脚本不会读取仓库内 `.env` 文件。`LITELLM_CODEX_MODEL` 和 `LITELLM_UPSTREAM_CODEX_MODEL` 已不再参与 Codex 严格转发配置；如果当前 shell 仍设置了它们，`check-chatgpt-env` 会提示这些变量已被忽略。参考 `./scripts/litellm.sh print-chatgpt-env` 的输出修正后，打开一个新的 zsh 重试。

### 6.12 当前 shell 已设置变量，但 compose 仍像默认配置

脚本会传入 `--env-file /dev/null`，避免 compose 自动读取本地 `.env`。确认变量已经 export，而不是只在 shell 里赋值：

```bash
export LITELLM_MASTER_KEY=sk-...
printenv LITELLM_MASTER_KEY
```
