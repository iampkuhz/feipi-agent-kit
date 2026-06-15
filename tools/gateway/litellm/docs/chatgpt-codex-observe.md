# ChatGPT Codex 观测链路

通过 LiteLLM 本地网关接入 ChatGPT Subscription，专门用于 Codex 请求的观测与调试。

## 目标链路

```txt
Codex 或 curl
  -> http://127.0.0.1:4000/v1/responses
  -> LiteLLM 本地网关（客户端使用 Virtual Keys private key 鉴权，管理接口使用 LITELLM_MASTER_KEY）
  -> LiteLLM chatgpt/ provider
  -> ChatGPT Subscription backend（OAuth device flow 登录）
```

模型映射：

| 客户端 model 参数 | LiteLLM 上游 | 说明 |
|---|---|---|
| `gpt-5.5` | `chatgpt/gpt-5.5` | Codex CLI/App 默认模型名，通过 `model_group_alias` 映射到 `codex-chatgpt` |
| `gpt-5.4` / `gpt-5.4-mini` / `gpt-5.3-codex` / `gpt-5.2` | `chatgpt/gpt-5.5` | Codex CLI/App 兼容候选名，同样映射到 `codex-chatgpt` |
| `codex-chatgpt` | `chatgpt/gpt-5.5` | LiteLLM 内部逻辑模型名，可用于 curl 直连验证 |

## 为什么不使用 Codex 的 `requires_openai_auth = true`

Codex 原生配置（`~/.codex/config.toml`）中 `requires_openai_auth = true` 意味着：

1. Codex 直接读取 `~/.codex/auth.json` 或系统 keychain 中的 OpenAI API Key。
2. 用户没有 OpenAI API Key，只有 ChatGPT 订阅登录态。
3. 直接修改 Codex 配置可能破坏其正常工作流程。

因此本方案在 LiteLLM 网关层独立走一遍 ChatGPT OAuth device flow，与 Codex 自身的登录态完全隔离。

## 为什么 LiteLLM 需要自己走 ChatGPT OAuth device flow

LiteLLM 的 `chatgpt/` provider 使用自己的 OAuth 实现：

1. 首次调用时，LiteLLM 在日志中输出 device code 和 verification URL。
2. 用户在浏览器中打开 verification URL，登录 ChatGPT 账号，输入 device code。
3. LiteLLM 将获取到的 OAuth token 持久化到 `CHATGPT_TOKEN_DIR` 指定的目录。
4. 后续请求复用已保存的 token，无需重复登录。

这个过程与 Codex 自己的 ChatGPT 登录态（`~/.codex/auth.json`）完全独立，互不影响。

## 首次启动步骤

```bash
cd /Users/zhehan/Documents/tools/llm/feipi-agent-kit/tools/gateway/litellm

# 查看需要放入 ~/.env 的 ChatGPT 订阅变量
./scripts/litellm.sh print-chatgpt-env

# 查看客户端 private key 变量
./scripts/litellm.sh print-client-env
```

脚本不会读取仓库内 `.env` 文件。Codex / Responses API 默认已经只走 ChatGPT 订阅，上游默认是 `chatgpt/gpt-5.5`。通常只需要配置：

1. `LITELLM_MASTER_KEY`

客户端访问 LiteLLM 时不要直接使用 `LITELLM_MASTER_KEY`。Dashboard -> Virtual Keys 中手工创建的 private key 按协议分别配置为：

1. `LITELLM_API_KEY_OPENAI` — OpenAI / Codex / OpenAI-compatible 客户端
2. `LITELLM_API_KEY_ANTHROPIC` — Anthropic / Claude-code / Anthropic-compatible 客户端

如需修改容器代理，再额外设置 `LITELLM_CONTAINER_HTTP_PROXY` 和 `LITELLM_CONTAINER_HTTPS_PROXY`。

只有需要切换 ChatGPT 上游时，才额外覆盖：

```bash
LITELLM_UPSTREAM_CODEX_MODEL=chatgpt/gpt-5.5
```

Codex CLI 默认推荐把上游设为 `chatgpt/gpt-5.5`。`chatgpt/gpt-5.4` 可作为备选。不要使用 `chatgpt/gpt-5.3-codex`，ChatGPT Codex 账号链路会返回 `model is not supported`。`chatgpt/gpt-5.3-codex-spark` 可用于基础 Responses API 验证，但 Codex CLI 会发送 `image_generation` 等工具，spark 会拒绝这类请求。

不要为 ChatGPT 订阅模式配置 `LITELLM_UPSTREAM_CODEX_API_BASE` 或 `LITELLM_UPSTREAM_CODEX_API_KEY`；当前 compose 不再把它们传入 LiteLLM。

启动前先在 ChatGPT 网页端的账号安全设置中启用 Codex 设备代码授权。LiteLLM 打开的 `https://auth.openai.com/codex/device` 使用的是 Codex device code 登录链路；如果账号侧没有开启这个开关，浏览器页面会提示“在 ChatGPT 安全设置中为 Codex 启用设备代码授权”，并且无法继续。

