# Qwen Code 配置管理说明

## 目标
- 用仓库管理可复用的 `~/.qwen/` 配置，避免把机器状态或密钥入库。
- `workbench install mac` 用 Stow 链接 `.qwen/` 下的公开配置。`settings.example.json` 保留在发布目录之外，主配置由本机维护，可包含认证与 `codingPlan` 字段。

## 已纳入的配置
- `./settings.example.json`
  - 说明：主配置示例，包含模型提供方与默认模型。
  - 关键字段语义：
    - `modelProviders`: 定义可用模型列表与接入地址。
    - `envKey`: 指定从环境变量读取密钥的变量名。
    - `generationConfig`: 模型生成参数（如 `contextWindowSize`）。
- `./.qwen/output-language.md`
  - 说明：控制助手输出语言的偏好规则。

## 明确不纳入的内容
- `~/.qwen/skills/`：由 workbench install skills 单独管理。
- `~/.qwen/installation_id`、`~/.qwen/debug/`、`~/.qwen/tmp/`、`~/.qwen/projects/`：运行态或机器相关文件。

## 密钥与本地覆盖
- `settings.example.json` 使用环境变量名引用密钥。
- 请在本机环境变量中提供密钥，例如（示例）：

```bash
export BAILIAN_CODING_PLAN_API_KEY="YOUR_KEY"
```

## 变更说明
- 共享的模型配置示例在 `settings.example.json` 中维护，本机生效的配置是 `~/.qwen/settings.json`。
- 若需要本机特有的私密配置，请放在 shell 环境变量中，不要提交到仓库。
