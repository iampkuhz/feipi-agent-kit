---
name: feipi-dingtalk-send-webhook
description: 用于向钉钉群机器人 webhook 发送文本或 Markdown 消息；在用户要发送通知、播报结果或验证 webhook 连通性时使用。
---

# 钉钉 Webhook 消息发送（中文）

## 核心目标

向钉钉群机器人 webhook 稳定发送文本或 Markdown 消息，并在失败时给出可执行的报错信息；遇到钉钉不支持的 Markdown 语法时，发送前直接删除。

## 适用场景

1. 部署完成后向钉钉群发送通知。
2. 自动化任务、定时任务或流水线向钉钉播报执行结果。
3. 服务告警、巡检摘要、值班提醒等需要快速推送到群机器人的场景。
4. 需要验证某个钉钉 webhook 环境变量是否配置正确。

## 不适用场景

1. 发送 `link`、`actionCard`、`feedCard` 等复杂消息类型。
2. 需要 `@` 指定人员、手机号列表或群内精细化提醒。
3. 用户未提供 webhook 环境变量名，且当前对话无法推断目标变量名。
4. 需要治理、重构或迁移 skill 本身；这类任务应使用 `feipi-skill-govern`。

## 先确认什么

1. 必填
- webhook URL 的环境变量名。
- 消息内容。

2. 按需确认
- 是否使用加签模式；若使用，需要密钥环境变量名。
- 发送文本还是 Markdown。
- 若发送 Markdown，是否有独立标题。
- 若正文包含钉钉不支持的 Markdown 语法，发送前会直接删除。

默认策略：
1. 只有一段简短纯文本时，默认发送文本消息。
2. 需要标题、多行结构、列表或引用时，默认发送 Markdown 消息。
3. 若正文含有钉钉不支持的 Markdown 语法，发送前直接删除，不做复杂兼容转换。
4. 缺少 webhook 环境变量名时先提问，不自行猜测。

## 输入与输出

1. 输入
- 文本消息：`<URL环境变量名> <消息内容> [密钥环境变量名]`
- Markdown 消息：`<URL环境变量名> <标题> <正文> [密钥环境变量名]`

2. 输出
- 成功：打印 `✓ 消息发送成功` 并返回退出码 `0`
- 失败：打印 `✗ 消息发送失败` 或具体错误原因，并返回非零退出码

## 执行流程（使用态）

1. Explore
- 确认用户要发文本还是 Markdown。
- 确认 webhook URL 环境变量名，若使用加签则确认密钥环境变量名。

2. Plan
- 文本消息使用 `scripts/send_dingtalk.sh`。
- Markdown 消息使用 `scripts/send_dingtalk_md.sh`。

3. Implement
- 读取环境变量并做基础校验。
- Markdown 消息发送前先做语法收敛，仅保留钉钉支持的 Markdown 类型。
- 按是否提供密钥决定是否追加签名参数。
- 调用钉钉 webhook 并解析 HTTP 状态码和 `errcode`。

4. Verify
- 发送前确保参数完整。
- 发送后检查脚本退出码、HTTP 状态码和钉钉返回体。

## 标准命令

### 文本消息

```bash
# 无加签模式
bash scripts/send_dingtalk.sh <URL环境变量名> "<消息内容>"

# 加签模式
bash scripts/send_dingtalk.sh <URL环境变量名> "<消息内容>" <密钥环境变量名>

# 示例
bash scripts/send_dingtalk.sh DINGTALK_WEBHOOK_URL "部署完成：服务已上线" DINGTALK_SECRET
```

### Markdown 消息

```bash
# 无加签模式
bash scripts/send_dingtalk_md.sh <URL环境变量名> "<标题>" "<正文>"

# 加签模式
bash scripts/send_dingtalk_md.sh <URL环境变量名> "<标题>" "<正文>" <密钥环境变量名>

# 示例
bash scripts/send_dingtalk_md.sh DINGTALK_WEBHOOK_URL "部署通知" "#### 部署完成
> 环境：生产" DINGTALK_SECRET

# 不支持的 Markdown 语法会在发送前直接删除
bash scripts/send_dingtalk_md.sh DINGTALK_WEBHOOK_URL "巡检结果" "| 服务 | 状态 |
| --- | --- |
| api | 成功 |
| worker | 失败 |" DINGTALK_SECRET
```

## 编写与发送规则

1. 优先使用环境变量名，不在命令行中直接暴露 webhook URL 或密钥。
2. 仅做基础 URL 校验；格式可疑时给出警告，但保留发送尝试。
3. 文本消息适合短通知；结构化内容优先用 Markdown。
4. 根据钉钉官方 Markdown 能力，优先使用标题、引用、文字效果、链接、图片、无序列表和有序列表。
5. Markdown 正文如需换行，优先直接传多行文本。
6. 表格、代码块围栏、HTML 标签等不支持语法会在发送前直接删除或去标签，不做额外转换。
7. 若钉钉返回 `errcode != 0`，视为发送失败。

## 验收标准

1. 环境变量缺失时，脚本能明确报错。
2. 提供加签密钥环境变量名但变量缺失时，脚本能明确报错。
3. 文本与 Markdown 两类脚本都能通过基础参数校验。
4. 本地校验脚本 `scripts/validate.sh` 与测试脚本 `scripts/test.sh` 可运行。

## 资源说明

- `scripts/send_dingtalk.sh`：文本消息发送脚本
- `scripts/send_dingtalk_md.sh`：Markdown 消息发送脚本
- `scripts/normalize_dingtalk_markdown.py`：删除不支持 Markdown 语法的收敛脚本
- `scripts/validate.sh`：本地结构校验入口
- `scripts/test.sh`：统一测试入口
- `references/test_cases.txt`：测试项列表