```bash
# 重启 LiteLLM 服务（应用新配置）
./scripts/litellm.sh restart-chatgpt

# 查看启动日志，确认无报错
./scripts/litellm.sh logs litellm
```

## 验证命令

### 健康检查

```bash
curl -s http://127.0.0.1:4000/health/readiness
```

预期返回包含 `{"status":"healthy"}` 或类似成功响应。

### 模型列表检查

```bash
cd /Users/zhehan/Documents/tools/llm/feipi-agent-kit/tools/gateway/litellm
./scripts/litellm.sh check-chatgpt-env

curl -s http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" | jq -r '.data[].id'
```

预期输出包含 `codex-chatgpt`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini`、`gpt-5.3-codex`、`gpt-5.2`。如果没有，说明当前容器没有加载当前 shell 环境中的订阅配置或最新 alias，执行以下命令后重试：

```bash
./scripts/litellm.sh check-chatgpt-env
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh check-chatgpt-runtime
```

如果容器环境已经是 `codex-chatgpt`，但 `/v1/models` 仍没有该模型，通常是启动时 ChatGPT OAuth 网络请求失败，LiteLLM 跳过了这条 deployment：

```bash
./scripts/litellm.sh check-chatgpt-network
./scripts/litellm.sh restart-chatgpt
./scripts/litellm.sh logs litellm
```

### Responses API 测试

```bash
cd /Users/zhehan/Documents/tools/llm/feipi-agent-kit/tools/gateway/litellm
./scripts/litellm.sh check-chatgpt-env
./scripts/litellm.sh check-client-env openai

curl -s http://127.0.0.1:4000/v1/responses \
  -H "Authorization: Bearer ${LITELLM_API_KEY_OPENAI}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "codex-chatgpt",
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

预期输出为 `hello`。

### 首次调用：OAuth device flow

如果这是第一次调用 `chatgpt/` provider，LiteLLM 日志会输出类似内容：

```txt
Please visit the following URL to authenticate:
https://auth.openai.com/activate?user_code=XXXX-XXXX
Device code: XXXX-XXXX
```

操作步骤：

1. 在浏览器中打开日志中的 verification URL。
2. 使用你的 ChatGPT 账号登录。
3. 输入 device code 并授权。
4. 回到终端，观察 LiteLLM 日志确认 token 已保存。

OAuth token 会保存到 `/Users/zhehan/Documents/service-data/litellm/chatgpt-tokens` 目录（已在 docker-compose.yml 中挂载）。

如果浏览器授权页提示需要在 ChatGPT 安全设置中为 Codex 启用设备代码授权，先完成账号侧设置，然后执行 `./scripts/litellm.sh restart-chatgpt` 生成新的 device code。不要复用旧 code。

### 查看日志

```bash
./scripts/litellm.sh logs litellm
```

默认不打开 raw request/response 日志，避免日志过重。需要排查 OAuth 或 Responses API 细节时，可临时在 `config/config.yaml` 中打开 LiteLLM 调试项，问题确认后再关闭。

## 常见问题

### Cloudflare / 403 / HTML response

症状：curl 返回 HTML 页面而非 JSON，或收到 403 错误。

排查步骤：

1. **检查容器代理配置**：确认当前 zsh 环境中的 `LITELLM_CONTAINER_HTTP_PROXY` / `LITELLM_CONTAINER_HTTPS_PROXY` 已正确设置，且代理本身可以访问 ChatGPT。
2. **检查 User-Agent**：LiteLLM 的 `chatgpt/` provider 可能使用特定的 User-Agent，某些网络环境可能对其有限制。
3. **检查 LiteLLM 版本**：当前默认使用 `v1.89.0`，如果 `chatgpt/` provider 行为异常，需要先修改 `compose/docker-compose.yml` 中的镜像版本。
4. **直接测试网络**：在容器内或宿主机上直接 curl ChatGPT API，排除网络层面的问题。

### ChatGPT OAuth 轮询超时，模型未暴露

症状：日志先打印 `codex-chatgpt`，随后出现：

```txt
Error creating deployment ... chatgpt/... Polling failed ... timed out
Initialized Model List ['litellm-code-openai', 'litellm-code-anthropic', 'litellm-autocomplate-openai']
```

这表示 LiteLLM 启动时访问 `auth.openai.com` 超时，并忽略了 `codex-chatgpt` deployment。处理步骤：

1. 确认宿主机代理正在运行，且端口与 `LITELLM_CONTAINER_HTTP_PROXY` / `LITELLM_CONTAINER_HTTPS_PROXY` 一致。
2. 执行 `./scripts/litellm.sh check-chatgpt-network`。
3. 网络检查通过后执行 `./scripts/litellm.sh restart-chatgpt`。
4. 再执行 `./scripts/litellm.sh check-chatgpt-runtime`，确认模型已暴露。

