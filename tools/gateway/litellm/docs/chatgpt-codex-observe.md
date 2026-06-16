# ChatGPT Codex 观测链路

通过 LiteLLM 本地网关接入 ChatGPT Subscription，专门用于 Codex Requests API 请求的观测与调试。

## 目标链路

```txt
Codex CLI/App 或 curl
  -> http://127.0.0.1:4000/v1/responses
  -> LiteLLM 本地网关（客户端使用 Virtual Keys private key 鉴权）
  -> LiteLLM chatgpt/ provider
  -> ChatGPT Subscription backend（OAuth device flow 登录）
```

## 严格转发模型

客户端只能看到标准 Codex 模型名。LiteLLM 后端逐项转发到同名 `chatgpt/...` 上游：

| 客户端 model 参数 | LiteLLM 上游 | 说明 |
|---|---|---|
| `gpt-5.5` | `chatgpt/gpt-5.5` | 推荐主模型，支持 Fast tier |
| `gpt-5.4` | `chatgpt/gpt-5.4` | 备选主模型，支持 Fast tier |
| `gpt-5.4-mini` | `chatgpt/gpt-5.4-mini` | 是否可用取决于 ChatGPT 账号侧支持 |
| `gpt-5.3-codex` | `chatgpt/gpt-5.3-codex` | 不受当前账号支持时会真实失败 |
| `gpt-5.3-codex-spark` | `chatgpt/gpt-5.3-codex-spark` | 可能因 Codex CLI 工具不兼容失败 |
| `gpt-5.2` | `chatgpt/gpt-5.2` | 是否可用取决于 ChatGPT 账号侧支持 |

`model_reasoning_effort` 和 Fast mode 是 Codex 客户端配置，不写入 LiteLLM 的 `litellm_params`。LiteLLM 只负责模型名路由和请求转发。

这些 deployment 都使用同一个 LiteLLM `chatgpt/` provider。OAuth token 存放在 `CHATGPT_TOKEN_DIR/auth.json`，因此只需要一次 device code 绑定；不同模型请求会复用同一份 ChatGPT 登录态，只改变转发给上游的 `model` 字符串。

## 首次启动

```bash
cd /Users/zhehan/Documents/tools/llm/feipi-agent-kit/tools/gateway/litellm

./scripts/litellm.sh print-chatgpt-env
./scripts/litellm.sh print-client-env
./scripts/litellm.sh restart-chatgpt
```

启动前需要在 ChatGPT 网页端的账号安全设置中启用 Codex 设备代码授权。LiteLLM 打开的 `https://auth.openai.com/codex/device` 使用 Codex device code 登录链路；如果账号侧没有开启，浏览器页面会提示启用设备代码授权，并且无法继续。

## 运行态验证

```bash
./scripts/litellm.sh check-chatgpt-runtime
```

预期结果：

```txt
✅ Codex CLI/App 可见模型名均为标准模型名：gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.3-codex-spark gpt-5.2
✅ 容器运行态已加载 Codex 严格转发配置
```

手工检查 `/v1/models`：

```bash
curl -s http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" | jq -r '.data[].id'
```

预期包含标准模型名，不应暴露内部逻辑模型名。

## Responses API 验证

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
  }'
```

再用 `gpt-5.4` 做同样验证，确认不是单模型固定上游。

## Codex CLI 配置

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

当前本地 Codex catalog 中，`gpt-5.5` 和 `gpt-5.4` 的 Fast tier id 是 `priority`。这些模型的 `model_reasoning_effort` 支持 `low`、`medium`、`high`、`xhigh`；可用 `codex exec -c model_reasoning_effort='"low"' ...` 做单次覆盖。

## 常见失败

| 现象 | 含义 | 处理 |
|---|---|---|
| `model is not supported` | 严格转发后的同名 `chatgpt/...` 上游不被账号支持 | 切换到账号支持的标准模型，如 `gpt-5.5` 或 `gpt-5.4` |
| `image_generation is not supported` | spark 上游不支持 Codex CLI 当前发送的工具 | 不在 Codex CLI/App 中选择 spark，或从 Virtual Key / 模型目录中移除 |
| `key not allowed to access model` | Virtual Key 未允许客户端选择的标准模型名 | 在 Dashboard -> Virtual Keys 中加入对应标准模型名 |
| `/v1/models` 缺少 Codex 模型 | 容器未加载新配置或 OAuth 初始化失败 | 执行 `check-chatgpt-network`、`restart-chatgpt`、`logs litellm` |