### ChatGPT 授权页要求启用 Codex 设备代码授权

症状：打开 `https://auth.openai.com/codex/device` 后，页面提示“在 ChatGPT 安全设置中为 Codex 启用设备代码授权”，并且“继续”按钮无法点击。

处理步骤：

1. 打开 ChatGPT 网页端，进入账号安全设置。
2. 启用 Codex 的设备代码授权。
3. 回到终端执行 `./scripts/litellm.sh restart-chatgpt`。
4. 使用日志中新生成的 device code 重新授权。

### ChatGPT 账号不支持当前上游模型

症状：

```txt
The 'gpt-5.3-codex' model is not supported when using Codex with a ChatGPT account.
```

处理步骤：

1. 把 `~/.env` 中的 `LITELLM_UPSTREAM_CODEX_MODEL` 改成 `chatgpt/gpt-5.5`，或用 `chatgpt/gpt-5.4` 作为备选。
2. 打开新的 zsh，确保新 shell 已加载 `~/.env`。
3. 执行 `./scripts/litellm.sh check-chatgpt-env`。
4. 执行 `./scripts/litellm.sh restart-chatgpt`。

### Codex CLI 报模型白名单或工具不支持

症状：

```txt
key not allowed to access model ... Tried to access gpt-5.5
Tool 'image_generation' is not supported with gpt-5.3-codex-spark.
```

处理步骤：

1. 确认容器已加载 `router_settings.model_group_alias`：`./scripts/litellm.sh check-chatgpt-runtime`。
2. 如果没有显示 `gpt-5.5 gpt-5.4 gpt-5.4-mini gpt-5.3-codex gpt-5.2` 已映射到 `codex-chatgpt`，执行 `./scripts/litellm.sh restart-chatgpt`。
3. 如果映射已存在但仍然 403，到 Dashboard -> Virtual Keys 编辑当前 `LITELLM_API_KEY_OPENAI` 对应的 key，把 Codex 客户端会选择的模型名加入允许列表。
4. 如果仍然报 `image_generation`，把 `~/.env` 中的上游从 `chatgpt/gpt-5.3-codex-spark` 改成 `chatgpt/gpt-5.5`，然后重启。

### Dashboard 日志页 token 失效

症状：Dashboard 能登录，但 Logs 页面持续加载，浏览器控制台出现：

```txt
Authentication Error, Invalid proxy server token passed
Unable to find token in cache or LiteLLM_VerificationTokenTable
```

这不是 ChatGPT OAuth token 失效，而是浏览器保存的 Dashboard 虚拟 key 已经不在当前 PostgreSQL 中。执行：

```bash
./scripts/litellm.sh check-dashboard-auth
```

然后清理 `localhost:4000` 的站点数据，并用当前 `LITELLM_MASTER_KEY` 重新登录 Dashboard。也可以在该站点 DevTools Console 执行：

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

### OAuth token 过期

如果之前的登录态失效，LiteLLM 会重新触发 device flow。删除 token 文件强制重新登录：

```bash
rm /Users/zhehan/Documents/service-data/litellm/chatgpt-tokens/auth.json
./scripts/litellm.sh restart
```

### 数据库迁移错误

如果启动时出现数据库相关错误，尝试：

```bash
./scripts/litellm.sh recreate
```

这会重新创建 LiteLLM 和 PostgreSQL 容器（数据目录已挂载，不会丢失数据）。

## 回滚方法

如果需要撤销本次改造：

```bash
cd /Users/zhehan/Documents/tools/llm/feipi-agent-kit

# 恢复配置文件
git checkout -- tools/gateway/litellm/config/config.yaml
git checkout -- tools/gateway/litellm/compose/docker-compose.yml
git checkout -- tools/gateway/litellm/env/.env.example
git checkout -- .gitignore

# 删除新增文档
rm tools/gateway/litellm/docs/chatgpt-codex-observe.md

# 重启服务应用回滚
cd tools/gateway/litellm
./scripts/litellm.sh restart
```

注意：`/Users/zhehan/Documents/service-data/litellm/chatgpt-tokens` 目录及其内容不会被 Git 跟踪，回滚后仍会保留。如需清理，手动删除即可。

## 重要提示

- 该链路可供 Codex CLI 或其他客户端通过 LiteLLM private key 调用；日常是否保留 Codex 原生 ChatGPT 登录路径取决于你的使用习惯。
- 不要将任何本地密钥文件或 `chatgpt-tokens/` 目录提交到 Git（已在 `.gitignore` 中配置）。
- 如果要让 Codex CLI 走 LiteLLM，需要修改 `~/.codex/config.toml` 的 `model_provider`、provider `env_key`、`wire_api = "responses"` 和 `model_catalog_json`；`model` 保持 Codex CLI/App 原生名，例如 `gpt-5.5`，不要直接写 LiteLLM 内部名 `codex-chatgpt`，也不要直接修改 `~/.codex/auth.json`。
- 如果不再需要此观测链路，按上述回滚方法清理即可。
